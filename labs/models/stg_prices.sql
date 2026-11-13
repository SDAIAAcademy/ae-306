MODEL (name stg.prices, kind FULL, grain (product_id, valid_from));

SELECT
  product_id,
  supplier_id,
  CAST(cost_piece_sar AS DECIMAL(12, 2)) AS cost_piece_sar,
  CAST(valid_from AS DATE) AS valid_from,
  COALESCE(CAST(NULLIF(CAST(valid_to AS VARCHAR), '') AS DATE), DATE '9999-12-31') AS valid_to
FROM raw.prices
