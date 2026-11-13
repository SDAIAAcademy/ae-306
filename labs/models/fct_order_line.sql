MODEL (name mart.fct_order_line, kind FULL, grain (order_id, line_no));

-- grain: one row per line of a confirmed order
WITH lines AS (
  SELECT
    l.order_id, l.line_no, o.order_date, o.created_at,
    COALESCE(c.customer_id, 'Unknown') AS customer_id,
    l.product_id, p.supplier_id,
    l.qty * CASE WHEN l.unit = 'carton' THEN p.units_per_carton ELSE 1 END AS qty_pieces,
    l.qty * l.unit_price_sar * (1 - l.discount_pct / 100) AS revenue
  FROM stg.order_lines AS l
  JOIN stg.orders AS o ON o.order_id = l.order_id AND o.status = 'confirmed'
  JOIN stg.products AS p ON p.product_id = l.product_id
  LEFT JOIN stg.customers AS c ON c.customer_id = o.customer_id
)
SELECT
  lines.order_id, lines.line_no, lines.order_date, lines.customer_id, lines.product_id,
  s.supplier_key,
  lines.qty_pieces,
  CAST(lines.revenue AS DECIMAL(14, 2)) AS revenue,
  CAST(lines.qty_pieces * pr.cost_piece_sar AS DECIMAL(14, 2)) AS cost,
  -- freight is per shipment: share it out by revenue so it is counted once
  CAST(sh.freight_sar * lines.revenue / sum(lines.revenue) OVER (PARTITION BY lines.order_id) AS DECIMAL(14, 4)) AS freight
FROM lines
JOIN stg.prices AS pr
  ON pr.product_id = lines.product_id AND lines.order_date BETWEEN pr.valid_from AND pr.valid_to
LEFT JOIN stg.shipments AS sh ON sh.order_id = lines.order_id
LEFT JOIN mart.dim_supplier AS s
  ON s.supplier_id = lines.supplier_id AND lines.created_at >= s.valid_from AND lines.created_at < s.valid_to
