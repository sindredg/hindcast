# 3. Document extraction: Azure Content Understanding for postmortems and charts

Status: Accepted (2026-10-25).

## Context

Status updates arrive as JSON from the providers' status APIs and need no extraction. Two other inputs do:

- **Library postmortems.** Earlier postmortems are long web pages with headings, tables, and charts. Search needs their text split by section, and every citation points to a section or a figure, so extraction has to keep both.
- **Answer keys.** Each case's postmortem becomes a structured key: attack or not, root cause, contributing factors, timeline events with times, and fixes. A person reviews it before it is frozen.

Charts carry part of the evidence: error rates and traffic in postmortems, and traffic or routing charts for a case where public data exists. The investigator starts from a description of each chart.

## Options considered

| Option | What it returns | What Hindcast builds itself | Cost |
|---|---|---|---|
| A. Azure Content Understanding, GA API `2025-11-01` | Markdown with headings from HTML; custom fields with confidence scores and source grounding; image descriptions and fields from chart images | The analyzer schemas; fetching the chart images a page links to | HTML on the lowest meter, billed per 3,000 characters; plus tokens on a Foundry model deployment for fields and images |
| B. Azure Document Intelligence layout, v4.0 GA | Markdown, sections, and tables; no generative fields or image descriptions | Field extraction and chart descriptions through separate model calls | Per page |
| C. A multimodal model reading screenshots of each page | Whatever the prompt asks for | Section mapping and fields. No grounding or confidence, and the model can produce text that is not on the page | Highest token use |
| D. An HTML parser plus one model call per chart | The page's text and structure | Field extraction and grounding | Lowest |

Sources, read 2026-10-25: [Content Understanding quotas and limits](https://learn.microsoft.com/azure/ai-services/content-understanding/service-limits), [Content Understanding pricing](https://learn.microsoft.com/azure/ai-services/content-understanding/pricing-explainer), [Document analysis elements](https://learn.microsoft.com/azure/ai-services/content-understanding/document/elements), [Choose the right Foundry Tool for document processing](https://learn.microsoft.com/azure/ai-services/content-understanding/choosing-right-ai-tool).

## Decision

Option A. It returns section-structured text, grounded fields for the answer key, and chart descriptions from one service, without Hindcast building them. Option C was ruled out because text a model produces from a screenshot cannot be trusted as the citation target.

## Trade-offs

- Content Understanding treats the whole main content of an HTML page as one page, so citations point to a section or a figure, not to a page number.
- Images inside an HTML page are not analysed by the HTML path. Hindcast fetches each chart and analyses it as an image, which is one more call per chart.
- The GA API accepts a fixed list of model families, which does not include the GPT-6 deployments the investigator uses ([findings](../findings/models.md)). The extraction model differs from the investigator's model.
- Field values come from a generative model. Confidence scores and grounding make them checkable, not correct; the answer key is reviewed by a person before it is frozen.
- Extraction costs money on every run, so its output is stored and reused.
