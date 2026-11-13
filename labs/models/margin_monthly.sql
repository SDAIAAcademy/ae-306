MODEL (name mart.margin_monthly, kind FULL, grain month);

SELECT
  strftime(order_date, '%Y-%m') AS month,
  round(sum(revenue), 2) AS revenue,
  round(sum(cost), 2) AS cost,
  round(sum(revenue) - sum(cost), 2) AS margin,
  round(100 * (sum(revenue) - sum(cost)) / sum(revenue), 2) AS margin_pct
FROM mart.fct_order_line
GROUP BY 1
ORDER BY 1
