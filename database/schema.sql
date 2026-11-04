-- Data Agent local business schema.
-- Target: MySQL 8.0.16+; import into an empty database.
-- This file intentionally contains no CREATE DATABASE, users, grants, or secrets.

SET NAMES utf8mb4;
SET time_zone = '+08:00';

CREATE TABLE `regions` (
  `id` INT UNSIGNED NOT NULL COMMENT '区域主键',
  `name` VARCHAR(32) NOT NULL COMMENT '销售区域名称',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_regions_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='销售区域维表';

CREATE TABLE `categories` (
  `id` INT UNSIGNED NOT NULL COMMENT '品类主键',
  `name` VARCHAR(64) NOT NULL COMMENT '商品品类名称',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_categories_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='商品品类维表';

CREATE TABLE `products` (
  `id` BIGINT UNSIGNED NOT NULL COMMENT '商品主键',
  `name` VARCHAR(128) NOT NULL COMMENT '商品名称',
  `category_id` INT UNSIGNED NOT NULL COMMENT '所属品类',
  `unit_price` DECIMAL(12,2) NOT NULL COMMENT '标准售价，单位元',
  `cost_price` DECIMAL(12,2) NOT NULL COMMENT '单位成本，单位元',
  `active` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否在售：1 是，0 否',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_products_name` (`name`),
  KEY `idx_products_category` (`category_id`),
  CONSTRAINT `fk_products_category`
    FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`),
  CONSTRAINT `chk_products_prices`
    CHECK (`unit_price` >= 0 AND `cost_price` >= 0),
  CONSTRAINT `chk_products_active`
    CHECK (`active` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='商品维表';

CREATE TABLE `customers` (
  `id` BIGINT UNSIGNED NOT NULL COMMENT '客户主键',
  `name` VARCHAR(64) NOT NULL COMMENT '演示客户名称',
  `region_id` INT UNSIGNED NOT NULL COMMENT '所属销售区域',
  `segment` VARCHAR(32) NOT NULL COMMENT '客户分层',
  `registered_at` DATE NOT NULL COMMENT '注册日期',
  PRIMARY KEY (`id`),
  KEY `idx_customers_region` (`region_id`),
  KEY `idx_customers_segment` (`segment`),
  KEY `idx_customers_registered` (`registered_at`),
  CONSTRAINT `fk_customers_region`
    FOREIGN KEY (`region_id`) REFERENCES `regions` (`id`),
  CONSTRAINT `chk_customers_segment`
    CHECK (`segment` IN ('个人', '小微企业', '中型企业', '大型企业'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='客户维表';

CREATE TABLE `orders` (
  `id` BIGINT UNSIGNED NOT NULL COMMENT '订单主键',
  `order_no` VARCHAR(32) NOT NULL COMMENT '业务订单编号',
  `customer_id` BIGINT UNSIGNED NOT NULL COMMENT '下单客户',
  `status` VARCHAR(20) NOT NULL COMMENT '订单状态',
  `created_at` DATETIME NOT NULL COMMENT '下单时间',
  `paid_at` DATETIME NULL COMMENT '支付时间；未支付为空',
  `amount` DECIMAL(14,2) NOT NULL COMMENT '订单明细折后金额合计，单位元',
  `channel` VARCHAR(32) NOT NULL COMMENT '下单渠道',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_orders_order_no` (`order_no`),
  KEY `idx_orders_created_status` (`created_at`, `status`),
  KEY `idx_orders_status_created` (`status`, `created_at`),
  KEY `idx_orders_customer` (`customer_id`),
  KEY `idx_orders_channel` (`channel`),
  CONSTRAINT `fk_orders_customer`
    FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`),
  CONSTRAINT `chk_orders_status`
    CHECK (`status` IN ('PAID', 'REFUNDED', 'CANCELLED', 'PENDING')),
  CONSTRAINT `chk_orders_amount`
    CHECK (`amount` >= 0),
  CONSTRAINT `chk_orders_payment_time`
    CHECK (`paid_at` IS NULL OR `paid_at` >= `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='订单事实表，一行代表一笔订单';

CREATE TABLE `order_items` (
  `id` BIGINT UNSIGNED NOT NULL COMMENT '订单明细主键',
  `order_id` BIGINT UNSIGNED NOT NULL COMMENT '所属订单',
  `product_id` BIGINT UNSIGNED NOT NULL COMMENT '商品',
  `quantity` INT UNSIGNED NOT NULL COMMENT '购买数量',
  `unit_price` DECIMAL(12,2) NOT NULL COMMENT '下单时成交单价，单位元',
  `discount` DECIMAL(5,4) NOT NULL DEFAULT 0 COMMENT '折扣比例，0.1000 表示九折',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_order_items_order_product` (`order_id`, `product_id`),
  KEY `idx_items_product` (`product_id`),
  CONSTRAINT `fk_items_order`
    FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`),
  CONSTRAINT `fk_items_product`
    FOREIGN KEY (`product_id`) REFERENCES `products` (`id`),
  CONSTRAINT `chk_items_quantity`
    CHECK (`quantity` > 0),
  CONSTRAINT `chk_items_price`
    CHECK (`unit_price` >= 0),
  CONSTRAINT `chk_items_discount`
    CHECK (`discount` >= 0 AND `discount` < 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='订单商品明细表';
