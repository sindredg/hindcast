# 29. Push the image CI tested, after every check

Status: Accepted (2026-11-06).

Replaces the two-builds trade-off in [decision 0016](0016-sign-in-credential-image-build-and-resource-group.md).

The artifact is `hindcast-image` in `.github/workflows/ci.yml`; `actions/download-artifact` reads the current run's artifacts only.

## Context

The push job waited for the image and infrastructure job only and rebuilt before pushing ([#87](https://github.com/sindredg/hindcast/issues/87)). Required checks guard a merge, not a push to `main`, so a failing test, workflow lint, or dependency audit did not stop the push. And the pushed image was not the tested one; digest-pinned bases make two builds close, not identical.

## Options considered

| Option | Fit | Catch |
|---|---|---|
| A. Keep the rebuild; wait for every check | One line | Not the tested image |
| B. Save the tested image as an artifact on `main`; the push job waits for every check, loads, pushes | Tested bytes are pushed | Two more pinned actions; an upload and download per run on `main`; lives one day |
| C. Push from the image and infrastructure job | No artifact | It runs on pull requests, where the `azure` environment refuses sign-in |

## Decision

B. The image and infrastructure job saves `hindcast:ci` with `docker save` after its checks, on `main` only, and uploads it with `actions/upload-artifact` (retention one day). The push job needs all four check jobs, downloads it with `actions/download-artifact`, loads it, and pushes `hindcast:<sha>` and `hindcast:main`. It no longer checks out or builds.

## Trade-offs

- A run on `main` moves the image twice more; pull requests upload nothing.
- The push job trusts the artifact store within one run.
- The two actions are pinned by commit and move with the pin batches.
