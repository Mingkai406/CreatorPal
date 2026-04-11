# CreatorPal Project Plan

> 分工文档（Source of Truth）: https://docs.google.com/document/d/1SsEtAD8QnOmN5LmqLN-x5jfprjswP7O3/edit?pli=1  
> 文档类型：软件工程项目计划（Software Engineering Project Plan）  
> 版本：v1.1  
> 基线日期：2026-04-10  
> 当前状态：Skeleton 已就位，进入并行实现阶段

---

## 1. 今日目标（2026-04-10）

四人并行完成数据与基础设施搭建，为后续所有模块提供可用输入与评估资产。

---

## 2. 今日执行计划

### 2.1 Step 1：重建仓库结构

- 将旧 ReAct/Gemini 代码替换为新 RAG 架构 skeleton。
- 全员 pull 最新代码，确认目录结构与函数签名一致。

### 2.2 Step 2：完成数据 pipeline（并行）

数据集来源：

- 文件名：`RS_2019-04.zst`
- URL：https://zenodo.org/records/3608135

| Person | 模块 | 任务 | 依赖关系 |
|---|---|---|---|
| Person 1 | `data/download_reddit.py` | 下载 Kaggle Pushshift 数据（15.53GB）到 GCP | 先行任务 |
| Person 2 | `data/preprocess_corpus.py` | 构建 subreddit profiles（sidebar + rules + top-50 posts），过滤 subscribers < 1000，输出 JSON | 依赖 Person 1 |
| Person 3 | `data/build_faiss_index.py` | 64-token window / 16-token overlap 切块，`all-mpnet-base-v2` 编码，构建 FAISS Flat | 依赖 Person 2 |
| Person 4 | `data/build_ground_truth.py` | 从 Reddit 帖子中提取含 `youtube.com` / `youtu.be` 的样本，过滤 `score >= 2`，输出 `(channel, subreddit)` CSV | 可与 Person 3 并行 |

### 2.3 临时本地策略（快速验证）

为避免在本地直接跑全量 15GB+ 数据，先用精简流程验证：

1. 本地流式读取 `.zst`，生成 `reddit_slim.ndjson`（保留核心字段，约几百 MB）。
2. 基于 `reddit_slim.ndjson` 并行生成：
   - `subreddit_profiles.json`
   - `ground_truth_pairs.csv`
3. 将产物放在 `data/processed/`：
   - `data/processed/reddit_slim.ndjson`
   - `data/processed/subreddit_profiles.json`
   - `data/processed/ground_truth_pairs.csv`

如果 `reddit_slim.ndjson` 超过 GitHub 文件限制（100MB），使用 Git LFS 或转存到 GCP/Google Drive，只在仓库保留派生产物。

---

## 3. 产出验证标准

在 GCP 跑完整 pipeline 后，必须验证：

- FAISS 索引文件已生成（目标规模约 1M 向量）。
- 清洗后的 `subreddit_profiles.json` 已生成。
- `ground_truth_pairs.csv` 已生成并可用于评估。

---

## 4. 模块分工（最新）

### 4.1 Person A（Gaoyuan）— 数据工程 + 集成支持

- 负责：`data/` + `src/pipeline.py` + `src/config.py`
- 工作：
  - 数据 pipeline 维护和修复
  - 统一配置管理（vLLM endpoint、模型名、索引路径等）
  - 主 pipeline 串联（调用其余三位模块）
  - 端到端集成测试与联调
- 交付：从用户输入到最终报告的完整调用链

### 4.2 Person B（Runxin）— 检索 Pipeline

- 负责：`src/ingest/` + `src/retrieval/`
- 工作：
  - `src/ingest/youtube.py`：YouTube Data API v3 摄取
  - `src/retrieval/theme_extractor.py`：主题关键词提取
  - `src/retrieval/hyde.py`：HyDE 查询扩展
  - `src/retrieval/faiss_search.py`：FAISS top-50 召回
  - `src/retrieval/reranker.py`：Cross-Encoder top-10 精排
- 交付：输入频道 URL，输出 top-10 subreddit 及元数据

### 4.3 Person C（Mingkai）— 分析模块 + 评估

- 负责：`src/pal/` + `src/sentiment/` + `eval/`
- 工作：
  - `src/pal/executor.py`：RestrictedPython PAL 执行器
  - `src/sentiment/analyzer.py`：社区情感评分
  - `eval/retrieval_eval.py`：Recall@K、MRR（channel-level 评估）
  - `eval/generation_eval.py`：人工评估框架（coherence / grounding / actionability）
- 交付：PAL、Sentiment 可独立跑通，评估脚本可产出指标

### 4.4 Person D（Ziqi）— 前端 + 部署

- 负责：`app/` + Docker 相关 + README
- 工作：
  - `app/streamlit_app.py`：输入框、推荐列表、策略报告展示
  - 确保每个推荐 subreddit 带可点击完整链接（Karl 的 demo 强制要求）
  - 与 Person A 协调，在生成 prompt 中强制输出完整 Reddit URL
  - `docker-compose.yml` / `Dockerfile` / `docker-startup` / `.env.example` 维护
- 交付：可演示 UI + 可启动部署配置

---

## 5. 协作与分支策略

- `feature/data-pipeline`（Person A）
- `feature/retrieval`（Person B）
- `feature/pal-sentiment`（Person C）
- `feature/frontend-deploy`（Person D）

协作规则：

- 通过 Pull Request 合并到 `main`。
- skeleton 已定义接口签名，模块可并行开发。
- 最终由 Person A 在 `src/pipeline.py` 完成端到端串联并组织 demo。

---

## 6. 质量门禁与验收（DoD）

- 数据产物：profiles、ground truth、index 路径与格式正确。
- 检索产物：可输出稳定 top-10 subreddit 推荐。
- 前端产物：推荐列表中的 URL 必须可点击并可跳转。
- 评估产物：`eval/` 脚本可输出检索与生成评估结果。
- 集成产物：`src/pipeline.py` 可从输入跑到报告输出。
