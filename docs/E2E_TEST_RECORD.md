# 本地端到端测试记录

测试日期：2026-11-04（Asia/Shanghai）  
入口：`http://127.0.0.1:8013`  
模式：`TEXT_TO_SQL_MODE=rules`  
业务库：MySQL 8.0.42 / `data_agent_local` / 只读账号  

测试通过真实 HTTP 登录会话提交自然语言问题。L1/L2 查询先返回
`approval_required`，随后使用同一条 SQL 的哈希完成审批，再由只读网关执行。SQL Guard
自动规范化 SQL，并在未指定时追加 `LIMIT 1000`。

## Q01 月度已支付销售额

问题：今年每个月的已支付销售额是多少？  
风险与流程：L0，自动完成。  

```sql
SELECT DATE_FORMAT(created_at, '%Y-%m') AS month,
       ROUND(SUM(amount), 2) AS paid_gmv
FROM orders
WHERE status = 'PAID' AND YEAR(created_at) = YEAR(CURRENT_DATE)
GROUP BY DATE_FORMAT(created_at, '%Y-%m')
ORDER BY month
LIMIT 1000;
```

结果：10 行；首行 `2026-01 / 11284.20`。

## Q02 本季度区域销售额

问题：本季度各区域销售额对比  
风险与流程：L1，确认后完成。  

```sql
SELECT r.name AS region, ROUND(SUM(o.amount), 2) AS paid_gmv,
       COUNT(o.id) AS order_count
FROM orders AS o
JOIN customers AS c ON c.id = o.customer_id
JOIN regions AS r ON r.id = c.region_id
WHERE o.status = 'PAID'
  AND YEAR(o.created_at) = YEAR(CURRENT_DATE)
  AND QUARTER(o.created_at) = QUARTER(CURRENT_DATE)
GROUP BY r.id, r.name
ORDER BY paid_gmv DESC
LIMIT 1000;
```

结果：10 行；首行 `上海城区 / 1338.77 / 2 笔`。

## Q03 商品销售额 TOP 10

问题：销售额最高的前 10 个商品  
风险与流程：L1，确认后完成。  

```sql
SELECT p.name AS product, SUM(oi.quantity) AS units_sold,
       ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.discount)), 2) AS paid_gmv
FROM order_items AS oi
JOIN orders AS o ON o.id = oi.order_id
JOIN products AS p ON p.id = oi.product_id
WHERE o.status = 'PAID' AND YEAR(o.created_at) = YEAR(CURRENT_DATE)
GROUP BY p.id, p.name
ORDER BY paid_gmv DESC
LIMIT 10;
```

结果：10 行；首行 `智能穿戴旗舰款 / 5 件 / 13029.25`。

## Q04 品类销售额和订单量

问题：各商品品类的销售额和订单量  
风险与流程：L2，管理员审批后完成。  

```sql
SELECT c.name AS category,
       ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.discount)), 2) AS paid_gmv,
       COUNT(DISTINCT o.id) AS order_count
FROM order_items AS oi
JOIN orders AS o ON o.id = oi.order_id
JOIN products AS p ON p.id = oi.product_id
JOIN categories AS c ON c.id = p.category_id
WHERE o.status = 'PAID' AND YEAR(o.created_at) = YEAR(CURRENT_DATE)
GROUP BY c.id, c.name
ORDER BY paid_gmv DESC
LIMIT 1000;
```

结果：49 行；首行 `手机配件 / 15398.09 / 5 笔`。

## Q05 渠道销售额

问题：不同下单渠道的销售额占比  
风险与流程：L0，自动完成。规则模式返回各渠道销售额和订单量，前端可据此计算占比。  

```sql
SELECT channel, ROUND(SUM(amount), 2) AS paid_gmv,
       COUNT(id) AS order_count
FROM orders
WHERE status = 'PAID' AND YEAR(created_at) = YEAR(CURRENT_DATE)
GROUP BY channel
ORDER BY paid_gmv DESC
LIMIT 1000;
```

结果：4 行；首行 `小程序 / 53936.48 / 53 笔`。

## Q06 客户分层客单价

问题：各客户分层的客单价是多少？  
风险与流程：L1，确认后完成。  

```sql
SELECT c.segment, COUNT(DISTINCT c.id) AS customers,
       COUNT(o.id) AS order_count, ROUND(AVG(o.amount), 2) AS avg_order_value,
       ROUND(SUM(o.amount), 2) AS paid_gmv
FROM orders AS o
JOIN customers AS c ON c.id = o.customer_id
WHERE o.status = 'PAID' AND YEAR(o.created_at) = YEAR(CURRENT_DATE)
GROUP BY c.segment
ORDER BY paid_gmv DESC
LIMIT 1000;
```

结果：4 行；首行 `个人 / 68 位 / 94 笔 / 客单价 1152.86`。

## Q07 每月新增客户

问题：今年每月新增客户数  
风险与流程：L0，自动完成。  

```sql
SELECT DATE_FORMAT(registered_at, '%Y-%m') AS month,
       COUNT(id) AS new_customers
FROM customers
WHERE YEAR(registered_at) = YEAR(CURRENT_DATE)
GROUP BY DATE_FORMAT(registered_at, '%Y-%m')
ORDER BY month
LIMIT 1000;
```

结果：3 行；首行 `2026-01 / 6 位`。

## Q08 品类销售毛利

问题：各品类的销售毛利是多少？  
风险与流程：L2，管理员审批后完成。  

```sql
SELECT c.name AS category,
       ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.discount)), 2) AS revenue,
       ROUND(SUM(oi.quantity * p.cost_price), 2) AS cost,
       ROUND(SUM(oi.quantity *
             (oi.unit_price * (1 - oi.discount) - p.cost_price)), 2) AS gross_profit
FROM order_items AS oi
JOIN orders AS o ON o.id = oi.order_id
JOIN products AS p ON p.id = oi.product_id
JOIN categories AS c ON c.id = p.category_id
WHERE o.status = 'PAID' AND YEAR(o.created_at) = YEAR(CURRENT_DATE)
GROUP BY c.id, c.name
ORDER BY gross_profit DESC
LIMIT 1000;
```

结果：49 行；首行 `智能穿戴 / 收入 14519.28 / 成本 9617.60 / 毛利 4901.68`。

## Q09 已支付订单总数

问题：已支付订单总数是多少？  
风险与流程：L0，自动完成。  

```sql
SELECT COUNT(id) AS paid_order_count
FROM orders
WHERE status = 'PAID' AND YEAR(created_at) = YEAR(CURRENT_DATE)
LIMIT 1000;
```

结果：1 行；2026 年已支付订单 `130` 笔。

## Q10 退款订单率

问题：退款订单率是多少？  
风险与流程：L0，自动完成。  

```sql
SELECT ROUND(
         100.0 * SUM(CASE WHEN status = 'REFUNDED' THEN 1 ELSE 0 END)
         / NULLIF(COUNT(id), 0), 2
       ) AS refund_rate_pct
FROM orders
WHERE YEAR(created_at) = YEAR(CURRENT_DATE)
LIMIT 1000;
```

结果：1 行；2026 年退款订单率 `8.54%`。

## HTTP 与平台检查

```text
GET /                            200
GET /live                        200 {"status":"ok"}
未登录 GET /api/v1/health       401
登录后 GET /api/v1/health       status=ok, connected=true
数据库                           data_agent_local / MySQL 8.0.42
数据目录                         六张白名单表均可见
问数历史                         10 条
十条问题最终状态                 10/10 completed
```

完整响应（含时间线、生成 SQL、规范化 SQL、SQL 哈希相关状态、图表类型和首行结果）保存在
本机 `.runtime/e2e-questions.json`。
