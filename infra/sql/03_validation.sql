WITH table_counts AS (
  SELECT 'sql_tpch_orders' AS table_name, COUNT(*) AS row_count
  FROM `{{CATALOG}}`.`{{SCHEMA}}`.tpch_orders
  UNION ALL
  SELECT 'sql_tpcds_store_sales', COUNT(*)
  FROM `{{CATALOG}}`.`{{SCHEMA}}`.tpcds_store_sales
  UNION ALL
  SELECT 'sql_nyctaxi_trips', COUNT(*)
  FROM `{{CATALOG}}`.`{{SCHEMA}}`.nyctaxi_trips
)
SELECT
  table_name,
  row_count,
  CASE WHEN row_count BETWEEN 1 AND 250000 THEN 'PASS' ELSE 'FAIL' END AS status
FROM table_counts
ORDER BY table_name;
