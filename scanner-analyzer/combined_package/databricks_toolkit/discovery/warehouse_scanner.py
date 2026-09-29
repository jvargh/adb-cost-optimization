"""
Warehouse Scanner Module for Databricks Workspace Discovery.
Scans and extracts metadata from SQL warehouses.
"""

import logging
from typing import Dict, List, Any
from databricks.sdk import WorkspaceClient
from .utils import safe_get_attribute

logger = logging.getLogger(__name__)


class WarehouseScanner:
    """
    Scanner for Databricks SQL warehouses.
    Extracts warehouse configurations, sizes, and states.
    """
    
    def __init__(self, client: WorkspaceClient, config):
        """
        Initialize warehouse scanner.
        
        Args:
            client: Authenticated Databricks WorkspaceClient
            config: Scan configuration object
        """
        self.client = client
        self.config = config
    
    def scan(self) -> Dict[str, Any]:
        """
        Scan all SQL warehouses in the workspace.
        
        For simple scan: Returns summary with warehouse count and basic warehouse info
        For deep scan: Returns detailed warehouse configurations
        
        Returns:
            Dictionary with summary and warehouses list (simple) or just warehouses list (deep)
        """
        logger.info("Starting warehouses scan...")
        
        try:
            # Get all warehouses
            all_warehouses = list(self.client.warehouses.list())
            logger.info(f"Found {len(all_warehouses)} warehouses to scan")
            
            # Process each warehouse
            warehouses_data = []
            
            for warehouse in all_warehouses:
                try:
                    warehouse_info = self._process_warehouse(warehouse)
                    warehouses_data.append(warehouse_info)
                except Exception as e:
                    logger.error(f"Error processing warehouse {warehouse.id}: {str(e)}")
                    warehouses_data.append({
                        'warehouse_id': warehouse.id,
                        'error': str(e)
                    })
            
            logger.info(f"Successfully scanned {len(warehouses_data)} warehouses")
            
            # For simple scan, return with summary
            if not self.config.is_deep_scan():
                return {
                    'summary': {
                        'total_warehouses': len(all_warehouses)
                    },
                    'warehouses': warehouses_data
                }
            
            # For deep scan, return just the list (backward compatibility)
            return warehouses_data
            
        except Exception as e:
            logger.error(f"Error scanning warehouses: {str(e)}")
            if not self.config.is_deep_scan():
                return {
                    'summary': {'total_warehouses': 0},
                    'warehouses': []
                }
            return []
    
    def _process_warehouse(self, warehouse) -> Dict[str, Any]:
        """
        Process a single warehouse and extract metadata.
        
        Args:
            warehouse: Warehouse object from list operation
            
        Returns:
            Dictionary containing warehouse metadata
        """
        # Extract basic warehouse metadata
        warehouse_info = {
            'warehouse_id': warehouse.id,
            'warehouse_name': warehouse.name,
            'cluster_size': warehouse.cluster_size,
            'min_num_clusters': warehouse.min_num_clusters,
            'max_num_clusters': warehouse.max_num_clusters,
            'auto_stop_mins': warehouse.auto_stop_mins,
            'state': safe_get_attribute(warehouse, 'state.value'),
            'creator_name': warehouse.creator_name,
            'warehouse_type': safe_get_attribute(warehouse, 'warehouse_type.value'),
            'enable_photon': warehouse.enable_photon,
            'enable_serverless_compute': warehouse.enable_serverless_compute,
        }
        
        # For deep scan, add more details
        if self.config.is_deep_scan():
            warehouse_info['spot_instance_policy'] = safe_get_attribute(warehouse, 'spot_instance_policy.value')
            warehouse_info['channel'] = safe_get_attribute(warehouse, 'channel.value')
            warehouse_info['jdbc_url'] = getattr(warehouse, 'jdbc_url', None)
            warehouse_info['odbc_params'] = getattr(warehouse, 'odbc_params', None)
            
            # Extract tags - handle both dict and object formats
            if hasattr(warehouse, 'tags') and warehouse.tags:
                try:
                    # Try to access as dict (EndpointTags object has custom_tags attribute)
                    if hasattr(warehouse.tags, 'custom_tags'):
                        warehouse_info['custom_tags'] = warehouse.tags.custom_tags
                    # Or try to iterate if it's a list
                    elif hasattr(warehouse.tags, '__iter__') and not isinstance(warehouse.tags, str):
                        warehouse_info['custom_tags'] = {
                            tag.key: tag.value for tag in warehouse.tags
                        }
                    # Otherwise, try to convert to dict
                    elif hasattr(warehouse.tags, 'as_dict'):
                        warehouse_info['custom_tags'] = warehouse.tags.as_dict()
                    else:
                        # Just store as string representation
                        warehouse_info['custom_tags'] = str(warehouse.tags)
                except Exception as e:
                    logger.debug(f"Could not extract tags for warehouse {warehouse.id}: {str(e)}")
                    warehouse_info['custom_tags'] = None
        
        return warehouse_info
    
    def flatten_for_csv(self, warehouses_data) -> List[Dict[str, Any]]:
        """
        Flatten warehouse data for CSV export.
        For simple scans: One row per warehouse with basic info.
        For deep scans: One row per warehouse with connection details.
        
        Args:
            warehouses_data: List of warehouse dictionaries from scan() or dict with 'warehouses' key
            
        Returns:
            List of flattened dictionaries suitable for CSV export
        """
        flattened = []
        
        # Handle both list and dict input
        if isinstance(warehouses_data, dict):
            warehouses = warehouses_data.get('warehouses', [])
        else:
            warehouses = warehouses_data
        
        for warehouse in warehouses:
            if self.config.is_deep_scan():
                # Deep scan: 14 columns with connection info
                flattened.append({
                    'warehouse_id': warehouse.get('warehouse_id'),
                    'warehouse_name': warehouse.get('warehouse_name'),
                    'cluster_size': warehouse.get('cluster_size'),
                    'min_num_clusters': warehouse.get('min_num_clusters'),
                    'max_num_clusters': warehouse.get('max_num_clusters'),
                    'auto_stop_mins': warehouse.get('auto_stop_mins'),
                    'state': warehouse.get('state'),
                    'creator_name': warehouse.get('creator_name'),
                    'enable_photon': warehouse.get('enable_photon'),
                    'enable_serverless_compute': warehouse.get('enable_serverless_compute'),
                    'warehouse_type': warehouse.get('warehouse_type'),
                    'spot_instance_policy': warehouse.get('spot_instance_policy'),
                    'jdbc_url': warehouse.get('jdbc_url'),
                    'odbc_params': warehouse.get('odbc_params')
                })
            else:
                # Simple scan: 9 columns with basic info
                flattened.append({
                    'warehouse_id': warehouse.get('warehouse_id'),
                    'warehouse_name': warehouse.get('warehouse_name'),
                    'cluster_size': warehouse.get('cluster_size'),
                    'min_num_clusters': warehouse.get('min_num_clusters'),
                    'max_num_clusters': warehouse.get('max_num_clusters'),
                    'auto_stop_mins': warehouse.get('auto_stop_mins'),
                    'state': warehouse.get('state'),
                    'creator_name': warehouse.get('creator_name'),
                    'enable_photon': warehouse.get('enable_photon')
                })
        
        return flattened
