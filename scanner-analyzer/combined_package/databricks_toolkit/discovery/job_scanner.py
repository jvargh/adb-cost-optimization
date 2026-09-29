"""
Job Scanner Module for Databricks Workspace Discovery.
Scans and extracts metadata from Databricks jobs.
"""

import logging
import concurrent.futures
from typing import Dict, List, Any, Optional
from databricks.sdk import WorkspaceClient
from .utils import safe_get_attribute, retry_with_backoff, format_epoch_timestamp

logger = logging.getLogger(__name__)


class JobScanner:
    """
    Scanner for Databricks jobs.
    Extracts job configurations, schedules, and execution metadata.
    """
    
    def __init__(self, client: WorkspaceClient, config):
        """
        Initialize job scanner.
        
        Args:
            client: Authenticated Databricks WorkspaceClient
            config: Scan configuration object
        """
        self.client = client
        self.config = config
        self.max_workers = config.max_workers
    
    def scan(self) -> Dict[str, Any]:
        """
        Scan all jobs in the workspace.
        
        Returns:
            Dictionary with total count and list of job metadata
        """
        logger.info("Starting jobs scan...")
        
        try:
            # Get all jobs
            all_jobs = list(self.client.jobs.list())
            total_count = len(all_jobs)
            logger.info(f"Found {total_count} jobs to scan")
            
            if not all_jobs:
                return {
                    'total_count': 0,
                    'jobs': []
                }
            
            # Process jobs in parallel
            jobs_data = []
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_job = {
                    executor.submit(self._process_job, job): job 
                    for job in all_jobs
                }
                
                for future in concurrent.futures.as_completed(future_to_job):
                    try:
                        job_data = future.result(timeout=120)
                        if job_data:
                            jobs_data.append(job_data)
                    except Exception as e:
                        job = future_to_job[future]
                        logger.error(f"Error processing job {job.job_id}: {str(e)}")
            
            logger.info(f"Successfully scanned {len(jobs_data)} jobs")
            
            return {
                'total_count': total_count,
                'jobs': jobs_data
            }
            
        except Exception as e:
            logger.error(f"Error scanning jobs: {str(e)}")
            return {
                'total_count': 0,
                'jobs': []
            }
    
    def flatten_for_csv(self, jobs_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Flatten job data for CSV export.
        For deep scans: Creates one row per task per run combination (fully denormalized).
        For simple scans: One row per job.
        
        Args:
            jobs_data: List of job dictionaries from scan()
            
        Returns:
            List of flattened dictionaries suitable for CSV export
        """
        flattened = []
        
        for job in jobs_data:
            if self.config.is_deep_scan():
                # Deep scan: Fully denormalized (one row per task per run)
                flattened.extend(self._flatten_deep_scan_job(job))
            else:
                # Simple scan: One row per job
                flattened.append({
                    'job_id': job.get('job_id'),
                    'job_name': job.get('job_name'),
                    'creator_user_name': job.get('creator_user_name'),
                    'max_concurrent_runs': job.get('max_concurrent_runs')
                })
        
        return flattened
    
    def _flatten_deep_scan_job(self, job: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Flatten a deep scan job into multiple rows (one per task per run).
        
        Args:
            job: Job dictionary from _process_job
            
        Returns:
            List of flattened row dictionaries
        """
        rows = []
        
        # Extract basic job info
        job_id = job.get('job_id')
        job_name = job.get('job_name')
        created_time = job.get('created_time')
        creator_user_name = job.get('creator_user_name')
        timeout_seconds = job.get('timeout_seconds')
        max_concurrent_runs = job.get('max_concurrent_runs')
        format_val = job.get('format')
        
        # Extract schedule info
        schedule = job.get('schedule', {})
        schedule_cron = schedule.get('cron_expression') if schedule else None
        schedule_timezone = schedule.get('timezone_id') if schedule else None
        schedule_pause = schedule.get('pause_status') if schedule else None
        
        # Extract email notification counts
        email_notif = job.get('email_notifications', {})
        email_success_count = len(email_notif.get('on_success', [])) if email_notif else 0
        email_failure_count = len(email_notif.get('on_failure', [])) if email_notif else 0
        email_start_count = len(email_notif.get('on_start', [])) if email_notif else 0
        
        # Get tasks and runs
        tasks = job.get('tasks', [])
        runs = job.get('recent_runs', [])
        
        total_tasks = len(tasks)
        total_runs = len(runs)
        
        # If no tasks and no runs, create single row with job info only
        if not tasks and not runs:
            rows.append(self._create_csv_row(
                job_id, job_name, created_time, creator_user_name, timeout_seconds,
                max_concurrent_runs, format_val, schedule_cron, schedule_timezone, schedule_pause,
                email_success_count, email_failure_count, email_start_count,
                total_tasks, None, None, None, None, None, None, None,
                total_runs, None, None, None, None, None, None, None, None, None
            ))
            return rows
        
        # If no tasks but has runs, create one row per run
        if not tasks and runs:
            for run_idx, run in enumerate(runs, 1):
                is_latest = (run_idx == 1)
                duration_ms = self._calculate_duration(run.get('start_time'), run.get('end_time'))
                
                rows.append(self._create_csv_row(
                    job_id, job_name, created_time, creator_user_name, timeout_seconds,
                    max_concurrent_runs, format_val, schedule_cron, schedule_timezone, schedule_pause,
                    email_success_count, email_failure_count, email_start_count,
                    total_tasks, None, None, None, None, None, None, None,
                    total_runs, run_idx, run.get('run_id'), run.get('start_time'),
                    run.get('end_time'), run.get('state'), run.get('result_state'),
                    run.get('cluster_id'), duration_ms, is_latest
                ))
            return rows
        
        # If has tasks but no runs, create one row per task
        if tasks and not runs:
            for task_idx, task in enumerate(tasks, 1):
                rows.append(self._create_csv_row(
                    job_id, job_name, created_time, creator_user_name, timeout_seconds,
                    max_concurrent_runs, format_val, schedule_cron, schedule_timezone, schedule_pause,
                    email_success_count, email_failure_count, email_start_count,
                    total_tasks, task_idx, task.get('task_key'), task.get('description'),
                    task.get('timeout_seconds'), task.get('max_retries'), task.get('cluster_type'),
                    self._get_task_cluster_info(task),
                    total_runs, None, None, None, None, None, None, None, None, None
                ))
            return rows
        
        # Has both tasks and runs: Create one row per task per run (fully denormalized)
        for task_idx, task in enumerate(tasks, 1):
            task_cluster_info = self._get_task_cluster_info(task)
            
            for run_idx, run in enumerate(runs, 1):
                is_latest = (run_idx == 1)
                duration_ms = self._calculate_duration(run.get('start_time'), run.get('end_time'))
                
                rows.append(self._create_csv_row(
                    job_id, job_name, created_time, creator_user_name, timeout_seconds,
                    max_concurrent_runs, format_val, schedule_cron, schedule_timezone, schedule_pause,
                    email_success_count, email_failure_count, email_start_count,
                    total_tasks, task_idx, task.get('task_key'), task.get('description'),
                    task.get('timeout_seconds'), task.get('max_retries'), task.get('cluster_type'),
                    task_cluster_info,
                    total_runs, run_idx, run.get('run_id'), run.get('start_time'),
                    run.get('end_time'), run.get('state'), run.get('result_state'),
                    run.get('cluster_id'), duration_ms, is_latest
                ))
        
        return rows
    
    def _create_csv_row(self, job_id, job_name, created_time, creator_user_name, timeout_seconds,
                        max_concurrent_runs, format_val, schedule_cron, schedule_timezone, schedule_pause,
                        email_success_count, email_failure_count, email_start_count,
                        total_tasks, task_number, task_key, task_description,
                        task_timeout_seconds, task_max_retries, task_cluster_type, task_cluster_info,
                        total_runs, run_number, run_id, run_start_time, run_end_time,
                        run_state, run_result_state, run_cluster_id, run_duration_ms, is_latest_run) -> Dict[str, Any]:
        """Create a single CSV row with all columns."""
        row = {
            'job_id': job_id,
            'job_name': job_name,
            'created_time': created_time,
            'creator_user_name': creator_user_name,
            'timeout_seconds': timeout_seconds,
            'max_concurrent_runs': max_concurrent_runs,
            'format': format_val,
            'schedule_cron_expression': schedule_cron,
            'schedule_timezone_id': schedule_timezone,
            'schedule_pause_status': schedule_pause,
            'email_on_success_count': email_success_count,
            'email_on_failure_count': email_failure_count,
            'email_on_start_count': email_start_count,
            'total_tasks': total_tasks,
            'task_number': task_number,
            'task_key': task_key,
            'task_description': task_description,
            'task_timeout_seconds': task_timeout_seconds,
            'task_max_retries': task_max_retries,
            'task_cluster_type': task_cluster_type,
        }
        
        # Add task cluster info (flattened)
        if task_cluster_info:
            row.update(task_cluster_info)
        else:
            row['task_existing_cluster_id'] = None
            row['task_job_cluster_key'] = None
            row['task_new_cluster_spark_version'] = None
            row['task_new_cluster_node_type'] = None
            row['task_new_cluster_num_workers'] = None
        
        # Add run info
        row.update({
            'total_runs': total_runs,
            'run_number': run_number,
            'run_id': run_id,
            'run_start_time': run_start_time,
            'run_end_time': run_end_time,
            'run_state': run_state,
            'run_result_state': run_result_state,
            'run_cluster_id': run_cluster_id,
            'run_execution_duration_ms': run_duration_ms,
            'is_latest_run': is_latest_run
        })
        
        return row
    
    def _get_task_cluster_info(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and flatten task cluster information."""
        cluster_type = task.get('cluster_type')
        
        if cluster_type == 'existing':
            return {
                'task_existing_cluster_id': task.get('existing_cluster_id'),
                'task_job_cluster_key': None,
                'task_new_cluster_spark_version': None,
                'task_new_cluster_node_type': None,
                'task_new_cluster_num_workers': None
            }
        elif cluster_type == 'job_cluster':
            return {
                'task_existing_cluster_id': None,
                'task_job_cluster_key': task.get('job_cluster_key'),
                'task_new_cluster_spark_version': None,
                'task_new_cluster_node_type': None,
                'task_new_cluster_num_workers': None
            }
        elif cluster_type == 'new_cluster':
            new_cluster = task.get('new_cluster', {})
            return {
                'task_existing_cluster_id': None,
                'task_job_cluster_key': None,
                'task_new_cluster_spark_version': new_cluster.get('spark_version'),
                'task_new_cluster_node_type': new_cluster.get('node_type_id'),
                'task_new_cluster_num_workers': new_cluster.get('num_workers')
            }
        else:
            return {
                'task_existing_cluster_id': None,
                'task_job_cluster_key': None,
                'task_new_cluster_spark_version': None,
                'task_new_cluster_node_type': None,
                'task_new_cluster_num_workers': None
            }
    
    def _calculate_duration(self, start_time, end_time) -> Optional[int]:
        """Calculate duration in milliseconds between start and end time."""
        if start_time and end_time:
            try:
                return end_time - start_time
            except:
                return None
        return None
    
    def _process_job(self, job) -> Dict[str, Any]:
        """
        Process a single job and extract metadata.
        
        Args:
            job: Job object from list operation
            
        Returns:
            Dictionary containing job metadata
        """
        try:
            # For simple scan, return only basic information
            if not self.config.is_deep_scan():
                settings = job.settings if hasattr(job, 'settings') else None
                return {
                    'job_id': job.job_id,
                    'job_name': settings.name if settings else 'Unknown',
                    'creator_user_name': job.creator_user_name,
                    'max_concurrent_runs': settings.max_concurrent_runs if settings else None,
                }
            
            # For deep scan, get detailed job information
            job_detail = retry_with_backoff(
                lambda: self.client.jobs.get(job.job_id),
                max_retries=2
            )
            
            settings = job_detail.settings if hasattr(job_detail, 'settings') else job.settings
            
            # Extract basic job metadata
            job_info = {
                'job_id': job.job_id,
                'job_name': settings.name if settings else 'Unknown',
                'created_time': format_epoch_timestamp(job.created_time),
                'creator_user_name': job.creator_user_name,
                'timeout_seconds': settings.timeout_seconds if settings else None,
                'max_concurrent_runs': settings.max_concurrent_runs if settings else None,
                'format': settings.format.value if settings and hasattr(settings, 'format') else None,
            }
            
            # Extract schedule information
            if settings and hasattr(settings, 'schedule') and settings.schedule:
                job_info['schedule'] = {
                    'cron_expression': safe_get_attribute(settings.schedule, 'quartz_cron_expression'),
                    'timezone_id': safe_get_attribute(settings.schedule, 'timezone_id'),
                    'pause_status': safe_get_attribute(settings.schedule, 'pause_status.value')
                }
            
            # Extract email notifications
            if settings and hasattr(settings, 'email_notifications') and settings.email_notifications:
                job_info['email_notifications'] = {
                    'on_success': list(settings.email_notifications.on_success) if settings.email_notifications.on_success else [],
                    'on_failure': list(settings.email_notifications.on_failure) if settings.email_notifications.on_failure else [],
                    'on_start': list(settings.email_notifications.on_start) if settings.email_notifications.on_start else []
                }
            
            # Extract task information
            if settings and hasattr(settings, 'tasks') and settings.tasks:
                job_info['tasks'] = []
                for task in settings.tasks:
                    task_info = {
                        'task_key': safe_get_attribute(task, 'task_key'),
                        'description': safe_get_attribute(task, 'description'),
                        'timeout_seconds': safe_get_attribute(task, 'timeout_seconds'),
                        'max_retries': safe_get_attribute(task, 'max_retries'),
                    }
                    
                    # Extract cluster configuration
                    if hasattr(task, 'existing_cluster_id') and task.existing_cluster_id:
                        task_info['cluster_type'] = 'existing'
                        task_info['existing_cluster_id'] = task.existing_cluster_id
                    elif hasattr(task, 'job_cluster_key') and task.job_cluster_key:
                        task_info['cluster_type'] = 'job_cluster'
                        task_info['job_cluster_key'] = task.job_cluster_key
                    elif hasattr(task, 'new_cluster') and task.new_cluster:
                        task_info['cluster_type'] = 'new_cluster'
                        task_info['new_cluster'] = {
                            'spark_version': safe_get_attribute(task.new_cluster, 'spark_version'),
                            'node_type_id': safe_get_attribute(task.new_cluster, 'node_type_id'),
                            'num_workers': safe_get_attribute(task.new_cluster, 'num_workers'),
                        }
                    
                    job_info['tasks'].append(task_info)
            
            # Get recent run history
            try:
                runs = list(self.client.jobs.list_runs(job_id=job.job_id, limit=5))
                job_info['recent_runs'] = []
                
                for run in runs:
                    # Extract cluster_id from multiple possible locations
                    cluster_id = None
                    
                    # Try cluster_instance first (most common)
                    if hasattr(run, 'cluster_instance') and run.cluster_instance:
                        cluster_id = safe_get_attribute(run, 'cluster_instance.cluster_id')
                    
                    # If not found, try cluster_spec (for some job types)
                    if not cluster_id and hasattr(run, 'cluster_spec') and run.cluster_spec:
                        cluster_id = safe_get_attribute(run, 'cluster_spec.existing_cluster_id')
                    
                    # If still not found, try tasks (for multi-task jobs)
                    if not cluster_id and hasattr(run, 'tasks') and run.tasks:
                        for task in run.tasks:
                            if hasattr(task, 'cluster_instance') and task.cluster_instance:
                                cluster_id = safe_get_attribute(task, 'cluster_instance.cluster_id')
                                if cluster_id:
                                    break
                    
                    run_info = {
                        'run_id': safe_get_attribute(run, 'run_id'),
                        'start_time': format_epoch_timestamp(safe_get_attribute(run, 'start_time')),
                        'end_time': format_epoch_timestamp(safe_get_attribute(run, 'end_time')),
                        'state': safe_get_attribute(run, 'state.life_cycle_state.value'),
                        'result_state': safe_get_attribute(run, 'state.result_state.value'),
                        'cluster_id': cluster_id,
                    }
                    job_info['recent_runs'].append(run_info)
                    
            except Exception as e:
                logger.debug(f"Could not get run history for job {job.job_id}: {str(e)}")
            
            return job_info
            
        except Exception as e:
            logger.error(f"Error processing job {job.job_id}: {str(e)}")
            return {
                'job_id': job.job_id if hasattr(job, 'job_id') else 'unknown',
                'error': str(e)
            }
