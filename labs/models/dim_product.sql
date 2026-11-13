MODEL (name mart.dim_product, kind FULL, grain product_id);

SELECT product_id, name, category, units_per_carton FROM stg.products
