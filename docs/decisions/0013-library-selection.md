# 13. Library selection: picked by outside symptoms, with decoys

Status: Accepted (2026-10-27).

## Context

The investigator searches a library of earlier postmortems ([decision 4](0004-retrieval.md)). A case is served only documents published before its outage began, and none about the case itself ([decision 5](0005-evidence-library-and-answer-key.md)). Neither rule says which documents go into the library in the first place, and that choice can tilt the score as much as a leak in the evidence.

The person who builds the library has read every case's postmortem while registering the cases. Left to judgment, the picks drift toward earlier outages with the same root cause. Retrieval then hands the investigator the answer by analogy, and the score measures the curator, not the investigator.

So the pick rule is written down and committed before any document is picked, together with the symptoms each case is picked by.

## Options considered

| Option | How documents are picked | Risk |
|---|---|---|
| A. By known cause | Earlier outages with the same root cause as each case | Retrieval is most useful, and the answer leaks by analogy. Scores inflate |
| B. By outside symptoms, with decoys | Earlier outages that showed what an outside engineer saw during the case: affected products, symptom type, scale. Decoys match the symptoms and have a different cause | The builder's memory of famous causes can still steer picks. Symptom matches are coarse |
| C. Case-blind set | A fixed set, such as each provider's newest postmortems before the earliest case, with no per-case picks | No tilt, but with about 25 documents most cases find nothing related, so the library search tests little |

## Decision

Option B. It picks what a real investigator would search for during the outage, and the decoys make sure that a symptom match alone does not point to the right cause.

The rule:

1. **Symptoms come from the case's cut evidence only.** Each case's updates before the resolved one are tagged in [`data/library.yaml`](../../data/library.yaml): `product`, `symptom`, or `scale`, each quoting its update word for word with the update's ID. A test checks every quote against the cut evidence wherever the captured sources are present; they are not in the repository, so CI skips it. The tags were committed before the search for library documents began, and that commit is the proof of order.
2. **Four kinds of document.** `other-provider`: an outage at another provider with the same outside symptoms. `same-provider`: the provider's own earlier outages. `attack-suspected`: outages where an attack was suspected and then confirmed or ruled out, with both outcomes in the library so it does not lean either way on the attack question. `decoy`: the same outside symptoms and a different cause.
3. **About 25 documents.** Two of each of the first three kinds per scored case, a few decoys, and a few documents for the development case. A kind with no good match stays short, and the registry says why, instead of taking a weaker pick.
4. **Every pick records its reason.** Each document names its kind, the cases it serves, and a one-line reason that quotes the case symptom it matches.
5. **The case's cause is used once, for decoys only.** `other-provider`, `same-provider`, and `attack-suspected` picks are made on symptoms alone. A decoy's cause is compared with the case's known cause only to make sure the two differ. That knowledge can only make the library harder, never easier.
6. **A page keeps its article body only.** A fixed rule per site cuts the page to its article and leaves out related posts, sidebars, tags, and bylines. Within the article, text dated on or after the start day of the earliest case the document serves, and undated update notes, are dropped, and each extract lists what it dropped. A page whose article the rule cannot find is not used.
7. **A monthly report is one document**, and each incident in it becomes a section.

No update in the four cases mentions an attack. The `attack-suspected` picks therefore quote a symptom an attack could also produce, such as errors or timeouts reaching the network.

## Trade-offs

- The builder knew the scored cases' causes before picking. The fixed rule, the quoted symptom on every pick, and the decoys reduce that risk; they do not remove it. Each evaluation report names it.
- Symptom tags are coarse. Two outages with elevated HTTP errors can have nothing else in common, so some library hits are noise by design.
- Decoys make retrieval harder on purpose. A library-using result is a lower bound on what retrieval could add with a library picked by cause.
- The tags follow what each provider chose to say during the outage. A provider that said little gives fewer tags and so fewer close matches.
- About 25 documents is small. Some kinds will have fewer than two matches for a case.
