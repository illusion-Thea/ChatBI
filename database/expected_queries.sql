-- Stage 2 acceptance queries for Data Agent's rules-mode Text-to-SQL provider.
-- Each query is read-only, avoids SELECT *, and uses only ALLOWED_TABLES.

-- Q01 今年每个月的已支付销售额是多少？
SELECT DATE_FORMAT(created_at, '%Y-%m') AS month,
       ROUND(SUM(amount), 2) AS paid_gmv
FROM orders
WHERE status = 'PAID' AND YEAR(created_at) = YEAR(CURRENT_DATE)
GROUP BY DATE_FORMAT(created_at, '%Y-%m')
ORDER BY month;

-- Q02 本季度各区域销售额对比。
SELECT r.name AS region,
       ROUND(SUM(o.amount), 2) AS paid_gmv,
       COUNT(o.id) AS order_count
FROM orders o
JOIN customers c ON c.id = o.customer_id
JOIN regions r ON r.id = c.region_id
WHERE o.status = 'PAID'
  AND YEAR(o.created_at) = YEAR(CURRENT_DATE)
  AND QUARTER(o.created_at) = QUARTER(CURRENT_DATE)
GROUP BY r.id, r.name
ORDER BY paid_gmv DESC;

-- Q03 销售额最高的前 10 个商品。
SELECT p.name AS product,
       SUM(oi.quantity) AS units_sold,
       ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.discount)), 2) AS paid_gmv
FROM order_items oi
JOIN orders o ON o.id = oi.order_id
JOIN products p ON p.id = oi.product_id
WHERE o.status = 'PAID' AND YEAR(o.created_at) = YEAR(CURRENT_DATE)
GROUP BY p.id, p.name
ORDER BY paid_gmv DESC
LIMIT 10;

-- Q04 各商品品类的销售额和订单量。
SELECT c.name AS category,
       ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.discount)), 2) AS paid_gmv,
       COUNT(DISTINCT o.id) AS order_count
FROM order_items oi
JOIN orders o ON o.id = oi.order_id
JOIN products p ON p.id = oi.product_id
JOIN categories c ON c.id = p.category_id
WHERE o.status = 'PAID' AND YEAR(o.created_at) = YEAR(CURRENT_DATE)
GROUP BY c.id, c.name
ORDER BY paid_gmv DESC;

-- Q05 不同下单渠道的销售额占比（应用规则返回金额和订单量，占比可由结果计算）。
SELECT channel,
       ROUND(SUM(amount), 2) AS paid_gmv,
       COUNT(id) AS order_count
FROM orders
WHERE status = 'PAID' AND YEAR(created_at) = YEAR(CURRENT_DATE)
GROUP BY channel
ORDER BY paid_gmv DESC;

-- Q06 各客户分层的客单价是多少？
SELECT c.segment,
       COUNT(DISTINCT c.id) AS customers,
       COUNT(o.id) AS order_count,
       ROUND(AVG(o.amount), 2) AS avg_order_value,
       ROUND(SUM(o.amount), 2) AS paid_gmv
FROM orders o
JOIN customers c ON c.id = o.customer_id
WHERE o.status = 'PAID' AND YEAR(o.created_at) = YEAR(CURRENT_DATE)
GROUP BY c.segment
ORDER BY paid_gmv DESC;

-- Q07 今年每月新增客户数。
SELECT DATE_FORMAT(registered_at, '%Y-%m') AS month,
       COUNT(id) AS new_customers
FROM customers
WHERE YEAR(registered_at) = YEAR(CURRENT_DATE)
GROUP BY DATE_FORMAT(registered_at, '%Y-%m')
ORDER BY month;

-- Q08 各品类的销售毛利是多少？
SELECT c.name AS category,
       ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.discount)), 2) AS revenue,
       ROUND(SUM(oi.quantity * p.cost_price), 2) AS cost,
       ROUND(SUM(oi.quantity * (oi.unit_price * (1 - oi.discount) - p.cost_price)), 2)
         AS gross_profit
FROM order_items oi
JOIN orders o ON o.id = oi.order_id
JOIN products p ON p.id = oi.product_id
JOIN categories c ON c.id = p.category_id
WHERE o.status = 'PAID' AND YEAR(o.created_at) = YEAR(CURRENT_DATE)
GROUP BY c.id, c.name
ORDER BY gross_profit DESC;

-- Q09 已支付订单总数是多少？
SELECT COUNT(id) AS paid_order_count
FROM orders
WHERE status = 'PAID' AND YEAR(created_at) = YEAR(CURRENT_DATE);

-- Q10 退款订单率是多少？
SELECT ROUND(
         100.0 * SUM(CASE WHEN status = 'REFUNDED' THEN 1 ELSE 0 END)
         / NULLIF(COUNT(id), 0),
         2
       ) AS refund_rate_pct
FROM orders
WHERE YEAR(created_at) = YEAR(CURRENT_DATE);
