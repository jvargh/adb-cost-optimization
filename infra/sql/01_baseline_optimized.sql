-- Baseline and optimized paths are compared in one statement so the API run is session-independent.
WITH baseline_result AS (
  SELECT
    date_trunc('MONTH', tpep_pickup_datetime) AS pickup_month,
    pickup_zip,
    COUNT(*) AS trip_count,
    ROUND(SUM(fare_amount), 2) AS fare_total
  FROM `{{CATALOG}}`.`{{SCHEMA}}`.sql_nyctaxi_trips
  WHERE year(tpep_pickup_datetime) >= 2010
  GROUP BY date_trunc('MONTH', tpep_pickup_datetime), pickup_zip
),
projected AS (
  SELECT tpep_pickup_datetime, pickup_zip, fare_amount
  FROM `{{CATALOG}}`.`{{SCHEMA}}`.sql_nyctaxi_trips
  WHERE tpep_pickup_datetime >= TIMESTAMP'2010-01-01'
),
optimized_result AS (
  SELECT
    date_trunc('MONTH', tpep_pickup_datetime) AS pickup_month,
    pickup_zip,
    COUNT(*) AS trip_count,
    ROUND(SUM(fare_amount), 2) AS fare_total
  FROM projected
  GROUP BY date_trunc('MONTH', tpep_pickup_datetime), pickup_zip
)
SELECT 'baseline_minus_optimized' AS difference, COUNT(*) AS differing_rows
FROM (SELECT * FROM baseline_result EXCEPT ALL SELECT * FROM optimized_result)
UNION ALL
SELECT 'optimized_minus_baseline', COUNT(*)
FROM (SELECT * FROM optimized_result EXCEPT ALL SELECT * FROM baseline_result);
