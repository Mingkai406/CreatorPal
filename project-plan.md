# CreatorPal Project Plan

> 文档类型：软件工程项目计划（Software Engineering Project Plan）  
> 版本：v1.0  
> 基线日期：2026-04-10  
> 项目状态：Scaffold 阶段（接口已定义，核心实现待完成）

---

## 1. 项目概述

CreatorPal 是一个面向内容创作者的 RAG 系统，目标是将 YouTube 创作者与高相关 Reddit 社区进行匹配，并输出可执行的受众增长策略报告。

系统主流程包括：YouTube 数据摄取、主题提取、HyDE 查询重写、FAISS 召回、Cross-Encoder 精排、PAL 分析、情感分析、最终报告生成与前端展示。

---

## 2. 项目目标与成功标准

### 2.1 业务目标

- 将“找社区 + 制定策略”的手工流程自动化。
- 为创作者提供可解释、可点击、可执行的社区推荐结果。

### 2.2 技术目标

- 构建可扩展的 RAG 检索与生成流水线。
- 建立可复现的数据处理与评估体系。
- 形成可部署的演示系统（Streamlit + vLLM）。

### 2.3 成功指标（KPI）

| 维度 | 指标 | 目标值 |
|---|---|---|
| 检索质量 | Recall@10 | >= 0.40（初始目标） |
| 检索质量 | MRR@50 | >= 0.30（初始目标） |
| 生成质量 | 人工评分（coherence/grounding/actionability） | 平均 >= 4.0/5 |
| 端到端稳定性 | 单次流程成功率 | >= 95% |
| Demo 可用性 | 前端展示可点击 Reddit 链接 | 100% |

---

## 3. 范围定义

### 3.1 In Scope

- YouTube 频道信息与评论数据摄取。
- Reddit 语料预处理、索引构建、ground-truth 构建。
- RAG 检索与排序链路实现（HyDE + FAISS + reranker）。
- PAL 沙箱执行与情感分析模块。
- 策略报告生成与 Streamlit 展示。
- 检索与生成评估脚本。

### 3.2 Out of Scope（当前阶段）

- 多租户权限系统与商业计费。
- 线上生产级监控告警系统。
- 大规模分布式训练与自动增量索引。

---

## 4. 架构与工作流

1. 输入：YouTube URL 或自由文本查询。  
2. 摄取：调用 YouTube Data API 拉取频道上下文。  
3. 主题：LLM 提取频道主题与关键词。  
4. 改写：HyDE 生成检索伪文档。  
5. 召回：`all-mpnet-base-v2` + FAISS 检索 top-50。  
6. 精排：`ms-marco-MiniLM-L-6-v2` 精排至 top-10。  
7. 分析：PAL 沙箱计算 + subreddit 情感评分。  
8. 生成：LLM 汇总证据生成策略报告。  
9. 展示：Streamlit 输出推荐列表和报告正文。

---

## 5. 工作分解结构（WBS）

| WBS | 模块 | 负责人 | 关键产出 |
|---|---|---|---|
| WBS-1 | 数据工程 | Person A | 4 个 `data/` 脚本可运行，产出 profile/index/ground-truth |
| WBS-2 | 检索链路 | Person B | `ingest/` 与 `retrieval/` 模块完成并可独立测试 |
| WBS-3 | 分析与评估 | Person C | `pal/`、`sentiment/`、`eval/` 可运行并输出指标 |
| WBS-4 | 前端与部署 | Person D | Streamlit UI + Docker 部署链路可用 |
| WBS-5 | 集成与验收 | Person A | `src/pipeline.py` 串联全链路并通过 E2E 验收 |

---

## 6. 里程碑计划

| Milestone | 目标日期 | 验收标准 |
|---|---|---|
| M1: Skeleton 完成 | 2026-04-10 | 目录、接口签名、依赖配置就绪 |
| M2: 数据资产就绪 | 2026-04-12 | 生成 subreddit profile、FAISS index、ground-truth |
| M3: 核心模块联调 | 2026-04-14 | 检索、分析、生成模块可串联运行 |
| M4: 前端与部署完成 | 2026-04-15 | 本地与 Docker 启动成功，可展示结果 |
| M5: 评估与Demo冻结 | 2026-04-16 | 产出检索指标与人工评估结果，Demo 可演示 |

---

## 7. 角色与职责

### Person A（数据工程 + 集成）

- 负责 `data/`、`src/config.py`、`src/pipeline.py`。
- 负责端到端集成、接口对齐和最终验收。

### Person B（检索链路）

- 负责 `src/ingest/`、`src/retrieval/`。
- 交付可从输入到 top-10 subreddit 的检索结果。

### Person C（分析与评估）

- 负责 `src/pal/`、`src/sentiment/`、`eval/`。
- 交付分析结果结构与评估指标脚本。

### Person D（前端与部署）

- 负责 `app/`、Docker 文件、README 文档。
- 确保推荐结果含可点击 Reddit 链接并可演示。

---

## 8. 开发流程与协作规范

### 8.1 分支策略

- `feature/data-pipeline`
- `feature/retrieval`
- `feature/pal-sentiment`
- `feature/frontend-deploy`

### 8.2 代码集成

- 所有变更通过 PR 合并到 `main`。
- 合并前至少完成模块级自测与接口检查。
- `main` 分支始终保持可构建状态。

### 8.3 文档规范

- 设计变更必须同步更新 `README.md` 与本计划文档。
- 新增配置项必须同步更新 `.env.example`。

---

## 9. 测试与质量门禁

### 9.1 测试层次

- 单元测试：核心函数输入输出正确性。
- 模块测试：每个子模块可独立运行。
- 集成测试：`CreatorPalPipeline.run()` 全链路联调。
- 验收测试：Streamlit 页面展示结果、链接可点击。

### 9.2 质量门禁（Quality Gates）

- 无阻塞级异常导致流程中断。
- 检索评估脚本可输出 Recall@K 和 MRR。
- 生成评估脚本可输出维度化人工评分汇总。
- Docker 部署脚本可一次性拉起服务。

---

## 10. 风险与缓解策略

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| Reddit 原始数据体量大（15GB+） | 数据处理时长和存储压力增加 | 分阶段下载，预留磁盘，建立抽样调试集 |
| 外部 API 限流或网络不稳定 | 摄取任务失败 | 增加重试、分页容错与缓存 |
| LLM 输出不稳定 | 主题抽取与报告一致性下降 | 约束 prompt、加结构化解析和兜底逻辑 |
| 模块并行开发接口漂移 | 集成阶段返工 | 锁定函数签名，PR 强制接口校验 |
| Demo 时间紧张 | 交付风险上升 | 先保证 mock 可演示，再逐步替换真实链路 |

---

## 11. 依赖与前置条件

- YouTube Data API Key 可用。
- vLLM 服务可访问，模型可推理。
- FAISS/Transformers 依赖安装成功。
- Reddit 原始语料下载权限与存储资源可用。

---

## 12. 验收标准（Definition of Done）

满足以下条件视为阶段性交付完成：

- `data/` 脚本可生成索引与评估样本文件。
- `src/pipeline.py` 可从输入运行到报告输出。
- Streamlit 页面可展示 top-10 subreddit 与完整链接。
- Docker 一键部署可启动 `vllm` 与 `app` 两个服务。
- `eval/` 可产出检索指标与生成评分汇总。
- README 与项目计划与当前实现保持一致。

---

## 13. 当前状态说明（2026-04-10 基线）

- 仓库已完成架构骨架搭建。
- 主要函数当前为 `NotImplementedError` 占位。
- 下一阶段重点是按 WBS 完成模块实现和联调。
