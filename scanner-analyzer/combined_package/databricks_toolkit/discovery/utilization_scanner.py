"""
Utilization Scanner Module for Databricks Workspace Discovery.
Scans cluster utilization and SQL query usage metrics for deep scans.
"""

import logging
import csv
import json
import os
from typing import Dict, List, Any, Optional
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem

logger = logging.getLogger(__name__)

# Maximum file size for JSON output (10MB)
MAX_JSON_SIZE_BYTES = 10 * 1024 * 1024


class UtilizationScanner:
    """
    Scanner for Databricks utilization metrics.
    Queries cluster utilization and SQL query usage for deep scan mode.
    """
    
    def __init__(self, client: WorkspaceClient, config):
        """
        Initialize utilization scanner.
        
        Args:
            client: Authenticated Databricks WorkspaceClient
            config: Scan configuration object
        """
        self.client = client
        self.config = config
        self.workspace_id = None
    
    def scan(self, workspace_id: str) -> Dict[str, Any]:
        """
        Scan utilization metrics for the workspace.
        Only runs for deep scans.
        
        Args:
            workspace_id: The workspace ID to scan
            
        Returns:
            Dictionary containing utilization data and file paths
        """
        if not self.config.is_deep_scan():
            logger.info("Skipping utilization scan - only available in deep scan mode")
            return {
                'skipped': True,
                'reason': 'Utilization scanning only available in deep scan mode'
            }
        
        logger.info("Starting utilization scan (deep scan mode)...")
        self.workspace_id = workspace_id
        
        results = {
            'workspace_id': workspace_id,
            'cluster_utilization': {
                'status': 'pending',
                'files': []
            },
            'sql_query_usage': {
                'status': 'pending',
                'files': []
            },
            'export_format': 'csv',  # Utilization data is always exported as CSV
            'errors': []
        }
        
        try:
            # Get or start a serverless warehouse for running queries
            warehouse_id = self._get_serverless_warehouse_id()
            
            if not warehouse_id:
                logger.warning("No serverless SQL warehouse available for utilization queries")
                results['cluster_utilization']['status'] = 'error'
                results['cluster_utilization']['error'] = 'No serverless warehouse available'
                results['sql_query_usage']['status'] = 'error'
                results['sql_query_usage']['error'] = 'No serverless warehouse available'
                return results
            
            logger.info(f"Using warehouse {warehouse_id} for utilization queries")
            
            # Scan cluster utilization
            try:
                cluster_util_data = self._scan_cluster_utilization(warehouse_id, workspace_id)
                if cluster_util_data:
                    files = self._save_utilization_data(
                        cluster_util_data,
                        workspace_id,
                        'cluster_utilization'
                    )
                    results['cluster_utilization']['status'] = 'success'
                    results['cluster_utilization']['files'] = files
                    results['cluster_utilization']['record_count'] = len(cluster_util_data)
                    logger.info(f"✓ Cluster utilization: {len(cluster_util_data)} records, {len(files)} file(s)")
                else:
                    results['cluster_utilization']['status'] = 'no_data'
                    logger.info("No cluster utilization data found")
            except Exception as e:
                logger.error(f"Error scanning cluster utilization: {str(e)}")
                results['cluster_utilization']['status'] = 'error'
                results['cluster_utilization']['error'] = str(e)
                results['errors'].append(f"Cluster utilization scan failed: {str(e)}")
            
            # Scan SQL query usage
            try:
                sql_usage_data = self._scan_sql_query_usage(warehouse_id, workspace_id)
                if sql_usage_data:
                    files = self._save_utilization_data(
                        sql_usage_data,
                        workspace_id,
                        'sql_query_usage'
                    )
                    results['sql_query_usage']['status'] = 'success'
                    results['sql_query_usage']['files'] = files
                    results['sql_query_usage']['record_count'] = len(sql_usage_data)
                    logger.info(f"✓ SQL query usage: {len(sql_usage_data)} records, {len(files)} file(s)")
                else:
                    results['sql_query_usage']['status'] = 'no_data'
                    logger.info("No SQL query usage data found")
            except Exception as e:
                logger.error(f"Error scanning SQL query usage: {str(e)}")
                results['sql_query_usage']['status'] = 'error'
                results['sql_query_usage']['error'] = str(e)
                results['errors'].append(f"SQL query usage scan failed: {str(e)}")
            
            logger.info("Utilization scan complete")
            return results
            
        except Exception as e:
            logger.error(f"Error in utilization scan: {str(e)}")
            results['errors'].append(str(e))
            return results
    
    def _get_serverless_warehouse_id(self) -> Optional[str]:
        """Get a serverless SQL warehouse ID for running queries."""
        try:
            warehouses = list(self.client.warehouses.list())
            
            # Look for serverless warehouses first
            for warehouse in warehouses:
                if (hasattr(warehouse, 'enable_serverless_compute') and 
                    warehouse.enable_serverless_compute):
                    logger.debug(f"Found serverless warehouse: {warehouse.id} ({warehouse.name})")
                    return warehouse.id
            
            # Fallback to any running warehouse
            for warehouse in warehouses:
                if warehouse.state and warehouse.state.value == 'RUNNING':
                    logger.debug(f"Using running warehouse: {warehouse.id} ({warehouse.name})")
                    return warehouse.id
            
            # Fallback to first available warehouse
            if warehouses:
                logger.info(f"Using warehouse: {warehouses[0].id} ({warehouses[0].name})")
                return warehouses[0].id
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting warehouse ID: {str(e)}")
            return None
    
    def _scan_cluster_utilization(self, warehouse_id: str, workspace_id: str) -> List[Dict[str, Any]]:
        """Execute cluster utilization query."""
        # Extract numeric workspace ID (remove adb- prefix if present)
        numeric_workspace_id = workspace_id.replace('adb-', '') if workspace_id.startswith('adb-') else workspace_id
        
        # Use INTERVAL syntax instead of parameterized date_add
        query = f"""
        WITH windowed_timeline AS (
                SELECT
                    cluster_id,
                    driver,
                    start_time,
                    (cpu_user_percent + cpu_system_percent) AS cpu_total_pct,
                    cpu_wait_percent,
                    mem_used_percent,
                    network_received_bytes,
                    network_sent_bytes
                FROM system.compute.node_timeline
                WHERE workspace_id = {numeric_workspace_id} AND 
                start_time >= now() - INTERVAL {abs(self.config.utilization_days)} DAYS
            ),
            cluster_config_snapshot AS (
                SELECT
                    c.cluster_id,
                    ANY_VALUE(c.cluster_name) AS cluster_name,
                    ANY_VALUE(c.driver_node_type) AS driver_node_type,
                    ANY_VALUE(c.worker_node_type) AS worker_node_type,
                    ANY_VALUE(c.worker_count) AS worker_count,
                    ANY_VALUE(c.min_autoscale_workers) AS min_autoscale_workers,
                    ANY_VALUE(c.max_autoscale_workers) AS max_autoscale_workers
                FROM system.compute.clusters c
                GROUP BY c.cluster_id
            ),
            util AS (
                SELECT
                    cluster_id,
                    driver,
                    ROUND(AVG(cpu_total_pct),2)                       AS `Avg CPU Utilization`,
                    ROUND(MAX(cpu_total_pct),2)                       AS `Peak CPU Utilization`,
                    ROUND(AVG(cpu_wait_percent),2)                    AS `Avg CPU Wait`,
                    ROUND(MAX(cpu_wait_percent),2)                    AS `Max CPU Wait`,
                    ROUND(AVG(mem_used_percent),2)                    AS `Avg Memory Utilization`,
                    ROUND(MAX(mem_used_percent),2)                    AS `Max Memory Utilization`,
                    ROUND(AVG(network_received_bytes) / (1024^2),2)   AS `Avg Network MB Received`,
                    ROUND(MAX(network_received_bytes) / (1024^2),2)   AS `Max Network MB Received`,
                    ROUND(AVG(network_sent_bytes)     / (1024^2),2)   AS `Avg Network MB Sent`,
                    ROUND(MAX(network_sent_bytes)     / (1024^2),2)   AS `Max Network MB Sent`
                FROM windowed_timeline
                GROUP BY cluster_id, driver
            ),
            usage_job_names AS (
                SELECT
                    workspace_id,
                    usage_metadata.cluster_id AS cluster_id,
                    ANY_VALUE(usage_metadata.job_id) AS job_id,
                    ANY_VALUE(COALESCE(usage_metadata.job_name, '')) AS job_name
                FROM system.billing.usage
                WHERE workspace_id = {numeric_workspace_id}
                AND usage_metadata.cluster_id IS NOT NULL
                AND usage_date >= CURRENT_DATE() - INTERVAL {abs(self.config.utilization_days)} DAYS
                GROUP BY workspace_id, usage_metadata.cluster_id
            )
            SELECT
                u.cluster_id,
                u.driver,
                -- Prefer job_id from billing.usage, fallback to cluster_name parsing
                COALESCE(CAST(ujn.job_id AS STRING),
                    CASE
                        WHEN cc.cluster_name IS NOT NULL THEN regexp_extract(cc.cluster_name, 'job-(\\d+)-', 1)
                        ELSE NULL
                    END
                ) AS job_id,
                -- Prefer job_name from billing.usage, fallback to cluster_name parsing
                COALESCE(ujn.job_name,
                    CASE
                        WHEN cc.cluster_name IS NOT NULL THEN regexp_extract(cc.cluster_name, 'job-\\d+-(.*)', 1)
                        ELSE NULL
                    END
                ) AS job_name,
                cc.driver_node_type,
                cc.worker_node_type,
                cc.min_autoscale_workers,
                cc.max_autoscale_workers,
                cc.worker_count,
                u.`Avg CPU Utilization`,
                u.`Peak CPU Utilization`,
                u.`Avg CPU Wait`,
                u.`Max CPU Wait`,
                u.`Avg Memory Utilization`,
                u.`Max Memory Utilization`,
                u.`Avg Network MB Received`,
                u.`Max Network MB Received`,
                u.`Avg Network MB Sent`,
                u.`Max Network MB Sent`
            FROM util u
            LEFT JOIN cluster_config_snapshot cc
            ON u.cluster_id = cc.cluster_id
            LEFT JOIN usage_job_names ujn
            ON u.cluster_id = ujn.cluster_id
            ORDER BY `Avg CPU Utilization` DESC
        """
        
        try:
            logger.debug(f"Executing cluster utilization query on warehouse {warehouse_id} for last {self.config.utilization_days} days")
            logger.info(f"Workspace ID: {workspace_id} -> Numeric ID: {numeric_workspace_id}")
            logger.debug(f"Query parameters: workspace_id={numeric_workspace_id}, days={abs(self.config.utilization_days)}")
            logger.info(f"Query SQL: {query[:200]}...")  # Log first 200 chars of query
            
            # Execute the statement without parameters (using direct substitution)
            result = self.client.statement_execution.execute_statement(
                statement=query,
                warehouse_id=warehouse_id,
                wait_timeout="50s"
            )
            
            # Extract data from result - handle both dict and object responses
            utilization_data = []
            
            # Check if result is a dict or object
            if isinstance(result, dict):
                result_data = result.get('result')
                if result_data:
                    data_array = result_data.get('data_array', [])
                    if data_array:
                        columns = [
                            'cluster_id', 'driver', 'job_id', 'job_name',
                            'driver_node_type', 'worker_node_type',
                            'min_autoscale_workers', 'max_autoscale_workers', 'worker_count',
                            'Avg CPU Utilization', 'Peak CPU Utilization',
                            'Avg CPU Wait', 'Max CPU Wait',
                            'Avg Memory Utilization', 'Max Memory Utilization',
                            'Avg Network MB Received', 'Max Network MB Received',
                            'Avg Network MB Sent', 'Max Network MB Sent'
                        ]
                        
                        for row in data_array:
                            record = {}
                            for idx, col_name in enumerate(columns):
                                record[col_name] = row[idx] if idx < len(row) else None
                            utilization_data.append(record)
            else:
                # Handle object response
                if result and hasattr(result, 'result') and result.result:
                    if hasattr(result.result, 'data_array') and result.result.data_array:
                        columns = [
                            'cluster_id', 'driver', 'job_id', 'job_name',
                            'driver_node_type', 'worker_node_type',
                            'min_autoscale_workers', 'max_autoscale_workers', 'worker_count',
                            'Avg CPU Utilization', 'Peak CPU Utilization',
                            'Avg CPU Wait', 'Max CPU Wait',
                            'Avg Memory Utilization', 'Max Memory Utilization',
                            'Avg Network MB Received', 'Max Network MB Received',
                            'Avg Network MB Sent', 'Max Network MB Sent'
                        ]
                        
                        for row in result.result.data_array:
                            record = {}
                            for idx, col_name in enumerate(columns):
                                record[col_name] = row[idx] if idx < len(row) else None
                            utilization_data.append(record)
            
            logger.debug(f"Retrieved {len(utilization_data)} cluster utilization records")
            
            # Debug: Log sample records to check job_id and job_name values
            if utilization_data:
                logger.info(f"Sample utilization record (first): {utilization_data[0]}")
                job_ids = [r.get('job_id') for r in utilization_data if r.get('job_id')]
                job_names = [r.get('job_name') for r in utilization_data if r.get('job_name')]
                logger.info(f"Found {len(job_ids)} records with job_id, {len(job_names)} records with job_name")
            
            return utilization_data
            
        except Exception as e:
            logger.error(f"Error executing cluster utilization query: {str(e)}")
            raise
    
    def _scan_sql_query_usage(self, warehouse_id: str, workspace_id: str) -> List[Dict[str, Any]]:
        """Execute SQL query usage query."""
        # Extract numeric workspace ID (remove adb- prefix if present)
        numeric_workspace_id = workspace_id.replace('adb-', '') if workspace_id.startswith('adb-') else workspace_id
        
        # Use positive days value for the query
        days_value = abs(self.config.utilization_days)
        
        # Use direct substitution instead of parameters
        query = f"""
        WITH billing_usage AS (
            SELECT
                hour(usage_end_time) AS usage_hour,
                usage_metadata.warehouse_id,
                usage_date,
				workspace_id,
				product_features.sql_tier AS sql_tier,
				product_features.is_serverless AS is_serverless,
				product_features.is_photon AS is_photon,
                SUM(usage_quantity) AS dbus_per_hour
            FROM system.billing.usage
            WHERE
                usage_date >= CURRENT_DATE() - INTERVAL {days_value} DAYS
                AND usage_metadata.warehouse_id IS NOT NULL
                AND usage_unit = 'DBU'
                AND cloud = 'AZURE'
            GROUP BY hour(usage_end_time), usage_metadata.warehouse_id, usage_date,
				workspace_id,
				sql_tier,
				is_serverless,
				is_photon
            ),
            query_history AS (
            SELECT
                hour(end_time) AS query_hour,
                DATE(end_time) AS query_date,
                compute.warehouse_id,
                statement_id AS query_id,
                statement_text,
                statement_type,
                total_duration_ms,
                executed_by,
                error_message
            FROM system.query.history
            WHERE workspace_id = {numeric_workspace_id}
                AND TO_DATE(end_time) >= CURRENT_DATE() - INTERVAL {days_value} DAYS
                AND compute.warehouse_id IS NOT NULL
            )
            SELECT
            q.query_id,
            q.query_date AS execution_date,
            q.statement_text,
            q.statement_type,
            q.error_message,
            q.executed_by,
            q.total_duration_ms,
			b.sql_tier,
			b.is_serverless,
			b.is_photon,
			b.warehouse_id,
			b.workspace_id,
            ROUND(
                COALESCE(
                b.dbus_per_hour * (q.total_duration_ms / 3600000.0),
                0
                ), 4
            ) AS estimated_dbu_cost
            FROM query_history q
            LEFT JOIN billing_usage b
            ON q.query_hour = b.usage_hour
            AND q.query_date = b.usage_date
            AND q.warehouse_id = b.warehouse_id
            ORDER BY estimated_dbu_cost DESC , q.total_duration_ms DESC
            LIMIT 100
        """
        
        try:
            logger.debug(f"Executing SQL query usage query on warehouse {warehouse_id} for last {self.config.utilization_days} days")
            logger.info(f"Workspace ID: {workspace_id} -> Numeric ID: {numeric_workspace_id}")
            logger.debug(f"Query parameters: workspace_id={numeric_workspace_id}, days_value={days_value}")
            logger.info(f"Query SQL: {query[:200]}...")  # Log first 200 chars of query
            
            # Execute the statement without parameters (using direct substitution)
            result = self.client.statement_execution.execute_statement(
                statement=query,
                warehouse_id=warehouse_id,
                wait_timeout="50s"
            )
            
            # Extract data from result - handle both dict and object responses
            query_usage_data = []
            
            # Check if result is a dict or object
            if isinstance(result, dict):
                result_data = result.get('result')
                if result_data:
                    data_array = result_data.get('data_array', [])
                    if data_array:
                        columns = [
                            'query_id', 'execution_date', 'statement_text', 'statement_type',
                            'error_message', 'executed_by', 'total_duration_ms', 
                            'sql_tier', 'is_serverless', 'is_photon', 
                            'warehouse_id', 'workspace_id', 'estimated_dbu_cost'
                        ]
                        
                        for row in data_array:
                            record = {}
                            for idx, col_name in enumerate(columns):
                                record[col_name] = row[idx] if idx < len(row) else None
                            query_usage_data.append(record)
            else:
                # Handle object response
                if result and hasattr(result, 'result') and result.result:
                    if hasattr(result.result, 'data_array') and result.result.data_array:
                        columns = [
                            'query_id', 'execution_date', 'statement_text', 'statement_type',
                            'error_message', 'executed_by', 'total_duration_ms', 
                            'sql_tier', 'is_serverless', 'is_photon', 
                            'warehouse_id', 'workspace_id', 'estimated_dbu_cost'
                        ]
                        
                        for row in result.result.data_array:
                            record = {}
                            for idx, col_name in enumerate(columns):
                                record[col_name] = row[idx] if idx < len(row) else None
                            query_usage_data.append(record)
            
            logger.debug(f"Retrieved {len(query_usage_data)} SQL query usage records")
            return query_usage_data
            
        except Exception as e:
            logger.error(f"Error executing SQL query usage query: {str(e)}")
            raise
    
    def _save_utilization_data(
        self, 
        data: List[Dict[str, Any]], 
        workspace_id: str, 
        data_type: str
    ) -> List[str]:
        """
        Save utilization data to file(s) in CSV format.
        Utilization data is always saved as CSV regardless of export_format setting.
        
        Args:
            data: List of records to save
            workspace_id: Workspace identifier
            data_type: Type of data (cluster_utilization or sql_query_usage)
            
        Returns:
            List of file paths created
        """
        if not data:
            return []
        
        # Determine output directory based on data type
        output_dir = self._get_output_directory(data_type)
        os.makedirs(output_dir, exist_ok=True)
        
        files_created = []
        
        # Always save utilization data as CSV
        csv_file = self._save_as_csv(data, workspace_id, data_type, output_dir)
        files_created.append(csv_file)
        
        return files_created
    
    def _get_output_directory(self, data_type: str) -> str:
        """Get the output directory for utilization files."""
        if self.config.output_file:
            # Determine if output_file is a directory or file path
            from pathlib import Path
            path = Path(self.config.output_file)
            
            # If it's an existing directory, use it directly
            # If it doesn't have a suffix (.json, .csv, etc.), treat as directory
            # Otherwise, extract the parent directory
            if path.is_dir() or not path.suffix:
                base_dir = str(path)
            else:
                base_dir = str(path.parent)
            
            if not base_dir:
                base_dir = './out'
        else:
            base_dir = './out'
        
        # Create subdirectory based on data type
        if data_type == 'cluster_utilization':
            output_dir = os.path.join(base_dir, 'utilization', 'cluster')
        elif data_type == 'sql_query_usage':
            output_dir = os.path.join(base_dir, 'utilization', 'query')
        else:
            output_dir = os.path.join(base_dir, 'utilization')
        
        return output_dir
    
    def _save_as_csv(
        self, 
        data: List[Dict[str, Any]], 
        workspace_id: str, 
        data_type: str,
        output_dir: str
    ) -> str:
        """Save data as CSV file."""
        filename = f"{workspace_id}_{data_type}.csv"
        filepath = os.path.join(output_dir, filename)
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                if not data:
                    return filepath
                
                # Get all unique keys from all records
                fieldnames = list(data[0].keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                writer.writerows(data)
            
            logger.debug(f"Saved CSV file: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error saving CSV file {filepath}: {str(e)}")
            raise
    
    def _save_as_json(
        self, 
        data: List[Dict[str, Any]], 
        workspace_id: str, 
        data_type: str,
        output_dir: str
    ) -> List[str]:
        """
        Save data as JSON file(s).
        Splits into multiple files if size exceeds 10MB.
        """
        files_created = []
        
        # Try to save as single file first
        temp_json = json.dumps(data, indent=2, default=str)
        json_size = len(temp_json.encode('utf-8'))
        
        if json_size <= MAX_JSON_SIZE_BYTES:
            # Single file is fine
            filename = f"{workspace_id}_{data_type}.json"
            filepath = os.path.join(output_dir, filename)
            
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(temp_json)
                
                logger.debug(f"Saved JSON file: {filepath} ({json_size / (1024*1024):.2f} MB)")
                files_created.append(filepath)
            except Exception as e:
                logger.error(f"Error saving JSON file {filepath}: {str(e)}")
                raise
        else:
            # Need to split into multiple files
            logger.info(f"JSON size ({json_size / (1024*1024):.2f} MB) exceeds 10MB limit, splitting into parts...")
            
            # Calculate approximate records per file
            avg_record_size = json_size / len(data)
            records_per_file = int(MAX_JSON_SIZE_BYTES / avg_record_size * 0.9)  # 90% to be safe
            
            part_num = 1
            for i in range(0, len(data), records_per_file):
                chunk = data[i:i + records_per_file]
                filename = f"{workspace_id}_{data_type}_part{part_num}.json"
                filepath = os.path.join(output_dir, filename)
                
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(chunk, f, indent=2, default=str)
                    
                    chunk_size = os.path.getsize(filepath)
                    logger.debug(f"Saved JSON part {part_num}: {filepath} "
                               f"({chunk_size / (1024*1024):.2f} MB, {len(chunk)} records)")
                    files_created.append(filepath)
                    part_num += 1
                except Exception as e:
                    logger.error(f"Error saving JSON file {filepath}: {str(e)}")
                    raise
        
        return files_created
