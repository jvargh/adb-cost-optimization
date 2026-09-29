"""
Pipeline Scanner Module for Databricks Workspace Discovery.
Scans Delta Live Tables (DLT) pipelines and their configurations.
"""

import logging
from typing import Dict, List, Any
from databricks.sdk import WorkspaceClient
from .utils import safe_get_attribute

logger = logging.getLogger(__name__)


class PipelineScanner:
    """
    Scanner for Delta Live Tables pipelines.
    Extracts pipeline configurations, settings, and state information.
    """
    
    def __init__(self, client: WorkspaceClient, config):
        """
        Initialize pipeline scanner.
        
        Args:
            client: Authenticated Databricks WorkspaceClient
            config: Scan configuration object
        """
        self.client = client
        self.config = config
    
    def scan(self) -> Dict[str, Any]:
        """
        Scan all Delta Live Tables pipelines in the workspace.
        
        For simple scan: Returns summary with pipeline count and basic pipeline info
        For deep scan: Returns detailed pipeline configurations with recent updates
        
        Returns:
            Dictionary with summary and pipelines list (simple) or just pipelines list (deep)
        """
        logger.info("Starting pipeline scan...")
        
        pipelines = []
        
        try:
            # Get all pipelines
            all_pipelines = list(self.client.pipelines.list_pipelines())
            logger.info(f"Found {len(all_pipelines)} pipelines")
            
            for pipeline in all_pipelines:
                try:
                    pipeline_info = self._process_pipeline(pipeline)
                    if pipeline_info:
                        pipelines.append(pipeline_info)
                except Exception as e:
                    logger.error(f"Error processing pipeline {pipeline.pipeline_id}: {str(e)}")
            
            logger.info(f"Pipeline scan complete: {len(pipelines)} pipelines processed")
            
            # For simple scan, return with summary
            if not self.config.is_deep_scan():
                return {
                    'summary': {
                        'total_pipelines': len(all_pipelines)
                    },
                    'pipelines': pipelines
                }
            
            # For deep scan, return just the list (backward compatibility)
            return pipelines
            
        except Exception as e:
            logger.error(f"Error scanning pipelines: {str(e)}")
            if not self.config.is_deep_scan():
                return {
                    'summary': {'total_pipelines': 0},
                    'pipelines': []
                }
            return pipelines
    
    def _process_pipeline(self, pipeline) -> Dict[str, Any]:
        """
        Process a single pipeline and extract metadata.
        
        Args:
            pipeline: Pipeline object from Databricks SDK
            
        Returns:
            Dictionary containing pipeline metadata
        """
        pipeline_info = {
            'pipeline_id': pipeline.pipeline_id,
            'name': pipeline.name,
            'state': safe_get_attribute(pipeline, 'state.value'),
            'creator_user_name': getattr(pipeline, 'creator_user_name', None),
            'creation_time': getattr(pipeline, 'creation_time', None),
        }
        
        # Add storage location
        if hasattr(pipeline, 'storage'):
            pipeline_info['storage'] = pipeline.storage
        
        # Add cluster configuration
        if hasattr(pipeline, 'cluster') and pipeline.cluster:
            cluster_info = {}
            for attr in ['num_workers', 'node_type_id', 'driver_node_type_id', 
                         'instance_pool_id', 'autoscale', 'spark_version']:
                if hasattr(pipeline.cluster, attr):
                    value = getattr(pipeline.cluster, attr)
                    if value is not None:
                        # Handle autoscale object
                        if attr == 'autoscale' and hasattr(value, 'min_workers'):
                            cluster_info[attr] = {
                                'min_workers': value.min_workers,
                                'max_workers': value.max_workers
                            }
                        else:
                            cluster_info[attr] = value
            
            if cluster_info:
                pipeline_info['cluster'] = cluster_info
        
        # Add continuous mode setting
        if hasattr(pipeline, 'continuous'):
            pipeline_info['continuous'] = pipeline.continuous
        
        # Add development mode setting
        if hasattr(pipeline, 'development'):
            pipeline_info['development'] = pipeline.development
        
        # Add photon enabled
        if hasattr(pipeline, 'photon'):
            pipeline_info['photon'] = pipeline.photon
        
        # Add channel (current/preview)
        if hasattr(pipeline, 'channel'):
            pipeline_info['channel'] = pipeline.channel
        
        # Add edition (core/pro/advanced)
        if hasattr(pipeline, 'edition'):
            pipeline_info['edition'] = pipeline.edition
        
        # Add library configurations
        if hasattr(pipeline, 'libraries') and pipeline.libraries:
            libraries = []
            for lib in pipeline.libraries:
                lib_info = {}
                if hasattr(lib, 'notebook') and lib.notebook:
                    lib_info['type'] = 'notebook'
                    lib_info['path'] = lib.notebook.path
                elif hasattr(lib, 'file') and lib.file:
                    lib_info['type'] = 'file'
                    lib_info['path'] = lib.file.path
                elif hasattr(lib, 'jar'):
                    lib_info['type'] = 'jar'
                    lib_info['path'] = lib.jar
                elif hasattr(lib, 'maven'):
                    lib_info['type'] = 'maven'
                    lib_info['coordinates'] = lib.maven.coordinates
                
                if lib_info:
                    libraries.append(lib_info)
            
            if libraries:
                pipeline_info['libraries'] = libraries
        
        # Add target schema/catalog
        if hasattr(pipeline, 'target'):
            pipeline_info['target'] = pipeline.target
        
        if hasattr(pipeline, 'catalog'):
            pipeline_info['catalog'] = pipeline.catalog
        
        # Add filters for change data capture
        if hasattr(pipeline, 'filters') and pipeline.filters:
            pipeline_info['filters'] = {
                'include': pipeline.filters.include if hasattr(pipeline.filters, 'include') else None,
                'exclude': pipeline.filters.exclude if hasattr(pipeline.filters, 'exclude') else None
            }
        
        # For deep scan, add update history
        if self.config.is_deep_scan():
            try:
                updates = self._get_pipeline_updates(pipeline.pipeline_id)
                if updates:
                    pipeline_info['recent_updates'] = updates
            except Exception as e:
                logger.debug(f"Could not fetch updates for pipeline {pipeline.pipeline_id}: {str(e)}")
        
        return pipeline_info
    
    def _get_pipeline_updates(self, pipeline_id: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent pipeline update history (for deep scans).
        
        Args:
            pipeline_id: Pipeline ID
            max_results: Maximum number of updates to retrieve
            
        Returns:
            List of recent pipeline updates
        """
        updates = []
        
        try:
            # Get pipeline updates
            all_updates = list(self.client.pipelines.list_pipeline_updates(pipeline_id=pipeline_id))
            
            # Limit to most recent updates
            recent_updates = all_updates[:max_results]
            
            for update in recent_updates:
                update_info = {
                    'update_id': update.update_id,
                    'state': safe_get_attribute(update, 'state.value'),
                    'creation_time': update.creation_time,
                }
                
                # Add cause if available
                if hasattr(update, 'cause'):
                    update_info['cause'] = safe_get_attribute(update, 'cause.value')
                
                # Add full refresh flag
                if hasattr(update, 'full_refresh'):
                    update_info['full_refresh'] = update.full_refresh
                
                updates.append(update_info)
            
        except Exception as e:
            logger.debug(f"Error fetching pipeline updates: {str(e)}")
        
        return updates
    
    def flatten_for_csv(self, pipelines_data) -> List[Dict[str, Any]]:
        """
        Flatten pipeline data for CSV export.
        For simple scans: One row per pipeline.
        For deep scans: One row per update per pipeline (update-level denormalization).
        
        Args:
            pipelines_data: List of pipeline dictionaries from scan() or dict with 'pipelines' key
            
        Returns:
            List of flattened dictionaries suitable for CSV export
        """
        flattened = []
        
        # Handle both list and dict input
        if isinstance(pipelines_data, dict):
            pipelines = pipelines_data.get('pipelines', [])
        else:
            pipelines = pipelines_data
        
        for pipeline in pipelines:
            if self.config.is_deep_scan():
                # Deep scan: 18 columns denormalized by update
                pipeline_id = pipeline.get('pipeline_id')
                pipeline_name = pipeline.get('name')
                creator_user_name = pipeline.get('creator_user_name')
                state = pipeline.get('state')
                catalog = pipeline.get('catalog')
                target = pipeline.get('target')
                storage = pipeline.get('storage')
                
                cluster = pipeline.get('cluster', {})
                cluster_label = cluster.get('label') if cluster else None
                cluster_node_type = cluster.get('node_type_id') if cluster else None
                cluster_num_workers = cluster.get('num_workers') if cluster else None
                cluster_spark_version = cluster.get('spark_version') if cluster else None
                cluster_policy_id = cluster.get('policy_id') if cluster else None
                
                updates = pipeline.get('recent_updates', [])
                total_updates = len(updates)
                
                if updates:
                    # One row per update
                    for update_idx, update in enumerate(updates, 1):
                        is_latest = (update_idx == 1)
                        flattened.append({
                            'pipeline_id': pipeline_id,
                            'pipeline_name': pipeline_name,
                            'creator_user_name': creator_user_name,
                            'state': state,
                            'catalog': catalog,
                            'target': target,
                            'storage': storage,
                            'cluster_label': cluster_label,
                            'cluster_node_type': cluster_node_type,
                            'cluster_num_workers': cluster_num_workers,
                            'cluster_spark_version': cluster_spark_version,
                            'cluster_policy_id': cluster_policy_id,
                            'total_updates': total_updates,
                            'update_number': update_idx,
                            'update_id': update.get('update_id'),
                            'creation_time': update.get('creation_time'),
                            'update_state': update.get('state'),
                            'is_latest_update': is_latest
                        })
                else:
                    # No updates, create single row
                    flattened.append({
                        'pipeline_id': pipeline_id,
                        'pipeline_name': pipeline_name,
                        'creator_user_name': creator_user_name,
                        'state': state,
                        'catalog': catalog,
                        'target': target,
                        'storage': storage,
                        'cluster_label': cluster_label,
                        'cluster_node_type': cluster_node_type,
                        'cluster_num_workers': cluster_num_workers,
                        'cluster_spark_version': cluster_spark_version,
                        'cluster_policy_id': cluster_policy_id,
                        'total_updates': 0,
                        'update_number': None,
                        'update_id': None,
                        'creation_time': None,
                        'update_state': None,
                        'is_latest_update': None
                    })
            else:
                # Simple scan: 5 columns, one row per pipeline
                flattened.append({
                    'pipeline_id': pipeline.get('pipeline_id'),
                    'pipeline_name': pipeline.get('name'),
                    'creator_user_name': pipeline.get('creator_user_name'),
                    'state': pipeline.get('state'),
                    'catalog': pipeline.get('catalog')
                })
        
        return flattened
