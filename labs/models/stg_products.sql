MODEL (name stg.products, kind FULL, grain product_id);

SELECT product_id, name, category, supplier_id,
       CAST(units_per_carton AS INTEGER) AS units_per_carton,
       CAST(list_price_piece_sar AS DECIMAL(12, 2)) AS list_price_piece_sar
FROM raw.products
