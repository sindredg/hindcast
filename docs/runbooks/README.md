# Runbooks

One operator procedure per milestone, written so that someone else can build the project again: a status line with the validation date, the inputs and access each one needs, numbered steps with the exact commands, and the expected result after each step. Local values are placeholders. The [reproduce page](../reproduce.md) gives the order to run them in and what each one leaves behind; each runbook's status line says when its steps last ran.

| Runbook | Covers |
|---|---|
| [Foundations](foundations.md) | Repository protection on GitHub, the Azure foundation (the Foundry resource and project, the model deployments, storage), the case sources, the prior-knowledge answers, and the model re-check |
| [Extraction](extraction.md) | Content Understanding, the chart descriptions, the evidence cut, the library capture and extraction, and the answer keys drafted, reviewed, and frozen |
| [Retrieval](retrieval.md) | The move to the pinned extraction model, the search service, the index build and its size, the gate, and the service's deletion |
| [Investigator](investigator.md) | The evidence check, the safety role, an investigation, reading its result, a challenge, its trace, the agents' removal, and a scored run on the page |
| [Sealing](sealing.md) | Choosing and registering outages without a published cause, sealing, revealing, dropping, and removing the agents |
| [Evaluation](evaluation.md) | Freezing the rubric and labels, the library snapshots, the injection tests, the scored runs, the Foundry cloud evaluation, the judge, the review and scores, and the clean-up |
| [Deployment](deployment.md) | The full environment from one template: preview, provision, the image, the data load, the signed-in page, its traces, the Foundry IQ comparison, and the removal |
| [Teardown](teardown.md) | The checks before anything is deleted, and the removal of the hand-built resources |
| [Local development](development.md) | The checks CI runs, the configuration, and the test-data requirements |
