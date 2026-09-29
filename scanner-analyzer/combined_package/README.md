# Databricks Toolkit

**Version 2.0.0** - Unified package combining workspace discovery and utilization analysis

A comprehensive Python toolkit for Databricks workspace management, combining:
- **Discovery Module**: Workspace scanning and artifact discovery
- **Analysis Module**: Utilization analysis and cost optimization

## Features

### 🔍 Discovery Module (formerly dbx-discovery)

Comprehensive workspace scanning capabilities:
- **Cluster Discovery**: All cluster types, configurations, and policies
- **Job Discovery**: Workflows, tasks, schedules, and dependencies
- **SQL Warehouse Discovery**: Endpoints, configurations, and usage
- **Pipeline Discovery**: Delta Live Tables pipelines and configurations
- **Unity Catalog**: Catalogs, schemas, tables, volumes, and permissions
- **Workspace Objects**: Notebooks, libraries, repos, and secrets
- **Billing Analysis**: Usage logs and cost tracking
- **Utilization Metrics**: Real-time cluster and query metrics

### 📊 Analysis Module (formerly dbx-analysis)

Advanced utilization analysis tools:
- **Cluster Utilization Analysis**: CPU, memory, network metrics with intelligent categorization
- **Query Performance Analysis**: SQL query costs, performance, and optimization opportunities
- **Network Traffic Analysis**: Identify network-intensive workloads
- **RI Opportunity Analysis**: Reserved Instance purchase recommendations
- **Worker Node Analysis**: Configuration analysis and optimization
- **Single-Node Detection**: Identify underutilized single-node clusters
- **Autoscaling Analysis**: Optimization recommendations for autoscaling configs
- **Comprehensive Recommendations**: Detailed cluster sizing and configuration guidance

## Installation

### Basic Installation

```bash
pip install databricks_toolkit-2.0.0-py3-none-any.whl
```

### With All Features

```bash
pip install databricks_toolkit-2.0.0-py3-none-any.whl[all]
```

### In Databricks Notebook

```python
%pip install /dbfs/FileStore/wheels/databricks_toolkit-2.0.0-py3-none-any.whl
```

## Quick Start

### Discovery: Scan Workspace

```python
from databricks_toolkit.discovery import WorkspaceDiscoveryScanner, ScanConfig

# Configure scan
config = ScanConfig(
    workspace_url="https://{WS_ID}.azuredatabricks.net",
    token="your-token-here",
    output_path="/dbfs/FileStore/discovery"
)

# Run scan
scanner = WorkspaceDiscoveryScanner(config)
results = scanner.scan_all()
```

### Analysis: Cluster Utilization

```python
from databricks_toolkit.analysis import ClusterUtilizationAnalyzer

# Analyze cluster utilization
analyzer = ClusterUtilizationAnalyzer(
    input_path="/dbfs/FileStore/discovery/cluster",
    output_dir="/dbfs/FileStore/reports"
)

# Run analysis with custom output file
results = analyzer.analyze(
    save_excel=True,
    output_file="/dbfs/FileStore/reports/cluster_analysis_nov_2024.xlsx"
)

print(f"Total clusters: {results['total_clusters']}")
print(f"Categories: {results['categories']}")
```

### Analysis: Query Performance

```python
from databricks_toolkit.analysis import QueryUtilizationAnalyzer

analyzer = QueryUtilizationAnalyzer(
    input_path="/dbfs/FileStore/discovery/query",
    output_dir="/dbfs/FileStore/reports"
)

results = analyzer.analyze()
print(f"Total queries: {results['total_queries']}")
print(f"Failed queries: {results['failed_queries']}")
print(f"Total DBU cost: ${results['total_dbu_cost']:.2f}")
```

### Complete Workflow: Discovery → Analysis

```python
from databricks_toolkit.discovery import WorkspaceDiscoveryScanner, ScanConfig
from databricks_toolkit.analysis import run_all_analysis

# Step 1: Discover and collect utilization data
config = ScanConfig(
    workspace_url="https://adb-xxx.azuredatabricks.net",
    token="dapi...",
    output_path="/dbfs/discovery"
)

scanner = WorkspaceDiscoveryScanner(config)
scanner.scan_utilization()  # Collect utilization metrics

# Step 2: Analyze the collected data
results = run_all_analysis(
    cluster_input_path="/dbfs/discovery/cluster",
    query_input_path="/dbfs/discovery/query",
    output_dir="/dbfs/reports"
)

print(f"✅ Discovery and analysis complete!")
print(f"Cluster report: {results['cluster_analysis']['output_file']}")
print(f"Query report: {results['query_analysis']['output_file']}")
```

## Module Structure

```
databricks_toolkit/
├── __init__.py                 # Main package exports
├── discovery/                  # Discovery module
│   ├── __init__.py
│   ├── main_scanner.py        # Orchestrator
│   ├── cluster_scanner.py     # Cluster discovery
│   ├── job_scanner.py         # Job discovery
│   ├── warehouse_scanner.py   # SQL Warehouse discovery
│   ├── pipeline_scanner.py    # DLT pipeline discovery
│   ├── unity_catalog_scanner.py  # UC metadata
│   ├── workspace_objs_scanner.py # Workspace objects
│   ├── billing_scanner.py     # Billing data
│   ├── utilization_scanner.py # Metrics collection
│   ├── auth.py                # Authentication
│   ├── config.py              # Configuration
│   └── utils.py               # Utilities
└── analysis/                   # Analysis module
    ├── __init__.py
    ├── analyzer.py            # Core analyzers
    ├── additional_analyzers.py  # Network & RI
    ├── specialized_analyzers.py # Worker node, autoscaling, recommendations
    └── storage_utils.py       # Storage integration
```

## Key Capabilities

### Discovery Module

**What it does:**
- Connects to Databricks workspace via REST API
- Enumerates all workspace artifacts and configurations
- Collects metadata, settings, and relationships
- Gathers real-time utilization metrics
- Exports data to JSON/CSV for analysis

**Use cases:**
- Workspace inventory and documentation
- Migration planning and assessment
- Compliance and governance auditing
- Cost allocation and chargeback
- Capacity planning

### Analysis Module

**What it does:**
- Processes utilization data from discovery
- Applies intelligent categorization algorithms
- Identifies optimization opportunities
- Generates actionable recommendations
- Creates comprehensive Excel reports

**Use cases:**
- Cost optimization analysis
- Right-sizing recommendations
- Reserved Instance planning
- Performance troubleshooting
- Utilization trending

## Advanced Examples

### All 8 Analyzers

```python
from databricks_toolkit.analysis import (
    ClusterUtilizationAnalyzer,
    QueryUtilizationAnalyzer,
    NetworkTrafficAnalyzer,
    RIOpportunityAnalyzer,
    WorkerNodeAnalyzer,
    SingleNodeClusterAnalyzer,
    AutoscalingAnalyzer,
    ClusterRecommendationGenerator
)

# 1. Cluster Utilization
cluster_analyzer = ClusterUtilizationAnalyzer(
    input_path="/dbfs/data/cluster",
    output_dir="/dbfs/reports"
)
cluster_results = cluster_analyzer.analyze(
    output_file="/dbfs/reports/cluster_utilization.xlsx"
)

# 2. Query Performance
query_analyzer = QueryUtilizationAnalyzer(
    input_path="/dbfs/data/query",
    output_dir="/dbfs/reports"
)
query_results = query_analyzer.analyze(
    output_file="/dbfs/reports/query_performance.xlsx"
)

# 3. Network Traffic
network_analyzer = NetworkTrafficAnalyzer(
    input_path="/dbfs/data/cluster",
    output_dir="/dbfs/reports"
)
network_results = network_analyzer.analyze(
    output_file="/dbfs/reports/network_traffic.xlsx"
)

# 4. RI Opportunities
# Note: RI Analyzer requires Cluster_Analysis_Consolidated*.xlsx file
# which contains cluster categorization in "All Clusters" sheet
ri_analyzer = RIOpportunityAnalyzer(
    input_path="/dbfs/reports/Cluster_Analysis_Consolidated_20240101.xlsx",
    output_dir="/dbfs/reports"
)
ri_results = ri_analyzer.analyze(
    node_type="Standard_E16a_v4",  # Or use analyze_all_types=True
    output_file="/dbfs/reports/ri_opportunities.xlsx"
)

# 5. Worker Node Analysis
worker_analyzer = WorkerNodeAnalyzer(
    input_path="/dbfs/data/cluster",
    output_dir="/dbfs/reports"
)
worker_results = worker_analyzer.analyze(
    output_file="/dbfs/reports/worker_nodes.xlsx"
)

# 6. Single-Node Detection
single_node_analyzer = SingleNodeClusterAnalyzer(
    input_path="/dbfs/data/cluster",
    output_dir="/dbfs/reports"
)
single_results = single_node_analyzer.analyze(
    output_file="/dbfs/reports/single_node_clusters.xlsx"
)

# 7. Autoscaling Analysis
autoscaling_analyzer = AutoscalingAnalyzer(
    input_path="/dbfs/data/cluster",
    output_dir="/dbfs/reports"
)
autoscaling_results = autoscaling_analyzer.analyze(
    output_file="/dbfs/reports/autoscaling_analysis.xlsx"
)

# 8. Comprehensive Recommendations
recommendation_generator = ClusterRecommendationGenerator(
    input_path="/dbfs/data/cluster",
    output_dir="/dbfs/reports"
)
recommendation_results = recommendation_generator.analyze(
    output_file="/dbfs/reports/cluster_recommendations.xlsx"
)
```

## Dependencies

### Core (Required)
- pandas >= 1.5.0
- numpy >= 1.23.0
- openpyxl >= 3.0.0

### Optional
- **Azure Storage**: azure-storage-blob >= 12.19.0, azure-identity >= 1.15.0
- **Databricks SDK**: databricks-sdk >= 0.12.0 (for discovery)

## Version History

- **v2.0.0** (Current): Unified package combining discovery and analysis
  - Combined dbx-discovery v1.0.0 and dbx-analysis v1.3.0
  - Unified namespace: `databricks_toolkit`
  - Single installation for all capabilities
  
- **v1.3.0** (Analysis): Added configurable output file paths
- **v1.2.0** (Analysis): Added 4 specialized analyzers
- **v1.1.0** (Analysis): Added network traffic and RI analyzers
- **v1.0.0** (Analysis/Discovery): Initial releases

## License

MIT License

## Support

For issues, questions, or contributions, please contact the Databricks Toolkit team.
