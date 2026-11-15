MODEL (name stg.shipments, kind FULL, grain shipment_id);

SELECT shipment_id, CAST(order_id AS BIGINT) AS order_id, carrier,
       CAST(shipped_at AS TIMESTAMPTZ) AS shipped_at,
       CAST(delivered_at AS TIMESTAMPTZ) AS delivered_at,
       CAST(freight_sar AS DECIMAL(12, 2)) AS freight_sar
FROM raw.shipments
