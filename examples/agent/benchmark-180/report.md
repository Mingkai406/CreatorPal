# 180-trial deterministic integration benchmark

Four research topics × five tool-requirement variants × three policies × three repeats.

| Check | Result |
|---|---:|
| Completed workflows | 180/180 |
| Correct analytics | 108/108 |
| Publication consistency | 180/180 |
| Identical report hashes across repeats | 60/60 |

[Summary](summary.json) · [Per-trial results](results.json) · [State and receipts](evidence.jsonl) · [Task matrix](cases.jsonl)

The deterministic model double drives real ADK tools and SQLite commits. Non-analytics tasks pass the numeric gate without claims. Repeats test stable execution; they are not independent model-quality samples. All policies use the same model double; this does not measure live routing quality, token savings or inference cost. Raw runs additionally retain traces and databases in the CI artifact.
