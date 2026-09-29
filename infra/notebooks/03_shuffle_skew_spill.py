# Databricks notebook source
# MAGIC %md
# MAGIC # Shuffle, skew, and spill
# MAGIC The baseline deliberately partitions by a low-cardinality key. The optimized path
# MAGIC pre-aggregates before the join. Inspect the Spark UI for task imbalance and spill; this lab
# MAGIC never manufactures an unbounded data set or intentionally exhausts executor memory.

# COMMAND ----------
from time import perf_counter
from pyspark.sql import functions as F
from pyspark.sql.functions import broadcast
import re

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "adb_cost_workshop")
dbutils.widgets.text("shuffle_partitions", "32")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
partitions = int(dbutils.widgets.get("shuffle_partitions"))
assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", catalog)
assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema)
assert 4 <= partitions <= 128
spark.conf.set("spark.sql.shuffle.partitions", str(partitions))
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")

orders = spark.table(f"{catalog}.{schema}.tpch_orders")
status_dimension = spark.createDataFrame(
    [("F", "fulfilled"), ("O", "open"), ("P", "pending")],
    ["status", "status_label"],
)

started = perf_counter()
baseline = (
    orders.repartition(partitions, "o_orderstatus")
    .join(status_dimension, F.col("o_orderstatus") == F.col("status"))
    .groupBy("status_label")
    .agg(F.count("*").alias("order_count"), F.round(F.sum("o_totalprice"), 2).alias("total_price"))
)
baseline_rows = baseline.collect()
baseline_seconds = perf_counter() - started

started = perf_counter()
optimized = (
    orders.groupBy("o_orderstatus")
    .agg(F.count("*").alias("order_count"), F.round(F.sum("o_totalprice"), 2).alias("total_price"))
    .join(broadcast(status_dimension), F.col("o_orderstatus") == F.col("status"))
    .select("status_label", "order_count", "total_price")
)
optimized_rows = optimized.collect()
optimized_seconds = perf_counter() - started

assert sorted(baseline_rows) == sorted(optimized_rows), "Pre-aggregation changed the result"
display(spark.createDataFrame(
    [("skewed_shuffle", baseline_seconds), ("pre_aggregate", optimized_seconds)],
    ["variant", "elapsed_seconds"],
))
