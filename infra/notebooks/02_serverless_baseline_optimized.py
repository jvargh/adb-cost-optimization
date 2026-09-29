# Databricks notebook source
# MAGIC %md
# MAGIC # Serverless compute: baseline and optimized
# MAGIC Demonstrates expression simplification and early projection on a bounded NYC Taxi table.

# COMMAND ----------
from time import perf_counter
from pyspark.sql import functions as F
import re

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "adb_cost_workshop")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", catalog)
assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema)

trips = spark.table(f"{catalog}.{schema}.nyctaxi_trips")

started = perf_counter()
baseline = (
    trips.withColumn("pickup_day", F.to_date("tpep_pickup_datetime"))
    .filter(F.year("pickup_day") >= 2010)
    .groupBy("pickup_day", "pickup_zip")
    .agg(
        F.count("*").alias("trip_count"),
        F.round(F.sum("fare_amount"), 2).alias("fare_total"),
    )
)
baseline_rows = baseline.collect()
baseline_seconds = perf_counter() - started

started = perf_counter()
optimized = (
    trips.select("tpep_pickup_datetime", "pickup_zip", "fare_amount")
    .filter(F.col("tpep_pickup_datetime") >= F.lit("2010-01-01").cast("timestamp"))
    .groupBy(F.to_date("tpep_pickup_datetime").alias("pickup_day"), "pickup_zip")
    .agg(
        F.count("*").alias("trip_count"),
        F.round(F.sum("fare_amount"), 2).alias("fare_total"),
    )
)
optimized_rows = optimized.collect()
optimized_seconds = perf_counter() - started

assert sorted(baseline_rows) == sorted(optimized_rows), "Serverless optimized result differs from baseline"
display(spark.createDataFrame(
    [("baseline", baseline_seconds), ("optimized", optimized_seconds)],
    ["variant", "elapsed_seconds"],
))
