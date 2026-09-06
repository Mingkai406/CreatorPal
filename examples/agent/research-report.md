# CreatorPal research report example

This view is generated from a recorded offline ADK control. Communities, source URLs and metrics are synthetic; the model is a deterministic test double.

## Task

Compare communities for my Python data analysis tutorials using their engagement_rate metrics.

## Recommendations and calculated metrics

| Community | Retrieved profile | Engagement rate | Evidence ID |
|---|---|---:|---|
| DemoPythonLearning | Python programming tutorials, data analysis, beginner coding exercises and practical automation projects. | 0.07 | `python-profile` |
| DemoDataProjects | Python data analysis, visualization, reproducible notebooks, statistics and portfolio project discussions. | 0.09 | `data-profile` |

The metric is read from the retrieved evidence. This task compares the supplied engagement rates; it does not request rules or infer posting permission.

## Saved analysis

```python
result = {r['community']: r['engagement_rate'] for r in rows}
```

The report references this saved analysis by ID. Its input rows, result, evidence and task events are available in the [state snapshot](offline-comparison/test-python-progressive-fast-0/state-snapshot.json).

## Inspect the artifacts

- [Committed report](offline-comparison/test-python-progressive-fast-0/reports.json)
- [Evidence, analysis and events](offline-comparison/test-python-progressive-fast-0/state-snapshot.json)
- [Configuration manifest](offline-comparison/test-python-progressive-fast-0/manifest.json)
- [Full policy control](offline-comparison/report.md)
