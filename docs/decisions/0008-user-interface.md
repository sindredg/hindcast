# 8. User interface: Streamlit with a structured investigation view

Status: Accepted (2026-10-25). Changed by [decision 0021](0021-screens-pii-and-challenge.md) and [decision 0028](0028-full-environment-and-live-page.md).

## Context

The output is a structured investigation, not a chat. The interface shows that structure and lets a reader open any cited update, chart, or library section, challenge one finding, and see the trace of tool calls, tokens, time, and cost. One web app behind Entra sign-in.

## Options considered

| Option | Fit | Cost |
|---|---|---|
| A. Streamlit 1.66.1 | Charts and graphs built in, all Python | Reruns on every interaction; websockets |
| B. Chainlit 2.12.0 | Chat transcript | Low |
| C. Gradio 6.30.0 | Less layout control | Low |
| D. FastAPI 0.162.0, server-rendered | Full control | HTML, CSS, JavaScript, each with a linter |
| E. Microsoft Teams or Microsoft 365 Copilot | Chat surface; tools run only in the app | A Microsoft 365 tenant |

Versions: latest on PyPI, 2026-10-24.

## Decision

Option A. Four visual parts besides the lists:

- **Attack assessment:** first, with verdict, reasoning, citations.
- **Timeline chart:** stated and inferred times drawn differently.
- **Evidence graph:** factors to findings, findings to the updates, charts, or library sections they cite, library citations marked.
- **Scored view:** the reconstruction next to the key: recovered, missed, unsupported.

## Trade-offs

- Streamlit's rerun model makes per-finding interaction awkward.
- Layout is limited to Streamlit's components and theme.
- Third-party charts carry licence and attribution.
