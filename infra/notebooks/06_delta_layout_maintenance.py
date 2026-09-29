# Databricks notebook source
# MAGIC %md
# MAGIC # Delta layout and maintenance
# MAGIC Copies the bounded NYC Taxi table, compacts and Z-Orders it, updates statistics, and verifies
# MAGIC that maintenance does not alter data. VACUUM is dry-run only.

# COMMAND ----------
from time import perf_counter
import re

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "adb_cost_workshop")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", catalog)
assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema)

source_name = f"{catalog}.{schema}.nyctaxi_trips"
target_name = f"{catalog}.{schema}.nyctaxi_layout_demo"
source = spark.table(source_name)
(source.repartition(16)
    .write.format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(target_name))

before = spark.table(target_name)
before_count = before.count()
before_digest = before.selectExpr(
    "bit_xor(xxhash64(*)) AS digest"
).first()["digest"]

started = perf_counter()
spark.sql(f"OPTIMIZE `{catalog}`.`{schema}`.`nyctaxi_layout_demo` ZORDER BY (pickup_zip)")
spark.sql(f"ANALYZE TABLE `{catalog}`.`{schema}`.`nyctaxi_layout_demo` COMPUTE STATISTICS")
maintenance_seconds = perf_counter() - started

after = spark.table(target_name)
after_count = after.count()
after_digest = after.selectExpr(
    "bit_xor(xxhash64(*)) AS digest"
).first()["digest"]
assert (before_count, before_digest) == (after_count, after_digest), "Delta maintenance changed table contents"

display(spark.sql(f"DESCRIBE DETAIL `{catalog}`.`{schema}`.`nyctaxi_layout_demo`"))
display(spark.sql(f"VACUUM `{catalog}`.`{schema}`.`nyctaxi_layout_demo` RETAIN 168 HOURS DRY RUN"))
print(f"Maintenance completed in {maintenance_seconds:.3f} seconds")
