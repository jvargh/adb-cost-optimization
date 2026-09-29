"""
Discovery Module - Databricks Workspace Scanner

A modular tool for discovering and analyzing Databricks workspace artifacts including:
- Clusters, Jobs, Warehouses, Pipelines
- Unity Catalog metadata
- Workspace objects
- Billing and utilization metrics
"""

__version__ = "1.0.0"
__author__ = "Amit Damle, RK Iyer"

from .cli import main
from .config import ScanConfig
from .main_scanner import WorkspaceDiscoveryScanner

__all__ = ['main', 'ScanConfig', 'WorkspaceDiscoveryScanner']
