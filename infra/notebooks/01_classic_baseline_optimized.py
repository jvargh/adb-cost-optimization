# Databricks notebook source
# MAGIC %md
# MAGIC # Classic compute: baseline and optimized
# MAGIC Run on bounded job compute. The optimized path projects early and broadcasts the bounded
# MAGIC customer dimension. Both paths must return exactly the same rows.

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
shuffle_partitions = int(dbutils.widgets.get("shuffle_partitions"))
assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", catalog)
assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema)
assert 4 <= shuffle_partitions <= 128
spark.conf.set("spark.sql.shuffle.partitions", str(shuffle_partitions))

orders = spark.table(f"{catalog}.{schema}.tpch_orders")
customers = spark.table(f"{catalog}.{schema}.tpch_customer")

started = perf_counter()
baseline = (
    orders.repartition(shuffle_partitions, "o_orderstatus")
    .join(customers, orders.o_custkey == customers.c_custkey)
    .groupBy("o_orderstatus", "c_mktsegment")
    .agg(
        F.count("*").alias("order_count"),
        F.round(F.sum("o_totalprice"), 2).alias("total_price"),
    )
)
baseline_rows = baseline.collect()
baseline_seconds = perf_counter() - started

started = perf_counter()
optimized = (
    orders.select("o_custkey", "o_orderstatus", "o_totalprice")
    .join(
        broadcast(customers.select("c_custkey", "c_mktsegment")),
        F.col("o_custkey") == F.col("c_custkey"),
    )
    .groupBy("o_orderstatus", "c_mktsegment")
    .agg(
        F.count("*").alias("order_count"),
        F.round(F.sum("o_totalprice"), 2).alias("total_price"),
    )
)
optimized_rows = optimized.collect()
optimized_seconds = perf_counter() - started

assert sorted(baseline_rows) == sorted(optimized_rows), "Classic optimized result differs from baseline"
display(spark.createDataFrame(
    [("baseline", baseline_seconds), ("optimized", optimized_seconds)],
    ["variant", "elapsed_seconds"],
))
