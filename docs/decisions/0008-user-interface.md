# 8. User interface: Streamlit with a structured investigation view

Status: Accepted (2026-10-25).

## Context

Hindcast's output is a structured investigation, not a chat transcript: an attack assessment, a timeline, findings with citations, contributing factors, open questions, and the limits of the evidence. The interface has to show that structure and let a reader check it:

- open any cited status update, chart, or library section
- challenge a single finding
- see the trace of tool calls, tokens, time, and cost

It runs as one web app behind Entra sign-in.

## Options considered

| Option | Fit | Cost |
|---|---|---|
| A. Streamlit 1.66.1 | Charts and graph rendering built in, all in Python | The page reruns on every interaction, so per-finding actions need session state. It uses websockets, which the hosting platform has to pass through |
| B. Chainlit 2.12.0 | Built around a chat transcript, which fights the structured output | Low |
| C. Gradio 6.30.0 | Similar to Streamlit, with less control over layout | Low |
| D. FastAPI 0.162.0 with server-rendered pages | Full control over layout, the source panel, and the graph | HTML, CSS, and JavaScript with a timeline library, each with its own linter in CI |
| E. Publishing the agent to Microsoft Teams or Microsoft 365 Copilot | A chat surface; its tools only run inside the app | Needs a Microsoft 365 tenant |

Versions are the latest on PyPI on 2026-10-24.

## Decision

Option A. Streamlit covers the whole view in Python, which keeps the interface off the critical path of a short build. The investigation view has four visual parts besides the lists:

- **Attack assessment:** shown first, with its verdict, reasoning, and citations.
- **Timeline chart:** events in order, with stated and inferred times drawn differently.
- **Evidence graph:** each contributing factor linked to the findings behind it, and each finding to the updates, charts, or library sections it cites, with library citations marked as such.
- **Scored view:** after a scored run, the reconstruction next to the postmortem's key, showing what was recovered, what was missed, and what was claimed without support.

## Trade-offs

- Streamlit's rerun model makes fine-grained interaction (one challenge per finding, a source panel that follows the selection) more awkward than a hand-built page.
- Layout control is limited to Streamlit's components and theme. A design that needs custom components costs time.
- Charts from third parties are shown with their licence and attribution next to them.
