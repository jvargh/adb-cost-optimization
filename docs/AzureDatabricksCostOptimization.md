# The Complete Guide to Azure Databricks Cost Optimization

**Analytics on Azure Blog** · **11 min read**

**Published:** August 25, 2026  
**Author:** Rafia Aqil  
**Co-authored by:** Aladdin Alchalabi, Sanjeev Nair, and Rafia Aqil

This guide walks through a proven approach to Azure Databricks cost optimization, structured in three phases: **1.** Discovery, **2.** Cluster/Data/Code Best Practices, and **3.** Team Alignment & Next Steps. 

## Phase 1: Discovery

For repeatable evidence collection, see the [Azure Databricks Cost Optimization Assessment Toolkit](./assessment/README.md). Its [validation record](./assessment/test-results.md) documents the tested read-only boundary and current live limitations.

### Assessing Your Current State

The following questions are designed to guide your initial assessment and help you identify areas for improvement. Documenting answers to each will provide a baseline for optimization and inform the next phases of your cost management strategy. 

| **Environment & Organization** | **Cluster Management** | **Cost Optimization** | **Data Management** | **Performance Monitoring** | **Future Planning** |
|---|---|---|---|---|---|
| What is the current scale of your Databricks environment?<br><br>How many workspaces do you have?<br><br>How are your workspaces organized (e.g., by environment type, region, use case)?<br><br>How many clusters are deployed?<br><br>How many users are active?<br><br>What are the primary use cases for Databricks in your organization?<br><br>• Data engineering<br>• Data science<br>• Machine learning<br>• Business intelligence | How are clusters currently managed?<br><br>• Manual configuration<br>• Automated scripts<br>• Databricks REST API<br>• Cluster policies<br><br>What is the average cluster uptime?<br><br>• Hours per day<br>• Days per week<br><br>What is the average cluster utilization rate?<br><br>• CPU usage<br>• Memory usage | What is the current monthly spend on Databricks?<br><br>• Total cost<br>• Breakdown by workspace<br>• Breakdown by cluster<br><br>What cost management tools are currently in use?<br><br>• Azure Cost Management<br>• Third-party tools<br><br>Are there any existing cost optimization strategies in place?<br><br>• Reserved instances<br>• Spot instances<br>• Cluster autoscaling | What is the current data storage strategy?<br><br>• Data lake<br>• Data warehouse<br>• Hybrid<br><br>What is the average data ingestion rate?<br><br>• GB per day<br>• Number of files<br><br>What is the average data processing time?<br><br>• ETL jobs<br>• Machine learning models<br><br>What types of data formats are used in your environment?<br><br>• Delta Lake<br>• Parquet<br>• JSON<br>• CSV<br>• Other formats relevant to your workloads | What performance monitoring tools are currently in use?<br><br>• Databricks Ganglia<br>• Azure Monitor<br>• Third-party tools<br><br>What are the key performance metrics tracked?<br><br>• Job execution time<br>• Cluster performance<br>• Data processing speed | Are there any planned expansions or changes to the Databricks environment?<br><br>• New use cases<br>• Increased data volume<br>• Additional users<br><br>What are the long-term goals for Databricks cost optimization?<br><br>• Reducing overall spend<br>• Improving resource utilization and cost attribution<br>• Enhancing performance |



### Understanding Databricks Cost Structure

**[Total Cost](https://azure.microsoft.com/en-us/pricing/details/databricks/?msockid=0a3e82160d2e6f3f2d3797df0c7f6e15) = Cloud Cost + DBU Cost** 

- **Cloud Cost:** Compute (VMs, networking, IP addresses), storage (ADLS, MLflow artifacts), other services (firewalls), and cluster type (serverless compute, classic compute).
- **DBU Cost:** Workload size, cluster/warehouse size, photon acceleration, compute runtime, workspace tier, SKU type (Jobs, Delta Live Tables, All Purpose Clusters, Serverless), model serving, queries per second, and model execution time.

### **Diagnose Cost and Issues** 

Effectively diagnosing cost and performance issues in Databricks requires a structured approach. Use the following steps and metrics to gain visibility into your environment and uncover actionable insights. 

#### **1. Identify Costly Workloads** 

- **[Account Console Usage Reports](https://learn.microsoft.com/en-us/azure/databricks/admin/account-settings/usage):** Review usage reports to identify usage breakdowns by product, SKU name, and custom tags. 

   - **Usage Breakdown by Product and SKU:** Helps you understand which services and compute types (clusters, SQL warehouses, serverless options) are consuming the most resources. 

   - **Custom Tags for Attribution:** Tags allow you to attribute costs to teams, projects, or departments, making it easier to identify high-cost areas. 

   - **Workflow and Job Analysis:** By correlating usage data with workflows and jobs, you can pinpoint longrunning or resource-heavy workloads that drive costs. 

**Focus on Long-Running Workloads:** Examine workloads with extended runtimes or high resource utilization. 

**Key Question:** Which pipelines or workloads are driving the majority of your costs? 

- **[Governance Hub](https://learn.microsoft.com/en-us/azure/databricks/admin/governance-hub/):** is a centralized, account-level UI for monitoring and managing governance across Databricks. **Note** this is a beta feature, we will update this article as we get more information and use-cases on this feature. 

### **Now That You’ve Identified Long-Running Workloads, Review These Key Areas:** 

#### **2. Review Cluster Metrics** 

- **CPU Utilization:** Track guest, iowait, idle, irq, nice, softirq, steal, system, and user times to understand how compute resources are being used. 

- **Memory Utilization:** Monitor used, free, buffer, and cached memory to identify over- or under-utilization. 



**Key Question:** Is your cluster over- or under-utilized? Are resources being wasted or stretched too thin? 

#### **3. Review SQL Warehouse Metrics** 

1. **Live Statistics:** Monitor warehouse status, running/queued queries, and current cluster count. 

2. **Time Scale Filter:** Analyze query and cluster activity over different time frames (8 hours, 24 hours, 7 days, 14 days). 

3. **Peak Query Count Chart:** Identify periods of high concurrency. 

4. **Completed Query Count Chart:** Track throughput and query success/failure rates. 

5. **Running Clusters Chart:** Observe cluster allocation and recycling events. 

6. **Query History Table:** Filter and analyze queries by user, duration, status, and statement type. 

   - **Key Question:** Is your SQL Warehouse over- or under-utilized? Are resources being wasted or stretched too thin? 

#### 4. Review Spark UI

- **Stages Tab:** Look for skewed data, high input/output, and shuffle times. Uneven task durations may indicate data skew or inefficient data handling.
- **Jobs Timeline:** Identify long-running jobs or stages that consume excessive resources.
- **Stage Analysis:** Determine if stages are I/O bound or suffering from data skew/spill.
- **Executor Metrics:** Monitor memory usage, CPU utilization, and disk I/O. Frequent garbage collection or high memory usage may signal the need for better resource allocation.

##### 4.1. Spark UI: Storage & Jobs Tab

- **Storage Level:** Check if data is stored in memory, on disk, or both.
- **Size:** Assess the size of cached data.
- **Job Analysis:** Investigate jobs that dominate the timeline or have unusually long durations. Look for gaps caused by complex execution plans, non-Spark code, driver overload, or cluster malfunction.

##### 4.2. Spark UI: Executor Tab

- **Storage Memory:** Compare used vs. available memory.
- **Task Time (Garbage Collection):** Review long tasks and garbage collection times.
- **Shuffle Read/Write:** Measure data transferred between stages.

#### 5. Additional Diagnostic Methods

- **[System Tables in Unity Catalog](https://learn.microsoft.com/en-us/azure/databricks/admin/system-tables/):**
  - Query system tables for cost attribution and resource usage trends.
    - <u>Cost Observability Queries</u>
- **Tagging Analysis:**
  - Use tags to identify which teams or projects consume the most resources.
- **Dashboards & Alerts:**
  - Set up cost dashboards and budget alerts for proactive monitoring.

## Phase 2: Cluster/Code/Data Best Practices Alignment

### Cluster UI Configuration and Cost Attribution

Effectively configuring clusters/workloads in Databricks is essential for balancing performance, scalability, and cost. Tuning settings and features strategically can help organizations maximize resource efficiency and minimize unnecessary spending.



### Key Configuration Strategies

1. **Reduce Idle Time:** Clusters continue to incur costs even when not actively processing workloads. To avoid paying for unused resources:

   - **Enable Auto-Terminate:** Set clusters to shut down automatically after a period of inactivity. This simple setting can significantly reduce wasted spending.

2. **Enable Autoscaling:** Workloads fluctuate in size and complexity. Autoscaling allows clusters to dynamically adjust the number of nodes based on demand:

   - **Automatic Resource Adjustment:** Scale up for heavy jobs and scale down for lighter loads, ensuring you only pay for what you use.



It significantly enhances cost efficiency and overall performance. For serverless and streaming, using Delta Live Tables with autoscaling is recommended. This approach leads to better resource management and reliability. 



3. **Use Spot Instances:** For batch processing and non-critical workloads, spot instances offer substantial cost savings:

   - **Lower VM Costs:** Spot instances are typically much cheaper than standard VMs. However, they are not recommended for jobs requiring constant uptime due to potential interruptions.



   - **Considerations:** Azure Spot VMs are intended for non-critical, fault-tolerant tasks. They can be evicted without notice, risking production stability. No SLA guarantees mean potential downtime for critical applications. Using Spot VMs could lead to reliability issues in production environments.

4. **Leverage Photon Engine:** Photon is Databricks’ high-performance, vectorized query engine:

   - **Accelerate Large Workloads:** Photon can dramatically reduce runtime for compute-intensive tasks, improving both speed and cost efficiency.

5. **Keep Runtimes Up to Date:** Using the latest Databricks runtime ensures optimal performance and security:

   - **Benefit from Improvements:** Regular updates include performance enhancements, bug fixes, and new features. 



6. **Apply Cluster Policies:** Cluster policies help standardize configurations and enforce cost controls across teams: 

   - **Governance and Consistency:** Policies can restrict certain settings, enforce tagging, and ensure clusters are created with cost-effective defaults. 

7. **[Optimize Storage](https://learn.microsoft.com/en-us/azure/databricks/optimizations/disk-cache#delta-cache-renamed-to-disk-cache):** Storage type impacts both performance and cost:

   - **Switch from HDDs to SSDs:** SSDs provide faster caching and shuffle operations, which can improve job efficiency and reduce runtime.



8. **Tag Clusters for Cost Attribution:** Tagging clusters enables granular tracking and reporting: 

   - **Visibility and Accountability:** Use tags to attribute costs to specific teams, projects, or environments, supporting better budgeting and chargeback processes. 

9. **Select the Right Cluster Type:** Different workloads require different cluster types, see table below for Serverless vs Classic Compute: 

| **Feature** | **Classic Compute** | **Serverless Compute** |
|---|---|---|
| **Control** | Full control over configuration and network | Minimal control; fully managed by Databricks |
| **Startup Time** | Slower (unless pre-warmed) | Instant |
| **Cost Model** | Hourly; supports reservations | Pay-per-use with elastic scaling |
| **Security** | VNet injection and private endpoints | NCC-based private connectivity |
| **Best For** | Heavy ETL, ML, and compliance workloads | Interactive queries and unpredictable demand |



10. **Choose a Compute Type for the Workload:**

    - **Job Clusters:** Ideal for scheduled jobs and Delta Live Tables.
    - **All-Purpose Clusters:** Suited for ad-hoc analysis and collaborative work.
    - **Single-Node Clusters:** Efficient for simple exploratory data analysis or pure Python tasks.
    - **Serverless Compute:** Scalable, managed workloads with automatic resource management.

11. **Monitor and Adjust Regularly:** Review cluster metrics and query history.

    - **Continuous Optimization:** Use built-in dashboards to monitor usage, identify bottlenecks, and adjust cluster size or configuration as needed.

### **Code Best Practices** 

1. **Avoid Reprocessing Large Tables** 

   - Use a CDC (Change Data Capture) architecture with Delta Live Tables (DLT) to process only new or changed data, minimizing unnecessary computation. 

2. **Ensure Code Parallelizes Well** 

Write Spark code that leverages parallel processing. Avoid loops, deeply nested structures, and inefficient userdefined functions (UDFs) that can hinder scalability. 

3. **Reduce Memory Consumption** 

Tweak Spark configurations to minimize memory overhead. Clean out legacy or unnecessary settings that may have carried over from previous Spark versions. 

4. **Prefer SQL Over Complex Python** 

Use SQL (declarative language) for Spark jobs whenever possible. SQL queries are typically more efficient and easier to optimize than complex Python logic. 

5. **Modularize Notebooks** 

Use %run to split large notebooks into smaller, reusable modules. This improves maintainability. 

6. **Use LIMIT in Exploratory Queries** 

When exploring data, always use the LIMIT clause to avoid scanning large datasets unnecessarily. 

7. **Monitor Job Performance** 

   - Regularly review Spark UI to detect inefficiencies such as high shuffle, input, or output. Review the table below for optimization opportunities:

| **High Shuffle** | **High Input** |
|---|---|
| • Use broadcast hash join to avoid data shuffling.<br>• Try shuffle hash join over sort-merge join.<br>• Leverage the cost-based optimizer to improve query plans. | • Use Delta format.<br>• Try Photon, especially for wide tables.<br>• Make the query more selective so it reads less data.<br>• Reconsider the data layout: Optimize, Z-Order, partitioning, and file-size tuning.<br>• Use data skipping and dynamic file pruning (DFP).<br>• Use Delta cache when reading the same data multiple times.<br>• For joins, consider enabling DFP. |
| **High Output** | **Long Duration & Low Shuffle/Input/Output** |
| • Optimize MERGE operations.<br>• Use deletion vectors to mark rows as removed or changed without rewriting the Parquet file.<br>• Try Photon to improve write speed. | • Reconsider the file format and data layout: Optimize, Z-Order, partitioning, and file-size tuning.<br>• Comment out UDFs and test performance. If a UDF is the bottleneck, rewrite it with native functions. |

For more guidance, review: <u>Spark stage high I/O - Azure Databricks | Microsoft Learn</u>

### Databricks Code Performance Enhancements & Data Engineering Best Practices

By enabling the below features and applying best practices, you can significantly lower costs, accelerate job execution, and build Databricks pipelines that are both scalable and highly reliable. For more guidance, review the [Comprehensive Guide to Optimize Data Workloads](https://www.databricks.com/discover/pages/optimize-data-workloads-guide#intro). 

| **Feature / Technique** | **Purpose / Benefit** | **How to Use / Enable / Key Notes** |
|---|---|---|
| **[Disk Caching](https://learn.microsoft.com/en-us/azure/databricks/optimizations/disk-cache)** | Accelerates repeated reads of Parquet files | Set `spark.databricks.io.cache.enabled = true`. |
| **[Dynamic File Pruning (DFP)](https://learn.microsoft.com/en-us/azure/databricks/optimizations/dynamic-file-pruning)** | Skips irrelevant data files during queries and improves query performance | Enabled by default in Databricks. |
| **[Low Shuffle Merge](https://learn.microsoft.com/en-us/azure/databricks/optimizations/low-shuffle-merge)** | Reduces data rewriting during MERGE operations and reduces the need to recalculate Z-Order | Use a Databricks Runtime with the feature enabled. |
| **[Adaptive Query Execution (AQE)](https://learn.microsoft.com/en-us/azure/databricks/optimizations/aqe)** | Dynamically optimizes query plans based on runtime statistics | Available in Spark 3.0+ and enabled by default. |
| **[Deletion Vectors](https://learn.microsoft.com/en-us/azure/databricks/delta/deletion-vectors)** | Removes or changes rows without rewriting the entire Parquet file | Enable in workspace settings and use with Delta Lake. |
| **[Materialized Views](https://www.databricks.com/blog/introducing-materialized-views-and-streaming-tables-databricks-sql)** | Speeds up BI queries and reduces compute for frequently accessed data | Create in Databricks SQL. |
| **[Optimize](https://learn.microsoft.com/en-us/azure/databricks/sql/language-manual/delta-optimize)** | Compacts Delta Lake files and improves query performance | Run regularly and combine with Z-Order on high-cardinality columns. |
| **ZORDER** | Physically co-locates data by selected columns for faster queries | Use with `OPTIMIZE`; select columns frequently used in filters. |
| **[Auto Optimize](https://learn.microsoft.com/en-us/azure/databricks/delta/tune-file-size#auto-optimize)** | Automatically compacts small files during writes | Enable `optimizeWrite` and `autoCompact` table properties. |
| **[Liquid Clustering](https://learn.microsoft.com/en-us/azure/databricks/delta/clustering)** | Simplifies data layout, replaces partitioning/Z-Order, and supports flexible clustering keys | Recommended for new Delta tables. |
| **[File Size Tuning](https://learn.microsoft.com/en-us/azure/databricks/delta/tune-file-size)** | Achieves optimal file size for performance and cost | Set the `delta.targetFileSize` table property. |
| **[Broadcast Hash Join](https://learn.microsoft.com/en-us/azure/databricks/sql/language-manual/sql-ref-syntax-qry-select-hints)** | Optimizes joins by broadcasting smaller tables | Adjust `spark.sql.autoBroadcastJoinThreshold` as appropriate. |
| **Shuffle Hash Join** | Provides a faster alternative to sort-merge join | Prefer over sort-merge join when broadcasting is not practical. |
| **[Cost-Based Optimizer (CBO)](https://learn.microsoft.com/en-us/azure/databricks/optimizations/cbo)** | Improves query plans for complex joins | Enabled by default; collect column and table statistics. |
| **[Data Spilling & Skew](https://learn.microsoft.com/en-us/azure/databricks/optimizations/aqe)** | Handles uneven data distribution and excessive shuffle | Use AQE and set `spark.sql.shuffle.partitions=auto`. |
| **Data Explosion Management** | Controls partition sizes after transformations such as `explode` and `join` | Adjust `spark.sql.files.maxPartitionBytes` and repartition as needed. |
| **[Delta Merge](https://learn.microsoft.com/en-us/azure/databricks/delta/merge)** | Supports efficient upserts and change data capture (CDC) | Use `MERGE` in Delta Lake and combine with low-shuffle merge. |
| **[Data Purging (Vacuum)](https://learn.microsoft.com/en-us/azure/databricks/sql/language-manual/delta-vacuum)** | Removes stale data files and maintains storage efficiency | Run `VACUUM` regularly based on transaction frequency and retention requirements. |



## Phase 3: Team Alignment and Next Steps

### Implementing Cost Observability and Taking Action

Effective cost management in Databricks goes beyond configuration and code—it requires robust observability, granular tracking, and proactive measures. Below outlines how your teams can achieve this using system tables, tagging, dashboards, and actionable scripts. 

#### 1. **Cost Observability with System Tables** 

Databricks Unity Catalog provides system tables that store operational data for your account. These tables enable historical cost observability and empower FinOps teams to analyze spend independently. 

- **System Tables Location:** Found inside Unity Catalog under the `system` schema.
- **Key Benefits:** Structured data for querying, historical analysis, and cost attribution.
- **Action:** Assign permissions to FinOps teams so they can access and analyze dedicated cost tables.



#### 2. **Enable Tags for Granular Tracking** 

Tagging is a powerful feature for tracking, reporting, and budgeting at a granular level. 

- **Classic Compute:** Manually add key/value pairs when creating clusters, jobs, SQL Warehouses, or Model Serving endpoints. Use cluster policies to enforce custom tags.
- **Serverless Compute:** Create budget policies and assign permissions to teams or members for serverless workloads.
- **Action:** Tag all compute resources to enable detailed cost attribution and reporting.

#### 3. **Track Costs with Dashboards and Alerts** 

Databricks offers prebuilt dashboards and queries for cost forecasting and usage analysis. 

- **Dashboards:** Visualize spend, usage trends, and forecast future costs.
- **Prebuilt Queries:** Use top queries with system tables to answer meaningful cost questions.
- **Budget Alerts:** Set up alerts in the Account Console (`Usage > Budget`) to receive notifications when spend approaches defined thresholds.



#### 4. **Build Culture of Efficiency** 

To go beyond technical fixes and build a culture of efficiency, by focusing on the below strategic actions: 

- **Collaborate with Internal Engineers:** Spend time with engineering teams to understand workload patterns and optimization opportunities.
- **Peer Reviews and Code Audits:** Conduct regular code review sessions and peer reviews to ensure best practices are followed for Spark jobs, data pipelines, and cluster configurations.
- **Create Internal Best Practice Documentation:** Develop clear guidelines for writing optimized code, managing data, and maintaining clusters. Make these resources easily accessible for all teams.
- **Implement Observability Dashboards:** Use Databricks’ built-in features to create dashboards that track spend, monitor resource utilization, and highlight anomalies.
- **Set Alerts and Budgets:** Configure alerts for long-running workloads and establish budgets using prebuilt Databricks capabilities to prevent cost overruns.

#### **5. Azure Reservations and Azure Savings Plan** 

When optimizing Databricks costs on Azure, it’s important to understand the two main commitment-based savings options: Azure Reservations and Azure Savings Plans. Both can help you reduce compute costs, but they differ in flexibility and how savings are applied. 

#### **<u>Which Should You Choose?</u>** 

- **Reservations** are ideal if you have stable, predictable Databricks workloads and want maximum savings. 

- **Savings Plans** are better if you expect your compute needs to change, or if you want a simpler, more flexible way to save across multiple services. 

**Pro Tip:** You can combine both options—use Reservations for your baseline, always-on Databricks clusters, and Savings Plans for bursty, variable, or new workloads. 

## **Summary Table: Action Steps** 

It’s critical to monitor costs continuously and align your teams with established best practices, while scheduling regular code review sessions to ensure efficiency and consistency. 

| **Area** | **Best Practice / Action** |
|---|---|
| **System Tables** | Use for historical cost analysis and attribution |
| **Tagging** | Apply to all compute resources for granular tracking |
| **Dashboards** | Visualize spend, usage, and forecasts |
| **Alerts** | Set budget alerts for proactive cost management |
| **Scripts/Queries** | Build custom analysis tools for deep insights |
| **Cluster/Data/Code Review & Align** | Regularly review best practices, share findings, and align teams on optimization |
| **Save on Your Usage** | Consider Azure Reservations and Azure Savings Plans |

---

*Updated September 21, 2026 · Version 3.0*
