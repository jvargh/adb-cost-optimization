-- Concurrency lab: the automation launches Query A-D with a maximum of four simultaneous statements.

-- Query A: TPCH daily revenue.
SELECT o_orderdate, o_orderstatus, COUNT(*) AS orders, ROUND(SUM(o_totalprice), 2) AS revenue
FROM `{{CATALOG}}`.`{{SCHEMA}}`.sql_tpch_orders
GROUP BY o_orderdate, o_orderstatus
ORDER BY o_orderdate, o_orderstatus
LIMIT 500;

-- COMMAND ----------

-- Query B: TPC-DS item sales.
SELECT ss_item_sk, SUM(ss_quantity) AS units, ROUND(SUM(ss_net_paid), 2) AS net_paid
FROM `{{CATALOG}}`.`{{SCHEMA}}`.sql_tpcds_store_sales
GROUP BY ss_item_sk
ORDER BY net_paid DESC
LIMIT 500;

-- COMMAND ----------

-- Query C: NYC Taxi pickup summary.
SELECT pickup_zip, COUNT(*) AS trips, ROUND(AVG(trip_distance), 2) AS avg_distance
FROM `{{CATALOG}}`.`{{SCHEMA}}`.sql_nyctaxi_trips
GROUP BY pickup_zip
ORDER BY trips DESC
LIMIT 500;

-- COMMAND ----------

-- Query D: NYC Taxi hourly summary.
SELECT date_trunc('HOUR', tpep_pickup_datetime) AS pickup_hour,
       COUNT(*) AS trips,
       ROUND(SUM(fare_amount), 2) AS fare_total
FROM `{{CATALOG}}`.`{{SCHEMA}}`.sql_nyctaxi_trips
GROUP BY date_trunc('HOUR', tpep_pickup_datetime)
ORDER BY pickup_hour
LIMIT 500;
