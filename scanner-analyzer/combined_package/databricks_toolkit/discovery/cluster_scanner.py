"""
Cluster Scanner Module for Databricks Workspace Discovery.
Scans and extracts metadata from Databricks clusters.
"""

import logging
from typing import Dict, List, Any
from databricks.sdk import WorkspaceClient
from .utils import safe_get_attribute

logger = logging.getLogger(__name__)


class ClusterScanner:
    """
    Scanner for Databricks clusters.
    Extracts cluster configurations, states, and resource specifications.
    """
    
    def __init__(self, client: WorkspaceClient, config):
        """
        Initialize cluster scanner.
        
        Args:
            client: Authenticated Databricks WorkspaceClient
            config: Scan configuration object
        """
        self.client = client
        self.config = config
    
    def scan(self) -> Dict[str, Any]:
        """
        Scan all clusters in the workspace.
        
        For simple scan: Returns summary with counts and basic cluster info
        For deep scan: Returns detailed cluster configurations
        
        Returns:
            Dictionary with summary and clusters list (simple) or just clusters list (deep)
        """
        logger.info("Starting clusters scan...")
        
        try:
            # Get all clusters
            all_clusters = list(self.client.clusters.list())
            logger.info(f"Found {len(all_clusters)} clusters to scan")
            
            # Get cluster policies and instance pools for summary
            total_policies = 0
            total_instance_pools = 0
            
            if not self.config.is_deep_scan():
                try:
                    policies = list(self.client.cluster_policies.list())
                    total_policies = len(policies)
                except Exception as e:
                    logger.debug(f"Could not count cluster policies: {str(e)}")
                
                try:
                    pools = list(self.client.instance_pools.list())
                    total_instance_pools = len(pools)
                except Exception as e:
                    logger.debug(f"Could not count instance pools: {str(e)}")
            
            # Process each cluster
            clusters_data = []
            
            for cluster in all_clusters:
                try:
                    cluster_info = self._process_cluster(cluster)
                    clusters_data.append(cluster_info)
                except Exception as e:
                    logger.error(f"Error processing cluster {cluster.cluster_id}: {str(e)}")
                    clusters_data.append({
                        'cluster_id': cluster.cluster_id,
                        'error': str(e)
                    })
            
            logger.info(f"Successfully scanned {len(clusters_data)} clusters")
            
            # For simple scan, return with summary
            if not self.config.is_deep_scan():
                return {
                    'summary': {
                        'total_clusters': len(all_clusters),
                        'total_cluster_policies': total_policies,
                        'total_instance_pools': total_instance_pools
                    },
                    'clusters': clusters_data
                }
            
            # For deep scan, return just the list (backward compatibility)
            return clusters_data
            
        except Exception as e:
            logger.error(f"Error scanning clusters: {str(e)}")
            if not self.config.is_deep_scan():
                return {
                    'summary': {'total_clusters': 0, 'total_cluster_policies': 0, 'total_instance_pools': 0},
                    'clusters': []
                }
            return []
    
    def _process_cluster(self, cluster) -> Dict[str, Any]:
        """
        Process a single cluster and extract metadata.
        
        Args:
            cluster: Cluster object from list operation
            
        Returns:
            Dictionary containing cluster metadata
        """
        # For simple scan, return only essential fields
        if not self.config.is_deep_scan():
            return {
                'cluster_id': cluster.cluster_id,
                'cluster_name': cluster.cluster_name,
                'policy_id': safe_get_attribute(cluster, 'policy_id'),
                'instance_pool_id': safe_get_attribute(cluster, 'instance_pool_id'),
                'node_type_id': cluster.node_type_id,
                'driver_node_type_id': cluster.driver_node_type_id,
                'custom_tags': safe_get_attribute(cluster, 'custom_tags', {}),
                'default_tags': safe_get_attribute(cluster, 'default_tags', {})
            }
        
        # Deep scan: Extract comprehensive cluster metadata
        cluster_info = {
            'cluster_id': cluster.cluster_id,
            'cluster_name': cluster.cluster_name,
            'policy_id': safe_get_attribute(cluster, 'policy_id'),
            'spark_version': cluster.spark_version,
            'node_type_id': cluster.node_type_id,
            'driver_node_type_id': cluster.driver_node_type_id,
            'num_workers': cluster.num_workers,
            'autotermination_minutes': cluster.autotermination_minutes,
            'cluster_source': safe_get_attribute(cluster, 'cluster_source.value'),
            'state': safe_get_attribute(cluster, 'state.value'),
            'state_message': safe_get_attribute(cluster, 'state_message'),
            'creator_user_name': cluster.creator_user_name,
            'start_time': cluster.start_time,
            'terminated_time': cluster.terminated_time,
        }
        
        # Extract autoscaling configuration
        if hasattr(cluster, 'autoscale') and cluster.autoscale:
            cluster_info['autoscale'] = {
                'min_workers': safe_get_attribute(cluster.autoscale, 'min_workers'),
                'max_workers': safe_get_attribute(cluster.autoscale, 'max_workers'),
            }
        
        # Extract Spark configuration
        if hasattr(cluster, 'spark_conf') and cluster.spark_conf:
            cluster_info['spark_conf'] = dict(cluster.spark_conf)
        
        # Extract disk configuration
        if hasattr(cluster, 'enable_elastic_disk'):
            cluster_info['enable_elastic_disk'] = cluster.enable_elastic_disk
        
        if hasattr(cluster, 'disk_spec') and cluster.disk_spec:
            cluster_info['disk_spec'] = {
                'disk_type': safe_get_attribute(cluster.disk_spec, 'disk_type.value'),
                'disk_count': safe_get_attribute(cluster.disk_spec, 'disk_count'),
                'disk_size': safe_get_attribute(cluster.disk_spec, 'disk_size'),
            }
        
        # Extract Azure-specific attributes
        if hasattr(cluster, 'azure_attributes') and cluster.azure_attributes:
            cluster_info['azure_attributes'] = {
                'availability': safe_get_attribute(cluster.azure_attributes, 'availability.value'),
                'first_on_demand': safe_get_attribute(cluster.azure_attributes, 'first_on_demand'),
                'spot_bid_max_price': safe_get_attribute(cluster.azure_attributes, 'spot_bid_max_price'),
            }
        
        # Extract custom tags
        if hasattr(cluster, 'custom_tags') and cluster.custom_tags:
            cluster_info['custom_tags'] = dict(cluster.custom_tags)
        
        # For deep scan, add more detailed information
            if self.config.is_deep_scan():
                cluster_info['init_scripts_count'] = len(cluster.init_scripts) if hasattr(cluster, 'init_scripts') and cluster.init_scripts else 0
                cluster_info['enable_local_disk_encryption'] = getattr(cluster, 'enable_local_disk_encryption', False)
                cluster_info['instance_pool_id'] = getattr(cluster, 'instance_pool_id', None)
                cluster_info['driver_instance_pool_id'] = getattr(cluster, 'driver_instance_pool_id', None)
        
        return cluster_info
    
    def flatten_for_csv(self, clusters_data) -> List[Dict[str, Any]]:
        """
        Flatten cluster data for CSV export.
        For simple scans: One row per cluster with basic info.
        For deep scans: One row per cluster with full configuration.
        
        Args:
            clusters_data: List of cluster dictionaries from scan() or dict with 'clusters' key
            
        Returns:
            List of flattened dictionaries suitable for CSV export
        """
        flattened = []
        
        # Handle both list and dict input
        if isinstance(clusters_data, dict):
            clusters = clusters_data.get('clusters', [])
        else:
            clusters = clusters_data
        
        for cluster in clusters:
            if self.config.is_deep_scan():
                # Deep scan: 22 columns with full configuration
                autoscale = cluster.get('autoscale', {})
                custom_tags = cluster.get('custom_tags', {})
                default_tags = cluster.get('default_tags', {})
                
                flattened.append({
                    'cluster_id': cluster.get('cluster_id'),
                    'cluster_name': cluster.get('cluster_name'),
                    'spark_version': cluster.get('spark_version'),
                    'node_type_id': cluster.get('node_type_id'),
                    'driver_node_type_id': cluster.get('driver_node_type_id'),
                    'state': cluster.get('state'),
                    'creator_user_name': cluster.get('creator_user_name'),
                    'cluster_source': cluster.get('cluster_source'),
                    'autoscale_enabled': bool(autoscale) if autoscale else None,
                    'autoscale_min_workers': autoscale.get('min_workers') if autoscale else None,
                    'autoscale_max_workers': autoscale.get('max_workers') if autoscale else None,
                    'num_workers': cluster.get('num_workers'),
                    'autotermination_minutes': cluster.get('autotermination_minutes'),
                    'enable_elastic_disk': cluster.get('enable_elastic_disk'),
                    'data_security_mode': cluster.get('data_security_mode'),
                    'runtime_engine': cluster.get('runtime_engine'),
                    'policy_id': cluster.get('policy_id'),
                    'instance_pool_id': cluster.get('instance_pool_id'),
                    'driver_instance_pool_id': cluster.get('driver_instance_pool_id'),
                    'custom_tags': str(custom_tags) if custom_tags else None,
                    'default_tags': str(default_tags) if default_tags else None,
                    'single_user_name': cluster.get('single_user_name')
                })
            else:
                # Simple scan: 8 columns with basic info
                flattened.append({
                    'cluster_id': cluster.get('cluster_id'),
                    'cluster_name': cluster.get('cluster_name'),
                    'spark_version': cluster.get('spark_version'),
                    'node_type_id': cluster.get('node_type_id'),
                    'state': cluster.get('state'),
                    'creator_user_name': cluster.get('creator_user_name'),
                    'cluster_source': cluster.get('cluster_source'),
                    'num_workers': cluster.get('num_workers')
                })
        
        return flattened