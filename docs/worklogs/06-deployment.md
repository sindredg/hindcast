# Worklog 06: deployment, slice 1 (thin deploy)

Status: In progress on 2026-10-31. The code, the templates, and the pipeline are built and checked; the app's resources are provisioned and sign-in is checked live (runbook steps 1 to 8). The image push, the deploy, the telemetry check, and the rebuild (steps 9 to 12) wait for the push job to reach `main`. Status lives in the [roadmap](../roadmap.md).

Scope: one `azd up` puts a signed-in page on Azure Container Apps that renders the committed development-case result, with telemetry in Application Insights, from an image CI builds. No model call from the app yet, and no full-environment template: those come with the later slices of [milestone 6](../roadmap.md#6-deployment-and-release). The reasons for the sign-in credential, the build path, and the resource group are in [decision 0016](../decisions/0016-sign-in-credential-image-build-and-resource-group.md).

## Built

- `app` extra in `pyproject.toml`: Streamlit 1.66.1 and azure-monitor-opentelemetry 1.8.11, installed and audited in CI with `--all-extras`.
- `hindcast.telemetry`: the exporter configured once per process, only with a connection string; `hindcast.app`: the page. Tests in `tests/test_telemetry.py` (6) and `tests/test_app.py` (3, using Streamlit's `AppTest`).
- `Dockerfile` and `.dockerignore`: uv 0.13.5 and `python:3.14-slim-trixie`, both by digest; the `app` extra on its own layer; a fixed non-root UID that cannot write the code; Streamlit on port 8501.
- `infra/main.bicep` (subscription scope) and `infra/app.bicep`: the app's resource group with `id-hindcast-app`, `id-hindcast-ci` and its GitHub federated credential, a Basic registry with `AcrPull` and `AcrPush`, a Container Apps environment logging through a diagnostic setting, the container app (0 to 1 replica; the image from `HINDCAST_IMAGE` on every provision, with port 8501 and probes on `/_stcore/health` for the app image and port 80 without probes for the placeholder), and the auth config with the federated-credential path by default and the client-secret path behind one parameter. `infra/bicepconfig.json` raises eight linter rules to errors. `azure.yaml` points azd at the image CI pushes (`imagePassthrough`).
- `infra/scripts/app-registration.sh` and `app-registration-complete.sh`: the azd hooks that create the app registration and finish it with the one redirect URI and the federated credential. `infra/scripts/github-subject.sh`: reads the repository's OIDC subject prefix from GitHub for the CI credential.
- `.github/workflows/ci.yml`: the `Image and infrastructure` job (hadolint 2.15.1, shellcheck 0.11.0, Bicep 0.48.1 build and lint, image build, and a run of the image that checks its user, its stored result, and its health path) on every run, and `Push the image` from `main` in the `azure` deployment environment over OIDC.
- Docs: decision 0016, the [deployment runbook](../runbooks/deployment.md), the deployment diagram, this worklog.

## Checks

Each new check was run once on a broken input before its pass was recorded. Local runs are on the workstation; CI runs are linked.

| Check | Broken input | Result on the broken input | Result on the real input |
|---|---|---|---|
| hadolint (local, 2.15.1) | `FROM python:latest` | `DL3007 warning: Using latest is prone to errors`, exit 1 | no output, exit 0 (after `USER app` → `USER 10001`: `DL3066` info fails the default threshold) |
| Image build (CI) | `COPY data/does-not-exist.yaml` | [run 41096898958](https://github.com/sindredg/hindcast/actions/runs/41096898958): `"/data/does-not-exist.yaml": not found`, job failed | the run before it: `Image and infrastructure` success, `Push the image` skipped on the pull request |
| Run the image (CI) | `--server.port 8502` in the `CMD` | [run 41204093396](https://github.com/sindredg/hindcast/actions/runs/41204093396): Streamlit up on 8502, no `ok` on 8501 within 60 seconds, job failed | [run 41203933810](https://github.com/sindredg/hindcast/actions/runs/41203933810): UID `10001`, `cloudflare-2026-02-20` loaded inside the image, `health: ok` |
| `az bicep lint` (local, 0.47.16 with the 0.48.1 rules) | `param unused string` in `app.bicep` | `Error no-unused-params`, exit 1 | no output, exit 0 |
| shellcheck (local, 0.11.0) | `echo $1` | `SC2086`, exit 1 | no output, exit 0 |
| `test_configure_once_per_process` | `enable_live_metrics=True` | 1 failed | 6 passed |
| `test_page_renders_the_sections` | header `Timeline` renamed `Events` | 1 failed | 3 passed |
| zizmor on the workflow | the push steps inside the lint job | `secrets-outside-env` ×6, `undocumented-permissions` | `No findings to report` after the push moved to its own job in the `azure` environment |

`az deployment sub what-if` with placeholder IDs (read-only, 2026-10-30): `Succeeded`, 11 `Create` in `rg-hindcast-app`, no change in the other resource group. The what-if did not catch the circular reference in the Live run table, because the container app did not exist yet.

`az deployment sub validate` (read-only, live, 2026-10-31), the check `azd` runs before it changes anything, runs before each provision. It catches template errors, not parameter values: on the template at `ccec94d` with the app existing it failed with `Circular dependency detected on resource`, exit 1, and with an empty image it passed. On the template at `b6dbf81`: `Succeeded` with the environment's values, and `Succeeded` with a client-secret value (the fallback path).

`az deployment sub what-if` with a registry image in place of the placeholder (read-only, live, 2026-10-31): `Modify` on `ca-hindcast`, target port 8501, liveness and readiness probes on `/_stcore/health:8501`.

Test suite after the slice: `uv run --frozen pytest -q` → 317 passed.

## Gate

| Criterion (slice) | Status | Evidence |
|---|---|---|
| `azd up` from an empty resource group creates the app's resources | configured, not tested | `azd up` from empty is runbook step 12, not run yet. `azd provision` succeeded on 2026-10-31 over resources that runs (1) and (2) had partly created (Live run) |
| `azd down` removes them and leaves the other resource group | pending | runbook step 12 |
| Sign-in is required; the health path is excluded | tested, live, 2026-10-31 | runbook step 6: browser request → `302` to `login.microsoftonline.com`, other client → `401`, `/_stcore/health` → `404` from the placeholder, not `302` |
| Other accounts are refused | configured, not tested | `allowedPrincipals` holds one object ID (`az containerapp auth show`); no second account was tried. The deploying account signed in through the federated credential (runbook step 7) |
| No key stored; the one container secret is the identity's client ID | tested, live, 2026-10-31 | runbook step 5: `az containerapp secret list` → `override-use-mi-fic-assertion-client-id` only; sign-in worked without a client secret (step 7) |
| The image is built in CI and pushed without a stored credential | pending | built on every pull request (the Checks table); the push is runbook step 9 |
| The page renders the result through the ingress (WebSocket) | pending | runbook step 10 |
| A span reaches Application Insights | pending | runbook step 11 |
| The push job's OIDC subject matches the CI identity's credential | configured, not tested | the repository uses immutable subjects (`gh api repos/sindredg/hindcast/actions/oidc/customization/sub` → `use_immutable_subject: true`); `az identity federated-credential list` → `repo:sindredg@<id>/hindcast@<id>:environment:azure` only, set from that prefix by the pre-provision hook. Tested by the first push (runbook step 9) |
| Each new linter fails on a broken input | tested | the Checks table |

## Live run

On 2026-10-31, from `feat/thin-deploy`, against the live subscription. Each failure below was found on the live system or in review, fixed in the template or a hook, and checked with `az deployment sub validate` before the next provision.

| Run | Result | Cause | Fix |
|---|---|---|---|
| `azd provision --preview` | prompt for `allowedUserObjectId` | `--preview` does not run hooks, so the app registration did not exist yet | runbook step 3 runs `azd hooks run preprovision` first |
| `azd provision` (1) | container app and auth config `InternalServerError` | the placeholder digest did not exist on the registry (`ImagePullFailure`), and the placeholder listens on port 80 with no health path | real digest; port and probes follow the image |
| `azd provision` (2) | `InvalidTemplate: Circular dependency` on `ca-hindcast` | with the app existing, the template read the resource it was updating | the image was read in a module of its own; since `4ed41d5` the template does not read the app at all (the review row below) |
| `azd provision` (3) | `SUCCESS` in 1 minute 21 seconds | | |
| `azd provision` (4) | `SUCCESS` | | the CI credential's environment subject |
| Push-job trust, before the first push | not run; found by reading the workflow against the credential | a job in the `azure` environment presents its environment as the subject, not the branch | credential subject changed, provisioned, the branch credential deleted |
| Push-job trust, in review | not run; found by the independent review | the repository uses immutable subjects, which carry the owner and repository IDs, so `repo:sindredg/hindcast:...` never matches | the pre-provision hook reads the prefix from GitHub; provisioned and read back |
| Image switch, in review | not run; found by the independent review in azd's source | `azd deploy` changes only the image, so the app image would keep the placeholder's port 80 and no probes | the image comes only from `HINDCAST_IMAGE`, and the switch is `azd provision`; what-if shows port 8501 and the probes |
| `azd provision` (5) | `SUCCESS` in 1 minute 8 seconds | | the CI credential subject updated in place; one redirect URI; the app still `Healthy` on the placeholder |

Sign-in (runbook step 7): the deploying account reached the placeholder page through Entra sign-in with no client secret, so the federated credential path works on Container Apps, and the client-secret fallback stays unused ([decision 0016](../decisions/0016-sign-in-credential-image-build-and-resource-group.md)).

Steps 9 to 12 wait for the push job to exist on `main`.

## Issues opened

None. The review's plan-only items were small enough to fix in this pull request (the Independent review section).

## Independent review

A read-only review from a fresh context on 2026-10-31 checked the branch at `fb5aac1` against the code, the live resources, and azd 1.37.2's source. It ran the suite, the linters, and `az deployment sub validate`, and read the live resources back. Its findings, each checked again before it was acted on:

| Finding | Checked | Outcome |
|---|---|---|
| The CI credential's subject does not match the repository's immutable OIDC subject | `gh api .../actions/oidc/customization/sub` → `use_immutable_subject: true`; GitHub's OIDC reference | Fixed: `github-subject.sh`; provisioned and read back |
| `azd deploy` changes only the image, so the app image would run on port 80 without probes | azd's source, as cited by the review; not observed live | Fixed: the image comes only from `HINDCAST_IMAGE`, and step 10 is a provision; what-if shows port 8501 and the probes |
| The rebuild in step 12 would start from an image in the new, empty registry | follows from the template at `fb5aac1`: azd keeps the last deployed image name in its environment | Fixed: step 12 resets `HINDCAST_IMAGE` to the placeholder first |
| The rebuild expects `redirect uri: present`, but a new environment gets a new domain | reasoned | Fixed: the hook sets the one current redirect URI; step 12 expects `set` |
| Gate row 1 labelled tested, but `azd up` from empty did not run | the row's own evidence cell | Fixed: configured, not tested |
| The architecture tables describe the registry and the app image as live | `az acr repository list` → empty | Fixed: the tables say what the template sets and what runs now |
| Decision 0016: "tested as a parameter path" without a command; option C names the branch, not the environment; the as-built alt text says the code does not use Application Insights; the deployment diagram's "2 federated credentials" | read in the files | Fixed in the same pull request |
| The image is built but never run in CI | the workflow | Fixed: the `Run the image` step, shown failing once |
| The post-provision hook can drop the redirect URIs when `az ad app show` fails inside a process substitution | `app-registration-complete.sh` at `fb5aac1` | Fixed: the hook sets one URI and reads the current list through a plain assignment |
| `chown -R` copies the virtual environment into a second layer; `data/cases.yaml` is in the image but unread | the Dockerfile; `hindcast.app` imports | Fixed: no `chown`, no case registry in the image |
