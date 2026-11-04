# Data Agent 本地运行说明

本地环境已按项目真实技术栈搭建完成：业务数据使用 MySQL 8.0，平台用户、会话、收藏、
问数快照和审计使用应用自动管理的 SQLite。当前正式入口为 QueryX 业务前端与 FastAPI
同源部署，旧版前端已移除。

## 已验证环境

| 组件 | 本机版本或地址 |
| --- | --- |
| Python | 3.11.15，虚拟环境 `.venv` |
| Node.js | 24.16.0 |
| pnpm | 11.25.0 |
| MySQL | 8.0.42，`127.0.0.1:3307` |
| 业务库 | `data_agent_local` |
| 应用地址 | `http://127.0.0.1:8013` |

## 数据库交付物

- `database/schema.sql`：六张业务表的完整 DDL、外键、索引、检查约束和字段注释。
- `database/seed.sql`：固定种子 `20261104` 生成的可迁移样例数据。
- `database/seed.manifest.json`：行数、日期范围、销售额及 SQL SHA-256。
- `database/expected_queries.sql`：十条规则模式验收 SQL。
- `database/docker-init-readonly.sh`：将容器应用账号权限收敛为 `SELECT, SHOW VIEW`。
- `scripts/generate_local_seed.py`：确定性种子生成器。
- `scripts/init_local_database.py`：安全初始化器；默认拒绝覆盖已有库。
- `scripts/validate_local_database.py`：结构、数据、UTF-8、权限和十条 SQL 验证器。
- `docker-compose.yml`：没有本机 MySQL 8.0 时的容器方案。

实际生成的数据量：

| 表 | 行数 |
| --- | ---: |
| `regions` | 50 |
| `categories` | 50 |
| `products` | 150 |
| `customers` | 250 |
| `orders` | 360 |
| `order_items` | 500 |

订单覆盖 2025-01-03 至 2026-10-26。全历史已支付订单 292 笔，销售额
302,235.41 元。订单金额与明细逐分一致，外键、注册/下单时间和支付时间均已验证。

本机 MySQL 数据文件位于 `.runtime/local-mysql/data`。该目录以及所有密码均被 Git
忽略，不应复制进源码或提交历史。

## 首次安装

所有命令均在项目根目录执行。

```powershell
uv sync --locked
pnpm --dir frontend-vben install --ignore-scripts --frozen-lockfile
pnpm --dir frontend-vben --filter @vben/node-utils stub
pnpm --dir frontend-vben --filter @vben/vite-config stub
pnpm --dir frontend-vben --filter @vben-core/shared stub
npm run build:business
```

若当前 `uv` 版本认为仓库锁文件需要升级，不要无条件改写锁文件。可按项目声明安装到现有
虚拟环境：

```powershell
uv pip install --python .venv\Scripts\python.exe -r pyproject.toml
```

## 生成与初始化数据库

重新生成固定种子：

```powershell
.\.venv\Scripts\python.exe scripts\generate_local_seed.py
```

初始化器通过环境变量接收管理员和应用密码，不把凭据写进脚本：

```powershell
$env:MYSQL_HOST = '127.0.0.1'
$env:MYSQL_PORT = '3307'
$env:MYSQL_ADMIN_USER = 'root'
$env:MYSQL_ADMIN_PASSWORD = '<本机 MySQL 管理员密码>'
$env:BUSINESS_DB_NAME = 'data_agent_local'
$env:BUSINESS_DB_USER = 'data_agent_ro'
$env:BUSINESS_DB_PASSWORD = '<至少 12 位的随机强密码>'

.\.venv\Scripts\python.exe scripts\init_local_database.py
```

数据库已存在时命令会退出，不会覆盖。只有明确需要重建本地演示库时才使用：

```powershell
.\.venv\Scripts\python.exe scripts\init_local_database.py --recreate
```

验证只读数据库：

```powershell
$env:BUSINESS_DB_PASSWORD = '<与 .env 相同的只读密码>'
.\.venv\Scripts\python.exe scripts\validate_local_database.py
```

容器方式使用 `docker-compose.yml`。先在当前 PowerShell 注入随机强密码，再启动：

```powershell
$env:BUSINESS_DB_PORT = '3307'
$env:BUSINESS_DB_NAME = 'data_agent_local'
$env:BUSINESS_DB_USER = 'data_agent_ro'
$env:BUSINESS_DB_PASSWORD = '<至少 12 位的随机强密码>'
docker compose up -d
```

## 本机配置

`.env` 从 `.env.example` 复制并按下列非敏感参数配置：

```dotenv
MOCK_MODE=false
TEXT_TO_SQL_MODE=rules
BUSINESS_DB_HOST=127.0.0.1
BUSINESS_DB_PORT=3307
BUSINESS_DB_NAME=data_agent_local
BUSINESS_DB_USER=data_agent_ro
ALLOWED_TABLES=regions,categories,customers,products,orders,order_items
```

`APP_SECRET_KEY` 和 `BUSINESS_DB_PASSWORD` 是本机随机值，保存在被 Git 忽略的 `.env`。
规则模式无需 LLM 地址、模型名或 API Key。

平台 SQLite 默认位于 `.runtime/platform/retail-platform.sqlite3`。首次管理员为 `admin`；
当前本机初始密码保存在 `.runtime/platform-admin-password.txt`。首次登录后应修改密码。

## 启动

当前本机可使用辅助脚本启动数据库和正式平台：

```powershell
.\scripts\start_local.ps1
```

或在 MySQL 已运行时直接启动：

```powershell
.\.venv\Scripts\python.exe start_business.py --port 8013
```

访问：<http://127.0.0.1:8013>。

辅助脚本只管理 `.runtime/local-mysql/data` 下的项目专属实例，不操作系统 MySQL 的数据
目录。关闭前台 Web 服务可在其终端按 `Ctrl+C`。

## 端到端验收

十个问题通过真实 HTTP 登录会话提交。需要审批的查询随后使用返回的 SQL 哈希审批，
再通过只读 MySQL 账号执行。问题、实际规范化 SQL 与结果记录在
`docs/E2E_TEST_RECORD.md`；完整机器可读响应位于 `.runtime/e2e-questions.json`。

| 问题 | 风险 | 初始状态 | 结果摘要 |
| --- | --- | --- | --- |
| 今年每个月的已支付销售额是多少？ | L0 | 自动完成 | 10 个月；首月 11,284.20 元 |
| 本季度各区域销售额对比 | L1 | 需要确认 | 10 个区域；上海城区居首 1,338.77 元 |
| 销售额最高的前 10 个商品 | L1 | 需要确认 | 10 个商品；智能穿戴旗舰款居首 |
| 各商品品类的销售额和订单量 | L2 | 管理员审批 | 49 个有成交品类；手机配件居首 |
| 不同下单渠道的销售额占比 | L0 | 自动完成 | 4 个渠道；小程序 53,936.48 元 |
| 各客户分层的客单价是多少？ | L1 | 需要确认 | 4 个分层；个人客单价 1,152.86 元 |
| 今年每月新增客户数 | L0 | 自动完成 | 3 个月有新增客户 |
| 各品类的销售毛利是多少？ | L2 | 管理员审批 | 49 个品类；智能穿戴毛利 4,901.68 元 |
| 已支付订单总数是多少？ | L0 | 自动完成 | 2026 年 130 笔 |
| 退款订单率是多少？ | L0 | 自动完成 | 2026 年 8.54% |

重跑 HTTP 验收：

```powershell
$env:PLATFORM_ADMIN_PASSWORD = Get-Content -Raw .runtime\platform-admin-password.txt
.\.venv\Scripts\python.exe scripts\e2e_local_questions.py
```

## 验证结果

```text
正式前端构建：成功，8024 个模块
Python 测试：30 passed
Vben 类型检查：通过
GET /：200
GET /live：200 {"status":"ok"}
未登录 GET /api/v1/health：401
登录后数据库健康：ok，MySQL 8.0.42
十个自然语言问题：10/10 completed
只读账号写入测试：拒绝，符合预期
```

测试套件存在一条上游 `TestClient` 弃用提示，不影响当前运行结果。
本机 Docker Desktop daemon 未运行，因此容器路径只完成了 `docker compose config` 配置
校验；本次全部数据库和端到端运行验收使用本机隔离的 MySQL 8.0.42 实例完成。

## 改动清单

未修改后端业务逻辑。新增文件为：

- `database/schema.sql`
- `database/seed.sql`
- `database/seed.manifest.json`
- `database/expected_queries.sql`
- `database/docker-init-readonly.sh`
- `docs/DATABASE_DESIGN_LOCAL.md`
- `docs/E2E_TEST_RECORD.md`
- `scripts/generate_local_seed.py`
- `scripts/init_local_database.py`
- `scripts/validate_local_database.py`
- `scripts/e2e_local_questions.py`
- `scripts/start_local.ps1`
- `docker-compose.yml`
- `README_LOCAL.md`

本机私有改动仅为 `.env` 与 `.runtime/` 下的数据库、报告和密码文件，两者均已被
`.gitignore` 排除。未保留早期 legacy 前端安装产生的无关源码或锁文件改动。

## 已知边界

- 规则模式只识别内置十类问题；通用自然语言问数需要配置受控的 OpenAI-compatible
  模型服务。
- L2 查询当前允许管理员审批自己的查询，项目尚未实现强制双人审批。
- 数据是固定种子的演示数据，不代表生产数据、容量或高可用验收。
- 项目专属 MySQL 是本机进程，机器重启后需先运行 `scripts/start_local.ps1` 或使用
  `docker compose up -d`。
