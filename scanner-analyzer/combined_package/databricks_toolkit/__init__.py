"""
Databricks Toolkit - Unified Package for Discovery and Analysis

This package combines:
- Discovery: Workspace scanning and artifact discovery tools
- Analysis: Utilization analysis and cost optimization tools

Version: 2.0.0
"""

__version__ = "2.0.0"

# Discovery module exports
from .discovery import (
    # Main scanner components
    main_scanner,
    cluster_scanner,
    job_scanner,
    warehouse_scanner,
    pipeline_scanner,
    unity_catalog_scanner,
    workspace_objs_scanner,
    billing_scanner,
    utilization_scanner,
    # Utilities
    auth,
    config,
    utils,
)

# Analysis module exports
from .analysis import (
    ClusterUtilizationAnalyzer,
    QueryUtilizationAnalyzer,
    NetworkTrafficAnalyzer,
    RIOpportunityAnalyzer,
    WorkerNodeAnalyzer,
    SingleNodeClusterAnalyzer,
    AutoscalingAnalyzer,
    ClusterRecommendationGenerator,
    StorageReader,
    run_all_analysis,
)

__all__ = [
    # Discovery exports
    "main_scanner",
    "cluster_scanner",
    "job_scanner",
    "warehouse_scanner",
    "pipeline_scanner",
    "unity_catalog_scanner",
    "workspace_objs_scanner",
    "billing_scanner",
    "utilization_scanner",
    "auth",
    "config",
    "utils",
    # Analysis exports
    "ClusterUtilizationAnalyzer",
    "QueryUtilizationAnalyzer",
    "NetworkTrafficAnalyzer",
    "RIOpportunityAnalyzer",
    "WorkerNodeAnalyzer",
    "SingleNodeClusterAnalyzer",
    "AutoscalingAnalyzer",
    "ClusterRecommendationGenerator",
    "StorageReader",
    "run_all_analysis",
]
