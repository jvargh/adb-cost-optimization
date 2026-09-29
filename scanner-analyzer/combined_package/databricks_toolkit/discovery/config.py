"""
Configuration module for Databricks Workspace Scanner.
Manages scan configuration and settings.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScanConfig:
    """
    Configuration for workspace scanning operations.
    
    Attributes:
        scan_type: Type of scan - 'simple' or 'deep'
        workspace_urls: List of workspace URLs to scan
        account_id: Optional account ID for account-level security scanning (encryption keys, networks, VPC endpoints)
                   For Azure: uses DefaultAzureCredential (Azure CLI, Managed Identity, Environment Variables)
        max_workers: Maximum number of worker threads (default: 2)
        output_file: Path to save output JSON file  
        log_level: Logging level (default: INFO)
        billing_details: Whether to include billing information (Y/N)
        billing_days: Number of days for billing analysis (1-365, default: 1)
        utilization_days: Number of days for utilization analysis in deep scans (1-365, default: 30)
        export_format: Format for utilization exports - 'json' or 'csv' (default: json)
        batch_size: Batch size for API requests (default: 50)
        request_timeout: Request timeout in seconds (default: 30)
    """
    
    scan_type: str = 'simple'
    workspace_urls: List[str] = None
    account_id: Optional[str] = None  # Account ID for account-level security scanning
    max_workers: int = 6  # Increased from 2 for better parallelism
    output_file: Optional[str] = None
    log_level: str = 'INFO'
    billing_details: str = 'N'
    billing_days: int = 1
    utilization_days: int = 30
    export_format: str = 'json'
    batch_size: int = 50
    request_timeout: int = 30
    collect_size_metrics: bool = False  # Enable size metrics collection for Unity Catalog
    uc_scan: str = 'partial'  # Unity Catalog scan mode: 'partial' (tables only) or 'complete' (catalogs, schemas, tables)
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        # Validate scan type
        if self.scan_type not in ['simple', 'deep']:
            raise ValueError(f"Invalid scan_type: {self.scan_type}. Must be 'simple' or 'deep'")
        
        # Validate workspace URLs
        if not self.workspace_urls or len(self.workspace_urls) == 0:
            raise ValueError("At least one workspace URL must be provided")
        
        # Validate max_workers
        if self.max_workers < 1 or self.max_workers > 10:
            raise ValueError(f"max_workers must be between 1 and 10, got {self.max_workers}")
        
        # Validate billing details
        if self.billing_details not in ['Y', 'N', 'y', 'n']:
            raise ValueError(f"billing_details must be Y or N, got {self.billing_details}")
        
        # Validate billing days
        if self.billing_days < 1 or self.billing_days > 365:
            raise ValueError(f"billing_days must be between 1 and 365, got {self.billing_days}")
        
        # Validate utilization days
        if self.utilization_days < 1 or self.utilization_days > 365:
            raise ValueError(f"utilization_days must be between 1 and 365, got {self.utilization_days}")
        
        # Validate export format
        if self.export_format.lower() not in ['json', 'csv']:
            raise ValueError(f"export_format must be 'json' or 'csv', got {self.export_format}")
        
        # Validate uc_scan mode
        if self.uc_scan.lower() not in ['partial', 'complete']:
            raise ValueError(f"uc_scan must be 'partial' or 'complete', got {self.uc_scan}")
        
        # Validate log level
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}, got {self.log_level}")
        
        # Normalize values
        self.scan_type = self.scan_type.lower()
        self.log_level = self.log_level.upper()
        self.billing_details = self.billing_details.upper()
        self.export_format = self.export_format.lower()
        self.uc_scan = self.uc_scan.lower()
    
    def is_deep_scan(self) -> bool:
        """Check if this is a deep scan."""
        return self.scan_type == 'deep'
    
    def is_billing_enabled(self) -> bool:
        """Check if billing details collection is enabled."""
        return self.billing_details == 'Y'
    
    def is_uc_complete_scan(self) -> bool:
        """Check if Unity Catalog complete scan is enabled (catalogs, schemas, tables)."""
        return self.uc_scan == 'complete'
    
    def is_uc_partial_scan(self) -> bool:
        """Check if Unity Catalog partial scan is enabled (tables only)."""
        return self.uc_scan == 'partial'
    
    def get_numeric_log_level(self) -> int:
        """Get numeric logging level."""
        levels = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        return levels.get(self.log_level, logging.INFO)
