# Worklog 06: deployment, slice 1 (thin deploy)

Status: In progress on 2026-10-31. The code, the templates, and the pipeline are built and checked; the app's resources are provisioned and sign-in is checked live (runbook steps 1 to 8). The image push, the deploy, the telemetry check, and the rebuild (steps 9 to 12) wait for the push job to reach `main`. Status lives in the [roadmap](../roadmap.md).

Scope: one `azd up` puts a signed-in page on Azure Container Apps that renders the committed development-case result, with telemetry in Application Insights, from an image CI builds. No model call from the app yet, and no full-environment template: those come with the later slices of [milestone 6](../roadmap.md#6-deployment-and-release). The reasons for the sign-in credential, the build path, and the resource group are in [decision 0016](../decisions/0016-sign-in-credential-image-build-and-resource-group.md).

## Built

- `app` extra in `pyproject.toml`: Streamlit 1.66.1 and azure-monitor-opentelemetry 1.8.11, installed and audited in CI with `--all-extras`.
- `hindcast.telemetry`: the exporter configured once per process, only with a connection string; `hindcast.app`: the page. Tests in `tests/test_telemetry.py` (6) and `tests/test_app.py` (3, using Streamlit's `AppTest`).
- `Dockerfile` and `.dockerignore`: uv 0.13.5 and `python:3.14-slim-trixie`, both by digest; the `app` extra on its own layer; a fixed non-root UID; Streamlit on port 8501.
- `infra/main.bicep` (subscription scope) and `infra/app.bicep`: the app's resource group with `id-hindcast-app`, `id-hindcast-ci` and its GitHub federated credential, a Basic registry with `AcrPull` and `AcrPush`, a Container Apps environment logging through a diagnostic setting, the container app (0 to 1 replica, probes on `/_stcore/health`), and the auth config with the federated-credential path by default and the client-secret path behind one parameter. `infra/bicepconfig.json` raises eight linter rules to errors. `azure.yaml` points azd at the image CI pushes (`imagePassthrough`).
- `infra/fetch-image.bicep`: reads the image the existing container app runs, in a module of its own, so a re-provision keeps the app image without a circular reference.
- `infra/scripts/app-registration.sh` and `app-registration-complete.sh`: the azd hooks that create the app registration and finish it with the redirect URI and the federated credential.
- `.github/workflows/ci.yml`: the `Image and infrastructure` job (hadolint 2.15.1, shellcheck 0.11.0, Bicep 0.48.1 build and lint, image build) on every run, and `Push the image` from `main` in the `azure` deployment environment over OIDC.
- Docs: decision 0016, the [deployment runbook](../runbooks/deployment.md), the deployment diagram, this worklog.

## Checks

Each new check was run once on a broken input before its pass was recorded. Local runs are on the workstation; CI runs are linked.

| Check | Broken input | Result on the broken input | Result on the real input |
|---|---|---|---|
| hadolint (local, 2.15.1) | `FROM python:latest` | `DL3007 warning: Using latest is prone to errors`, exit 1 | no output, exit 0 (after `USER app` → `USER 10001`: `DL3066` info fails the default threshold) |
| Image build (CI) | `COPY data/does-not-exist.yaml` | [run 41096898958](https://github.com/sindredg/hindcast/actions/runs/41096898958): `"/data/does-not-exist.yaml": not found`, job failed | the run before it: `Image and infrastructure` success, `Push the image` skipped on the pull request |
| `az bicep lint` (local, 0.47.16 with the 0.48.1 rules) | `param unused string` in `app.bicep` | `Error no-unused-params`, exit 1 | no output, exit 0 |
| shellcheck (local, 0.11.0) | `echo $1` | `SC2086`, exit 1 | no output, exit 0 |
| `test_configure_once_per_process` | `enable_live_metrics=True` | 1 failed | 6 passed |
| `test_page_renders_the_sections` | header `Timeline` renamed `Events` | 1 failed | 3 passed |
| zizmor on the workflow | the push steps inside the lint job | `secrets-outside-env` ×6, `undocumented-permissions` | `No findings to report` after the push moved to its own job in the `azure` environment |

`az deployment sub what-if` with placeholder IDs (read-only, 2026-10-30): `Succeeded`, 11 `Create` in `rg-hindcast-app`, no change in the other resource group. The what-if did not catch the circular reference in the Live run table, because the container app did not exist yet.

`az deployment sub validate` (read-only, live, 2026-10-31), the check `azd` runs before it changes anything, now runs for `webExists=true` and `webExists=false` before each provision. On the template at `ccec94d` with `webExists=true`: `Circular dependency detected on resource`, exit 1. On the current template: `Succeeded` for both values.

Test suite after the slice: `uv run --frozen pytest -q` → 317 passed.

## Gate

| Criterion (slice) | Status | Evidence |
|---|---|---|
| `azd up` from an empty resource group creates the app's resources | tested, live, 2026-10-31 | `azd provision` → `SUCCESS` after three template fixes (see Live run); `azd up` from empty is runbook step 12, not run yet |
| `azd down` removes them and leaves the other resource group | pending | runbook step 12 |
| Sign-in is required; the health path is excluded | tested, live, 2026-10-31 | runbook step 6: browser request → `302` to `login.microsoftonline.com`, other client → `401`, `/_stcore/health` → `404` from the placeholder, not `302` |
| Other accounts are refused | configured, not tested | `allowedPrincipals` holds one object ID (`az containerapp auth show`); no second account was tried. The deploying account signed in through the federated credential (runbook step 7) |
| No key stored; the one container secret is the identity's client ID | tested, live, 2026-10-31 | runbook step 5: `az containerapp secret list` → `override-use-mi-fic-assertion-client-id` only; sign-in worked without a client secret (step 7) |
| The image is built in CI and pushed without a stored credential | pending | built on every pull request (the Checks table); the push is runbook step 9 |
| The page renders the result through the ingress (WebSocket) | pending | runbook step 10 |
| A span reaches Application Insights | pending | runbook step 11 |
| The push job's OIDC subject matches the CI identity's credential | configured, not tested | `az identity federated-credential list` → `repo:sindredg/hindcast:environment:azure` only; tested by the first push (runbook step 9) |
| Each new linter fails on a broken input | tested | the Checks table |

## Live run

On 2026-10-31, from `feat/thin-deploy`, against the live subscription. Each failure below was found on the live system, fixed in the template, and checked with `az deployment sub validate` for both values of `webExists` before the next run.

| Run | Result | Cause | Fix |
|---|---|---|---|
| `azd provision --preview` | prompt for `allowedUserObjectId` | `--preview` does not run hooks, so the app registration did not exist yet | runbook step 3 runs `azd hooks run preprovision` first |
| `azd provision` (1) | container app and auth config `InternalServerError` | the placeholder digest did not exist on the registry (`ImagePullFailure`), and the placeholder listens on port 80 with no health path | real digest; port and probes follow the image |
| `azd provision` (2) | `InvalidTemplate: Circular dependency` on `ca-hindcast` | with the app existing, the template read the resource it was updating | the image is read in `infra/fetch-image.bicep`, a module of its own |
| `azd provision` (3) | `SUCCESS` in 1 minute 21 seconds | | |
| Push-job trust, before the first push | not run; found by reading the workflow against the credential | a job in the `azure` environment presents `repo:<repo>:environment:azure`, not the branch | credential subject changed, provisioned, the branch credential deleted |

Sign-in (runbook step 7): the deploying account reached the placeholder page through Entra sign-in with no client secret, so the federated credential path works on Container Apps, and the client-secret fallback stays unused ([decision 0016](../decisions/0016-sign-in-credential-image-build-and-resource-group.md)).

Steps 9 to 12 wait for the push job to exist on `main`.

## Issues opened

Pending.

## Independent review

Pending.
