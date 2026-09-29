# Databricks notebook source
spark.sql("DROP TABLE IF EXISTS dbscannercatalog.catalog_inventory.workspace_scan_summary")
spark.sql("DROP TABLE IF EXISTS dbscannercatalog.catalog_inventory.workspace_scan_clusters")
spark.sql("DROP TABLE IF EXISTS dbscannercatalog.catalog_inventory.workspace_scan_uc_tables")
spark.sql("DROP TABLE IF EXISTS dbscannercatalog.catalog_inventory.workspace_scan_warehouses")
spark.sql("DROP TABLE IF EXISTS dbscannercatalog.catalog_inventory.workspace_scan_pipelines")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Create catalog (optional, if it does not already exist)
# MAGIC CREATE CATALOG IF NOT EXISTS dbscannercatalog MANAGED LOCATION 'abfss://unity-catalog-storage@dbstoragejinj63qvq437o.dfs.core.windows.net/7405617048577650';
# MAGIC
# MAGIC -- Use the catalog
# MAGIC USE CATALOG dbscannercatalog;
# MAGIC
# MAGIC -- Create schemas
# MAGIC CREATE SCHEMA IF NOT EXISTS catalog_inventory;
# MAGIC
# MAGIC

# COMMAND ----------

# MAGIC %sql
# MAGIC
# MAGIC -- Main summary table
# MAGIC CREATE TABLE IF NOT EXISTS dbscannercatalog.catalog_inventory.workspace_scan_summary (
# MAGIC   -- Scan Metadata
# MAGIC   scan_id STRING NOT NULL,
# MAGIC   workspace_id STRING NOT NULL,
# MAGIC   workspace_url STRING,
# MAGIC   scan_start_timestamp TIMESTAMP NOT NULL,
# MAGIC   scan_end_timestamp TIMESTAMP NOT NULL,
# MAGIC   scan_duration_seconds DOUBLE,
# MAGIC   scan_type STRING,
# MAGIC   
# MAGIC   -- Top Row KPIs - Counts
# MAGIC   total_clusters INT,
# MAGIC   total_jobs INT,
# MAGIC   total_pipelines INT,
# MAGIC   total_uc_tables INT,
# MAGIC   total_warehouses INT,
# MAGIC   total_ml_experiments INT,
# MAGIC   total_repos INT,
# MAGIC   total_serving_endpoints INT,
# MAGIC   total_genie_spaces INT,
# MAGIC   total_alerts INT,
# MAGIC   total_notebooks INT,  
# MAGIC   -- Constraints
# MAGIC   PRIMARY KEY (scan_id, workspace_id)
# MAGIC ) USING DELTA
# MAGIC PARTITIONED BY (scan_start_timestamp)
# MAGIC COMMENT 'Workspace scan summary data for dashboard visualization';

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Cluster details table (normalized)
# MAGIC CREATE TABLE IF NOT EXISTS dbscannercatalog.catalog_inventory.workspace_scan_clusters (
# MAGIC   workspace_id STRING NOT NULL,
# MAGIC   scan_id STRING NOT NULL,
# MAGIC   cluster_id STRING NOT NULL,
# MAGIC   cluster_name STRING,
# MAGIC   state STRING,
# MAGIC   cluster_source STRING,
# MAGIC   node_type_id STRING,
# MAGIC   driver_node_type_id STRING,
# MAGIC   min_workers INT,
# MAGIC   max_workers INT,
# MAGIC   num_workers INT,
# MAGIC   autotermination_minutes INT,
# MAGIC   creator_user_name STRING,
# MAGIC   uptime_hours DOUBLE,
# MAGIC   spot_enabled BOOLEAN,
# MAGIC   enable_elastic_disk BOOLEAN,
# MAGIC   spark_version STRING,
# MAGIC   policy_id STRING,
# MAGIC   PRIMARY KEY (scan_id, cluster_id)
# MAGIC ) USING DELTA
# MAGIC COMMENT 'Detailed cluster information per scan';

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Unity Catalog tables detail
# MAGIC CREATE TABLE IF NOT EXISTS dbscannercatalog.catalog_inventory.workspace_scan_uc_tables (
# MAGIC   workspace_id STRING NOT NULL,
# MAGIC   scan_id STRING NOT NULL,
# MAGIC   catalog_name STRING,
# MAGIC   schema_name STRING,
# MAGIC   table_name STRING,
# MAGIC   table_type STRING,  -- MANAGED, EXTERNAL
# MAGIC   table_format STRING,  -- DELTA, PARQUET, CSV, etc.
# MAGIC   storage_location STRING,
# MAGIC   is_delta BOOLEAN,
# MAGIC   
# MAGIC   PRIMARY KEY (scan_id, catalog_name, schema_name, table_name)
# MAGIC ) USING DELTA
# MAGIC COMMENT 'Unity Catalog table details per scan';

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Warehouse details table
# MAGIC CREATE TABLE IF NOT EXISTS dbscannercatalog.catalog_inventory.workspace_scan_warehouses (
# MAGIC   workspace_id STRING NOT NULL,
# MAGIC   scan_id STRING NOT NULL,
# MAGIC   warehouse_id STRING NOT NULL,
# MAGIC   warehouse_name STRING,
# MAGIC   cluster_size STRING,
# MAGIC   min_num_clusters INT,
# MAGIC   max_num_clusters INT,
# MAGIC   auto_stop_mins INT,
# MAGIC   state STRING,
# MAGIC   warehouse_type STRING,
# MAGIC   enable_photon BOOLEAN,
# MAGIC   enable_serverless_compute BOOLEAN,
# MAGIC   spot_instance_policy STRING,
# MAGIC   creator_name STRING,
# MAGIC   
# MAGIC   PRIMARY KEY (scan_id, warehouse_id)
# MAGIC ) USING DELTA
# MAGIC COMMENT 'SQL Warehouse details per scan';
# MAGIC

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Pipeline details table
# MAGIC CREATE TABLE IF NOT EXISTS dbscannercatalog.catalog_inventory.workspace_scan_pipelines (
# MAGIC   workspace_id STRING NOT NULL,
# MAGIC   scan_id STRING NOT NULL,
# MAGIC   pipeline_id STRING NOT NULL,
# MAGIC   pipeline_name STRING,
# MAGIC   state STRING,
# MAGIC   creator_user_name STRING,
# MAGIC   creation_time TIMESTAMP,
# MAGIC   
# MAGIC   PRIMARY KEY (scan_id, pipeline_id)
# MAGIC ) USING DELTA
# MAGIC COMMENT 'DLT Pipeline details per scan';