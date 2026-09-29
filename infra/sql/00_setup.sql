-- Databricks SQL workshop setup. The environment scripts create this catalog and schema.
CREATE SCHEMA IF NOT EXISTS `{{CATALOG}}`.`{{SCHEMA}}`;

-- COMMAND ----------

CREATE OR REPLACE TABLE `{{CATALOG}}`.`{{SCHEMA}}`.sql_tpch_orders
USING DELTA AS
SELECT *
FROM samples.tpch.orders
ORDER BY o_orderkey
LIMIT 250000;

-- COMMAND ----------

CREATE OR REPLACE TABLE `{{CATALOG}}`.`{{SCHEMA}}`.sql_tpcds_store_sales
USING DELTA AS
SELECT *
FROM samples.tpcds_sf1.store_sales
ORDER BY ss_ticket_number, ss_item_sk
LIMIT 250000;

-- COMMAND ----------

CREATE OR REPLACE TABLE `{{CATALOG}}`.`{{SCHEMA}}`.sql_nyctaxi_trips
USING DELTA AS
SELECT *
FROM samples.nyctaxi.trips
ORDER BY tpep_pickup_datetime
LIMIT 250000;

-- COMMAND ----------

SELECT 'sql_tpch_orders' AS table_name, COUNT(*) AS row_count
FROM `{{CATALOG}}`.`{{SCHEMA}}`.sql_tpch_orders
UNION ALL
SELECT 'sql_tpcds_store_sales', COUNT(*)
FROM `{{CATALOG}}`.`{{SCHEMA}}`.sql_tpcds_store_sales
UNION ALL
SELECT 'sql_nyctaxi_trips', COUNT(*)
FROM `{{CATALOG}}`.`{{SCHEMA}}`.sql_nyctaxi_trips;
