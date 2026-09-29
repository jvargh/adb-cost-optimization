# Databricks notebook source
# MAGIC %md
# MAGIC # Workshop setup
# MAGIC Creates small, deterministic Delta tables from Databricks sample data. Re-running this
# MAGIC notebook replaces only the selected workshop schema.

# COMMAND ----------
from pyspark.sql import functions as F
import re

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "adb_cost_workshop")
dbutils.widgets.text("max_rows", "250000")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
max_rows = int(dbutils.widgets.get("max_rows"))

identifier = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
assert identifier.fullmatch(catalog) and identifier.fullmatch(schema), "Catalog and schema must be simple identifiers"
assert 1 <= max_rows <= 500_000, "max_rows must be between 1 and 500,000"

target = f"`{catalog}`.`{schema}`"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {target}")

sources = {
    "tpch_orders": ("samples.tpch.orders", "o_orderkey"),
    "tpch_customer": ("samples.tpch.customer", "c_custkey"),
    "tpcds_store_sales": ("samples.tpcds_sf1.store_sales", "ss_ticket_number"),
    "nyctaxi_trips": ("samples.nyctaxi.trips", "tpep_pickup_datetime"),
}

for table, (source, order_column) in sources.items():
    bounded = spark.table(source).orderBy(F.col(order_column)).limit(max_rows)
    (bounded.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(f"{catalog}.{schema}.{table}"))

actual = {
    table: spark.table(f"{catalog}.{schema}.{table}").count()
    for table in sources
}
assert all(0 < count <= max_rows for count in actual.values()), actual
display(spark.createDataFrame(actual.items(), ["table_name", "row_count"]))
