# Documentation

Every page states its own status with the evidence behind it. The [roadmap](roadmap.md) owns each milestone's state.

## Where to start

| To | Read |
|---|---|
| See what the investigator found | The [evaluation report](../eval/reconstruction/showcase-v1/README.md), the [sealed report](../eval/reconstruction/sealed-v1/README.md), and the [screenshots](screenshots/README.md) |
| Understand how it is built | The [architecture](architecture/README.md), what an [investigation returns](architecture/investigation-results.md), and the [decision records](decisions/README.md) |
| Check a claim | The [roadmap](roadmap.md), whose status table links each milestone's gate and independent review in its [worklog](worklogs/README.md), and the evaluation pages under [`eval/`](../eval/) |
| Build it again | [Reproduce](reproduce.md), the [runbooks](runbooks/README.md) in its order, [local development](runbooks/development.md), and [troubleshooting](troubleshooting.md) |
| Look up a term or a platform behaviour | The [glossary](glossary.md) and the [findings](findings/README.md) |

## Kinds of pages

| Kind | Where | What it holds |
|---|---|---|
| Roadmap | [roadmap.md](roadmap.md) | The completion criteria of each milestone and its verified state, with a link to the evidence |
| Architecture | [architecture/](architecture/README.md) | What exists now, part by part, with the diagrams and the Azure resources as they ran |
| Decision records | [decisions/](decisions/README.md) | One record per consequential choice: the context, the options, the decision, and its trade-offs. An accepted record keeps its text; a change is a new record that the old one points to |
| Evaluation reports | [eval/](../eval/) | Per dataset version: the status, the results, the error analysis, and the limits, each naming the models, prompts, and runs behind it |
| Runbooks | [runbooks/](runbooks/README.md) | One operator procedure per milestone, with the exact commands and the expected result of each step |
| Worklogs | [worklogs/](worklogs/README.md) | What each milestone built, the gate with a row per criterion, and the independent review. A worklog says what was true on its day |
| Findings | [findings/](findings/README.md) | Platform and source behaviour the documentation does not state, by topic |
| Troubleshooting | [troubleshooting.md](troubleshooting.md) | Failures that showed something: the symptom, the confirmed cause, the fix, and its verification |
| Glossary | [glossary.md](glossary.md) | The terms the page, the documentation, and the evaluation use |
| Reproduce | [reproduce.md](reproduce.md) | What a second build needs, the runbook order, and what cannot be repeated |
| Diagrams | [diagrams/](diagrams/) | The HTML sources and the exported SVGs that the pages embed |
| Screenshots | [screenshots/](screenshots/README.md) | Captures of the page with what each one shows |

Status words: **Verified** means every criterion has a tested row or an accepted gap and an independent review ran; **Built** and **Written** mean it exists, unchecked; **Accepted** marks a decision or an accepted gap; **Open** marks work that waits on something named.
