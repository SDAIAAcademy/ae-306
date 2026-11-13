MODEL (name stg.orders, kind FULL, grain order_id);

SELECT
  CAST(order_id AS BIGINT) AS order_id,
  customer_id,
  CAST(order_date AS DATE) AS order_date,
  status,
  CAST(created_at AS TIMESTAMPTZ) AS created_at,
  CAST(updated_at AS TIMESTAMPTZ) AS updated_at
FROM raw.orders
