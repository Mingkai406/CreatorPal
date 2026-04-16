# `read_zst.py` Command Examples

```bash
# Print the first 5 records (default fields)
python data/read_zst.py RS_2019-04.zst --limit 5

# Print full raw JSON for 2 records
python data/read_zst.py RS_2019-04.zst --raw --limit 2

# Filter by subreddit and minimum score
python data/read_zst.py RS_2019-04.zst --subreddit AskReddit --min-score 10 --limit 10

# Count matching records (scans the full file)
python data/read_zst.py RS_2019-04.zst --subreddit AskReddit --count
```

For the full option reference see [`doc/data-pipeline.md`](../doc/data-pipeline.md#inspecting-raw-data).
