"""
Billing Scanner Module for Databricks Workspace Discovery.
Scans and analyzes billing information using system.billing.usage table.
"""

import logging
from typing import Dict, List, Any, Optional
from databricks.sdk import WorkspaceClient
from .utils import retry_with_backoff

logger = logging.getLogger(__name__)


class BillingScanner:
    """
    Scanner for Databricks billing information.
    Queries system.billing.usage table for DBU consumption and cost analysis.
    """
    
    def __init__(self, client: WorkspaceClient, config):
        """
        Initialize billing scanner.
        
        Args:
            client: Authenticated Databricks WorkspaceClient
            config: Scan configuration object
        """
        self.client = client
        self.config = config
        self.billing_days = config.billing_days
        self.dbu_price = 0.40  # Default DBU price in USD
    
    def scan(self) -> Dict[str, Any]:
        """
        Scan billing information for the workspace.
        
        Returns:
            Dictionary containing billing analysis data
        """
        logger.info(f"Starting billing scan for last {self.billing_days} days...")
        
        results = {
            'billing_period_days': self.billing_days,
            'total_usage': {
                'total_dbus': 0.0,
                'estimated_cost_usd': 0.0,
            },
            'product_breakdown': {},
            'sku_breakdown': {},
            'error': None
        }
        
        try:
            # Get SQL warehouse for running queries
            warehouse_id = self._get_warehouse_id()
            
            if not warehouse_id:
                logger.warning("No SQL warehouse available for billing queries")
                results['error'] = "No SQL warehouse available"
                return results
            
            # Execute billing query
            billing_data = self._execute_billing_query(warehouse_id)
            
            if billing_data:
                results = self._process_billing_data(billing_data, results)
            else:
                results['error'] = "No billing data returned"
            
            logger.info(f"Billing scan complete. Total DBUs: {results['total_usage']['total_dbus']:.2f}, "
                       f"Cost: ${results['total_usage']['estimated_cost_usd']:.2f}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error scanning billing information: {str(e)}")
            results['error'] = str(e)
            return results
    
    def _get_warehouse_id(self) -> Optional[str]:
        """Get an available SQL warehouse ID for running queries."""
        try:
            warehouses = list(self.client.warehouses.list())
            
            # Find a running warehouse
            for warehouse in warehouses:
                if warehouse.state and warehouse.state.value == 'RUNNING':
                    logger.debug(f"Using warehouse {warehouse.id} ({warehouse.name})")
                    return warehouse.id
            
            # If no running warehouse, return first available
            if warehouses:
                logger.info(f"Using warehouse {warehouses[0].id} ({warehouses[0].name})")
                return warehouses[0].id
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting warehouse ID: {str(e)}")
            return None
    
    def _execute_billing_query(self, warehouse_id: str) -> List[List[Any]]:
        """Execute billing query against system.billing.usage table."""
        query = f"""
        SELECT 
            DATE(usage_start_time) as usage_date,
            sku_name,
            ROUND(SUM(usage_quantity), 4) as total_dbus,
            COUNT(*) as record_count
        FROM system.billing.usage 
        WHERE usage_start_time >= date_sub(CURRENT_DATE(), {self.billing_days})
            AND usage_start_time < CURRENT_DATE()
            AND usage_unit = 'DBU'
        GROUP BY DATE(usage_start_time), sku_name
        ORDER BY usage_date DESC, total_dbus DESC
        LIMIT 1000
        """
        
        try:
            logger.debug(f"Executing billing query on warehouse {warehouse_id}")
            
            result = retry_with_backoff(
                lambda: self.client.statement_execution.execute_statement(
                    statement=query,
                    warehouse_id=warehouse_id,
                    wait_timeout="50s"
                ),
                max_retries=2
            )
            
            # Extract data from result
            if result and hasattr(result, 'result') and result.result:
                if hasattr(result.result, 'data_array') and result.result.data_array:
                    logger.debug(f"Retrieved {len(result.result.data_array)} billing records")
                    return result.result.data_array
            
            logger.warning("No billing data returned from query")
            return []
            
        except Exception as e:
            logger.error(f"Error executing billing query: {str(e)}")
            return []
    
    def _process_billing_data(self, billing_data: List[List[Any]], results: Dict[str, Any]) -> Dict[str, Any]:
        """Process billing query results."""
        total_dbus = 0.0
        product_breakdown = {}
        sku_breakdown = {}
        
        for row in billing_data:
            try:
                usage_date = row[0] if len(row) > 0 else None
                sku_name = row[1] if len(row) > 1 else 'UNKNOWN'
                dbus = float(row[2]) if len(row) > 2 and row[2] is not None else 0.0
                record_count = int(row[3]) if len(row) > 3 and row[3] is not None else 0
                
                # Update totals
                total_dbus += dbus
                
                # Update SKU breakdown
                if sku_name not in sku_breakdown:
                    sku_breakdown[sku_name] = {
                        'dbus': 0.0,
                        'cost_usd': 0.0,
                        'records': 0
                    }
                
                sku_breakdown[sku_name]['dbus'] += dbus
                sku_breakdown[sku_name]['cost_usd'] += dbus * self.dbu_price
                sku_breakdown[sku_name]['records'] += record_count
                
                # Categorize by product type
                product = self._categorize_sku(sku_name)
                
                if product not in product_breakdown:
                    product_breakdown[product] = {
                        'dbus': 0.0,
                        'cost_usd': 0.0,
                        'records': 0
                    }
                
                product_breakdown[product]['dbus'] += dbus
                product_breakdown[product]['cost_usd'] += dbus * self.dbu_price
                product_breakdown[product]['records'] += record_count
                
            except Exception as e:
                logger.warning(f"Error processing billing row: {str(e)}")
                continue
        
        # Update results
        results['total_usage']['total_dbus'] = round(total_dbus, 4)
        results['total_usage']['estimated_cost_usd'] = round(total_dbus * self.dbu_price, 2)
        results['product_breakdown'] = product_breakdown
        results['sku_breakdown'] = sku_breakdown
        
        return results
    
    def _categorize_sku(self, sku_name: str) -> str:
        """Categorize SKU into product type."""
        if not sku_name:
            return 'OTHER'
        
        sku_upper = sku_name.upper()
        
        if 'JOBS' in sku_upper or 'JOB' in sku_upper:
            return 'JOBS'
        elif 'DLT' in sku_upper or 'DELTA' in sku_upper or 'PIPELINE' in sku_upper:
            return 'DLT'
        elif 'SQL' in sku_upper or 'WAREHOUSE' in sku_upper or 'SERVERLESS' in sku_upper:
            return 'SQL'
        elif 'ALL_PURPOSE' in sku_upper or 'ALLPURPOSE' in sku_upper:
            return 'ALL_PURPOSE'
        elif 'INTERACTIVE' in sku_upper or 'NOTEBOOK' in sku_upper:
            return 'INTERACTIVE'
        elif 'CLUSTER' in sku_upper:
            return 'CLUSTER'
        else:
            return 'OTHER'
    
    def flatten_for_csv(self, billing_data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Flatten billing data for CSV export.
        Creates 3 separate CSV-ready lists: summary, product_breakdown, and sku_breakdown.
        
        Args:
            billing_data: Dictionary from scan() containing billing information
            
        Returns:
            Dictionary with 3 keys (summary, product_breakdown, sku_breakdown), each containing a list of rows
        """
        result = {}
        
        # Summary CSV: 3 columns (single row)
        total_usage = billing_data.get('total_usage', {})
        result['summary'] = [{
            'billing_period_days': billing_data.get('billing_period_days'),
            'total_dbus': total_usage.get('total_dbus'),
            'estimated_cost_usd': total_usage.get('estimated_cost_usd')
        }]
        
        # Product breakdown CSV: 3 columns (one row per product type)
        product_breakdown = billing_data.get('product_breakdown', {})
        result['product_breakdown'] = [{
            'product_type': product_type,
            'total_dbus': data.get('dbus'),
            'estimated_cost_usd': data.get('cost_usd')
        } for product_type, data in product_breakdown.items()]
        
        # SKU breakdown CSV: 3 columns (one row per SKU)
        sku_breakdown = billing_data.get('sku_breakdown', {})
        result['sku_breakdown'] = [{
            'sku_name': sku_name,
            'total_dbus': data.get('dbus'),
            'estimated_cost_usd': data.get('cost_usd')
        } for sku_name, data in sku_breakdown.items()]
        
        return result
