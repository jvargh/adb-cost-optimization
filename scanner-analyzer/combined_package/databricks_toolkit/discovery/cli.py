"""
Command Line Interface for Databricks Workspace Discovery Scanner.
Entry point for the scanner tool.
"""

import sys
import logging
import argparse
from typing import List

from .config import ScanConfig
from .main_scanner import WorkspaceDiscoveryScanner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def parse_workspace_urls(urls_string: str) -> List[str]:
    """
    Parse comma-separated workspace URLs.
    
    Args:
        urls_string: Comma-separated list of workspace URLs
        
    Returns:
        List of workspace URLs
    """
    urls = [url.strip() for url in urls_string.split(',')]
    return [url for url in urls if url]  # Filter out empty strings


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Databricks Workspace Discovery Scanner - Discover and analyze workspace artifacts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simple scan of a single workspace
  python -m dbx_discovery --scan-type simple --workspace-url https://adb-123.azuredatabricks.net
  
  # Simple scan with account-level security scanning enabled
  python -m dbx_discovery --scan-type simple --workspace-url https://adb-123.azuredatabricks.net --account-id 12345678-1234-1234-1234-123456789012
  
  # Deep scan with utilization metrics exported as CSV (last 60 days)
  python -m dbx_discovery --scan-type deep --workspace-url https://adb-123.azuredatabricks.net --export-format csv --utilization-days 60
  
  # Deep scan with billing for 7 days (simple scan only)
  python -m dbx_discovery --scan-type simple --workspace-url https://adb-123.azuredatabricks.net --billing-details Y --billing-days 7
  
  # Scan multiple workspaces
  python -m dbx_discovery --scan-type simple --workspace-url "https://adb-123.azuredatabricks.net,https://adb-456.azuredatabricks.net"
  
  # Specify output directory
  python -m dbx_discovery --scan-type simple --workspace-url https://adb-123.azuredatabricks.net --output-file ./results/scan.json

Deep Scan Features:
  - Excludes billing data from artifact JSONs
  - Executes cluster utilization and SQL query usage analysis using serverless warehouse
  - Configurable analysis period (1-90 days, default 30)
  - Exports utilization data as JSON (auto-split if >10MB) or CSV format
  - Provides detailed metadata for all artifacts including run history, configurations, and dependencies

Requirements:
  - Databricks SDK authentication configured (Azure CLI, environment variables, or Databricks config)
  - Appropriate permissions to access workspace resources
  - For billing: access to system.billing.usage table and SQL warehouse (simple scan only)
  - For utilization: access to system.compute.node_timeline and system.query.history tables (deep scan only)
        """
    )
    
    # Required arguments
    parser.add_argument(
        '--scan-type',
        required=True,
        choices=['simple', 'deep'],
        default='simple',
        help='Type of scan: simple (basic metadata) or deep (detailed analysis including run history)'
    )
    
    parser.add_argument(
        '--workspace-url',
        required=True,
        help='Comma-separated list of Databricks workspace URLs to scan (e.g., "https://adb-123.azuredatabricks.net,https://adb-456.azuredatabricks.net")'
    )
    
    # Optional arguments
    parser.add_argument(
        '--account-id',
        default=None,
        help='Databricks account ID for account-level security scanning (encryption keys, VPC networks, VPC endpoints). If not provided, account-level scans will be skipped. For Azure, ensure authentication via: az login, Managed Identity, or Environment Variables (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID).'
    )
    
    parser.add_argument(
        '--max-workers',
        type=int,
        default=2,
        help='Maximum number of parallel worker threads (default: 2, range: 1-10)'
    )
    
    parser.add_argument(
        '--output-file',
        default=None,
        help='Path to save output JSON file (default: ./out/<workspace_id>_<timestamp>.json)'
    )
    
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--billing-details',
        default='N',
        choices=['Y', 'N', 'y', 'n'],
        help='Include billing information (Y/N, default: N)'
    )
    
    parser.add_argument(
        '--billing-days',
        type=int,
        default=1,
        help='Number of days for billing analysis (default: 1, range: 1-365)'
    )
    
    parser.add_argument(
        '--utilization-days',
        type=int,
        default=30,
        help='Number of days for utilization analysis in deep scans (default: 30, range: 1-365)'
    )
    
    parser.add_argument(
        '--export-format',
        default='json',
        choices=['json', 'csv'],
        help='Export format for utilization data in deep scans (default: json). JSON files >10MB will be automatically split.'
    )
    
    parser.add_argument(
        '--collect-size-metrics',
        action='store_true',
        default=False,
        help='Collect size metrics for Unity Catalog tables (WARNING: slow for many tables, runs in parallel batches of 3)'
    )
    
    return parser.parse_args()


def main():
    """Main entry point for the scanner."""
    try:
        # Parse arguments
        args = parse_arguments()
        
        # Set logging level
        numeric_level = getattr(logging, args.log_level.upper(), None)
        logging.getLogger().setLevel(numeric_level)
        
        # Parse workspace URLs
        workspace_urls = parse_workspace_urls(args.workspace_url)
        
        if not workspace_urls:
            logger.error("At least one workspace URL must be provided")
            sys.exit(1)
        
        logger.info(f"{'='*80}")
        logger.info("Databricks Workspace Discovery Scanner")
        logger.info(f"{'='*80}")
        logger.info(f"Scan Type: {args.scan_type}")
        logger.info(f"Workspaces to scan: {len(workspace_urls)}")
        for idx, url in enumerate(workspace_urls, 1):
            logger.info(f"  {idx}. {url}")
        logger.info(f"Max Workers: {args.max_workers}")
        if args.account_id:
            logger.info(f"Account ID: {args.account_id} (account-level security scanning enabled)")
            logger.info("Azure account-level authentication: Using Default Credentials (Azure CLI, Managed Identity, or Environment Variables)")
        else:
            logger.info(f"Account ID: Not provided (account-level security scanning disabled)")
        if args.scan_type == 'deep':
            logger.info(f"Utilization Export Format: {args.export_format}")
            logger.info(f"Utilization Analysis Period: {args.utilization_days} days")
            logger.info(f"Collect Size Metrics: {args.collect_size_metrics}")
        logger.info(f"Billing Details: {args.billing_details}")
        if args.billing_details.upper() == 'Y':
            logger.info(f"Billing Days: {args.billing_days}")
        logger.info(f"{'='*80}\n")
        
        # Create configuration
        config = ScanConfig(
            scan_type=args.scan_type,
            workspace_urls=workspace_urls,
            account_id=args.account_id,
            max_workers=args.max_workers,
            output_file=args.output_file,
            log_level=args.log_level,
            billing_details=args.billing_details,
            billing_days=args.billing_days,
            utilization_days=args.utilization_days,
            export_format=args.export_format,
            collect_size_metrics=args.collect_size_metrics
        )
        
        # Create and run scanner
        scanner = WorkspaceDiscoveryScanner(config)
        results = scanner.scan_workspaces()
        
        # Print summary
        logger.info(f"\n{'='*80}")
        logger.info("SCAN SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"Total workspaces scanned: {len(results['workspaces'])}")
        logger.info(f"Total duration: {results['scan_metadata']['total_duration_seconds']:.2f} seconds")
        
        for idx, workspace in enumerate(results['workspaces'], 1):
            logger.info(f"\nWorkspace {idx}: {workspace['workspace_id']}")
            logger.info(f"  Duration: {workspace.get('scan_duration_seconds', 0):.2f} seconds")
            
            artifacts = workspace.get('artifacts', {})
            if 'jobs' in artifacts and isinstance(artifacts['jobs'], list):
                logger.info(f"  Jobs: {len(artifacts['jobs'])}")
            if 'clusters' in artifacts and isinstance(artifacts['clusters'], list):
                logger.info(f"  Clusters: {len(artifacts['clusters'])}")
            if 'warehouses' in artifacts and isinstance(artifacts['warehouses'], list):
                logger.info(f"  Warehouses: {len(artifacts['warehouses'])}")
            
            # Billing summary
            if 'billing' in artifacts and not artifacts['billing'].get('error'):
                billing = artifacts['billing']
                total_usage = billing.get('total_usage', {})
                logger.info(f"  Billing: ${total_usage.get('estimated_cost_usd', 0):.2f} "
                          f"({total_usage.get('total_dbus', 0):.2f} DBUs)")
            
            # Errors
            errors = workspace.get('errors', [])
            if errors:
                logger.warning(f"  Errors: {len(errors)}")
                for error in errors:
                    logger.warning(f"    - {error}")
        
        logger.info(f"\n{'='*80}")
        logger.info("✓ Scan completed successfully")
        logger.info(f"{'='*80}")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("\n\nScan interrupted by user")
        return 1
        
    except Exception as e:
        logger.error(f"\n\nFatal error: {str(e)}")
        import traceback
        logger.debug(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
