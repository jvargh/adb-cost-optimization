"""
Unity Catalog Scanner Module for Databricks Workspace Discovery.
Scans Unity Catalog metastore including catalogs, schemas, and tables.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from databricks.sdk import WorkspaceClient
from .utils import safe_get_attribute

logger = logging.getLogger(__name__)


class UnityCatalogScanner:
    """
    Scanner for Unity Catalog objects.
    Extracts catalogs, schemas, tables, and volumes metadata.
    """
    
    def __init__(self, client: WorkspaceClient, config):
        """
        Initialize Unity Catalog scanner.
        
        Args:
            client: Authenticated Databricks WorkspaceClient
            config: Scan configuration object
        """
        self.client = client
        self.config = config
        self.warehouse_id = None
    
    def scan(self) -> Dict[str, Any]:
        """
        Scan Unity Catalog objects in the workspace.
        
        Scan modes controlled by uc_scan parameter:
        - partial (default): Scans tables only with essential fields
        - complete: Scans catalogs, schemas, and tables with full metadata
        
        For simple scan: Returns tables and volumes with basic info
        For deep scan: Returns detailed metadata based on uc_scan mode
        
        Returns:
            Dictionary containing summary and tables (partial) or full hierarchy (complete)
        """
        logger.info(f"Starting Unity Catalog scan (mode: {self.config.uc_scan})...")
        
        # Partial scan (default): only tables with essential fields
        if self.config.is_uc_partial_scan():
            results = {
                'summary': {
                    'total_tables': 0,
                    'scan_mode': 'partial'
                },
                'tables': []
            }
        elif not self.config.is_deep_scan():
            # Simple scan: tables and volumes with basic info
            results = {
                'summary': {
                    'total_tables': 0,
                    'total_volumes': 0,
                    'scan_mode': 'simple'
                },
                'tables': [],
                'volumes': []
            }
        else:
            # Complete scan: full hierarchy
            results = {
                'summary': {
                    'total_catalogs': 0,
                    'total_schemas': 0,
                    'total_tables': 0,
                    'total_volumes': 0,
                    'scan_mode': 'complete'
                },
                'catalogs': [],
                'schemas': [],
                'tables': [],
                'volumes': []
            }
        
        try:
            # Get all catalogs, excluding system and internal catalogs
            all_catalogs = list(self.client.catalogs.list())
            
            # Filter out system catalogs (system, __databricks_internal, etc.)
            excluded_catalogs = {'system', '__databricks_internal'}
            catalogs = [
                cat for cat in all_catalogs 
                if cat.name.lower() not in excluded_catalogs
            ]
            
            logger.info(f"Found {len(catalogs)} user catalogs (excluding {len(all_catalogs) - len(catalogs)} system catalogs)")
            
            # Update summary for complete scan
            if self.config.is_uc_complete_scan() and self.config.is_deep_scan():
                results['summary']['total_catalogs'] = len(catalogs)
            
            for catalog in catalogs:
                try:
                    # Add catalog info only in complete scan mode
                    if self.config.is_uc_complete_scan() and self.config.is_deep_scan():
                        catalog_info = {
                            'catalog_name': catalog.name,
                            'catalog_type': safe_get_attribute(catalog, 'catalog_type.value'),
                            'comment': catalog.comment,
                            'created_at': self._format_timestamp(catalog.created_at),
                            'updated_at': self._format_timestamp(catalog.updated_at),
                            'owner': getattr(catalog, 'owner', None),
                        }
                        results['catalogs'].append(catalog_info)
                    
                    # Scan schemas in this catalog
                    self._scan_schemas(catalog.name, results)
                    
                    # Scan volumes only in complete scan mode or simple scan
                    if not self.config.is_uc_partial_scan():
                        self._scan_volumes(catalog.name, results)
                    
                except Exception as e:
                    logger.error(f"Error processing catalog {catalog.name}: {str(e)}")
            
            # Log summary based on scan mode
            if self.config.is_uc_partial_scan():
                logger.info(f"Unity Catalog scan complete: {results['summary']['total_tables']} tables")
            else:
                logger.info(f"Unity Catalog scan complete: {results['summary']['total_tables']} tables, "
                           f"{results['summary']['total_volumes']} volumes")
            
            return results
            
        except Exception as e:
            logger.error(f"Error scanning Unity Catalog: {str(e)}")
            return results
    
    def _scan_schemas(self, catalog_name: str, results: Dict[str, Any]):
        """Scan schemas in a catalog, excluding system schemas."""
        try:
            schemas = list(self.client.schemas.list(catalog_name=catalog_name))
            
            # Filter out system schemas (information_schema, etc.)
            excluded_schemas = {'information_schema'}
            filtered_schemas = [
                schema for schema in schemas 
                if schema.name.lower() not in excluded_schemas
            ]
            
            logger.debug(f"Found {len(filtered_schemas)} user schemas in catalog {catalog_name} "
                        f"(excluding {len(schemas) - len(filtered_schemas)} system schemas)")
            
            # Update summary for complete scan only
            if self.config.is_uc_complete_scan() and self.config.is_deep_scan():
                results['summary']['total_schemas'] += len(filtered_schemas)
            
            for schema in filtered_schemas:
                try:
                    # Add schema info only in complete scan mode
                    if self.config.is_uc_complete_scan() and self.config.is_deep_scan():
                        schema_info = {
                            'catalog_name': catalog_name,
                            'schema_name': schema.name,
                            'full_name': schema.full_name,
                            'comment': schema.comment,
                            'created_at': self._format_timestamp(schema.created_at),
                            'updated_at': self._format_timestamp(schema.updated_at),
                            'owner': getattr(schema, 'owner', None),
                        }
                        results['schemas'].append(schema_info)
                    
                    # Scan tables in this schema (all modes)
                    self._scan_tables(catalog_name, schema.name, results)
                    
                except Exception as e:
                    logger.debug(f"Error processing schema {schema.name}: {str(e)}")
                    
        except Exception as e:
            logger.debug(f"Error scanning schemas in catalog {catalog_name}: {str(e)}")
    
    def _scan_tables(self, catalog_name: str, schema_name: str, results: Dict[str, Any]):
        """
        Scan all tables in a schema.
        Simple scan: basic table info (table_name, schema_name, catalog_name, owner)
        Deep scan: comprehensive metadata with columns, partitions, etc.
        With collect_size_metrics enabled: processes tables in parallel batches of 3.
        """
        try:
            tables = list(self.client.tables.list(
                catalog_name=catalog_name,
                schema_name=schema_name
            ))
            
            logger.debug(f"Found {len(tables)} tables in {catalog_name}.{schema_name}")
            
            # Update summary
            results['summary']['total_tables'] += len(tables)
            
            # If size metrics collection is enabled, use parallel processing
            if self.config.collect_size_metrics and self.config.is_deep_scan():
                self._scan_tables_parallel(tables, catalog_name, schema_name, results)
            else:
                # Sequential processing (original behavior)
                for table in tables:
                    self._process_single_table(table, catalog_name, schema_name, results)
                    
        except Exception as e:
            logger.debug(f"Error scanning tables in {catalog_name}.{schema_name}: {str(e)}")
    
    def _scan_tables_parallel(self, tables: List, catalog_name: str, schema_name: str, results: Dict[str, Any]):
        """Process tables in parallel batches of 3 to collect size metrics efficiently."""
        import concurrent.futures
        import threading
        
        logger.info(f"Collecting size metrics for {len(tables)} tables in {catalog_name}.{schema_name} (parallel batches of 3)")
        
        # Thread-safe results collection
        lock = threading.Lock()
        
        def process_and_append(table):
            table_info = self._process_single_table_info(table, catalog_name, schema_name)
            if table_info:
                with lock:
                    results['tables'].append(table_info)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_table = {executor.submit(process_and_append, table): table for table in tables}
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_table):
                table = future_to_table[future]
                try:
                    future.result(timeout=30)
                    completed += 1
                    if completed % 10 == 0 or completed == len(tables):
                        logger.info(f"Progress: {completed}/{len(tables)} tables processed in {catalog_name}.{schema_name}")
                except Exception as e:
                    logger.error(f"Error processing table {table.name}: {str(e)}")
    
    def _process_single_table(self, table, catalog_name: str, schema_name: str, results: Dict[str, Any]):
        """Process a single table and append to results (sequential version)."""
        try:
            table_info = self._process_single_table_info(table, catalog_name, schema_name)
            if table_info:
                results['tables'].append(table_info)
        except Exception as e:
            logger.debug(f"Error processing table {table.name}: {str(e)}")
    
    def _process_single_table_info(self, table, catalog_name: str, schema_name: str) -> Optional[Dict[str, Any]]:
        """Extract table information - can be called sequentially or in parallel."""
        try:
            if self.config.is_uc_partial_scan():
                # Partial scan: essential table fields only
                table_info = {
                    'table_name': table.name,
                    'catalog_name': catalog_name,
                    'schema_name': schema_name,
                    'metastore_path': getattr(table, 'storage_location', None),
                    'table_type': safe_get_attribute(table, 'table_type.value'),
                    'data_source_format': safe_get_attribute(table, 'data_source_format.value'),
                    'owner': getattr(table, 'owner', None),
                    'created_at': self._format_timestamp(table.created_at),
                    'updated_at': self._format_timestamp(table.updated_at),
                    'created_by': getattr(table, 'created_by', None),
                    'updated_by': getattr(table, 'updated_by', None),
                    'partitions': self._get_table_partitions(catalog_name, schema_name, table.name),
                    'properties': getattr(table, 'properties', {}),
                }
            elif not self.config.is_deep_scan():
                # Simple scan: basic table info only
                table_info = {
                    'table_name': table.name,
                    'schema_name': schema_name,
                    'catalog_name': catalog_name,
                    'owner': getattr(table, 'owner', None),
                }
            else:
                # Deep scan: comprehensive table metadata
                columns = self._get_table_columns(table)
                partitions = self._get_table_partitions(catalog_name, schema_name, table.name)
                
                # Get comprehensive details from DESCRIBE DETAIL if enabled (can be slow for many tables)
                describe_details = {}
                table_type = safe_get_attribute(table, 'table_type.value')
                if self.config.collect_size_metrics and table_type in ['MANAGED', 'EXTERNAL']:
                    describe_details = self._get_table_size_metrics(catalog_name, schema_name, table.name)
                
                # Calculate derived metrics
                days_since_update = self._calculate_staleness(table.updated_at)
                
                # Extract Delta Lake features from properties (lightweight)
                properties_dict = getattr(table, 'properties', {})
                delta_features = self._extract_delta_features(properties_dict) if properties_dict else {}
                
                table_info = {
                    'table_name': table.name,
                    'schema_name': schema_name,
                    'catalog_name': catalog_name,
                    'full_name': table.full_name,
                    'metastore_path': getattr(table, 'storage_location', None),
                    'table_type': table_type,
                    'data_source_format': safe_get_attribute(table, 'data_source_format.value'),
                    'owner': getattr(table, 'owner', None),
                    'created_at': self._format_timestamp(table.created_at),
                    'updated_at': self._format_timestamp(table.updated_at),
                    'created_by': getattr(table, 'created_by', None),
                    'updated_by': getattr(table, 'updated_by', None),
                    'comment': table.comment,
                    'columns': columns,
                    'partitions': partitions,
                    'properties': getattr(table, 'properties', {}),
                    'table_id': getattr(table, 'table_id', None),
                    'delta_runtime_properties_kvpairs': getattr(table, 'delta_runtime_properties_kvpairs', None),
                    'enable_predictive_optimization': getattr(table, 'enable_predictive_optimization', None),
                    'sql_path': getattr(table, 'sql_path', None),
                    'view_definition': getattr(table, 'view_definition', None),
                    # DESCRIBE DETAIL metrics (actual table data)
                    'num_files': describe_details.get('num_files'),
                    'size_bytes': describe_details.get('size_bytes'),
                    'num_rows': describe_details.get('num_rows'),  # Note: DESCRIBE DETAIL doesn't return numRows for all tables
                    'describe_detail_created_at': describe_details.get('created_at'),
                    'describe_detail_last_modified': describe_details.get('last_modified'),
                    'describe_detail_location': describe_details.get('location'),
                    'describe_detail_format': describe_details.get('format'),
                    'describe_detail_partition_columns': describe_details.get('partition_columns'),
                    'describe_detail_min_reader_version': describe_details.get('min_reader_version'),
                    'describe_detail_min_writer_version': describe_details.get('min_writer_version'),
                    'describe_detail_table_features': describe_details.get('table_features'),
                    # Derived metrics
                    'column_count': len(columns),
                    'partition_count': len(partitions) if partitions else 0,
                    'is_partitioned': bool(partitions),
                    'days_since_last_update': days_since_update,
                    # Delta Lake features from properties (lightweight extraction)
                    'delta_features': delta_features
                }
            
            return table_info
        except Exception as e:
            logger.debug(f"Error processing table {table.name}: {str(e)}")
            return None
                    
        except Exception as e:
            logger.debug(f"Error scanning tables in {catalog_name}.{schema_name}: {str(e)}")
    
    def _get_table_columns(self, table) -> List[Dict[str, Any]]:
        """Extract column information from table metadata."""
        columns = []
        try:
            if hasattr(table, 'columns') and table.columns:
                for col in table.columns:
                    column_info = {
                        'name': col.name,
                        'type_name': safe_get_attribute(col, 'type_name.value') if hasattr(col, 'type_name') else str(getattr(col, 'type_text', None)),
                        'type_text': getattr(col, 'type_text', None),
                        'position': getattr(col, 'position', None),
                        'comment': getattr(col, 'comment', None),
                        'nullable': getattr(col, 'nullable', None),
                        'partition_index': getattr(col, 'partition_index', None),
                    }
                    columns.append(column_info)
        except Exception as e:
            logger.debug(f"Error extracting columns: {str(e)}")
        
        return columns
    
    def _get_table_partitions(self, catalog_name: str, schema_name: str, table_name: str) -> Optional[List[str]]:
        """Get partition columns for a table."""
        try:
            # Get table details to check for partitions
            table_details = self.client.tables.get(
                full_name=f"{catalog_name}.{schema_name}.{table_name}"
            )
            
            partition_columns = []
            if hasattr(table_details, 'columns') and table_details.columns:
                for col in table_details.columns:
                    if hasattr(col, 'partition_index') and col.partition_index is not None:
                        partition_columns.append(col.name)
            
            return partition_columns if partition_columns else None
            
        except Exception as e:
            logger.debug(f"Error getting partitions for {catalog_name}.{schema_name}.{table_name}: {str(e)}")
            return None
    
    def _scan_volumes(self, catalog_name: str, results: Dict[str, Any]):
        """
        Scan volumes in a catalog.
        Simple scan: basic volume info (volume_name, schema_name, catalog_name, owner, volume_type)
        Deep scan: comprehensive volume metadata
        """
        try:
            # Get all schemas in catalog to scan volumes
            schemas = list(self.client.schemas.list(catalog_name=catalog_name))
            
            # Filter out system schemas
            excluded_schemas = {'information_schema'}
            filtered_schemas = [
                schema for schema in schemas 
                if schema.name.lower() not in excluded_schemas
            ]
            
            for schema in filtered_schemas:
                try:
                    volumes = list(self.client.volumes.list(
                        catalog_name=catalog_name,
                        schema_name=schema.name
                    ))
                    
                    logger.debug(f"Found {len(volumes)} volumes in {catalog_name}.{schema.name}")
                    
                    # Update summary
                    results['summary']['total_volumes'] += len(volumes)
                    
                    for volume in volumes:
                        try:
                            if not self.config.is_deep_scan():
                                # Simple scan: basic volume info
                                volume_info = {
                                    'volume_name': volume.name,
                                    'schema_name': schema.name,
                                    'catalog_name': catalog_name,
                                    'owner': getattr(volume, 'owner', None),
                                    'volume_type': safe_get_attribute(volume, 'volume_type.value'),
                                }
                            else:
                                # Deep scan: comprehensive volume metadata
                                volume_info = {
                                    'volume_name': volume.name,
                                    'schema_name': schema.name,
                                    'catalog_name': catalog_name,
                                    'full_name': volume.full_name,
                                    'owner': getattr(volume, 'owner', None),
                                    'volume_type': safe_get_attribute(volume, 'volume_type.value'),
                                    'storage_location': getattr(volume, 'storage_location', None),
                                    'comment': getattr(volume, 'comment', None),
                                    'created_at': self._format_timestamp(getattr(volume, 'created_at', None)),
                                    'updated_at': self._format_timestamp(getattr(volume, 'updated_at', None)),
                                    'created_by': getattr(volume, 'created_by', None),
                                    'updated_by': getattr(volume, 'updated_by', None),
                                    'volume_id': getattr(volume, 'volume_id', None),
                                }
                            
                            results['volumes'].append(volume_info)
                            
                        except Exception as e:
                            logger.debug(f"Error processing volume {volume.name}: {str(e)}")
                            
                except Exception as e:
                    logger.debug(f"Error scanning volumes in {catalog_name}.{schema.name}: {str(e)}")
                    
        except Exception as e:
            logger.debug(f"Error scanning volumes in catalog {catalog_name}: {str(e)}")
    
    def _get_warehouse_id(self) -> Optional[str]:
        """Get a SQL warehouse ID for running queries."""
        if self.warehouse_id:
            return self.warehouse_id
        
        try:
            warehouses = list(self.client.warehouses.list())
            
            # Look for serverless warehouses first
            for warehouse in warehouses:
                if (hasattr(warehouse, 'enable_serverless_compute') and 
                    warehouse.enable_serverless_compute):
                    self.warehouse_id = warehouse.id
                    return self.warehouse_id
            
            # Fallback to any running warehouse
            for warehouse in warehouses:
                if warehouse.state and warehouse.state.value == 'RUNNING':
                    self.warehouse_id = warehouse.id
                    return self.warehouse_id
            
            # Fallback to first available warehouse
            if warehouses:
                self.warehouse_id = warehouses[0].id
                return self.warehouse_id
            
            return None
        except Exception as e:
            logger.debug(f"Error getting warehouse ID: {str(e)}")
            return None
    
    def _format_timestamp(self, timestamp) -> Optional[str]:
        """
        Convert timestamp to dd/mm/yyyy format.
        
        Args:
            timestamp: Timestamp in milliseconds or seconds
            
        Returns:
            Formatted date string in dd/mm/yyyy format or None
        """
        if timestamp:
            try:
                # Handle both timestamp in milliseconds and seconds
                if timestamp > 10000000000:  # Likely milliseconds
                    dt = datetime.fromtimestamp(timestamp / 1000)
                else:  # Likely seconds
                    dt = datetime.fromtimestamp(timestamp)
                return dt.strftime('%d/%m/%Y')
            except Exception as e:
                logger.debug(f"Error formatting timestamp: {str(e)}")
                return None
        return None
    
    def _calculate_staleness(self, updated_at) -> Optional[int]:
        """Calculate days since last update."""
        if updated_at:
            try:
                now = datetime.now()
                # Handle both timestamp in milliseconds and seconds
                if updated_at > 10000000000:  # Likely milliseconds
                    updated = datetime.fromtimestamp(updated_at / 1000)
                else:  # Likely seconds
                    updated = datetime.fromtimestamp(updated_at)
                return (now - updated).days
            except Exception as e:
                logger.debug(f"Error calculating staleness: {str(e)}")
                return None
        return None
    
    def _get_table_size_metrics(self, catalog_name: str, schema_name: str, table_name: str) -> Dict[str, Any]:
        """Get comprehensive table details using DESCRIBE DETAIL.
        
        Extracts all available fields from DESCRIBE DETAIL including:
        - Size metrics: numFiles, sizeInBytes, numRows
        - Timestamps: createdAt, lastModified
        - Location and format information
        - Partitioning details
        - Delta Lake metadata
        """
        try:
            warehouse_id = self._get_warehouse_id()
            if not warehouse_id:
                logger.debug(f"No warehouse available for DESCRIBE DETAIL")
                return {}
            
            # Log progress
            logger.debug(f"Collecting DESCRIBE DETAIL for {catalog_name}.{schema_name}.{table_name}")
            
            query = f"DESCRIBE DETAIL `{catalog_name}`.`{schema_name}`.`{table_name}`"
            
            # Use shorter timeout to avoid hanging
            result = self.client.statement_execution.execute_statement(
                statement=query,
                warehouse_id=warehouse_id,
                wait_timeout="30s"
            )
            
            # Extract data from result
            details = {}
            
            # Define fields to extract from DESCRIBE DETAIL
            # Format: (column_name, target_key, converter_function)
            fields_to_extract = [
                ('format', 'format', str),
                ('id', 'table_id', str),
                ('name', 'name', str),
                ('description', 'description', str),
                ('location', 'location', str),
                ('createdAt', 'created_at', self._safe_timestamp),
                ('lastModified', 'last_modified', self._safe_timestamp),
                ('partitionColumns', 'partition_columns', str),
                ('numFiles', 'num_files', self._safe_int),
                ('sizeInBytes', 'size_bytes', self._safe_int),
                ('properties', 'properties', str),
                ('minReaderVersion', 'min_reader_version', self._safe_int),
                ('minWriterVersion', 'min_writer_version', self._safe_int),
                ('tableFeatures', 'table_features', str),
            ]
            
            if isinstance(result, dict):
                result_data = result.get('result')
                if result_data:
                    # Get schema to find column indices
                    schema = result_data.get('schema', {})
                    columns = schema.get('columns', [])
                    
                    # Build column name to index mapping
                    col_index_map = {col.get('name', ''): idx for idx, col in enumerate(columns)}
                    
                    data_array = result_data.get('data_array', [])
                    if data_array and len(data_array) > 0:
                        row = data_array[0]
                        
                        # Extract all defined fields
                        for col_name, target_key, converter in fields_to_extract:
                            if col_name in col_index_map:
                                idx = col_index_map[col_name]
                                if idx < len(row) and row[idx] is not None:
                                    details[target_key] = converter(row[idx])
            else:
                # Handle object response (StatementResponse)
                if result and hasattr(result, 'result') and result.result:
                    # Get schema from manifest
                    schema = None
                    if hasattr(result, 'manifest') and hasattr(result.manifest, 'schema'):
                        schema = result.manifest.schema
                    
                    # Build column name to index mapping
                    col_index_map = {}
                    if schema and hasattr(schema, 'columns'):
                        for idx, col in enumerate(schema.columns):
                            col_name = col.name if hasattr(col, 'name') else ''
                            if col_name:
                                col_index_map[col_name] = idx
                    
                    if hasattr(result.result, 'data_array') and result.result.data_array:
                        if len(result.result.data_array) > 0:
                            row = result.result.data_array[0]
                            
                            # Extract all defined fields
                            for col_name, target_key, converter in fields_to_extract:
                                if col_name in col_index_map:
                                    idx = col_index_map[col_name]
                                    if idx < len(row) and row[idx] is not None:
                                        details[target_key] = converter(row[idx])
                            
                            # Log what we found
                            if details:
                                logger.debug(f"  -> Extracted {len(details)} fields from DESCRIBE DETAIL")
            
            if not details:
                logger.warning(f"No details extracted from DESCRIBE DETAIL for {catalog_name}.{schema_name}.{table_name}")
            
            return details
        except Exception as e:
            logger.warning(f"Error getting DESCRIBE DETAIL for {catalog_name}.{schema_name}.{table_name}: {str(e)}")
            return {}
    
    def _extract_delta_features(self, properties: Dict[str, str]) -> Dict[str, Any]:
        """
        Extract useful Delta Lake features from table properties.
        
        This is a lightweight extraction focused only on Delta Lake metadata
        that is commonly populated and useful for analysis.
        
        Args:
            properties: Table properties dictionary
            
        Returns:
            Dictionary with Delta Lake features
        """
        if not properties:
            return {}
        
        features = {}
        
        # Extract Delta Lake metadata that is commonly populated
        last_commit = properties.get('delta.lastCommitTimestamp')
        if last_commit:
            features['last_commit_timestamp'] = self._format_timestamp(self._safe_int(last_commit))
        
        last_version = properties.get('delta.lastUpdateVersion')
        if last_version:
            features['last_update_version'] = self._safe_int(last_version)
        
        # Delta Lake version information
        min_reader = properties.get('delta.minReaderVersion')
        if min_reader:
            features['min_reader_version'] = self._safe_int(min_reader)
        
        min_writer = properties.get('delta.minWriterVersion')
        if min_writer:
            features['min_writer_version'] = self._safe_int(min_writer)
        
        # Feature flags
        if properties.get('delta.enableDeletionVectors') == 'true':
            features['deletion_vectors_enabled'] = True
        
        if 'delta.feature.appendOnly' in properties:
            features['append_only'] = True
        
        if 'delta.feature.invariants' in properties:
            features['invariants_supported'] = True
        
        if 'delta.enableChangeDataFeed' in properties:
            features['change_data_feed_enabled'] = properties.get('delta.enableChangeDataFeed') == 'true'
        
        # Liquid clustering
        if 'delta.feature.clustering' in properties:
            features['clustering_enabled'] = True
        
        return features
    
    def _safe_int(self, value: Any) -> Optional[int]:
        """Safely convert value to int."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    
    def _safe_timestamp(self, value: Any) -> Optional[str]:
        """Safely convert timestamp string to formatted date string (dd/mm/yyyy)."""
        if value is None:
            return None
        try:
            timestamp_int = int(value)
            return self._format_timestamp(timestamp_int)
        except (ValueError, TypeError):
            return None
    
    def flatten_for_csv(self, catalog_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Flatten Unity Catalog data for CSV export.
        Creates one row per column per table (column-level denormalization).
        Same structure for both simple and deep scan.
        
        Args:
            catalog_data: Dictionary from scan() containing tables
            
        Returns:
            List of flattened dictionaries with 14 columns
        """
        flattened = []
        
        # Handle both simple and deep scan structures
        tables = catalog_data.get('tables', [])
        
        for table in tables:
            table_name = table.get('table_name')
            table_type = table.get('table_type')
            catalog_name = table.get('catalog_name')
            schema_name = table.get('schema_name')
            created_at = table.get('created_at')
            updated_at = table.get('updated_at')
            created_by = table.get('created_by')
            updated_by = table.get('updated_by')
            
            # Get enhanced metrics (deep scan only)
            num_files = table.get('num_files')
            size_bytes = table.get('size_bytes')
            column_count = table.get('column_count')
            partition_count = table.get('partition_count')
            is_partitioned = table.get('is_partitioned')
            days_since_last_update = table.get('days_since_last_update')
            owner = table.get('owner')
            data_source_format = table.get('data_source_format')
            
            # Get columns if available
            columns = table.get('columns', [])
            
            if columns:
                # One row per column
                for column in columns:
                    flattened.append({
                        'table_name': table_name,
                        'catalog_name': catalog_name,
                        'schema_name': schema_name,
                        'owner': owner,
                        'table_type': table_type,
                        'data_source_format': data_source_format,
                        'created_at': created_at,
                        'updated_at': updated_at,
                        'created_by': created_by,
                        'updated_by': updated_by,
                        'column_name': column.get('name'),
                        'column_type': column.get('type_name'),
                        'column_position': column.get('position'),
                        'nullable': column.get('nullable'),
                        'comment': column.get('comment'),
                        'partition_index': column.get('partition_index'),
                        # Enhanced metrics
                        'num_files': num_files,
                        'size_bytes': size_bytes,
                        'size_gb': round(size_bytes / (1024**3), 2) if size_bytes else None,
                        'column_count': column_count,
                        'partition_count': partition_count,
                        'is_partitioned': is_partitioned,
                        'days_since_last_update': days_since_last_update
                    })
            else:
                # Table has no columns, create single row with table info
                flattened.append({
                    'table_name': table_name,
                    'catalog_name': catalog_name,
                    'schema_name': schema_name,
                    'owner': owner,
                    'table_type': table_type,
                    'data_source_format': data_source_format,
                    'created_at': created_at,
                    'updated_at': updated_at,
                    'created_by': created_by,
                    'updated_by': updated_by,
                    'column_name': None,
                    'column_type': None,
                    'column_position': None,
                    'nullable': None,
                    'comment': None,
                    'partition_index': None,
                    # Enhanced metrics
                    'num_files': num_files,
                    'size_bytes': size_bytes,
                    'size_gb': round(size_bytes / (1024**3), 2) if size_bytes else None,
                    'column_count': column_count,
                    'partition_count': partition_count,
                    'is_partitioned': is_partitioned,
                    'days_since_last_update': days_since_last_update
                })
        
        return flattened

