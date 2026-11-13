MODEL (name stg.order_lines, kind FULL, grain (order_id, line_no));

-- the nightly extract re-sent one day's lines: keep one copy of each line
SELECT
  CAST(order_id AS BIGINT) AS order_id,
  CAST(line_no AS INTEGER) AS line_no,
  product_id,
  unit,
  CAST(qty AS INTEGER) AS qty,
  CAST(unit_price_sar AS DECIMAL(12, 2)) AS unit_price_sar,
  CAST(discount_pct AS DECIMAL(5, 2)) AS discount_pct
FROM raw.order_lines
QUALIFY row_number() OVER (PARTITION BY order_id, line_no) = 1
