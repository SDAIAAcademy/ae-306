MODEL (name mart.dim_supplier, kind FULL, grain supplier_key);

-- type 2: one row per version of a supplier, valid_from inclusive, valid_to exclusive
SELECT
  supplier_id || '@' || strftime(CAST(valid_from AS TIMESTAMPTZ), '%Y-%m-%d %H:%M') AS supplier_key,
  supplier_id, name_en, country, currency, CAST(payment_terms_days AS INTEGER) AS payment_terms_days,
  CAST(valid_from AS TIMESTAMPTZ) AS valid_from,
  COALESCE(CAST(NULLIF(CAST(valid_to AS VARCHAR), '') AS TIMESTAMPTZ), TIMESTAMPTZ '9999-12-31 00:00:00+00') AS valid_to
FROM raw.supplier_history
