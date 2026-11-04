# Data Agent 项目说明与新人入门指南

> 文档依据：2026-08-20 对当前代码、配置、测试和本机运行结果的核对。本文把“已经实现”与“设计目标”分开描述，避免把 README 中的规划误认为现状。

## 1. 一句话认识项目

Data Agent 是一个面向 MySQL 的安全智能问数 MVP：用户用中文提问，系统生成只读 SQL，经过 AST 安全校验和查询成本预检后自动执行或进入人工审批，最后返回简短结论、数据表格或 ECharts 图表，并保留本次请求的执行轨迹。

它解决的不是“让大模型随意操作数据库”，而是“让大模型只负责提出候选 SQL，把权限、审批和执行权牢牢放在确定性程序与只读数据库账号手里”。

## 2. 项目背景与要解决的问题

传统业务取数通常依赖数据分析师手写 SQL，存在响应慢、沟通成本高、指标口径容易反复确认等问题。直接让 LLM 连接生产数据库虽然方便，却会带来写入、越权查询、系统库探测、大查询拖垮数据库、提示注入和结果不可审计等风险。

本项目选择“单 Agent + 受控 Pipeline”的折中路线：

- LLM 或本地规则负责理解自然语言、生成候选 SQL 和建议图表。
- 程序负责 SQL 解析、安全判断、风险分级、审批、执行和结果整形。
- MySQL 只读账号构成最后一道数据库权限边界。
- 每个处理阶段写入时间线，让用户能看到请求走到了哪里。

这使项目适合做企业内部智能问数的安全原型、Text-to-SQL 技术验证或后续 BI/数据助手的受控执行内核。

## 3. 当前实现边界

### 已实现

- FastAPI 提供健康检查、示例问题、元数据、提交问题、查询状态、审批和取消接口。
- 两种 Text-to-SQL Provider：无需模型密钥的确定性规则模式，以及 OpenAI-compatible LLM 模式。
- 从 MySQL `information_schema` 读取授权表与字段元数据。
- 基于 SQLGlot 的 MySQL AST 校验、单语句限制、表白名单、系统库/危险函数/写操作拦截和 `LIMIT` 强制改写。
- 基于 SQL 结构和 `EXPLAIN FORMAT=JSON` 估算行数的 L0/L1/L2/L3 风险分级。
- 审批时使用 SQL + 参数的 SHA-256 哈希，防止审批后 SQL 被替换。
- 通过只读 MySQL 账号执行查询，限制执行时间和最多返回行数。
- 自动生成表格、指标、折线图或柱状图规格；Vue 3 前端用 ECharts 展示结果。
- 请求时间线、SQL、风险理由、口径假设、耗时、行数和截断状态的展示基础。

### 尚未实现或仍是 MVP 形态

- 没有正式登录鉴权；`X-User`、`X-Role` 是前端写死/请求头传入的占位机制，不能作为生产权限控制。
- `QuestionStore` 是进程内字典；应用重启后请求、审批和时间线全部丢失，多实例之间也不共享。
- README 设计中的 `SCOPED`、`VISUALIZING` 状态没有出现在当前状态枚举和 Pipeline 中。
- README 提到的 SSE 流式更新尚未实现；当前前端等待一次 HTTP 请求完整返回。
- `config/policy.example.yml` 和 `semantic-model.example.yml` 是设计样例，当前运行代码没有加载它们；策略实际来自环境变量和代码常量。
- 真实模式元数据目前主要提供表/字段/注释，未读取外键关系，也没有业务指标、同义词召回、行级租户过滤和敏感字段策略落地。
- LLM 生成结果只做 Pydantic 结构校验；没有自动澄清、多轮上下文、错误修复重试或离线准确率评测。
- 查询网关实施了执行时间和行数限制，但 `QUERY_RESULT_MAX_BYTES` 当前未被实际使用。
- 后端定义了 `pie`、`scatter` 图表类型，但前端只注册了柱状图和折线图；规则模式当前也只建议 `metric`、`line`、`bar`、`table`。
- 前端没有接入取消接口，也没有问题历史列表、持久化审计后台或管理员审批台。

## 4. 技术栈

| 层级 | 技术 | 作用 |
| --- | --- | --- |
| 前端 | Vue 3、TypeScript、Vite | 问数工作台与交互状态 |
| 图表 | ECharts 6 | 折线图、柱状图和数据展示 |
| API | FastAPI、Pydantic v2 | HTTP 路由、请求/响应模型与校验 |
| Text-to-SQL | 本地规则 / OpenAI-compatible API | 把自然语言转换为结构化候选查询 |
| SQL 安全 | SQLGlot | MySQL AST 解析、危险节点识别、SQL 规范化和 LIMIT 改写 |
| 数据访问 | SQLAlchemy 2、PyMySQL | MySQL 连接池、EXPLAIN 与只读执行 |
| 配置 | pydantic-settings、`.env` | 数据库、模型、阈值、白名单等运行参数 |
| 测试/质量 | pytest、pytest-asyncio、Ruff、vue-tsc | 后端单测、类型检查和前端构建 |
| 包管理 | uv、npm | Python 和前端依赖管理 |

## 5. 目录地图

```text
data_agent/
├─ start_business.py              # QueryX 同源平台启动入口
├─ pyproject.toml / uv.lock       # Python 项目、依赖、pytest/Ruff 配置
├─ package.json                   # 根目录前端命令代理
├─ .env / .env.example            # 当前环境与配置模板（不要提交真实密钥）
├─ backend/
│  ├─ app/
│  │  ├─ main.py                  # 组装 Settings、Engine、Pipeline 和 FastAPI
│  │  ├─ api.py                   # /api/v1 路由
│  │  ├─ schemas.py               # 状态机、风险、查询结果和请求记录模型
│  │  ├─ pipeline.py              # 核心编排：问数全链路
│  │  ├─ llm.py                   # 规则/LLM Text-to-SQL Provider
│  │  ├─ metadata.py              # 授权数据库元数据快照
│  │  ├─ sql_guard.py             # SQL 安全边界与结构风险判断
│  │  ├─ database.py              # MySQL 连接、EXPLAIN、查询执行
│  │  ├─ visualization.py         # 根据结果推断图表规格
│  │  └─ store.py                 # 进程内请求记录仓库
│  └─ tests/                      # 配置、规则、SQL Guard、Pipeline 测试
├─ frontend-vben/apps/web-business/
│  ├─ src/views/data-agent/workbench.vue # 主页面、提问、审批和执行轨迹
│  ├─ src/views/data-agent/api.ts        # 前端 API 封装
│  ├─ src/views/data-agent/types.ts      # 后端响应对应的 TypeScript 类型
│  └─ src/views/data-agent/result-chart.vue # ECharts/表格结果组件
├─ scripts/
│  ├─ init_demo_database.py       # 创建 6 张表、确定性造数、创建只读账号
│  ├─ bootstrap_readonly_user.sql # 生产接入时的只读账号参考脚本
│  └─ dev.ps1                     # 双终端启动提示
└─ config/
   ├─ policy.example.yml          # 尚未接入运行时的策略设计样例
   └─ semantic-model.example.yml  # 尚未接入运行时的语义模型样例
```

## 6. 核心对象与职责

| 对象 | 主要职责 | 不负责什么 |
| --- | --- | --- |
| `App.vue` | 收集问题、调用 API、展示状态/审批/结果 | 不判断 SQL 是否安全 |
| `api.py` | HTTP 参数、404/403/409 转换、调用 Pipeline | 不直接访问数据库执行 SQL |
| `QuestionPipeline` | 串联上下文、生成、校验、预检、审批、执行、图表 | 不自行解析 SQL 语义细节 |
| `TextToSqlProvider` | 规则或 LLM 生成 `GeneratedQuery` | 没有数据库连接和执行能力 |
| `MetadataCatalog` | 提供允许暴露给生成器的数据库结构 | 当前不负责完整语义治理 |
| `SqlGuard` | 确定性检查、规范化、限制行数、结构风险分级 | 不依赖模型“自觉遵守”安全规则 |
| `QueryGateway` | 唯一查询入口、EXPLAIN、超时、行数限制 | 不生成 SQL |
| `QuestionStore` | 保存请求当前状态和时间线副本 | 当前不持久化到数据库 |
| `build_chart_spec` | 根据结果列和建议选择展示类型 | 不执行前端 JavaScript |

## 7. 一次问数的完整流转

### 7.1 前端提交

1. 用户在 `App.vue` 输入自然语言问题。
2. `api.ts` 调用 `POST /api/v1/questions`，请求包含 `question` 和 `preferred_chart`。
3. API 从 `X-User` 读取请求人；当前前端固定为 `local-user`。

### 7.2 创建记录与加载上下文

1. `QuestionPipeline.submit()` 创建 `q_<16位随机串>` 请求 ID。
2. 状态写入 `RECEIVED`，保存到 `QuestionStore`。
3. `MetadataCatalog.snapshot()` 返回允许使用的表和字段；真实模式从 `information_schema` 读取，Mock 模式返回内置订单表样例。
4. 状态进入 `CONTEXT_READY`。

### 7.3 生成候选 SQL

- 规则模式：`TextToSqlProvider._rule_generate()` 根据中文关键词匹配 10 类内置问题，返回固定只读 SQL、口径假设和建议图表。
- LLM 模式：把系统约束、用户问题和元数据发送到 OpenAI-compatible `/chat/completions`，要求只返回符合 `GeneratedQuery` 的 JSON。

生成完成后状态进入 `SQL_GENERATED`。此时 SQL 仍只是候选，不能执行。

### 7.4 SQL 安全校验

`SqlGuard.validate()` 按以下顺序工作：

1. 拒绝空 SQL、注释、锁定读取和文件输出关键词。
2. 用 SQLGlot 按 MySQL 方言解析，要求只有一条语句。
3. 根节点只允许 `SELECT` 或 `UNION`，拒绝写入、DDL、事务、命令和 `INTO` 等 AST 节点。
4. 拒绝 `SLEEP`、`BENCHMARK`、`LOAD_FILE` 等危险函数。
5. 拒绝 `SELECT *`。
6. 拒绝系统库和不在 `ALLOWED_TABLES` 白名单中的表。
7. 没有固定整数 `LIMIT` 时自动补上；超过最大行数时下调到配置上限。
8. JOIN、子查询、窗口函数至少提升为 L1；3 个及以上 JOIN 提升为 L2。

校验通过后保存格式化 SQL 和 SQL+参数哈希，状态进入 `SQL_VALIDATED`。触碰禁止边界则进入 `REJECTED/L3`，不会访问查询执行入口。

### 7.5 成本预检与风险合并

1. `QueryGateway.explain()` 执行 `EXPLAIN FORMAT=JSON`。
2. 递归提取 `rows_examined_per_scan`、`rows_produced_per_join` 的最大估计值。
3. 预计扫描行数达到 `QUERY_L1_SCAN_ROWS` 时至少为 L1；达到 `QUERY_L2_SCAN_ROWS` 时为 L2。
4. 状态进入 `COST_CHECKED`。

最终风险由“SQL 结构风险”和“预计扫描成本”取较高等级：

| 等级 | 当前含义 | 当前行为 |
| --- | --- | --- |
| L0 | 简单、低成本只读查询 | 自动执行 |
| L1 | JOIN/子查询/窗口或扫描量达到一级阈值 | analyst 可审批 |
| L2 | 3+ JOIN 或扫描量达到二级阈值 | 仅 `X-Role: admin` 可审批 |
| L3 | 写操作、越权表、系统库、危险能力等 | 永久拒绝 |

### 7.6 自动执行或审批分支

- L0：直接进入 `_execute()`。
- L1/L2：状态进入 `APPROVAL_REQUIRED`，先返回前端。
- 用户确认时，前端提交原记录的 `sql_hash`；Pipeline 核对状态、哈希和角色，再执行。
- L3：不会出现“允许强行审批”的分支。

哈希绑定非常关键：审批针对的是一份确定的 SQL 和参数，而不是一个可能被后台替换的请求 ID。

### 7.7 查询执行与结果展示

1. 状态进入 `EXECUTING` 并先保存。
2. Query Gateway 设置 MySQL Session 最大执行时间。
3. 使用 SQLAlchemy 参数化执行，最多读取 `QUERY_MAX_ROWS + 1` 行，用多出的一行判断是否截断。
4. Decimal 转为浮点数，日期/时间转为 ISO 字符串。
5. `build_chart_spec()` 按用户偏好、Provider 建议和结果列推断 `metric/line/bar/table`。
6. Pipeline 生成简短答案并进入 `COMPLETED`。
7. 前端展示答案、风险、行数、耗时、图表/表格、时间线、规范化 SQL 和口径假设。

任何未捕获异常都会把记录置为 `FAILED`；未结束请求可被取消为 `CANCELLED`。

## 8. 数据模型与演示数据

本地初始化脚本创建 6 张业务表：

```text
regions ──< customers ──< orders ──< order_items >── products >── categories
   区域         客户          订单          明细            商品          品类
```

- `regions`：4 个销售区域。
- `categories`：5 个商品品类。
- `products`：20 个商品，含售价和成本。
- `customers`：60 个客户，含区域、客户分层和注册日期。
- `orders`：1,500 笔订单，覆盖 2025-01-01 至 2026-08-20，包含状态、渠道、金额。
- `order_items`：订单商品明细；脚本使用固定随机种子，重复初始化得到确定性数据。

真实应用连接使用 `data_agent_ro@127.0.0.1`，只授予目标数据库的 `SELECT, SHOW VIEW`。Root 账号只应在初始化/运维脚本中使用，不能进入应用配置。

## 9. API 速查

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/api/v1/health` | 数据库连通性、模式和服务状态 |
| GET | `/api/v1/examples` | 返回规则模式示例问题 |
| GET | `/api/v1/metadata/tables` | 返回当前授权表和字段快照 |
| POST | `/api/v1/questions` | 提交自然语言问题 |
| GET | `/api/v1/questions/{id}` | 查询已有请求状态 |
| POST | `/api/v1/questions/{id}/approve` | 用 SQL 哈希和角色审批 |
| POST | `/api/v1/questions/{id}/cancel` | 取消未结束请求 |

本地开发的 Swagger UI：`http://127.0.0.1:8000/docs`。

## 10. 本地启动与验证

### 环境要求

- Python 3.11+
- uv
- Node.js 与 npm
- MySQL 8（真实模式）

### 启动

根目录终端 1：

```powershell
    uv sync
    python start_business.py --port 8013
```

根目录终端 2：

```powershell
npm run dev
```

访问：

- 前端：`http://localhost:5173`
- API 文档：`http://127.0.0.1:8000/docs`

### 验证

```powershell
uv run pytest
npm run build
```

本次核对的实际结果：

- 后端：23 项测试全部通过。
- 前端：TypeScript 检查和 Vite 生产构建通过。
- 数据库：本机 MySQL 8.0.12、`data_agent_demo` 连接正常。
- L0 实链路：月度销售额问题自动完成，返回 8 行。
- L1 实链路：区域对比先进入待审批，analyst 审批后完成，返回 4 行。

## 11. 如果今天是入职第一天，应该从哪里开始

不要从 500 多行 README 的远期规划开始，也不要先钻进 ECharts 样式。先建立一条能运行、能调试、能解释的主链路。

### 第 0 步：先画清安全边界（15 分钟）

记住四句话：

1. 模型只能生成候选 SQL。
2. `SqlGuard` 决定 SQL 能否进入预检。
3. `QueryGateway` 是唯一执行入口。
4. MySQL 只读账号是最后权限边界。

### 第 1 步：跑通最小闭环（30～45 分钟）

1. 启动后端和前端。
2. 打开 `/docs` 和页面。
3. 提问“今年每个月的已支付销售额是多少？”观察 L0 自动执行。
4. 提问“本季度各区域销售额对比”观察 L1 审批。
5. 展开 SQL 和执行轨迹，逐个状态对照 `schemas.py`。

完成标准：你能不用看代码说清楚 L0 与 L1 的分叉点。

### 第 2 步：按调用顺序读代码（约 2 小时）

推荐阅读顺序：

1. `frontend-vben/apps/web-business/src/views/data-agent/workbench.vue`：用户动作和页面状态。
2. `frontend-vben/apps/web-business/src/views/data-agent/api.ts`：每个动作调用哪个 API。
3. `backend/app/api.py`：HTTP 如何进入业务层。
4. `backend/app/pipeline.py`：全项目主干，先通读两遍。
5. `backend/app/schemas.py`：状态、风险和记录结构。
6. `backend/app/llm.py`：规则 SQL 与 LLM 切换方式。
7. `backend/app/sql_guard.py`：最重要的安全模块。
8. `backend/app/database.py`：预检和执行边界。
9. `backend/app/metadata.py`、`visualization.py`、`store.py`：支撑模块。
10. `frontend-vben/apps/web-business/src/views/data-agent/result-chart.vue`：结果如何变成图表。

每读一个模块都回答三个问题：它接收什么、产出什么、失败时由谁处理。

### 第 3 步：用测试理解规则（约 1 小时）

- 先读 `test_pipeline.py`，看成功闭环。
- 再读 `test_sql_guard.py`，理解拒绝边界和 JOIN 风险。
- 再读 `test_rule_provider.py`，了解当前支持的问题集合。
- 最后读 `test_config.py`，理解逗号分隔配置解析。

建议新增一个小测试作为第一笔改动：例如验证非固定 `LIMIT` 被拒绝，或验证 L2 只能由 admin 审批。它比改 UI 更能帮助理解系统边界。

### 第 4 步：理解数据库与业务口径（约 1 小时）

1. 阅读 `scripts/init_demo_database.py` 的 6 张表和外键。
2. 手工写出“区域销售额”需要经过哪些 JOIN。
3. 对照 `llm.py` 中规则 SQL，检查销售额、退款率、毛利和新增客户的口径。
4. 访问 `/metadata/tables`，观察实际给 Provider 的上下文。

完成标准：你能解释为什么订单金额和订单明细折后金额在不同问题中可能形成口径差异。

### 第 5 步：再看生产化缺口（半天以后）

按优先级建议关注：

1. 正式认证授权 + 服务端角色判定。
2. 请求、审批、审计持久化。
3. 语义模型和策略配置真正接入运行时。
4. 数据结果字节上限、敏感字段和行级权限。
5. LLM 准确率评测、澄清机制和受控重试。
6. SSE/任务化执行、多实例一致性和可观测性。
7. 扩展图表类型前，先补齐后端/前端能力一致性。

## 12. 推荐的调试断点

| 想观察什么 | 断点位置 |
| --- | --- |
| 请求如何进入系统 | `api.py:create_question` |
| 元数据实际长什么样 | `pipeline.py` 中 `catalog.snapshot()` 之后 |
| Provider 生成了什么 | `pipeline.py` 中 `provider.generate()` 之后 |
| SQL 为什么被拒绝/升级 | `sql_guard.py:validate` |
| 扫描成本如何改变风险 | `pipeline.py:_merge_cost_risk` |
| 审批为什么失败 | `pipeline.py:approve` |
| 实际执行参数和超时 | `database.py:execute` |
| 图表为什么选成 bar/line | `visualization.py:build_chart_spec` |
| 页面为何显示某状态 | `App.vue:submit/approve` |

## 13. 常见误区

- **误区：LLM 提示词保证安全。** 提示词只能减少错误，安全必须依赖 AST、白名单、审批和数据库权限。
- **误区：只要是 SELECT 就安全。** SELECT 仍可能访问系统库、读取文件、锁表或制造超大查询。
- **误区：README 里的能力都已实现。** README 后半部分含大量路线图和设计草案，要以代码、测试和运行结果为准。
- **误区：切到 LLM 模式就能问任意问题。** 表/字段元数据、业务口径、准确率评测和澄清机制仍决定结果质量。
- **误区：前端传 `X-Role: admin` 就是管理员。** 当前只是本地 MVP 占位，生产中必须由可信认证系统在服务端确定角色。
- **误区：进程内时间线等于审计。** 真正审计需要持久、不可抵赖、可检索，并记录审批主体和策略版本。

## 14. 建议的下一步改造路线

### P0：先补安全与持久化

- 接入真实身份认证，移除前端可伪造角色。
- 将 Question/Timeline/Approval 持久化，并记录策略版本和审批人。
- 实现结果字节上限、敏感字段/行级权限和日志脱敏。
- 为 L2、哈希不匹配、取消竞态和数据库超时补测试。

### P1：提高问数准确率

- 把语义模型 YAML 接入 MetadataCatalog/Provider。
- 建立典型问题、标准 SQL、结果一致性的评测集。
- 增加缺少时间范围/指标口径时的澄清状态。
- 对数据库错误最多做一次受控修复，重新走完整安全链路。

### P2：改善工程与体验

- 引入后台任务和 SSE/轮询，避免长查询占用一次 HTTP 请求。
- 增加请求历史、审批队列和管理员页面。
- 对齐 `pie/scatter` 等图表类型的后端声明与前端实现。
- 增加容器化、迁移脚本、结构化日志、指标和部署说明。

## 15. 关键结论

这个项目最值得学习的不是关键词匹配 SQL，也不是 ECharts，而是“如何把不确定的模型输出包在一条确定、可审查、可拒绝的执行链路里”。新人掌握 `pipeline.py`、`sql_guard.py` 和 `database.py` 三个文件，就掌握了项目的主心骨；理解 `App.vue` 和 `api.py`，就能把用户动作与后端状态对应起来；最后再研究 LLM 与语义层，才不会在还没弄清安全边界前被模型细节带偏。
