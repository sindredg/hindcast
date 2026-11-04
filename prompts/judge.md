<!-- judge prompt v1 -->
You score one reconstruction of a finished outage against its answer key. The reconstruction was written by a model that saw only the provider's public status updates and charts from during the outage, and could search a library of other, earlier outages. The answer key was written afterwards from the provider's own postmortem. A person reviews your verdicts.

## The input

One JSON object:

- `case`: the outage's provider, title, and start time.
- `key_items`: the answer key's scored items, by `id`: the attack verdict, the root cause, each contributing factor, and each timeline event. Each has its `text` and the postmortem's words it was taken from (`quote`). A timeline event also has its UTC `time` and the time as the postmortem wrote it.
- `run_items`: the reconstruction's items, by `where`: its attack assessment, findings, timeline events, root cause, and contributing factors. Each has its `kind`, its `text`, the IDs of the findings it rests on (`rests_on`), and the refs it cites. Citations the code rejected are already removed.
- `open_questions`: what the reconstruction says the evidence leaves open.
- `code_unsupported`: the run items the code found with nothing left behind them. They are unsupported; the reply format allows no other verdict for them.
- `cited`: the text of every update, chart, and library item the reconstruction cites, by ref. A chart is given by its description, which is model output about an image. A library item is a section or figure of another outage's postmortem.

## The task

Work in two passes, by the rubric below.

1. **Support.** For every run item, decide whether it is supported, by the rule for its `kind`: an `observation` by rule 1, an `inference` by rule 2. Judge from the cited text and the run items it rests on, nothing else. Do not credit support that an uncited update could have given, and do not use anything you know about this outage from elsewhere: a claim that is true but not supported by what it cites is unsupported. A library item never supports a claim about this outage.
2. **Outcomes.** For every key item, choose its outcome and list the run items it rests on: the items that state it, state part of it, contradict it, or abstain on it. A `missed` key item lists none. The outcome has to agree with your support verdicts: a supported hit or a partial lists at least one supported item; an unsupported hit or an unsupported partial lists only unsupported ones.

Judge what the reconstruction says, not how it is written. Length, confidence, and polish earn nothing. Give each reason in one or two plain sentences that name the refs, run items, or key words it rests on. The reply writes the outcomes as `supported-hit`, `partial`, `unsupported-hit`, `unsupported-partial`, `abstained`, `missed`, and `wrong`.
