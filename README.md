# 车主智能客服 Agent（LangGraph 多智能体 + RAG + 多级记忆 + 人工审阅环）

基于 **LangGraph** 编排的车主智能客服系统（智能车管家，面向私家车主的车辆问答与车辆健康报告）：父图做意图路由，聊天与报告两条子图各自闭环，报告流程内建 **AI 质检自动重生成** 与 **人工审阅中断（interrupt / resume）**，配套 **RAG 知识库问答**、**多级记忆** 与 **自建评测（evals）**，前端为 Streamlit。

## 架构总览

```text
用户输入 → Streamlit (app.py) → GraphAgent 父图
                                   │
                    START → summarize_node（历史超阈值时压缩）
                                   │
                        intent_analysis 条件边（关键词优先，模型兜底）
                              ┌────┴────┐
                        chat ▼          ▼ report
              chat_scene_subgraph   report_scene_subgraph
              ┌──────────────────┐  ┌────────────────────────────────┐
              │ chat_scene_node  │  │ messages_transform_node（读历史偏好）│
              │   ↓ 条件边        │  │   ↓                            │
              │ tool_call_node   │  │ report_scene_node（生成草稿）      │
              │   ↺ 回到自身      │  │   ↓ tool_call_router           │
              └──────────────────┘  │   ├ 有工具→tool_call ↺ 回到草稿   │
                                    │   └ 无工具→quality_agent_node 打分 │
                                    │   ↓ 分数 < 80 回炉重生成（≤3 次）  │
                                    │ user_decision_node ← interrupt() │
                                    │   accept→落库 / cancel→结束 /     │
                                    │   edit→写偏好并重新生成           │
                                    └────────────────────────────────┘
```

- **父图**：`agent/graph_agent.py`。`OverAllState`（继承 `MessagesState`）+ `SqliteSaver` 检查点 + `SqliteStore` 长期记忆，`compile(checkpointer=..., store=...)`；`execute_stream` / `resume_stream` 以 `stream_mode=["messages","updates","custom"]` 与 `subgraphs=True` 输出，并把 `__interrupt__` 转成前端可渲染的中断载荷。
- **意图路由**：先匹配「报告 / 报表 / report」关键词直接进报告子图；未命中才调用 `with_structured_output` 的小模型判定，失败重试后兜底为 `chat`。
- **报告子图**：`ReportState` 独立于父图消息（`subgraph_messages`），质检模型输出 `QualityScore(0~100)`；低于 80 自动 `goto=report_scene_node` 重生成，最多重生成 3 次（`DEFAULT_RETRY_COUNT`），仍不达标则降级为人工审阅；质检分数解析失败同样转人工审阅（此时 `quality_score = -1`）。
- **人工审阅环**：`interrupt()` 挂起并把草稿报告交给用户，前端用 `segmented_control` 收集「接受 / 修改 / 取消」+ 修改建议，`Command(resume=...)` 恢复执行。选择「修改」时把建议以**追加型偏好**写入长期记忆，下次生成自动带入。
- **可靠性**：节点级 `RetryPolicy(max_attempts=3)`；工具调用经 `wrap_tool_call` 钩子链（`retry_tool_call` → `log_tool_call`），重试耗尽返回 `ToolMessage("工具调用失败...")` 而不是抛异常中断整条链路。

## 记忆体系

| 层级 | 载体 | 隔离键 | 说明 |
| --- | --- | --- | --- |
| 短期会话 | `SqliteSaver`（`databases/memory.db`） | `thread_id` | 多轮上下文与断点续跑，中断状态也存这里 |
| 长期用户 | `SqliteStore` + `services/long_term_memory_service.py` | `user_id` | 三类固定分类（用户画像 / 偏好 / 事实），属性受 `config/memory.yaml` 枚举约束 |
| 追加型记忆 | 同上，`append_attrs: [报告要求]` | `user_id` | 同 key 多次写入累积去重、按 `append_max_length` 截断；其余分类为覆盖型 |
| 历史压缩 | `summarize_node` | `thread_id` | 消息数超 `summarization_trigger` 时，把旧消息交给模型摘要并 `RemoveMessage(REMOVE_ALL_MESSAGES)` 重建 |
| 会话管理 | `services/session_service.py` | `user_id` | 创建 / 查询会话，查询始终按 `user_id` 过滤 |
| 产物库 | `services/artifact_service.py`（`databases/business.db`） | `user_id` | 定稿报告落库，返回 `artifact_id` 供 `get_user_artifact_detail` 回查 |

## 工具层

`agent/tools/agent_tools.py` 以 `@tool` 定义，通过 `RunnableConfig` 注入 `user_id`，模型无法伪造：

| 工具 | 作用 |
| --- | --- |
| `rag_search` | Milvus 向量检索知识库 |
| `get_current_month` / `get_weather` / `get_user_location` | 时间、天气、定位 |
| `fetch_external_data` | 按月份读取用户车辆数据（档案 / 健康 / 保养耗材 / 横向对比） |
| `save_long_term_memory` / `get_long_term_memory` | 长期记忆读写（Pydantic `args_schema` 约束分类-属性） |
| `get_user_artifacts_overview` / `get_user_artifact_detail` | 历史产物概览与详情 |

聊天子图挂载 8 个工具，报告子图挂载 5 个（`report_subgraph.py:23`）。

## RAG

`langchain-milvus` 本地文件模式（`milvus.db/`）+ `pypdf` 文档加载 + `RecursiveCharacterTextSplitter` 分块（`chunk_size` / `chunk_overlap` / `separators` 均在 `config/milvus.yaml`）；入库文件以 MD5 记录去重（`rag/md5_hex_store.db`）。知识库源文件为 `data/` 下的特斯拉车主手册分册。

## 模型工厂

`model/factory.py` 用抽象工厂 + provider 注册表按模型名前缀（`ollama:` / `deepseek:`）动态实例化，并缓存实例。对话与嵌入模型分别注册，切换 provider 只改 `config/rag.yaml` 一行、不改代码；密钥与地址走 `.env`（`ollama_base_url`、`deepseek_api_key` 等），不入库不入仓。

## 自建评测（evals）

不依赖托管平台，用 LangChain callback 采集事实、表驱动判定：

```bash
python -m evals.runner        # 全绿退出码 0，任一断言失败退出码 1
```

- `evals/trace_handler.py` — `ToolTrace(BaseCallbackHandler)`：`on_tool_start` 记录工具名，`on_tool_error` 记录报错，`on_chain_start` 从 `metadata["langgraph_node"]` 记录实际执行的节点，用于反推场景路由。**采集层只写不判**。
- `evals/evaluators.py` — 通用算子（`subset` / `disjoint` / `equals` / `not_contains` / `is_empty`）+ `SPEC` 注册表（case 字段名 → 算子 + 事实键），`run_checks(case, actual)` 返回 `[(标签, 布尔, 说明)]`。**加一个验证点 = 表里加一行，不写新分支**。
- `evals/cases.jsonl` — 数据驱动的 case，声明 `expect_tools` / `expect_scene` / `expect_interrupted` / `expect_no_tools` 与多轮 `resume_decision`。
- `evals/runner.py` — 每次运行重置评测库（带「只允许删 eval 库」的路径校验），逐 case 新建 `user_id` 隔离的 thread，处理至多两轮中断，打印 `PASS/FAIL` 与统计。

评测断言的是**行为**（调了哪个工具、进了哪个子图、是否中断、有没有把内部错误串漏进用户可见文本），不是文本措辞——所以不因模型改写而假红。

## 技术栈

| 类别 | 选型 |
| --- | --- |
| Agent 编排 | LangGraph 1.2.11（父图 + 双子图、checkpointer、store、interrupt/resume） |
| 模型接入 | LangChain 1.3.16 `init_chat_model` / `init_embeddings`，Ollama 本地模型 |
| 向量库 | Milvus（langchain-milvus，本地文件模式） |
| 持久化 | SQLite（检查点、Store、会话、产物、业务数据） |
| 前端 | Streamlit 1.51 |
| 语言 | Python 3.13 |

## 快速开始

```bash
# 1. 依赖
pip install -r requirements.txt

# 2. 配置：在项目根目录准备 .env，填写 Ollama 地址与密钥（已被 .gitignore 忽略）
#    模型名称在 config/rag.yaml，例如 chat_model_name: ollama:qwen3.5:9b

# 3. 启动本地 Ollama，并拉取配置中指定的对话 / 嵌入模型

# 4. 知识库首次入库（必须在项目根目录以模块方式运行，项目使用绝对导入）
python -m rag.vector_store

# 5. 启动前端
streamlit run app.py

# 6. 跑评测（连接本地 Ollama，读写 databases/eval_*.db）
python -m evals.runner
```

## 项目结构

```text
agent/graph_agent.py          父图：意图路由、历史压缩、流式输出与中断转发
agent/subgraphs/              chat_subgraph.py（对话+工具循环）、report_subgraph.py（生成-质检-审阅环）
agent/tools/agent_tools.py    工具定义
model/factory.py              模型工厂与 provider 注册表
rag/                          rag_service.py 检索服务、vector_store.py 分块入库与 MD5 去重
services/                     session_service / artifact_service / long_term_memory_service
utils/                        配置加载、日志、路径、提示词加载、llm_tools、hooks（工具重试与日志、消息截断）
config/                       agent / business / memory / milvus / prompt / rag 六个 YAML
prompts/                      system / report / report_quality / intent_analysis / messages_summary
data/                         知识库源文件与外部业务数据（records.csv）
databases/                    SQLite 运行库（业务库、记忆库、评测库）
evals/                        callback 采集 + 表驱动判定 + runner
app.py                        Streamlit 入口（流式渲染、中断审阅面板）
```

## 配置说明

| 文件 | 内容 |
| --- | --- |
| `config/rag.yaml` | 对话 / 嵌入模型名（provider 前缀决定走哪个工厂） |
| `config/milvus.yaml` | 向量库目录、集合名、top-k、分块与分隔符、维度 |
| `config/memory.yaml` | 记忆库路径、长期记忆分类与属性枚举、追加型 attr、摘要触发/保留阈值 |
| `config/business.yaml` | 业务库路径、产物表与会话表名 |
| `config/prompt.yaml` | 五个提示词模板文件路径 |
| `config/agent.yaml` | 外部报告数据源路径 |
| `.env` | 模型服务地址与密钥 |
