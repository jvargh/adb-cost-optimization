"""
Main Scanner Orchestrator for Databricks Workspace Discovery.
Coordinates all scanning operations with parallel processing.
"""

import logging
import time
import os
import concurrent.futures
from typing import Dict, List, Any
from datetime import datetime

from .auth import AuthManager
from .job_scanner import JobScanner
from .cluster_scanner import ClusterScanner
from .warehouse_scanner import WarehouseScanner
from .workspace_objs_scanner import WorkspaceObjectsScanner
from .unity_catalog_scanner import UnityCatalogScanner
from .billing_scanner import BillingScanner
from .pipeline_scanner import PipelineScanner
from .utilization_scanner import UtilizationScanner
from .security_scanner import SecurityScanner
from .utils import save_json, save_csv, extract_workspace_id, get_timestamp

logger = logging.getLogger(__name__)


class WorkspaceDiscoveryScanner:
    """
    Main orchestrator for Databricks workspace discovery.
    Manages parallel scanning of multiple workspaces and artifacts.
    """
    
    def __init__(self, config):
        """
        Initialize the workspace discovery scanner.
        
        Args:
            config: ScanConfig object with scan parameters
        """
        self.config = config
        self.auth_manager = AuthManager()
        self.results = {}
    
    def scan_workspaces(self) -> Dict[str, Any]:
        """
        Scan all configured workspaces.
        
        Returns:
            Dictionary containing all scan results
        """
        logger.info(f"Starting workspace discovery scan for {len(self.config.workspace_urls)} workspace(s)")
        start_time = time.time()
        
        all_results = {
            'scan_metadata': {
                'scan_type': self.config.scan_type,
                'start_time': get_timestamp(),
                'max_workers': self.config.max_workers,
                'billing_enabled': self.config.is_billing_enabled(),
                'billing_days': self.config.billing_days if self.config.is_billing_enabled() else 0,
                'export_format': self.config.export_format,
            },
            'workspaces': []
        }
        
        # Scan each workspace
        for workspace_url in self.config.workspace_urls:
            logger.info(f"\n{'='*80}\nScanning workspace: {workspace_url}\n{'='*80}")
            
            workspace_result = self._scan_single_workspace(workspace_url)
            all_results['workspaces'].append(workspace_result)
        
        # Calculate total duration
        total_duration = time.time() - start_time
        all_results['scan_metadata']['end_time'] = get_timestamp()
        all_results['scan_metadata']['total_duration_seconds'] = round(total_duration, 2)
        
        logger.info(f"\n{'='*80}\nScan completed in {total_duration:.2f} seconds\n{'='*80}")
        
        # Save results
        self._save_results(all_results)
        
        return all_results
    
    def _scan_single_workspace(self, workspace_url: str) -> Dict[str, Any]:
        """Scan a single workspace with tiered execution strategy for optimized performance."""
        workspace_id = extract_workspace_id(workspace_url)
        start_time = time.time()
        
        workspace_result = {
            'workspace_url': workspace_url,
            'workspace_id': workspace_id,
            'scan_start_time': get_timestamp(),
            'artifacts': {},
            'errors': [],
            'phase_timings': {}
        }
        
        try:
            # Authenticate to workspace
            logger.info(f"Authenticating to workspace...")
            client = self.auth_manager.get_client(workspace_url)
            
            # Verify connection
            if not self.auth_manager.verify_connection(client):
                workspace_result['errors'].append("Failed to verify connection")
                return workspace_result
            
            # Initialize all scanners
            all_scanners = {
                'jobs': JobScanner(client, self.config),
                'clusters': ClusterScanner(client, self.config),
                'warehouses': WarehouseScanner(client, self.config),
                'workspace_objects': WorkspaceObjectsScanner(client, self.config),
                'unity_catalog': UnityCatalogScanner(client, self.config),
                'pipelines': PipelineScanner(client, self.config),
                'security': SecurityScanner(client, self.config, account_id=self.config.account_id),
            }
            
            # Add billing scanner if enabled (only for simple scans)
            # For deep scans, billing is excluded - use utilization scanner instead
            billing_enabled = self.config.is_billing_enabled() and not self.config.is_deep_scan()
            if billing_enabled:
                all_scanners['billing'] = BillingScanner(client, self.config)
            
            # Define 2-tier scan groups for optimized execution
            # TIER 1 (Fast): Lightweight to moderate operations - high concurrency
            tier1_fast_scanners = {
                'warehouses': all_scanners['warehouses'],
                'pipelines': all_scanners['pipelines'],
                'clusters': all_scanners['clusters'],
                'security': all_scanners['security'],
            }
            logger.info(f"DEBUG: Tier 1 scanners configured: {list(tier1_fast_scanners.keys())}")
            logger.info(f"DEBUG: Security scanner included in Tier 1: {'security' in tier1_fast_scanners}")
            
            # TIER 2 (Slow): Resource-intensive operations - controlled concurrency
            tier2_slow_scanners = {
                'workspace_objects': all_scanners['workspace_objects'],
                'jobs': all_scanners['jobs'],
                'unity_catalog': all_scanners['unity_catalog'],
            }
            
            # Add billing to appropriate tier if enabled
            if billing_enabled:
                tier2_slow_scanners['billing'] = all_scanners['billing']
            
            total_scanners = len(tier1_fast_scanners) + len(tier2_slow_scanners)
            completed_scanners = 0
            
            logger.info(f"\n{'='*80}\nExecuting {total_scanners} scanners in 2 optimized tiers\n{'='*80}")
            
            # TIER 1: Fast scanners with high concurrency (warehouses, pipelines, clusters)
            if tier1_fast_scanners:
                phase_start = time.time()
                logger.info(f"\n🚀 TIER 1 (FAST): Executing {len(tier1_fast_scanners)} fast scanners with high concurrency")
                logger.info(f"   Concurrency: {self.config.max_workers * 2} workers (capped at 12) | Timeout: 10 minutes")
                results = self._execute_scanner_group(
                    tier1_fast_scanners,
                    max_workers=min(self.config.max_workers * 2, 12),  # 2x concurrency, cap at 12
                    timeout=600  # 10 minute timeout
                )
                workspace_result['artifacts'].update(results['artifacts'])
                workspace_result['errors'].extend(results['errors'])
                completed_scanners += len(tier1_fast_scanners)
                phase_duration = time.time() - phase_start
                workspace_result['phase_timings']['tier1_fast'] = round(phase_duration, 2)
                logger.info(f"✓ Tier 1 completed in {phase_duration:.2f}s ({completed_scanners}/{total_scanners})")
            
            # TIER 2: Slow scanners with controlled concurrency (workspace_objects, jobs, unity_catalog, billing)
            if tier2_slow_scanners:
                phase_start = time.time()
                logger.info(f"\n🐢 TIER 2 (SLOW): Executing {len(tier2_slow_scanners)} slow scanners with controlled concurrency")
                logger.info(f"   Concurrency: {max(2, self.config.max_workers // 2)} workers | Timeout: 30 minutes")
                results = self._execute_scanner_group(
                    tier2_slow_scanners,
                    max_workers=max(2, self.config.max_workers // 2),  # 1/2 concurrency, minimum 2
                    timeout=1800  # 30 minute timeout
                )
                workspace_result['artifacts'].update(results['artifacts'])
                workspace_result['errors'].extend(results['errors'])
                completed_scanners += len(tier2_slow_scanners)
                phase_duration = time.time() - phase_start
                workspace_result['phase_timings']['tier2_slow'] = round(phase_duration, 2)
                logger.info(f"✓ Tier 2 completed in {phase_duration:.2f}s ({completed_scanners}/{total_scanners})")
            
            # TIER 3: Utilization scanner for deep scans only (runs after all others)
            if self.config.is_deep_scan():
                phase_start = time.time()
                logger.info(f"\n📊 TIER 3 (UTILIZATION): Running utilization analysis for deep scan")
                logger.info(f"   Concurrency: 1 worker (sequential) | Timeout: 10 minutes")
                try:
                    utilization_scanner = UtilizationScanner(client, self.config)
                    utilization_result = utilization_scanner.scan(workspace_id)
                    workspace_result['artifacts']['utilization'] = utilization_result
                    phase_duration = time.time() - phase_start
                    workspace_result['phase_timings']['tier3_utilization'] = round(phase_duration, 2)
                    logger.info(f"✓ Tier 3 (utilization) completed in {phase_duration:.2f}s")
                except Exception as e:
                    error_msg = f"Utilization scan failed: {str(e)}"
                    logger.error(f"✗ {error_msg}")
                    workspace_result['errors'].append(error_msg)
            
            # Calculate scan duration
            scan_duration = time.time() - start_time
            workspace_result['scan_duration_seconds'] = round(scan_duration, 2)
            workspace_result['scan_end_time'] = get_timestamp()
            
            # Log tier performance summary
            logger.info(f"\n{'='*80}\nTier Performance Summary:\n{'='*80}")
            for tier_name, tier_time in workspace_result['phase_timings'].items():
                logger.info(f"  {tier_name}: {tier_time:.2f}s")
            logger.info(f"\n{'='*80}\nWorkspace scan completed in {scan_duration:.2f} seconds\n{'='*80}")
            
        except Exception as e:
            error_msg = f"Error scanning workspace: {str(e)}"
            logger.error(error_msg)
            workspace_result['errors'].append(error_msg)
        
        return workspace_result
    
    def _execute_scanner_group(self, scanners: Dict[str, Any], max_workers: int, timeout: int) -> Dict[str, Any]:
        """
        Execute a group of scanners with specified concurrency and timeout.
        
        Args:
            scanners: Dictionary of scanner_name -> scanner_instance
            max_workers: Maximum concurrent workers for this group
            timeout: Timeout in seconds for each scanner
        
        Returns:
            Dictionary with 'artifacts' and 'errors' keys
        """
        results = {
            'artifacts': {},
            'errors': []
        }
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all scanners in the group
            future_to_scanner = {
                executor.submit(scanner.scan): name
                for name, scanner in scanners.items()
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_scanner):
                scanner_name = future_to_scanner[future]
                try:
                    result = future.result(timeout=timeout)
                    results['artifacts'][scanner_name] = result
                    if scanner_name == 'security':
                        logger.info(f"  ✓ DEBUG: Security scan completed! Result type: {type(result)}, Keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
                    logger.info(f"  ✓ Completed {scanner_name} scan")
                except concurrent.futures.TimeoutError:
                    error_msg = f"{scanner_name} scan timed out after {timeout}s"
                    logger.error(f"  ✗ {error_msg}")
                    results['errors'].append(error_msg)
                except Exception as e:
                    error_msg = f"{scanner_name} scan failed: {str(e)}"
                    logger.error(f"  ✗ {error_msg}")
                    results['errors'].append(error_msg)
        
        return results
    
    def _save_results(self, results: Dict[str, Any]):
        """
        Save scan results to files (JSON or CSV based on export_format).
        Creates individual files for each artifact type.
        Does NOT create a consolidated file - only individual artifact files.
        """
        try:
            logger.info(f"\n{'='*80}\nSaving individual artifact files (format: {self.config.export_format})...\n{'='*80}")
            
            # Save individual artifact files for each workspace
            for workspace in results.get('workspaces', []):
                ws_id = workspace.get('workspace_id', 'unknown')
                artifacts = workspace.get('artifacts', {})
                
                # Create metadata to include with each artifact file
                artifact_metadata = {
                    'workspace_url': workspace.get('workspace_url'),
                    'workspace_id': ws_id,
                    'scan_time': workspace.get('scan_start_time'),
                    'scan_type': results['scan_metadata']['scan_type'],
                    'scan_duration_seconds': workspace.get('scan_duration_seconds')
                }
                
                is_csv = self.config.export_format.lower() == 'csv'
                
                # Save jobs
                if 'jobs' in artifacts:
                    if is_csv:
                        jobs_list = artifacts['jobs'].get('jobs', []) if isinstance(artifacts['jobs'], dict) else artifacts['jobs']
                        job_scanner = JobScanner(None, self.config)
                        flattened = job_scanner.flatten_for_csv(jobs_list)
                        save_csv(flattened, self.config.output_file, f"{ws_id}_jobs", artifact_type="jobs")
                        logger.info(f"  ✓ Jobs CSV saved to jobs/csv/ ({len(flattened)} rows)")
                    else:
                        save_json({'metadata': artifact_metadata, 'jobs': artifacts['jobs']}, 
                                 self.config.output_file, f"{ws_id}_jobs", artifact_type="jobs")
                        logger.info(f"  ✓ Jobs JSON saved to jobs/json/")
                
                # Save clusters
                if 'clusters' in artifacts:
                    if is_csv:
                        cluster_scanner = ClusterScanner(None, self.config)
                        flattened = cluster_scanner.flatten_for_csv(artifacts['clusters'])
                        save_csv(flattened, self.config.output_file, f"{ws_id}_clusters", artifact_type="clusters")
                        logger.info(f"  ✓ Clusters CSV saved to clusters/csv/ ({len(flattened)} rows)")
                    else:
                        save_json({'metadata': artifact_metadata, 'clusters': artifacts['clusters']}, 
                                 self.config.output_file, f"{ws_id}_clusters", artifact_type="clusters")
                        logger.info(f"  ✓ Clusters JSON saved to clusters/json/")
                
                # Save warehouses
                if 'warehouses' in artifacts:
                    if is_csv:
                        warehouse_scanner = WarehouseScanner(None, self.config)
                        flattened = warehouse_scanner.flatten_for_csv(artifacts['warehouses'])
                        save_csv(flattened, self.config.output_file, f"{ws_id}_warehouses", artifact_type="warehouses")
                        logger.info(f"  ✓ Warehouses CSV saved to warehouses/csv/ ({len(flattened)} rows)")
                    else:
                        save_json({'metadata': artifact_metadata, 'warehouses': artifacts['warehouses']}, 
                                 self.config.output_file, f"{ws_id}_warehouses", artifact_type="warehouses")
                        logger.info(f"  ✓ Warehouses JSON saved to warehouses/json/")
                
                # Save pipelines
                if 'pipelines' in artifacts:
                    if is_csv:
                        pipeline_scanner = PipelineScanner(None, self.config)
                        flattened = pipeline_scanner.flatten_for_csv(artifacts['pipelines'])
                        save_csv(flattened, self.config.output_file, f"{ws_id}_pipelines", artifact_type="pipelines")
                        logger.info(f"  ✓ Pipelines CSV saved to pipelines/csv/ ({len(flattened)} rows)")
                    else:
                        save_json({'metadata': artifact_metadata, 'pipelines': artifacts['pipelines']}, 
                                 self.config.output_file, f"{ws_id}_pipelines", artifact_type="pipelines")
                        logger.info(f"  ✓ Pipelines JSON saved to pipelines/json/")
                
                # Save Unity Catalog
                if 'unity_catalog' in artifacts:
                    if is_csv:
                        uc_scanner = UnityCatalogScanner(None, self.config)
                        flattened = uc_scanner.flatten_for_csv(artifacts['unity_catalog'])
                        save_csv(flattened, self.config.output_file, f"{ws_id}_unity_catalog", artifact_type="unity_catalog")
                        logger.info(f"  ✓ Unity Catalog CSV saved to unity_catalog/csv/ ({len(flattened)} rows)")
                    else:
                        save_json({'metadata': artifact_metadata, 'unity_catalog': artifacts['unity_catalog']}, 
                                 self.config.output_file, f"{ws_id}_unity_catalog", artifact_type="unity_catalog")
                        logger.info(f"  ✓ Unity Catalog JSON saved to unity_catalog/json/")
                
                # Save workspace objects (multiple CSV files in CSV mode)
                if 'workspace_objects' in artifacts:
                    if is_csv:
                        ws_obj_scanner = WorkspaceObjectsScanner(None, self.config)
                        flattened_dict = ws_obj_scanner.flatten_for_csv(artifacts['workspace_objects'])
                        
                        # Map object types to their folder names
                        object_type_folders = {
                            'repos': 'workspace_objects/repos',
                            'experiments': 'workspace_objects/experiments',
                            'serving_endpoints': 'workspace_objects/serving',
                            'alerts': 'workspace_objects/alerts',
                            'genie_spaces': 'workspace_objects/genie',
                            'notebooks': 'workspace_objects/notebooks'
                        }
                        
                        # Save each object type in its own subfolder
                        for obj_type, rows in flattened_dict.items():
                            if rows:  # Only save non-empty CSVs
                                folder_name = object_type_folders.get(obj_type, f'workspace_objects/{obj_type}')
                                save_csv(rows, self.config.output_file, f"{ws_id}_workspace_objects_{obj_type}", artifact_type=folder_name)
                                logger.info(f"  ✓ Workspace {obj_type} CSV saved to {folder_name}/csv/ ({len(rows)} rows)")
                    else:
                        save_json({'metadata': artifact_metadata, 'workspace_objects': artifacts['workspace_objects']}, 
                                 self.config.output_file, f"{ws_id}_workspace_objects", artifact_type="workspace_objects")
                        logger.info(f"  ✓ Workspace objects JSON saved to workspace_objects/json/")
                
                # Save billing (3 CSV files in CSV mode)
                if 'billing' in artifacts and not artifacts['billing'].get('error'):
                    if is_csv:
                        billing_scanner = BillingScanner(None, self.config)
                        flattened_dict = billing_scanner.flatten_for_csv(artifacts['billing'])
                        
                        # Save each billing breakdown as separate CSV in billing/csv/ folder
                        for breakdown_type, rows in flattened_dict.items():
                            if rows:  # Only save non-empty CSVs
                                save_csv(rows, self.config.output_file, f"{ws_id}_billing_{breakdown_type}", artifact_type="billing")
                                logger.info(f"  ✓ Billing {breakdown_type} CSV saved to billing/csv/ ({len(rows)} rows)")
                    else:
                        save_json({'metadata': artifact_metadata, 'billing': artifacts['billing']}, 
                                 self.config.output_file, f"{ws_id}_billing", artifact_type="billing")
                        logger.info(f"  ✓ Billing JSON saved to billing/json/")
                
                # Save security
                logger.info(f"DEBUG: Checking for 'security' in artifacts. Keys present: {list(artifacts.keys())}")
                if 'security' in artifacts:
                    logger.info(f"DEBUG: Security data found! Preparing to save. Format: {'CSV' if is_csv else 'JSON'}")
                    if is_csv:
                        security_scanner = SecurityScanner(None, self.config, account_id=self.config.account_id)
                        flattened = security_scanner.flatten_for_csv(artifacts['security'])
                        logger.info(f"DEBUG: Flattened {len(flattened)} rows for CSV export")
                        save_csv(flattened, self.config.output_file, f"{ws_id}_security", artifact_type="security")
                        logger.info(f"  ✓ Security CSV saved to security/csv/ ({len(flattened)} rows)")
                    else:
                        logger.info(f"DEBUG: Saving security JSON with {len(artifacts['security'])} keys")
                        save_json({'metadata': artifact_metadata, 'security': artifacts['security']}, 
                                 self.config.output_file, f"{ws_id}_security", artifact_type="security")
                        logger.info(f"  ✓ Security JSON saved to security/json/")
                else:
                    logger.warning(f"DEBUG: Security data NOT found in artifacts! Cannot save security scan results.")
                
                # Utilization data is already saved by the utilization scanner
                if 'utilization' in artifacts:
                    util_result = artifacts['utilization']
                    if not util_result.get('skipped'):
                        cluster_files = util_result.get('cluster_utilization', {}).get('files', [])
                        sql_files = util_result.get('sql_query_usage', {}).get('files', [])
                        
                        for filepath in cluster_files:
                            logger.info(f"  ✓ Cluster utilization saved: {os.path.basename(filepath)}")
                        for filepath in sql_files:
                            logger.info(f"  ✓ SQL query usage saved: {os.path.basename(filepath)}")
            
            logger.info(f"\n{'='*80}\nAll artifact files saved successfully\n{'='*80}")
            
        except Exception as e:
            logger.error(f"Failed to save results: {str(e)}")
