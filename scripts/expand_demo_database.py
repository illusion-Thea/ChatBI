"""Append synthetic demo rows without replacing existing records. Safe to rerun.

MYSQL_ROOT_PASSWORD is required; only data_agent_demo is writable here.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import runpy
import pymysql

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / '.runtime' / 'queryx-migration'
TABLES = ('regions', 'categories', 'products', 'customers', 'orders', 'order_items')

def digest(rows):
    return hashlib.sha256(json.dumps(rows, default=str, ensure_ascii=False).encode()).hexdigest()

def main():
    password = os.environ['MYSQL_ROOT_PASSWORD']
    data = runpy.run_path(str(ARTIFACTS / 'expanded_seed.py'))['build_seed_data']()
    connection = pymysql.connect(host='127.0.0.1', user='root', password=password,
                                 database='data_agent_demo', charset='utf8mb4', autocommit=False)
    try:
        with connection.cursor() as cursor:
            before = {}
            for table in TABLES:
                cursor.execute(f'SELECT * FROM `{table}` ORDER BY id')
                before[table] = cursor.fetchall()
            # Never overwrite dimensions: generated order lines use these exact prices.
            assert tuple(data['products']) == before['products'], 'Product catalog changed; aborting.'
            existing_customers = {row[0] for row in before['customers']}
            existing_orders = {row[0] for row in before['orders']}
            customers = [row for row in data['customers'] if row[0] not in existing_customers]
            orders = [row for row in data['orders'] if row[0] not in existing_orders]
            order_ids = {row[0] for row in orders}
            first_dates = {}
            for order in orders:
                first_dates[order[2]] = min(first_dates.get(order[2], order[4].date()), order[4].date())
            customers = [(*row[:4], min(row[4], first_dates.get(row[0], row[4]))) for row in customers]
            next_id = max((row[0] for row in before['order_items']), default=0) + 1
            items = [(next_id + index, *row[1:]) for index, row in enumerate(
                row for row in data['order_items'] if row[1] in order_ids)]
            snapshot = {'tables': before, 'sha256': {table:digest(rows) for table, rows in before.items()}}
            backup = ARTIFACTS / 'database-before.json'
            if not backup.exists():
                backup.write_text(json.dumps(snapshot, default=str, ensure_ascii=False), encoding='utf-8')
            for table, rows in [('customers', customers), ('orders', orders), ('order_items', items)]:
                if rows:
                    sql = f"INSERT INTO `{table}` VALUES ({','.join(['%s'] * len(rows[0]))})"
                    for offset in range(0, len(rows), 1000):
                        cursor.executemany(sql, rows[offset:offset + 1000])
            after = {}
            for table in TABLES:
                cursor.execute(f'SELECT * FROM `{table}` ORDER BY id')
                after[table] = cursor.fetchall()
                old_ids = {row[0] for row in before[table]}
                assert digest([row for row in after[table] if row[0] in old_ids]) == digest(before[table]), table
            cursor.execute('SELECT COUNT(*) FROM orders o LEFT JOIN customers c ON c.id=o.customer_id WHERE c.id IS NULL')
            assert cursor.fetchone()[0] == 0
            cursor.execute('SELECT COUNT(*) FROM orders o JOIN (SELECT order_id, SUM(ROUND(quantity*unit_price*(1-discount),2)) total FROM order_items GROUP BY order_id) i ON i.order_id=o.id WHERE ABS(o.amount-i.total)>0.01')
            assert cursor.fetchone()[0] == 0, 'Order totals do not match line items'
            connection.commit()
            report = {'before':{t:len(r) for t,r in before.items()},
                      'after':{t:len(r) for t,r in after.items()},
                      'inserted':{'customers':len(customers),'orders':len(orders),'order_items':len(items)},
                      'original_rows_unchanged':True, 'orphan_orders':0,'amount_mismatches':0,
                      'synthetic':True,'end_date':'2026-10-30'}
            (ARTIFACTS / 'data-expansion.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            print(json.dumps(report,indent=2))
    finally:
        connection.close()

if __name__ == '__main__':
    main()
