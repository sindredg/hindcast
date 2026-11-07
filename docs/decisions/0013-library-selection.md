# 13. Library selection: picked by outside symptoms, with decoys

Status: Accepted (2026-10-27).

## Context

A case is served only documents published before its outage and none about itself ([decision 4](0004-retrieval.md), [decision 5](0005-evidence-library-and-answer-key.md)). Neither rule says which documents enter the library. The builder has read every postmortem, and picks left to judgment drift toward earlier outages with the same cause, which hands over the answer by analogy. So the pick rule and each case's symptoms are committed before any pick.

## Options considered

| Option | Picks | Risk |
|---|---|---|
| A. By known cause | Earlier outages with the same root cause | The answer leaks by analogy |
| B. By outside symptoms, with decoys | Outages that showed what an outsider saw: products, symptom type, scale. Decoys match the symptoms with another cause | Memory of famous causes can still steer; matches are coarse |
| C. Case-blind set | Each provider's newest postmortems before the earliest case | With about 25 documents most cases find nothing related |

## Decision

Option B. The rule:

1. **Symptoms come from the cut evidence only.** Each case's updates before the resolved one are tagged in [`data/library.yaml`](../../data/library.yaml) (`product`, `symptom`, `scale`), each quoting its update by ID. A test checks every quote where the captured sources are present; CI skips it. The tags were committed before the search for documents began.
2. **Four kinds.** `other-provider`: the same symptoms elsewhere. `same-provider`: the provider's own earlier outages. `attack-suspected`: an attack suspected, then confirmed or ruled out, both outcomes present. `decoy`: the same symptoms, a different cause.
3. **About 25 documents.** Two of each of the first three kinds per scored case, a few decoys, a few for the development case. A kind with no good match stays short, with the reason in the registry.
4. **Every pick records its reason:** kind, cases served, and a one-line reason quoting the symptom.
5. **The case's cause is used once, for decoys only,** to confirm the causes differ. That can only make the library harder.
6. **A page keeps its article body only.** A fixed rule per site drops related posts, sidebars, tags, and bylines. Text dated on or after the start day of the earliest case served, and undated update notes, are dropped and listed. A page whose article the rule cannot find is not used.
7. **A monthly report is one document;** each incident is a section.

No update in the four cases mentions an attack, so `attack-suspected` picks quote a symptom an attack could also produce.

## Trade-offs

- The builder knew the causes. The rule, quoted symptoms, and decoys reduce that risk, not remove it; each evaluation report names it.
- Coarse tags make some hits noise by design.
- Decoys make retrieval harder on purpose; a library-using result is a lower bound.
- A provider that said little gives fewer tags and matches.
- About 25 documents is small; some kinds have fewer than two matches per case.
