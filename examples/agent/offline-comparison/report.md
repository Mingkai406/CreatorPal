# CreatorPal policy comparison

Adapter: `offline-adk`. Repeats: 1.

Offline controls test implementation, not model quality. Citation integrity checks IDs and source/community relationships; semantic grounding requires separate human review.

| Task | Policy | Complete | Recall@K | Loaded skill chars | Duration ms |
|---|---|---|---:|---:|---:|
| test-plants | eager-fast | True | 1.0 | 1985 | 507.89 |
| test-plants | progressive-fast | True | 1.0 | 1294 | 19.51 |
| test-plants | progressive-routed | True | 1.0 | 1294 | 21.3 |
| test-python | eager-fast | True | 1.0 | 1985 | 41.58 |
| test-python | progressive-fast | True | 1.0 | 1612 | 41.53 |
| test-python | progressive-routed | True | 1.0 | 1612 | 41.67 |
| test-bread | eager-fast | True | 1.0 | 1985 | 15.52 |
| test-bread | progressive-fast | True | 1.0 | 1294 | 17.15 |
| test-bread | progressive-routed | True | 1.0 | 1294 | 16.25 |
| test-camera | eager-fast | True | 1.0 | 1985 | 40.81 |
| test-camera | progressive-fast | True | 1.0 | 1612 | 40.85 |
| test-camera | progressive-routed | True | 1.0 | 1612 | 41.8 |
