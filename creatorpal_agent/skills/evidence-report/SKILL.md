---
name: evidence-report
description: Commit a research report with traceable recommendations and explicit evidence limitations.
metadata:
  version: "1.0"
---
Call publish_report with the task ID, distinct recommendations, rationale, evidence_ids,
limitations, and analysis_id when an analysis was requested. Every recommendation must cite
a retrieved profile for that same community. If rules were requested, cite a rules snapshot
too. State unresolved gaps. The host validates source references, not the semantic truth of
your prose. A report is complete only when publish_report returns a persisted receipt.
Return that receipt as the final JSON response; saying the work is done does not create it.
