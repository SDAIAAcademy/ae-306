MODEL (name mart.dim_customer, kind FULL, grain customer_id);

SELECT customer_id, name, customer_type, city FROM stg.customers
UNION ALL
SELECT 'Unknown', 'Unknown customer', 'Unknown', 'Unknown'   -- the unknown member: orders whose customer is gone
