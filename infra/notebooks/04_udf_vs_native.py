# Databricks notebook source
# MAGIC %md
# MAGIC # Python UDF versus native Spark expression
# MAGIC Compares equivalent fare bucketing logic over the bounded NYC Taxi workshop table.

# COMMAND ----------
from time import perf_counter
from pyspark.sql import functions as F
from pyspark.sql.types import StringType
import re

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "adb_cost_workshop")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", catalog)
assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema)

trips = spark.table(f"{catalog}.{schema}.nyctaxi_trips").select("fare_amount")

@F.udf(returnType=StringType())
def fare_band(fare):
    if fare is None:
        return "unknown"
    if fare < 15:
        return "low"
    if fare < 40:
        return "medium"
    return "high"

started = perf_counter()
udf_result = trips.groupBy(fare_band("fare_amount").alias("fare_band")).count()
udf_rows = udf_result.collect()
udf_seconds = perf_counter() - started

native_band = (
    F.when(F.col("fare_amount").isNull(), "unknown")
    .when(F.col("fare_amount") < 15, "low")
    .when(F.col("fare_amount") < 40, "medium")
    .otherwise("high")
)
started = perf_counter()
native_result = trips.groupBy(native_band.alias("fare_band")).count()
native_rows = native_result.collect()
native_seconds = perf_counter() - started

assert sorted(udf_rows) == sorted(native_rows), "Native expression changed fare buckets"
display(spark.createDataFrame(
    [("python_udf", udf_seconds), ("native_expression", native_seconds)],
    ["variant", "elapsed_seconds"],
))
