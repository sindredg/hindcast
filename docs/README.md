# Documentation

Start with the [project overview](../README.md). This map points to explanations, results, and operating procedures. The [roadmap](roadmap.md) records which milestones are complete and links to their verification evidence.

## Where to start

| Goal | Start here |
|---|---|
| See what the investigator found | The [evaluation report](../eval/reconstruction/showcase-v1/README.md), the [sealed report](../eval/reconstruction/sealed-v1/README.md), and the [screenshots](screenshots/README.md) |
| Understand how it is built | The [architecture](architecture/README.md), what an [investigation returns](architecture/investigation-results.md), and the [decision records](decisions/README.md) |
| Check a claim | The [roadmap](roadmap.md) links each milestone's required checks and independent review. The [worklogs](worklogs/README.md) record delivery evidence, and [`eval/`](../eval/) holds the evaluation data and results. |
| Rebuild or run the project | Follow [Reproduce](reproduce.md), which lists the [runbooks](runbooks/README.md) in execution order. Use [local development](runbooks/development.md) for setup and [troubleshooting](troubleshooting.md) for known problems. |
| Look up a term or a platform behaviour | The [glossary](glossary.md) and the [findings](findings/README.md) |

## Kinds of pages

| Document type | Location | Contents |
|---|---|---|
| Roadmap | [roadmap.md](roadmap.md) | Criteria and verified state per milestone |
| Architecture | [architecture/](architecture/README.md) | What exists, part by part, with diagrams |
| Decisions | [decisions/](decisions/README.md) | Context, options, decision, trade-offs; a change is a new record |
| Evaluation reports | [eval/](../eval/) | Status, results, error analysis, limits, per dataset version |
| Runbooks | [runbooks/](runbooks/README.md) | Commands and expected results, one per milestone |
| Worklogs | [worklogs/](worklogs/README.md) | Required checks, recorded results, and independent review for each milestone |
| Findings | [findings/](findings/README.md) | Observed platform behaviour and its implications for Hindcast |
| Troubleshooting | [troubleshooting.md](troubleshooting.md) | Symptom, cause, fix, verification |
| Glossary | [glossary.md](glossary.md) | Terms, also on the page |
| Reproduce | [reproduce.md](reproduce.md) | Prerequisites and the order of steps for a fresh deployment |
| Diagrams | [diagrams/](diagrams/) | HTML sources and exported SVGs |
| Screenshots | [screenshots/](screenshots/README.md) | Page captures and what each shows |

Status labels distinguish completed checks from work that only exists: **Verified** means each requirement was tested or has a documented accepted gap, and review was completed. **Built** and **Written** mean the implementation or document exists but has not been verified. **Accepted** records an agreed decision or limitation. **Open** identifies an unresolved item and what it depends on.
