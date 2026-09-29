**Databricks workspaces**

**Summary**

| Recommendation | Impact | Category | Automation Available | In Azure Advisor |
|----|----|----|----|----|
| [Databricks runtime version is not latest or is not LTS version](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#databricks-runtime-version-is-not-latest-or-is-not-lts-version) | Medium | Other Best Practices | No | No |
| [Use SSD backed VMs for Worker VM Type and Driver type](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#use-ssd-backed-vms-for-worker-vm-type-and-driver-type) | Medium | Scalability | No | No |
| [Enable autoscaling for batch workloads](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#enable-autoscaling-for-batch-workloads) | High | Scalability | No | No |
| [Enable autoscaling for SQL warehouse](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#enable-autoscaling-for-sql-warehouse) | High | Scalability | No | No |
| [Use Delta Live Tables enhanced autoscaling](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#use-delta-live-tables-enhanced-autoscaling) | Medium | Scalability | No | No |
| [Automatic Job Termination is enabled, ensure there are no user-defined local processes](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#automatic-job-termination-is-enabled-ensure-there-are-no-user-defined-local-processes) | Medium | High Availability | No | No |
| [Enable Logging-Cluster log delivery](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#enable-logging-cluster-log-delivery) | Medium | Monitoring and Alerting | No | No |
| [Use Delta Lake for higher reliability](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#use-delta-lake-for-higher-reliability) | High | High Availability | No | No |
| [Automatically rescue invalid or nonconforming data with Databricks Auto Loader or Delta Live Tables](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#automatically-rescue-invalid-or-nonconforming-data-with-databricks-auto-loader-or-delta-live-tables) | Low | Business Continuity | No | No |
| [Configure jobs for automatic retries and termination](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#configure-jobs-for-automatic-retries-and-termination) | High | High Availability | No | No |
| [Use a scalable and production-grade model serving infrastructure](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#use-a-scalable-and-production-grade-model-serving-infrastructure) | High | Scalability | No | No |
| [Use a layered storage architecture](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#use-a-layered-storage-architecture) | Medium | High Availability | No | No |
| [Improve data integrity by reducing data redundancy](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#improve-data-integrity-by-reducing-data-redundancy) | Low | Business Continuity | No | No |
| [Actively manage schemas](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#actively-manage-schemas) | Medium | Other Best Practices | No | No |
| [Use constraints and data expectations](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#use-constraints-and-data-expectations) | Low | Business Continuity | No | No |
| [Create regular backups](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#create-regular-backups) | Low | Disaster Recovery | No | No |
| [Recover from Structured Streaming query failures](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#recover-from-structured-streaming-query-failures) | High | High Availability | No | No |
| [Recover ETL jobs based on Delta time travel](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#recover-etl-jobs-based-on-delta-time-travel) | Medium | Disaster Recovery | No | No |
| [Use Databricks Workflows and built-in recovery](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#use-databricks-workflows-and-built-in-recovery) | Low | Disaster Recovery | No | No |
| [Configure a disaster recovery pattern](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#configure-a-disaster-recovery-pattern) | High | Disaster Recovery | No | No |
| [Automate deployments and workloads](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#automate-deployments-and-workloads) | High | Other Best Practices | No | No |
| [Set up monitoring, alerting, and logging](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#set-up-monitoring-alerting-and-logging) | High | Monitoring and Alerting | No | No |
| [Deploy workspaces in separate Subscriptions](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#deploy-workspaces-in-separate-subscriptions) | High | Scalability | No | No |
| [Isolate each workspace in its own VNet](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#isolate-each-workspace-in-its-own-vnet) | High | Scalability | No | No |
| [Do not Store any Production Data in Default DBFS Folders](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#do-not-store-any-production-data-in-default-dbfs-folders) | High | High Availability | No | No |
| [Do not use Azure Spot VMs for critical Production workloads](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#do-not-use-azure-spot-vms-for-critical-production-workloads) | High | High Availability | No | No |
| [Evaluate regional isolation for workspaces](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#evaluate-regional-isolation-for-workspaces) | High | High Availability | No | No |
| [Define alternate VM SKUs](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#define-alternate-vm-skus) | Medium | Personalized | No | No |
| [Use managed services where possible](https://azure.github.io/Azure-Proactive-Resiliency-Library-v2/azure-resources/Databricks/workspaces/#use-managed-services-where-possible) | High | Scalability | No | No |

**Details**

------------------------------------------------------------------------

**Databricks runtime version is not latest or is not LTS version**

**Impact: **Medium**Category: **Other Best Practices

**APRL GUID: **0e835cc2-2551-a247-b1f1-3c5f25c9cb70

**Advisor GUID: **n/a

**Description:**

Databricks recommends migrating workloads to the latest or LTS version
of its runtime for enhanced stability and support. If on Runtime 11.3
LTS or above, move directly to the latest 12.x version. If below, first
migrate to 11.3 LTS, then to the latest 12.x version as per the
migration guide.

**Potential Benefits:**

Enhanced stability and support

**Learn More:**

| [Databricks runtime support lifecycles](https://learn.microsoft.com/azure/databricks/release-notes/runtime/databricks-runtime-ver) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Use SSD backed VMs for Worker VM Type and Driver type**

**Impact: **Medium**Category: **Scalability

**APRL GUID: **5877a510-8444-7a4c-8412-a8dab8662f7e

**Advisor GUID: **n/a

**Description:**

Upgrade HDDs in premium VMs to SSDs for better speed and reliability.
Premium SSDs boost IO-heavy apps; Standard SSDs balance cost and
performance. Ideal for critical workloads, upgrading improves
connectivity with brief reboot. Consider for vital VMs

**Potential Benefits:**

Faster, reliable VM performance

**Learn More:**

| [Azure managed disk types](https://learn.microsoft.com/azure/virtual-machines/disks-types#premium-ssd) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Enable autoscaling for batch workloads**

**Impact: **High**Category: **Scalability

**APRL GUID: **5c72f0d6-55ec-d941-be84-36c194fa78c0

**Advisor GUID: **n/a

**Description:**

Autoscaling adjusts cluster sizes automatically based on workload
demands, offering benefits for many use cases in terms of costs and
performance. It includes guidance on when and how to best utilize
Autoscaling. For streaming, Delta Live Tables with autoscaling is
advised.

**Potential Benefits:**

Cost and performance optimization

**Learn More:**

| [Best practices for reliability](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/reliability/best-practices#enable-autoscaling-for-batch-workloadss) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Enable autoscaling for SQL warehouse**

**Impact: **High**Category: **Scalability

**APRL GUID: **362ad2b6-b92c-414f-980a-0cf69467ccce

**Advisor GUID: **n/a

**Description:**

The scaling parameter of a SQL warehouse defines the min and max number
of clusters for distributing queries. By default, it's set to one.
Increasing the cluster count can accommodate more concurrent users
effectively.

**Potential Benefits:**

Improves concurrency and efficiency

**Learn More:**

| [Best practices for reliability](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/reliability/best-practices#enable-autoscaling-for-sql-warehouse) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Use Delta Live Tables enhanced autoscaling**

**Impact: **Medium**Category: **Scalability

**APRL GUID: **cd77db98-9b13-6e4b-bd2b-74c2cb538628

**Advisor GUID: **n/a

**Description:**

Databricks enhanced autoscaling optimizes cluster utilization by
automatically allocating cluster resources based on workload volume,
with minimal impact on the data processing latency of your pipelines.

**Potential Benefits:**

Optimized resource use and minimal latency

**Learn More:**

| [Databricks enhanced autoscaling](https://learn.microsoft.com/azure/databricks/delta-live-tables/settings#use-autoscaling-to-increase-efficiency-and-reduce-resource-usage) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Automatic Job Termination is enabled, ensure there are no user-defined
local processes**

**Impact: **Medium**Category: **High Availability

**APRL GUID: **3d3e53b5-ebd1-db42-b43b-d4fad74824ec

**Advisor GUID: **n/a

**Description:**

To conserve cluster resources, you can terminate a cluster to store its
configuration for future reuse or autostart jobs. Clusters can
auto-terminate after inactivity, but this only tracks Spark jobs, not
local processes, which might still be running even after Spark jobs end.

**Potential Benefits:**

Saves cluster resources, avoids idle use

**Learn More:**

| [Best practices for reliability](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/reliability/best-practices) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Enable Logging-Cluster log delivery**

**Impact: **Medium**Category: **Monitoring and Alerting

**APRL GUID: **7fb90127-5364-bb4d-86fa-30778ed713fb

**Advisor GUID: **n/a

**Description:**

When creating a Databricks cluster, you can set a log delivery location
for the Spark driver, worker nodes, and events. Logs are delivered every
5 mins and archived hourly. Upon cluster termination, all generated logs
until that point are guaranteed to be delivered.

**Potential Benefits:**

Improved troubleshooting and audit

**Learn More:**

| [Create a cluster](https://learn.microsoft.com/azure/databricks/clusters/configure#cluster-log-delivery) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Use Delta Lake for higher reliability**

**Impact: **High**Category: **High Availability

**APRL GUID: **da4ea916-4df3-8c4d-8060-17b49da45977

**Advisor GUID: **n/a

**Description:**

Delta Lake is an open source storage format enhancing data lakes'
reliability with ACID transactions, schema enforcement, and scalable
metadata handling.

**Potential Benefits:**

Enhances data reliability and processing

**Learn More:**

| [Best practices for reliability](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/reliability/best-practices) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Automatically rescue invalid or nonconforming data with Databricks
Auto Loader or Delta Live Tables**

**Impact: **Low**Category: **Business Continuity

**APRL GUID: **7e52d64d-8cc0-8548-a593-eb49ab45630d

**Advisor GUID: **n/a

**Description:**

Invalid or nonconforming data can crash workloads dependent on specific
data formats. Best practices recommend filtering such data at ingestion
to improve end-to-end resilience, ensuring no data is lost or missed.

**Potential Benefits:**

Enhanced data resilience and integrity

**Learn More:**

| [Best practices for reliability](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/reliability/best-practices) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Configure jobs for automatic retries and termination**

**Impact: **High**Category: **High Availability

**APRL GUID: **84e44da6-8cd7-b349-b02c-c8bf72cf587c

**Advisor GUID: **n/a

**Description:**

Use Databricks and MLflow for deploying models as Spark UDFs for job
scheduling, retries, autoscaling. Model serving offers scalable
infrastructure, processes models using MLflow, and serves them via REST
API using serverless compute managed in Databricks cloud.

**Potential Benefits:**

Enhanced reliability and autoscaling

**Learn More:**

| [Best practices for reliability](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/reliability/best-practices) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Use a scalable and production-grade model serving infrastructure**

**Impact: **High**Category: **Scalability

**APRL GUID: **4cbb7744-ff3d-0447-badb-baf068c95696

**Advisor GUID: **n/a

**Description:**

Use Databricks and MLflow for deploying models as Apache Spark UDFs,
benefiting from job scheduling, retries, autoscaling, etc.

**Potential Benefits:**

Enhances scalability and reliability

**Learn More:**

| [Best practices for reliability](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/reliability/best-practices) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Use a layered storage architecture**

**Impact: **Medium**Category: **High Availability

**APRL GUID: **1b0d0893-bf0e-8f4c-9dc6-f18f145c1ecf

**Advisor GUID: **n/a

**Description:**

Curate data by creating a layered architecture to increase data quality
across layers. Start with a raw layer for ingested source data, continue
with a curated layer for cleansed and refined data, and finish with a
final layer catered to business needs, focusing on security and
performance.

**Potential Benefits:**

Enhances data quality and trust

**Learn More:**

| [Best practices for reliability](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/reliability/best-practices) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Improve data integrity by reducing data redundancy**

**Impact: **Low**Category: **Business Continuity

**APRL GUID: **e93fe702-e385-d741-ba37-1f1656482ecd

**Advisor GUID: **n/a

**Description:**

Copying data leads to redundancy, lost integrity, lineage, and access
issues, affecting lakehouse data quality. Temporary copies are useful
for agility and innovation but can become problematic operational data
silos, questioning data's master status and currency.

**Potential Benefits:**

Enhanced data integrity and quality

**Learn More:**

| [Best practices for reliability](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/reliability/best-practices) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Actively manage schemas**

**Impact: **Medium**Category: **Other Best Practices

**APRL GUID: **b7e1d13f-54c9-1648-8a52-34c0abe8ce16

**Advisor GUID: **n/a

**Description:**

Uncontrolled schema changes can lead to invalid data and failing jobs.
Databricks validates and enforces schema through Delta Lake, which
prevents bad records during ingestion, and Auto Loader, which detects
new columns and supports schema evolution to maintain data integrity.

**Potential Benefits:**

Prevents invalid data and job failures

**Learn More:**

| [Best practices for reliability](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/reliability/best-practices) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Use constraints and data expectations**

**Impact: **Low**Category: **Business Continuity

**APRL GUID: **a42297c4-7e4f-8b41-8d4b-114033263f0e

**Advisor GUID: **n/a

**Description:**

Delta tables verify data quality automatically with SQL constraints,
triggering an error for violations. Delta Live Tables enhance this by
defining expectations for data quality, utilizing Python or SQL, to
manage actions for record failures, ensuring data integrity and
compliance.

**Potential Benefits:**

Ensures data quality and integrity

**Learn More:**

| [Best practices for reliability](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/reliability/best-practices#use-constraints-and-data-expectations) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Create regular backups**

**Impact: **Low**Category: **Disaster Recovery

**APRL GUID: **932d45d6-b46d-e341-abfb-d97bce832f1f

**Advisor GUID: **n/a

**Description:**

To recover from a failure, regular backups are needed. The Databricks
Labs project migrate lets admins create backups by exporting workspace
assets using the Databricks CLI/API. These backups help in restoring or
migrating workspaces.

**Potential Benefits:**

Ensures data recovery and migration

**Learn More:**

| [Best practices for reliability](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/reliability/best-practices#create-regular-backups) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Recover from Structured Streaming query failures**

**Impact: **High**Category: **High Availability

**APRL GUID: **12e9d852-5cdc-2743-bffe-ee21f2ef7781

**Advisor GUID: **n/a

**Description:**

Structured Streaming ensures fault-tolerance and data consistency in
streaming queries. With Azure Databricks workflows, you can set up your
queries to automatically restart after failure, picking up precisely
where they left off.

**Potential Benefits:**

Fault-tolerance and auto-restart for queries

**Learn More:**

| [Best practices for reliability](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/reliability/best-practices#recover-from-structured-streaming-query-failures) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Recover ETL jobs based on Delta time travel**

**Impact: **Medium**Category: **Disaster Recovery

**APRL GUID: **a18d60f8-c98c-ba4e-ad6e-2fac72879df1

**Advisor GUID: **n/a

**Description:**

Despite thorough testing, a production job can fail or yield unexpected
data. Sometimes, repairs are done by adding jobs post-issue
identification and pipeline correction.

**Potential Benefits:**

Easy rollback and fix for ETL jobs

**Learn More:**

| [Best practices for reliability](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/reliability/best-practices#recover-etl-jobs-based-on-delta-time-travel) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Use Databricks Workflows and built-in recovery**

**Impact: **Low**Category: **Disaster Recovery

**APRL GUID: **c0e22580-3819-444d-8546-a80e4ed85c83

**Advisor GUID: **n/a

**Description:**

Databricks Workflows enable efficient error recovery in multi-task jobs
by offering a matrix view for issue examination. Fixes can be applied to
initiate repair runs targeting only failed and dependent tasks,
preserving successful outcomes and thereby saving time and money.

**Potential Benefits:**

Saves time and money with smart recovery

**Learn More:**

| [Best practices for reliability](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/reliability/best-practices) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Configure a disaster recovery pattern**

**Impact: **High**Category: **Disaster Recovery

**APRL GUID: **4fdb7112-4531-6f48-b60e-c917a6068d9b

**Advisor GUID: **n/a

**Description:**

Implementing a disaster recovery pattern is vital for Azure Databricks,
ensuring data teams' access even during rare regional outages.

It is important to note that the Azure Databricks service is not
entirely zone redudant and does support zonal failover.

**Potential Benefits:**

Ensures service continuity during disasters

**Learn More:**

| [Azure Databricks Best Practices](https://github.com/Azure/AzureDatabricksBestPractices/tree/master) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Automate deployments and workloads**

**Impact: **High**Category: **Other Best Practices

**APRL GUID: **42aedaa8-6151-424d-b782-b8666c779969

**Advisor GUID: **n/a

**Description:**

The Databricks Terraform provider manages Azure Databricks workspaces
and cloud infrastructure flexibly and powerfully.

**Potential Benefits:**

Efficient, reliable automation

**Learn More:**

| [Best practices for operational excellence](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/operational-excellence/best-practices#2-automate-deployments-and-workloads) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Set up monitoring, alerting, and logging**

**Impact: **High**Category: **Monitoring and Alerting

**APRL GUID: **20193ff9-dbcd-a74e-b197-71d7d9d3c1e6

**Advisor GUID: **n/a

**Description:**

The Databricks Terraform provider is a flexible, powerful tool for
managing Azure Databricks workspaces and cloud infrastructure.

**Potential Benefits:**

Enhanced reliability and automation

**Learn More:**

| [Best practices for operational excellence](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/operational-excellence/best-practices#system-monitoring) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Deploy workspaces in separate Subscriptions**

**Impact: **High**Category: **Scalability

**APRL GUID: **397cdebb-9d6e-ab4f-83a1-8c481de0a3a7

**Advisor GUID: **n/a

**Description:**

Customers often naturally divide workspaces by teams or departments.
However, it's crucial to also consider Azure Subscription and Azure
Databricks (ADB) Workspace limits when partitioning.

**Potential Benefits:**

Enhanced limits management, team separation

**Learn More:**

| [Azure Databricks Best Practices](https://github.com/Azure/AzureDatabricksBestPractices/blob/master/toc.md#deploy-workspaces-in-multiple-subscriptions-to-honor-azure-capacity-limits) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Isolate each workspace in its own VNet**

**Impact: **High**Category: **Scalability

**APRL GUID: **5e722c4f-415a-9b4c-bd4c-96b74dce29ad

**Advisor GUID: **n/a

**Description:**

Deploying only one Databricks Workspace per VNet aligns with Azure
Databricks' isolation model.

**Potential Benefits:**

Enhanced security and resource isolation

**Learn More:**

| [Azure Databricks Best Practices](https://github.com/Azure/AzureDatabricksBestPractices/blob/master/toc.md#consider-isolating-each-workspace-in-its-own-vnet) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Do not Store any Production Data in Default DBFS Folders**

**Impact: **High**Category: **High Availability

**APRL GUID: **14310ba6-77ad-3641-a2db-57a2218b9bc7

**Advisor GUID: **n/a

**Description:**

Driven by security and data availability concerns, each Azure Databricks
Workspace comes with a default DBFS designed for system-level artifacts
like libraries and Init scripts, not for production data.

**Potential Benefits:**

Enhanced security, data protection

**Learn More:**

| [Azure Databricks Best Practices](https://github.com/Azure/AzureDatabricksBestPractices/blob/master/toc.md#do-not-store-any-production-data-in-default-dbfs-folders) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Do not use Azure Spot VMs for critical Production workloads**

**Impact: **High**Category: **High Availability

**APRL GUID: **b5af7e26-3939-1b48-8fba-f8d4a475c67a

**Advisor GUID: **n/a

**Description:**

Azure Spot VMs are not suitable for critical production workloads
needing high availability and reliability. They are meant for
fault-tolerant tasks and can be evicted with 30-seconds notice if Azure
needs the capacity, with no SLA guarantees.

**Potential Benefits:**

Ensures high reliability for production

**Learn More:**

| [Use Azure Spot Virtual Machines](https://learn.microsoft.com/azure/virtual-machines/spot-vms) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Evaluate regional isolation for workspaces**

**Impact: **High**Category: **High Availability

**APRL GUID: **8aa63c34-dd9d-49bd-9582-21ec310dfbdd

**Advisor GUID: **n/a

**Description:**

Move workspaces to in-region control plane for increased regional
isolation. Identify current control plane region using the workspace URL
and nslookup. When region from CNAME differs from workspace region and
an in-region control is available, consider migration using tools
provided below.

**Potential Benefits:**

Improves resilience and data sovereignty

**Learn More:**

| [Azure Databricks control plane addresses](https://learn.microsoft.com/azure/databricks/resources/supported-regions#--azure-databricks-control-plane-addresses) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Define alternate VM SKUs**

**Impact: **Medium**Category: **Personalized

**APRL GUID: **028593be-956e-4736-bccf-074cb10b92f4

**Advisor GUID: **n/a

**Description:**

Azure Databricks planning should include VM SKU swap strategies for
capacity issues. VMs are regional, and allocation failures may occur,
shown by a "CLOUD PROVIDER" error.

**Potential Benefits:**

Ensures service availability

**Learn More:**

| [Compute configuration best practices](https://learn.microsoft.com/azure/databricks/compute/cluster-config-best-practices) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph

------------------------------------------------------------------------

**Use managed services where possible**

**Impact: **High**Category: **Scalability

**APRL GUID: **e94da1f8-33e7-48a6-b301-72f19a53bc29

**Advisor GUID: **n/a

**Description:**

Where possible Leverage managed services (serverless compute) from the
Databricks Data Intelligence Platform, such as:serverless SQL
warehouses, model serving, serverless jobs, serverless compute for
notebooks.

**Potential Benefits:**

Improve resiliency and scalability at no additional cost

**Learn More:**

| [Best practices for reliability](https://learn.microsoft.com/azure/databricks/lakehouse-architecture/reliability/best-practices#use-managed-services-where-possible) |
|----|

**ARG Query:**

**Click the Azure Resource Graph tab to view the query**

Azure Resource Graph
