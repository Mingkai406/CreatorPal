# `read_zst.py` Command Examples

```bash
# 看前 5 条（默认字段）
.venv/bin/python data/read_zst.py RS_2019-04.zst --limit 5

# 看完整原始 JSON
.venv/bin/python data/read_zst.py RS_2019-04.zst --raw --limit 2

# 过滤 subreddit + 最低分
.venv/bin/python data/read_zst.py RS_2019-04.zst --subreddit AskReddit --min-score 10 --limit 10

# 只计数（会扫描全文件）
.venv/bin/python data/read_zst.py RS_2019-04.zst --subreddit AskReddit --count
```
