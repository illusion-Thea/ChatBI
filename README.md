# Data Agent

面向企业内部的受控智能问数与数据分析平台。基于 **Vben Admin、Vue 3、FastAPI 和 MySQL**，提供自然语言查询、风险分级确认、交互图表和可追溯的查询记录。

> 当前定位为单组织、单业务数据源的内部试运行版本。已实现账号、角色和持久化记录，但不等同于已通过生产安全、性能或高可用验收的商业发行版。

## 目录

- [功能与架构](#功能与架构)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [开发与测试](#开发与测试)
- [配置说明](#配置说明)
- [权限与查询安全](#权限与查询安全)
- [数据与迁移](#数据与迁移)
- [项目结构](#项目结构)
- [部署与运维](#部署与运维)
- [常见问题](#常见问题)
- [第三方组件与许可](#第三方组件与许可)

## 功能与架构

| 模块 | 当前实现 |
| --- | --- |
| 经营概览 | 销售指标、月度趋势、时间筛选、月度排行及查询状态汇总 |
| 查询工作台 | 中文问题、SQL 生成、安全检查、执行轨迹及查询口径 |
| 结果展示 | ECharts 趋势图、柱状图、表格切换与 CSV 导出 |
| 历史与收藏 | SQLite 持久化记录、搜索、状态筛选、查询复用与个人收藏 |
| 审批中心 | L1 确认、L2 管理员审批、SQL 哈希校验与取消 |
| 数据目录 | 授权业务表与字段元数据 |
| 账号管理 | 登录、退出、密码修改、用户新增、角色调整及停用 |
| 操作审计 | 登录、查询、审批、导出和用户管理事件记录 |

```text
浏览器 / Vben Admin + Vue 3 + ECharts
                │ 同源 HTTP / Cookie / CSRF
                ▼
        FastAPI 内部平台接口
        ├── 账号、会话、权限、收藏、审计 ── SQLite
        └── 受控问数 Pipeline
            问题 → 元数据 → SQL 生成 → AST 校验
                 → EXPLAIN 预检 → 执行或等待确认
                 → 只读查询 → 结果与图表
                                      │
                                      ▼
                              MySQL 业务数据库
```

业务数据与平台元数据分离：应用通过 MySQL 只读账号访问业务表；用户、会话、查询快照、收藏和审计保存到本机 SQLite。

## 环境要求

| 组件 | 要求 |
| --- | --- |
| Python | 3.11+，以 `pyproject.toml` 与 `uv.lock` 为准 |
| Python 包管理 | 推荐 uv |
| Node.js | `^22.18.0` 或 `^24.12.0` |
| 前端包管理 | pnpm 11+；工作区声明版本为 11.16.0 |
| 数据库 | MySQL 8.0+ |

以下命令以 PowerShell 为例，在项目根目录执行。不要使用从其他机器直接复制的 `.venv` 或 `node_modules`。

## 快速开始

### 1. 获取项目与安装依赖

```powershell
git clone git@github.com:345488485/data-agent.git
cd data-agent
uv sync --locked

# 安装工作区依赖，随后生成内部构建配置包。
# 安装脚本不会自动执行，所需构建步骤显式列在下方。
pnpm --dir frontend-vben install --ignore-scripts --frozen-lockfile
pnpm --dir frontend-vben --filter @vben/node-utils stub
pnpm --dir frontend-vben --filter @vben/vite-config stub
pnpm --dir frontend-vben --filter @vben-core/shared stub
```

工作区安装量较大，首次安装需要网络和足够磁盘空间。锁文件不一致时先检查 pnpm 版本；不要直接删除锁文件或无条件升级依赖。

### 2. 导入业务数据

使用数据库管理员连接 MySQL，在客户端执行：

```sql
CREATE DATABASE data_agent_retail
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE data_agent_retail;
SOURCE /absolute/path/to/data-agent/database/retail_demo_20261030.sql;
```

将 `SOURCE` 后的路径替换为实际文件路径；Windows 可使用正斜杠。**必须导入新建的空库**，不要对生产库直接试导入。

随后单独创建应用只读账号。下方密码仅为占位符，必须替换：

```sql
CREATE USER 'data_agent_ro'@'127.0.0.1'
  IDENTIFIED BY 'REPLACE_WITH_A_RANDOM_STRONG_PASSWORD';
GRANT SELECT, SHOW VIEW ON data_agent_retail.*
  TO 'data_agent_ro'@'127.0.0.1';
```

账号的主机部分需匹配实际部署方式；远程部署不要照抄本机授权。**不要给应用配置 root 账号。**

### 3. 配置环境

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

编辑 `.env`，至少配置：

```dotenv
MOCK_MODE=false
TEXT_TO_SQL_MODE=rules
BUSINESS_DB_HOST=127.0.0.1
BUSINESS_DB_PORT=3306
BUSINESS_DB_NAME=data_agent_retail
BUSINESS_DB_USER=data_agent_ro
BUSINESS_DB_PASSWORD=REPLACE_WITH_READONLY_PASSWORD
ALLOWED_TABLES=regions,categories,customers,products,orders,order_items
```

`.env` 是本机私有配置，不应提交。默认规则模式无需外部模型密钥，但只支持内置业务问题及匹配规则，并非通用问答模型。

### 4. 构建与启动

```powershell
npm run build:business
uv run --locked python start_business.py --port 8013
```

访问 **[http://127.0.0.1:8013](http://127.0.0.1:8013)**。后端直接提供构建后的前端资源，无需额外启动 Vite。

也可执行 `npm start`；此命令调用系统 `python`。存在多个 Python 环境时，优先使用上述 `uv run` 命令。

### 5. 首次登录

- 默认管理员用户名：`admin`。
- 新平台数据库首次创建时，可通过进程环境变量 `PLATFORM_ADMIN_PASSWORD` 提供至少 12 位的初始密码。
- 未设置时，系统生成随机密码，写入**平台 SQLite 所在目录**的 `initial-admin.txt`。
- 默认凭据文件：`.runtime/platform/initial-admin.txt`。
- 管理员已存在时，再次设置初始密码变量不会重置其密码。

`PLATFORM_*` 由进程读取，不能仅写入业务 `.env` 文件。例如：

```powershell
# 从安全的环境配置渠道注入，不要将实际密码写入脚本或提交历史。
# $env:PLATFORM_ADMIN_PASSWORD = ...
uv run --locked python start_business.py --port 8013
```

首次登录后修改密码，并妥善保管或移除初始化凭据文件。修改密码会使该用户的现有会话失效。

## 开发与测试

### 前后端分离开发

终端一：

```powershell
uv run --locked python -m uvicorn commercial.main:app --host 127.0.0.1 --port 8013 --reload
```

终端二：

```powershell
npm run dev
```

前端地址为 [http://127.0.0.1:5181](http://127.0.0.1:5181)，`/api` 代理到本机 `8013`。修改后端端口时需同步调整 `frontend-vben/apps/web-business/vite.config.ts`。

### 验证命令

```powershell
# 同时覆盖原 SQL 安全测试、平台权限和演示数据一致性测试。
# 仅执行 uv run pytest 会使用默认 testpaths，不会覆盖 commercial/tests。
$env:PLATFORM_NO_DEFAULT_APP = '1'
try {
  uv run --locked pytest backend/tests commercial/tests -q
} finally {
  Remove-Item Env:PLATFORM_NO_DEFAULT_APP -ErrorAction SilentlyContinue
}

pnpm --dir frontend-vben --filter @data-agent/web typecheck
npm run build:business
# git add 后执行，检查即将提交的文件，不打印密钥值
python scripts/check_secrets.py
```

本地验收记录为 30 项测试通过，另有上游 TestClient 弃用提示；以实际运行结果为准。平台单元测试显式注入模拟查询网关并使用临时 SQLite，不依赖本机凭据；这些测试不能替代真实 MySQL 端到端验收。

### 常用命令

| 命令 | 用途 |
| --- | --- |
| `npm run dev` | 当前企业平台前端开发服务 |
| `npm run build` / `npm run build:business` | 当前平台生产资源构建 |
| `npm start` | 构建资源的本机单服务预览，端口 8013 |
旧版 `frontend/` 和 `web-antd` 已移除；当前只保留 QueryX 企业平台入口。

## 配置说明

### 业务配置：项目根目录 `.env`

| 配置 | 含义 |
| --- | --- |
| `BUSINESS_DB_HOST/PORT/NAME/USER/PASSWORD` | MySQL 地址、库名及只读账号 |
| `TEXT_TO_SQL_MODE` | `rules` 为内置规则；`llm` 为模型生成 |
| `LLM_BASE_URL/API_KEY/MODEL` | 仅模型模式需要，使用 OpenAI-compatible 接口 |
| `ALLOWED_TABLES` | 允许查询的业务表白名单 |
| `QUERY_MAX_ROWS` | 默认最大返回 1,000 行 |
| `QUERY_TIMEOUT_SECONDS` | 默认普通查询超时 15 秒 |
| `QUERY_APPROVED_TIMEOUT_SECONDS` | 默认确认后查询超时 60 秒 |
| `QUERY_RESULT_MAX_BYTES` | 默认结果上限 5 MiB |
| `QUERY_L1_SCAN_ROWS` | 默认 100,000 行，参与风险预检 |
| `QUERY_L2_SCAN_ROWS` | 默认 1,000,000 行，参与高风险预检 |

启用模型模式会向所配置服务发送问题及相关元数据。接入外部服务前，应确认企业的数据使用、网络和合规要求。

### 平台进程环境变量

| 配置 | 含义 |
| --- | --- |
| `PLATFORM_DB_PATH` | 平台 SQLite 路径，默认 `.runtime/platform/retail-platform.sqlite3` |
| `PLATFORM_ADMIN_PASSWORD` | 仅首次初始化管理员时使用 |
| `PLATFORM_HTTPS=1` | 为会话 Cookie 启用 Secure，必须配合 HTTPS |
| `PLATFORM_NO_DEFAULT_APP=1` | 测试期间禁止模块导入自动创建默认应用；正常启动时不要设置 |

## 权限与查询安全

| 操作 | 管理员 | 分析员 | 浏览员 |
| --- | --- | --- | --- |
| 查看业务概览和数据目录 | 是 | 是 | 是 |
| 发起查询 | 是 | 是 | 否 |
| 查看、导出查询结果 | 全部 | 自己的记录 | 自己的记录 |
| 收藏查询 | 是，个人范围 | 是，个人范围 | 是，个人范围 |
| 确认 L1 查询 | 全部 | 自己的查询 | 否 |
| 审批 L2 查询 | 全部 | 否 | 否 |
| 用户管理、操作审计 | 是 | 否 | 否 |

- L0 查询可自动执行；L1 需要确认；L2 需要管理员审批；L3 拒绝执行。
- **当前并未强制双人审批**：管理员可以审批自己的 L2 查询，分析员可以确认自己的 L1 查询。
- 审批绑定待执行 SQL 的哈希；确认并不允许绕过 SQL 安全检查。
- 执行链路包括 AST 校验、业务表白名单、成本预检、结果上限与数据库只读权限。
- 用户身份来自服务端会话，不信任前端传入的 `X-User` / `X-Role`。
- 密码使用 scrypt 散列；会话使用 HttpOnly、SameSite Cookie；写操作校验 CSRF Token。
- 连续失败登录具有节流；账号停用、角色调整或密码修改会使相应会话失效。
- CSV 导出对可能被表格软件解释为公式的字符串做前缀处理。

这些措施不代表已完成渗透测试。审计记录存于本机 SQLite，未实现独立的防篡改审计系统。

## 数据与迁移

当前 SQL 是小型零售业务的**合成演示数据**，不代表真实营收或客户信息。

| 表 | 行数 | 说明 |
| --- | ---: | --- |
| `regions` | 4 | 区域 |
| `categories` | 5 | 商品品类 |
| `products` | 20 | 售价、成本和在售状态 |
| `customers` | 637 | 明确标记为演示客户 |
| `orders` | 3,864 | 订单、状态、渠道及金额 |
| `order_items` | 5,484 | 商品、数量、成交价和折扣 |

订单覆盖 **2025-01-01 至 2026-10-29**；已支付销售额 **505,476.56 元**，已支付订单平均客单价 **149.33 元**。金额与明细逐分一致，客户注册、下单和支付时间先后关系已校验。

- [迁移 SQL](database/retail_demo_20261030.sql)：UTF-8，含表结构、索引、外键与完整业务数据。
- [迁移说明](database/README.md)：导入、迁移范围、备份与本机回退。
- [校验报告](database/retail_demo_20261030.validation.json)：SQL 哈希及独立数据库重新导入的内容校验。

SQL 不包含账号、密码或平台 SQLite 数据。平台账号、收藏、会话与查询快照需要单独迁移。原数据生成和扩容脚本保留用于追溯，**不要直接运行旧的重建脚本**，它们可能清空指定演示库或恢复不再使用的数据口径。

## 项目结构

```text
.
├── commercial/                 当前平台接口、权限与 SQLite 存储
│   └── tests/                  平台及数据一致性测试
├── backend/app/                SQL 生成、校验、元数据和查询 Pipeline
├── backend/tests/              原 SQL 安全及配置测试
├── frontend-vben/              Vben 工作区与第三方许可
│   └── apps/web-business/      当前企业平台前端
├── database/                   可迁移 SQL、导入说明与校验报告
├── scripts/                    数据生成、历史初始化及辅助脚本
├── config/                     策略与语义模型示例
├── docs/                       历史设计与补充说明
├── start_business.py           当前平台启动入口
├── package.json                根目录启动与构建命令
├── pyproject.toml / uv.lock     Python 依赖与锁文件
└── .env.example                可提交的业务配置模板
```

`.runtime/` 存放本机数据库、初始凭据、日志和验收产物，不属于发布源码。项目根目录 README 与当前入口优先于 `docs/` 中的早期设计说明。

## 部署与运维

当前启动器只监听 `127.0.0.1`，适合本机验收。部署到企业网络前，至少完成：

1. 在反向代理配置 HTTPS、请求体上限、连接超时和访问控制，设置 `PLATFORM_HTTPS=1`。
2. 使用独立的 MySQL 只读账号和强密码，通过受控渠道注入凭据。
3. 将平台 SQLite 放在持久化目录，使用 SQLite backup API 一致性备份；不要忽略 WAL 文件。
4. 验证业务库与平台元数据的备份恢复流程，并设置审计及查询快照保留策略。
5. 在目标环境执行权限回归、真实问数、导出和审批端到端测试。
6. 评估容量、并发、告警与单点故障，不要将多进程直接等同于高可用。

`GET /live` 是公开存活检查；`GET /api/v1/health` 需要登录，包含业务数据库状态。当前平台未开放 Swagger / OpenAPI 文档接口。

当前不包含多租户隔离、SSO、行列级权限、强制双人审批、定时报表、计费、完整的数据库版本迁移机制或分布式作业系统。

## 常见问题

**页面仍显示旧主题或旧金额？** 先确认使用当前入口和正确数据库，重新构建后按 `Ctrl + F5`。旧的查询快照不会自动变成新数据集的结果，应重新发起查询。

**数据库连接失败？** 检查地址、端口、库名、账号主机授权与业务表白名单。不要将 root 凭据写入前端或提交到仓库。

**提示先构建前端？** 执行 `npm run build:business`，确认生成 `frontend-vben/apps/web-business/dist/index.html`。

**虚拟环境无法启动？** 不要复用其他机器的 `.venv`。在备份本机配置后重新创建环境并执行 `uv sync --locked`。

**忘记管理员密码？** `PLATFORM_ADMIN_PASSWORD` 不是密码重置开关。当前没有自助找回功能，应通过经过审计的维护流程处理，不要删除生产平台数据库来重置账号。

## 第三方组件与许可

前端基于 [Vben Admin](https://github.com/vbenjs/vue-vben-admin) 定制；上游许可与声明保留在 `frontend-vben/`。其他依赖遵循各自许可证。根项目尚未单独声明开源许可证，不能仅依据第三方的 MIT 许可推定整个项目的授权范围。
