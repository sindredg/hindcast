# Worklog 06: deployment, slice 1 (thin deploy)

Status: In progress on 2026-10-30. The code, the templates, and the pipeline are built and checked; the live deployment steps are recorded below as they run. Status lives in the [roadmap](../roadmap.md).

Scope: one `azd up` puts a signed-in page on Azure Container Apps that renders the committed development-case result, with telemetry in Application Insights, from an image CI builds. No model call from the app yet, and no full-environment template: those come with the later slices of [milestone 6](../roadmap.md#6-deployment-and-release). The reasons for the sign-in credential, the build path, and the resource group are in [decision 0016](../decisions/0016-sign-in-credential-image-build-and-resource-group.md).

## Built

- `app` extra in `pyproject.toml`: Streamlit 1.66.1 and azure-monitor-opentelemetry 1.8.11, installed and audited in CI with `--all-extras`.
- `hindcast.telemetry`: the exporter configured once per process, only with a connection string; `hindcast.app`: the page. Tests in `tests/test_telemetry.py` (6) and `tests/test_app.py` (3, using Streamlit's `AppTest`).
- `Dockerfile` and `.dockerignore`: uv 0.13.5 and `python:3.14-slim-trixie`, both by digest; the `app` extra on its own layer; a fixed non-root UID; Streamlit on port 8501.
- `infra/main.bicep` (subscription scope) and `infra/app.bicep`: the app's resource group with `id-hindcast-app`, `id-hindcast-ci` and its GitHub federated credential, a Basic registry with `AcrPull` and `AcrPush`, a Container Apps environment logging through a diagnostic setting, the container app (0 to 1 replica, probes on `/_stcore/health`), and the auth config with the federated-credential path by default and the client-secret path behind one parameter. `infra/bicepconfig.json` raises eight linter rules to errors. `azure.yaml` points azd at the image CI pushes (`imagePassthrough`).
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

`az deployment sub what-if` with placeholder IDs (read-only, 2026-10-30): `Succeeded`, 11 `Create` in `rg-hindcast-app`, no change in the other resource group.

Test suite after the slice: `uv run --frozen pytest -q` → 317 passed.

## Gate

| Criterion (slice) | Status | Evidence |
|---|---|---|
| `azd up` from an empty resource group creates the app's resources | pending | runbook step 4 |
| `azd down` removes them and leaves the other resource group | pending | runbook step 12 |
| Sign-in is required; the health path is excluded | pending | runbook step 6 |
| Other accounts are refused | pending | runbook step 7 |
| No key stored; the one container secret is the identity's client ID | pending | runbook step 5 |
| The image is built in CI and pushed without a stored credential | pending | runbook step 9 |
| The page renders the result through the ingress (WebSocket) | pending | runbook step 10 |
| A span reaches Application Insights | pending | runbook step 11 |
| Each new linter fails on a broken input | tested | the Checks table |

## Live run

Pending.

## Issues opened

Pending.

## Independent review

Pending.
