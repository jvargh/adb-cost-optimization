# Databricks notebook source
# MAGIC %md
# MAGIC # Full refresh versus incremental CDC
# MAGIC Builds a deterministic change batch from TPC-DS, applies it by full recompute and by MERGE,
# MAGIC then proves both targets are equivalent. Re-running starts from the same bounded snapshot.

# COMMAND ----------
from time import perf_counter
from pyspark.sql import functions as F
from pyspark.sql import Window
import re

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "adb_cost_workshop")
dbutils.widgets.text("change_rows", "5000")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
change_rows = int(dbutils.widgets.get("change_rows"))
assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", catalog)
assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema)
assert 1 <= change_rows <= 10_000

base_name = f"{catalog}.{schema}.tpcds_store_sales"
full_name = f"{catalog}.{schema}.sales_full_target"
cdc_name = f"{catalog}.{schema}.sales_cdc_target"
changes_name = f"{catalog}.{schema}.sales_changes"
keyed_base_name = f"{catalog}.{schema}.sales_keyed_base"
key_columns = ["_workshop_key"]

source = spark.table(base_name)
sort_columns = [F.col(name).asc_nulls_first() for name in source.columns]
(source.withColumn("_workshop_key", F.row_number().over(Window.orderBy(*sort_columns)))
    .write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(keyed_base_name))
base = spark.table(keyed_base_name)
(base.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(cdc_name))

changes = (
    base.orderBy(*key_columns)
    .limit(change_rows)
    .withColumn("ss_quantity", F.coalesce(F.col("ss_quantity"), F.lit(0)) + F.lit(1))
)
(changes.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(changes_name))

started = perf_counter()
unchanged = base.join(changes.select(*key_columns), key_columns, "left_anti")
full_result = unchanged.unionByName(changes)
(full_result.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(full_name))
full_seconds = perf_counter() - started

started = perf_counter()
spark.sql(f"""
MERGE INTO `{catalog}`.`{schema}`.`sales_cdc_target` AS target
USING `{catalog}`.`{schema}`.`sales_changes` AS source
ON target.ss_ticket_number <=> source.ss_ticket_number
AND target._workshop_key = source._workshop_key
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
""")
cdc_seconds = perf_counter() - started

full_df = spark.table(full_name).drop("_workshop_key")
cdc_df = spark.table(cdc_name).drop("_workshop_key")
assert full_df.exceptAll(cdc_df).limit(1).count() == 0
assert cdc_df.exceptAll(full_df).limit(1).count() == 0
display(spark.createDataFrame(
    [("full_refresh", full_seconds), ("incremental_merge", cdc_seconds)],
    ["variant", "elapsed_seconds"],
))
