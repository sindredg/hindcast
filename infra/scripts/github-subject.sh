#!/usr/bin/env bash
# azd preprovision hook: the start of the OIDC subject GitHub puts in this
# repository's workflow tokens, which the CI identity's federated credential
# must match exactly. Repositories created after 2026-07-15, and those that
# opt in, use immutable subjects that carry the owner and repository IDs
# (repo:owner@1/name@2), so the prefix is read from GitHub, not built from the
# name.
set -euo pipefail

REPO="${HINDCAST_GITHUB_REPOSITORY:-sindredg/hindcast}"

# One tab-separated line: whether the default claim template is in use, and
# the prefix (empty when GitHub does not return one). Assigned first, so a
# failed call stops the script under set -e.
line="$(gh api "repos/$REPO/actions/oidc/customization/sub" \
  --jq '[.use_default, (.sub_claim_prefix // "")] | @tsv')"
read -r use_default prefix <<< "$line"
# A customized claim template changes the whole subject format, not only the
# prefix; the template assumes the default one.
if [ "$use_default" != "true" ]; then
  echo "github-subject: $REPO uses a customized OIDC subject template" >&2
  exit 1
fi
if [ -z "${prefix:-}" ]; then
  prefix="repo:$REPO"
fi

azd env set GITHUB_SUBJECT_PREFIX "$prefix"
echo "github subject prefix: ${prefix%%@*}@..."
