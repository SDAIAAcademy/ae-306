MODEL (name stg.customers, kind FULL, grain customer_id);

SELECT customer_id, name, customer_type, city
FROM raw.customers
