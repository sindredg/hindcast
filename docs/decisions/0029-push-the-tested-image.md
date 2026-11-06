# 29. Push the image CI tested, after every check

Status: Accepted (2026-11-06).

Replaces the image-build trade-off in [decision 0016](0016-sign-in-credential-image-build-and-resource-group.md) that the image is built twice per push to `main`.

The artifact named in the trade-offs is `hindcast-image` in `.github/workflows/ci.yml`, the same name on every run; `actions/download-artifact` reads the current run's artifacts only, which is what keeps the push job on the image its own run tested.

## Context

Until this change, the push job in `.github/workflows/ci.yml` waited for the image and infrastructure job only, and it built the image a second time before pushing it ([#87](https://github.com/sindredg/hindcast/issues/87)). Two gaps follow:

1. The repository's required checks guard a merge, not a push to `main` or a manual run from `main`. A failing test, workflow lint, or dependency audit did not stop the push.
2. The pushed image was not the one the job ran as the non-root user, with its runtime download and health checks. Digest-pinned bases make the two builds close, not identical: a package index or a build tool can differ between them.

## Options considered

| Option | Fit | Catch |
|---|---|---|
| A. Keep the rebuild; make the push job wait for every check | One line | The pushed image is still not the tested one |
| B. Save the tested image as a workflow artifact on `main`; the push job waits for every check, loads it, and pushes it | The pushed bytes are the tested bytes | Two more pinned actions; an upload and a download of the compressed image per run on `main`; the artifact lives one day |
| C. Push from the image and infrastructure job | No artifact | That job runs on pull requests, so it would need the Azure sign-in, which the `azure` environment admits only on `main` |

## Decision

B. The image and infrastructure job saves `hindcast:ci` with `docker save` after its checks, on `main` only, and uploads it with `actions/upload-artifact` (retention one day). The push job needs all four check jobs, downloads the artifact with `actions/download-artifact`, loads it, and pushes it as `hindcast:<sha>` and `hindcast:main`. It no longer checks out the repository or builds.

## Trade-offs

- A run on `main` moves the image twice more over the network, so it takes longer. Pull requests are unchanged: they upload nothing.
- The push job trusts the artifact store between two jobs of the same run. The artifact is named per run, and only the same run's push job downloads it.
- The two artifact actions are pinned by commit like every other action, and move with the pin batches.
