---
name: programmatic-analytics
description: Calculate comparisons over retrieved community metrics using restricted Python programs.
metadata:
  version: "1.0"
---
Call run_analysis after retrieval. The host supplies rows containing community, evidence_id,
and numeric metric fields. Generate a short Python program assigning a JSON-serializable result.
Only numeric builtins, comprehensions, indexing, arithmetic and local assignment are available.
Imports, attribute access, file access and networking are unavailable. Use actual metric keys
returned by search, never guessed metrics. For example:

    result = {r['community']: r['engagement_rate'] for r in rows}

On a syntax or missing-data error, inspect the error category and correct the program within
the attempt budget. Cite the returned analysis_id in the report. Never invent numeric results.
