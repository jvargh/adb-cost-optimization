"""
Workspace Objects Scanner Module for Databricks Workspace Discovery.
Scans repos, experiments, genie spaces, serving endpoints, and alerts.
Note: Pipelines are scanned separately by pipeline_scanner.py
"""

import logging
from typing import Dict, List, Any
from databricks.sdk import WorkspaceClient
from .utils import safe_get_attribute

logger = logging.getLogger(__name__)


class WorkspaceObjectsScanner:
    """
    Scanner for various Databricks workspace objects.
    Consolidates scanning of repos, experiments, serving endpoints, alerts, and genie spaces.
    """
    
    def __init__(self, client: WorkspaceClient, config):
        """
        Initialize workspace objects scanner.
        
        Args:
            client: Authenticated Databricks WorkspaceClient
            config: Scan configuration object
        """
        self.client = client
        self.config = config
    
    def scan(self) -> Dict[str, Any]:
        """
        Scan all workspace objects.
        
        For simple scan: Returns summary with object counts and basic object info
        For deep scan: Returns detailed object configurations
        
        Returns:
            Dictionary containing all workspace objects organized by type
        """
        logger.info("Starting workspace objects scan...")
        
        repos = self.scan_repos()
        experiments = self.scan_experiments()
        serving_endpoints = self.scan_serving_endpoints()
        alerts = self.scan_alerts()
        genie_spaces = self.scan_genie_spaces()
        notebooks = self.scan_notebooks()
        
        results = {
            'repos': repos,
            'experiments': experiments,
            'serving_endpoints': serving_endpoints,
            'alerts': alerts,
            'genie_spaces': genie_spaces,
            'notebooks': notebooks,
        }
        
        # For simple scan, add summary block
        if not self.config.is_deep_scan():
            results['summary'] = {
                'total_repos': len(repos),
                'total_experiments': len(experiments),
                'total_serving_endpoints': len(serving_endpoints),
                'total_alerts': len(alerts),
                'total_genie_spaces': len(genie_spaces),
                'total_notebooks': len(notebooks)
            }
        
        # Move summary to the top for simple scan
        if not self.config.is_deep_scan():
            results = {'summary': results.pop('summary'), **results}
        
        logger.info("Completed workspace objects scan")
        return results
    
    def scan_repos(self) -> List[Dict[str, Any]]:
        """Scan Git repositories in the workspace."""
        logger.info("Scanning repos...")
        
        try:
            repos = list(self.client.repos.list())
            logger.info(f"Found {len(repos)} repos")
            
            repos_data = []
            for repo in repos:
                repo_info = {
                    'repo_id': repo.id,
                    'path': repo.path,
                    'url': repo.url,
                    'provider': repo.provider,
                    'branch': repo.branch,
                    'head_commit_id': repo.head_commit_id,
                }
                repos_data.append(repo_info)
            
            return repos_data
            
        except Exception as e:
            logger.error(f"Error scanning repos: {str(e)}")
            return []
    
    def scan_experiments(self) -> List[Dict[str, Any]]:
        """Scan MLflow experiments in the workspace."""
        logger.info("Scanning experiments...")
        
        try:
            experiments = list(self.client.experiments.list_experiments())
            logger.info(f"Found {len(experiments)} experiments")
            
            experiments_data = []
            for exp in experiments:
                exp_info = {
                    'experiment_id': exp.experiment_id,
                    'name': exp.name,
                    'artifact_location': exp.artifact_location,
                    'lifecycle_stage': exp.lifecycle_stage,
                    'creation_time': getattr(exp, 'creation_time', None),
                    'last_update_time': getattr(exp, 'last_update_time', None),
                }
                experiments_data.append(exp_info)
            
            return experiments_data
            
        except Exception as e:
            logger.error(f"Error scanning experiments: {str(e)}")
            return []
    
    def scan_serving_endpoints(self) -> List[Dict[str, Any]]:
        """Scan model serving endpoints in the workspace."""
        logger.info("Scanning serving endpoints...")
        
        try:
            endpoints = list(self.client.serving_endpoints.list())
            logger.info(f"Found {len(endpoints)} serving endpoints")
            
            endpoints_data = []
            for endpoint in endpoints:
                endpoint_info = {
                    'endpoint_name': endpoint.name,
                    'creator': endpoint.creator,
                    'creation_timestamp': getattr(endpoint, 'creation_timestamp', None),
                    'last_updated_timestamp': getattr(endpoint, 'last_updated_timestamp', None),
                    'state': safe_get_attribute(endpoint, 'state.config_update.value'),
                }
                endpoints_data.append(endpoint_info)
            
            return endpoints_data
            
        except Exception as e:
            logger.error(f"Error scanning serving endpoints: {str(e)}")
            return []
    
    def scan_alerts(self) -> List[Dict[str, Any]]:
        """Scan SQL alerts in the workspace."""
        logger.info("Scanning alerts...")
        
        try:
            alerts = list(self.client.alerts.list())
            logger.info(f"Found {len(alerts)} alerts")
            
            alerts_data = []
            for alert in alerts:
                alert_info = {
                    'alert_id': alert.id,
                    'display_name': getattr(alert, 'display_name', None),
                    'query_id': getattr(alert, 'query_id', None),
                    'owner_user_name': getattr(alert, 'owner_user_name', None),
                    'state': safe_get_attribute(alert, 'state.value'),
                }
                
                # Add schedule if available
                if hasattr(alert, 'schedule') and alert.schedule:
                    alert_info['schedule'] = {
                        'cron_expression': safe_get_attribute(alert.schedule, 'quartz_cron_expression'),
                        'timezone_id': safe_get_attribute(alert.schedule, 'timezone_id'),
                    }
                
                alerts_data.append(alert_info)
            
            return alerts_data
            
        except Exception as e:
            logger.error(f"Error scanning alerts: {str(e)}")
            return []
    
    def scan_genie_spaces(self) -> List[Dict[str, Any]]:
        """Scan Genie spaces in the workspace using REST API."""
        logger.info("Scanning Genie spaces...")
        
        try:
            # Use the Databricks REST API directly
            # GET /api/2.0/genie/spaces
            api_client = self.client.api_client
            
            # List all Genie spaces
            response = api_client.do('GET', '/api/2.0/genie/spaces')
            
            if not response or 'spaces' not in response:
                logger.info("No Genie spaces found")
                return []
            
            spaces = response.get('spaces', [])
            logger.info(f"Found {len(spaces)} Genie spaces")
            
            spaces_data = []
            for space in spaces:
                space_info = {
                    'space_id': space.get('space_id'),
                    'title': space.get('title'),
                    'description': space.get('description'),
                    'warehouse_id': space.get('warehouse_id'),
                }
                spaces_data.append(space_info)
            
            return spaces_data
            
        except Exception as e:
            logger.error(f"Error scanning Genie spaces: {str(e)}")
            return []
    
    def scan_notebooks(self) -> List[Dict[str, Any]]:
        """Scan notebooks in the workspace."""
        logger.info("Scanning notebooks...")
        
        try:
            # List all notebooks recursively from root
            all_notebooks = []
            
            def list_notebooks_recursive(path: str):
                """Recursively list notebooks in the workspace."""
                try:
                    objects = list(self.client.workspace.list(path, recursive=False))
                    
                    for obj in objects:
                        if obj.object_type and obj.object_type.value == 'NOTEBOOK':
                            notebook_info = {
                                'notebook_name': obj.path.split('/')[-1] if obj.path else None,
                                'notebook_path': obj.path,
                                'notebook_author': safe_get_attribute(obj, 'created_by'),
                            }
                            
                            # For deep scan, add more details
                            if self.config.is_deep_scan():
                                notebook_info['language'] = safe_get_attribute(obj, 'language.value')
                                notebook_info['created_at'] = safe_get_attribute(obj, 'created_at')
                                notebook_info['modified_at'] = safe_get_attribute(obj, 'modified_at')
                                notebook_info['size'] = safe_get_attribute(obj, 'size')
                            
                            all_notebooks.append(notebook_info)
                        
                        elif obj.object_type and obj.object_type.value == 'DIRECTORY':
                            # Recursively scan subdirectories
                            list_notebooks_recursive(obj.path)
                
                except Exception as e:
                    logger.debug(f"Error listing path {path}: {str(e)}")
            
            # Start scanning from root
            list_notebooks_recursive('/')
            
            logger.info(f"Found {len(all_notebooks)} notebooks")
            return all_notebooks
            
        except Exception as e:
            logger.error(f"Error scanning notebooks: {str(e)}")
            return []
    
    def flatten_for_csv(self, workspace_data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Flatten workspace objects for CSV export.
        Creates separate CSV-ready lists for each object type.
        
        Args:
            workspace_data: Dictionary from scan() containing all workspace objects
            
        Returns:
            Dictionary with keys for each object type, each containing a list of flattened rows
        """
        result = {}
        
        # Flatten repos (6 columns)
        repos = workspace_data.get('repos', [])
        result['repos'] = [{
            'repo_id': repo.get('repo_id'),
            'path': repo.get('path'),
            'url': repo.get('url'),
            'provider': repo.get('provider'),
            'branch': repo.get('branch'),
            'head_commit_id': repo.get('head_commit_id')
        } for repo in repos]
        
        # Flatten experiments (6 columns)
        experiments = workspace_data.get('experiments', [])
        result['experiments'] = [{
            'experiment_id': exp.get('experiment_id'),
            'name': exp.get('name'),
            'artifact_location': exp.get('artifact_location'),
            'lifecycle_stage': exp.get('lifecycle_stage'),
            'creation_time': exp.get('creation_time'),
            'last_update_time': exp.get('last_update_time')
        } for exp in experiments]
        
        # Flatten serving endpoints (5 columns)
        endpoints = workspace_data.get('serving_endpoints', [])
        result['serving_endpoints'] = [{
            'endpoint_name': endpoint.get('endpoint_name'),
            'creator': endpoint.get('creator'),
            'creation_timestamp': endpoint.get('creation_timestamp'),
            'last_updated_timestamp': endpoint.get('last_updated_timestamp'),
            'state': endpoint.get('state')
        } for endpoint in endpoints]
        
        # Flatten alerts (8 columns - denormalize schedule)
        alerts = workspace_data.get('alerts', [])
        flattened_alerts = []
        for alert in alerts:
            schedule = alert.get('schedule', {})
            flattened_alerts.append({
                'alert_id': alert.get('alert_id'),
                'display_name': alert.get('display_name'),
                'query_id': alert.get('query_id'),
                'owner_user_name': alert.get('owner_user_name'),
                'state': alert.get('state'),
                'schedule_cron_expression': schedule.get('cron_expression') if schedule else None,
                'schedule_timezone_id': schedule.get('timezone_id') if schedule else None,
                'has_schedule': bool(schedule)
            })
        result['alerts'] = flattened_alerts
        
        # Flatten genie spaces (4 columns)
        genie_spaces = workspace_data.get('genie_spaces', [])
        result['genie_spaces'] = [{
            'space_id': space.get('space_id'),
            'title': space.get('title'),
            'description': space.get('description'),
            'warehouse_id': space.get('warehouse_id')
        } for space in genie_spaces]
        
        # Flatten notebooks (varies by scan type)
        notebooks = workspace_data.get('notebooks', [])
        if self.config.is_deep_scan():
            # Deep scan: 6 columns
            result['notebooks'] = [{
                'notebook_name': nb.get('notebook_name'),
                'notebook_path': nb.get('notebook_path'),
                'notebook_author': nb.get('notebook_author'),
                'language': nb.get('language'),
                'created_at': nb.get('created_at'),
                'modified_at': nb.get('modified_at')
            } for nb in notebooks]
        else:
            # Simple scan: 3 columns
            result['notebooks'] = [{
                'notebook_name': nb.get('notebook_name'),
                'notebook_path': nb.get('notebook_path'),
                'notebook_author': nb.get('notebook_author')
            } for nb in notebooks]
        
        return result
