# 3. Document extraction: Azure Content Understanding for postmortems and charts

Status: Accepted (2026-10-25).

## Context

Status updates arrive as JSON. Library postmortems need their text split by section and figure for search and citation; answer keys are structured from each case's postmortem and reviewed before freezing. The investigator starts from a description of each chart.

## Options considered

| Option | Returns | Hindcast builds | Cost |
|---|---|---|---|
| A. Azure Content Understanding, GA API `2025-11-01` | Markdown with headings; grounded fields with confidence; chart descriptions | Analyzer schemas; chart fetching | Lowest HTML meter, per 3,000 characters, plus deployment tokens |
| B. Azure Document Intelligence layout, v4.0 GA | Markdown, sections, tables | Fields and chart descriptions via model calls | Per page |
| C. A multimodal model over screenshots | What the prompt asks | Sections and fields; no grounding | Highest tokens |
| D. HTML parser plus one model call per chart | Text and structure | Fields and grounding | Lowest |

Sources, read 2026-10-25: [limits](https://learn.microsoft.com/azure/ai-services/content-understanding/service-limits), [pricing](https://learn.microsoft.com/azure/ai-services/content-understanding/pricing-explainer), [elements](https://learn.microsoft.com/azure/ai-services/content-understanding/document/elements), [tool choice](https://learn.microsoft.com/azure/ai-services/content-understanding/choosing-right-ai-tool).

## Decision

Option A: section text, grounded fields, and chart descriptions from one service. Option C was ruled out: model-produced text cannot be a citation target.

## Trade-offs

- An HTML page is one page, so citations point to a section or figure, not a page number.
- Images in a page are analysed separately, one more call per chart.
- The GA API excludes the GPT-6 deployments ([findings](../findings/models.md)), so the extraction model differs from the investigator's.
- Field values are generative; confidence and grounding make them checkable, not correct.
- Extraction costs per run, so output is stored and reused.
