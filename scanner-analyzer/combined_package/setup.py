"""
Setup configuration for databricks-toolkit unified package.
Combines discovery (scanning) and analysis capabilities into one package.
"""

from setuptools import setup, find_packages
import os

# Read long description
long_description = ""
readme_path = os.path.join(os.path.dirname(__file__), "README.md")
if os.path.exists(readme_path):
    with open(readme_path, "r", encoding="utf-8") as f:
        long_description = f.read()
else:
    long_description = """
# Databricks Toolkit

A unified Python package for Databricks workspace discovery and utilization analysis.

## Features

### Discovery Module
- Comprehensive workspace scanning (clusters, jobs, warehouses, pipelines)
- Unity Catalog metadata discovery
- Workspace object enumeration
- Billing and usage collection
- Utilization metrics gathering

### Analysis Module  
- Cluster utilization analysis with intelligent categorization
- SQL query performance and cost analysis
- Network traffic pattern detection
- Reserved Instance opportunity identification
- Worker node configuration analysis
- Single-node cluster detection
- Autoscaling optimization recommendations
- Comprehensive cluster sizing recommendations

## Quick Start

```python
# Discovery: Scan workspace
from databricks_toolkit.discovery import WorkspaceDiscoveryScanner

scanner = WorkspaceDiscoveryScanner(workspace_url, token)
results = scanner.scan_all()

# Analysis: Analyze utilization
from databricks_toolkit.analysis import ClusterUtilizationAnalyzer

analyzer = ClusterUtilizationAnalyzer(input_path="data/", output_dir="results/")
results = analyzer.analyze()
```
"""

setup(
    name="databricks-toolkit",
    version="2.0.2",
    author="Databricks Toolkit Team",
    author_email="toolkit@example.com",
    description="Unified toolkit for Databricks workspace discovery and utilization analysis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/databricks-toolkit",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Systems Administration",
        "Topic :: System :: Monitoring",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    
    # Core dependencies (minimal for Databricks compatibility)
    install_requires=[
        "pandas>=1.5.0",
        "numpy>=1.20.0,<2.0",  # Compatible with Databricks runtime (contourpy, pyarrow, scipy)
        "openpyxl>=3.0.0",
    ],
    
    # Optional dependencies
    extras_require={
        "azure": [
            "azure-storage-blob>=12.19.0",
            "azure-identity>=1.15.0",
        ],
        "databricks": [
            "databricks-sdk>=0.12.0",
        ],
        "all": [
            "azure-storage-blob>=12.19.0",
            "azure-identity>=1.15.0",
            "databricks-sdk>=0.12.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
    },
    
    # Entry points for CLI
    entry_points={
        "console_scripts": [
            "databricks-toolkit=databricks_toolkit.discovery.cli:main",
            "dbx-discovery=databricks_toolkit.discovery.cli:main",
        ],
    },
    
    # Include non-Python files
    package_data={
        'databricks_toolkit.analysis': ['security_checks_metadata.json'],
    },
    
    include_package_data=True,
    zip_safe=False,
)
