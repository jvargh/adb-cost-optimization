"""
Job Analysis Module for Databricks Job Scanner Output

This module analyzes Databricks job scanner JSON output and generates
comprehensive Excel reports with job insights and metrics.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import pandas as pd
import numpy as np


class JobAnalyzer:
    """
    Analyzes Databricks job scanner output and generates insights.
    
    Provides metrics on:
    - Job ownership and distribution
    - Failure analysis
    - Alert/notification coverage
    - Task complexity
    - Cluster type usage
    - Retry policy coverage
    - Long-running job identification
    """
    
    def __init__(self, input_path: str, output_dir: str):
        """
        Initialize the Job Analyzer.
        
        Args:
            input_path: Path to job scanner JSON output file or directory containing JSON files
            output_dir: Directory where Excel report will be saved
        """
        self.input_path = input_path
        self.output_dir = output_dir
        self.jobs_data = None
        self.metadata = None
    
    def _resolve_json_path(self, input_path: str) -> str:
        """
        Resolve input path to actual JSON file path.
        If input_path is a directory, finds the first matching JSON file.
        
        Args:
            input_path: File or directory path
            
        Returns:
            Resolved JSON file path
        """
        # If it's a file, return as-is
        if os.path.isfile(input_path):
            return input_path
        
        # If it's a directory, find JSON files
        if os.path.isdir(input_path):
            import glob
            
            # Look for JSON files in the directory
            json_files = glob.glob(os.path.join(input_path, '*.json'))
            
            if not json_files:
                raise FileNotFoundError(f"No JSON files found in directory: {input_path}")
            
            # Prefer files with 'jobs' in the name
            job_files = [f for f in json_files if 'jobs' in os.path.basename(f).lower()]
            if job_files:
                return job_files[0]
            
            # Otherwise return the first JSON file
            return json_files[0]
        
        raise FileNotFoundError(f"Path does not exist: {input_path}")
        
    def load_data(self) -> None:
        """Load and parse the job scanner JSON file."""
        # Resolve the input path to actual JSON file
        json_file_path = self._resolve_json_path(self.input_path)
        
        print(f"📂 Loading job data from: {json_file_path}")
        
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.metadata = data.get('metadata', {})
        self.jobs_data = data.get('jobs', {}).get('jobs', [])
        
        print(f"✅ Loaded {len(self.jobs_data)} jobs from workspace {self.metadata.get('workspace_id', 'Unknown')}")
    
    def _has_notifications(self, email_notifications: Dict) -> bool:
        """Check if job has any email notifications configured."""
        if not email_notifications:
            return False
        
        on_failure = email_notifications.get('on_failure', [])
        on_success = email_notifications.get('on_success', [])
        on_start = email_notifications.get('on_start', [])
        
        return bool(on_failure or on_success or on_start)
    
    def _has_retry_policy(self, tasks: List[Dict]) -> bool:
        """Check if any task in the job has a retry policy configured."""
        if not tasks:
            return False
        
        for task in tasks:
            max_retries = task.get('max_retries')
            if max_retries is not None and max_retries > 0:
                return True
        
        return False
    
    def _count_tasks_without_retry(self, tasks: List[Dict]) -> int:
        """Count tasks without retry policy."""
        if not tasks:
            return 0
        
        count = 0
        for task in tasks:
            max_retries = task.get('max_retries')
            if max_retries is None or max_retries == 0:
                count += 1
        
        return count
    
    def _get_cluster_types(self, tasks: List[Dict]) -> List[str]:
        """Extract cluster types from job tasks."""
        cluster_types = []
        for task in tasks:
            cluster_type = task.get('cluster_type', 'unknown')
            cluster_types.append(cluster_type)
        return cluster_types
    
    def _calculate_run_duration(self, run: Dict) -> Optional[float]:
        """
        Calculate run duration in minutes.
        
        Args:
            run: Run information dictionary
            
        Returns:
            Duration in minutes, or None if cannot be calculated
        """
        start_time = run.get('start_time')
        end_time = run.get('end_time')
        
        if start_time and end_time:
            try:
                # Convert to int if they are strings
                start_time = int(start_time) if isinstance(start_time, str) else start_time
                end_time = int(end_time) if isinstance(end_time, str) else end_time
                
                # Times are in milliseconds
                duration_ms = end_time - start_time
                duration_minutes = duration_ms / 1000 / 60
                return duration_minutes
            except (ValueError, TypeError):
                # If conversion fails, return None
                return None
        
        return None
    
    def _is_failed_run(self, run: Dict) -> bool:
        """Check if a run failed."""
        result_state = run.get('result_state', '').upper()
        return result_state == 'FAILED'
    
    def generate_summary_metrics(self) -> Dict[str, Any]:
        """
        Generate summary metrics and detail data for all tabs.
        
        Returns:
            Dictionary containing summary DataFrame and detail DataFrames
        """
        print("📊 Generating summary metrics...")
        
        # Initialize storage for all data
        failed_jobs_no_alert_data = []
        multi_task_jobs_data = []
        jobs_without_retry_data = []
        
        # Counters for summary
        total_jobs = len(self.jobs_data)
        total_failed_jobs = 0
        failed_jobs_no_notification_count = 0
        jobs_with_multiple_tasks_count = 0
        jobs_without_retry_count = 0
        jobs_per_user = defaultdict(int)
        failed_jobs_per_user = defaultdict(int)
        jobs_per_cluster_type = defaultdict(int)
        
        # Process each job
        for job in self.jobs_data:
            job_id = job.get('job_id')
            job_name = job.get('job_name', 'Unknown')
            creator = job.get('creator_user_name', 'Unknown')
            tasks = job.get('tasks', [])
            job_format = job.get('format', 'SINGLE_TASK')
            email_notifications = job.get('email_notifications', {})
            recent_runs = job.get('recent_runs', [])
            
            # Count jobs per user
            jobs_per_user[creator] += 1
            
            # Check for failed runs
            has_failed_run = any(self._is_failed_run(run) for run in recent_runs)
            if has_failed_run:
                total_failed_jobs += 1
                failed_jobs_per_user[creator] += 1
                
                # Check if failed job has notifications
                has_notification = self._has_notifications(email_notifications)
                if not has_notification:
                    failed_jobs_no_notification_count += 1
                    failed_jobs_no_alert_data.append({
                        'Job ID': job_id,
                        'Job Name': job_name,
                        'Creator': creator,
                        'Has Notification': 'No'
                    })
            
            # Check for multiple tasks
            task_count = len(tasks)
            if task_count > 1:
                jobs_with_multiple_tasks_count += 1
                multi_task_jobs_data.append({
                    'Job ID': job_id,
                    'Job Name': job_name,
                    'Creator': creator,
                    'Task Count': task_count,
                    'Format': job_format
                })
            
            # Count cluster types
            cluster_types = self._get_cluster_types(tasks)
            for ct in cluster_types:
                jobs_per_cluster_type[ct] += 1
            
            # Check for retry policy
            tasks_without_retry = self._count_tasks_without_retry(tasks)
            if tasks_without_retry > 0:
                jobs_without_retry_count += 1
                jobs_without_retry_data.append({
                    'Job ID': job_id,
                    'Job Name': job_name,
                    'Creator': creator,
                    'Tasks Without Retry': tasks_without_retry,
                    'Task Count': task_count
                })
        
        # Build simple summary table (like the image)
        summary_data = [
            {'Metric': 'Total Jobs Analyzed', 'Value': total_jobs},
            {'Metric': 'Total Failed Jobs', 'Value': total_failed_jobs},
            {'Metric': 'Failed Jobs Without Notifications', 'Value': failed_jobs_no_notification_count},
            {'Metric': 'Jobs with Multiple Tasks', 'Value': jobs_with_multiple_tasks_count},
            {'Metric': 'Jobs Without Retry Policy', 'Value': jobs_without_retry_count},
            {'Metric': '', 'Value': ''},  # Blank row
        ]
        
        # Add jobs per user section
        summary_data.append({'Metric': 'User', 'Value': 'Job Count'})
        for user, count in sorted(jobs_per_user.items(), key=lambda x: x[1], reverse=True):
            summary_data.append({'Metric': user, 'Value': count})
        
        summary_data.append({'Metric': '', 'Value': ''})  # Blank row
        
        # Add failed jobs per user section
        summary_data.append({'Metric': 'User', 'Value': 'Failed Job Count'})
        for user, count in sorted(failed_jobs_per_user.items(), key=lambda x: x[1], reverse=True):
            summary_data.append({'Metric': user, 'Value': count})
        
        summary_data.append({'Metric': '', 'Value': ''})  # Blank row
        
        # Add cluster type section
        summary_data.append({'Metric': 'Cluster Type', 'Value': 'Count'})
        for cluster_type, count in sorted(jobs_per_cluster_type.items(), key=lambda x: x[1], reverse=True):
            summary_data.append({'Metric': cluster_type, 'Value': count})
        
        return {
            'summary': pd.DataFrame(summary_data),
            'failed_no_alert': pd.DataFrame(failed_jobs_no_alert_data),
            'multi_task': pd.DataFrame(multi_task_jobs_data),
            'no_retry': pd.DataFrame(jobs_without_retry_data)
        }
    
    def generate_long_running_jobs(self) -> pd.DataFrame:
        """
        Generate long-running jobs analysis.
        
        Returns:
            DataFrame with long-running job details including average and p95 durations
        """
        print("⏱️  Analyzing long-running jobs...")
        
        job_durations = []
        
        for job in self.jobs_data:
            job_id = job.get('job_id')
            job_name = job.get('job_name', 'Unknown')
            creator = job.get('creator_user_name', 'Unknown')
            recent_runs = job.get('recent_runs', [])
            
            # Calculate durations for all runs
            durations = []
            for run in recent_runs:
                duration = self._calculate_run_duration(run)
                if duration is not None and duration > 0:
                    durations.append(duration)
            
            if durations:
                avg_duration = np.mean(durations)
                p95_duration = np.percentile(durations, 95)
                max_duration = max(durations)
                min_duration = min(durations)
                run_count = len(durations)
                
                job_durations.append({
                    'Job ID': job_id,
                    'Job Name': job_name,
                    'Creator': creator,
                    'Run Count': run_count,
                    'Avg Duration (mins)': round(avg_duration, 2),
                    'P95 (mins)': round(p95_duration, 2),
                    'Max Duration (mins)': round(max_duration, 2),
                    'Min Duration (mins)': round(min_duration, 2)
                })
        
        # Sort by P95 duration (descending)
        df = pd.DataFrame(job_durations)
        if not df.empty:
            df = df.sort_values('P95 (mins)', ascending=False)
        
        return df
    
    def generate_report(self) -> str:
        """
        Generate comprehensive Excel report with job analysis.
        
        Returns:
            Path to generated Excel file
        """
        # Load data
        self.load_data()
        
        # Generate timestamp for filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Determine output filename
        workspace_id = self.metadata.get('workspace_id', 'unknown')
        output_filename = f"Job_Analysis_{workspace_id}_{timestamp}.xlsx"
        output_path = os.path.join(self.output_dir, output_filename)
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        print(f"📝 Generating Excel report: {output_filename}")
        
        # Generate analysis DataFrames
        summary_data = self.generate_summary_metrics()
        long_running_df = self.generate_long_running_jobs()
        
        # Write to Excel with specific tab order
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Tab 1: Summary
            summary_data['summary'].to_excel(writer, sheet_name='Summary', index=False)
            
            # Tab 2: Long Running Jobs (always create with headers)
            if long_running_df.empty:
                # Create empty DataFrame with headers
                empty_df = pd.DataFrame(columns=['Job ID', 'Job Name', 'Creator', 'Run Count', 
                                                  'Avg Duration (mins)', 'P95 (mins)', 
                                                  'Max Duration (mins)', 'Min Duration (mins)'])
                empty_df.to_excel(writer, sheet_name='Long_Running_Jobs', index=False)
            else:
                long_running_df.to_excel(writer, sheet_name='Long_Running_Jobs', index=False)
            
            # Tab 3: Failed Jobs No Alert (always create with headers)
            if summary_data['failed_no_alert'].empty:
                # Create empty DataFrame with headers
                empty_df = pd.DataFrame(columns=['Job ID', 'Job Name', 'Creator', 'Has Notification'])
                empty_df.to_excel(writer, sheet_name='Failed_Jobs_No_Alert', index=False)
            else:
                summary_data['failed_no_alert'].to_excel(writer, sheet_name='Failed_Jobs_No_Alert', index=False)
            
            # Tab 4: Multi-Task Jobs (always create with headers)
            if summary_data['multi_task'].empty:
                # Create empty DataFrame with headers
                empty_df = pd.DataFrame(columns=['Job ID', 'Job Name', 'Creator', 'Task Count', 'Format'])
                empty_df.to_excel(writer, sheet_name='Multi_Task_Jobs', index=False)
            else:
                summary_data['multi_task'].to_excel(writer, sheet_name='Multi_Task_Jobs', index=False)
            
            # Tab 5: Jobs Without Retry (always create with headers)
            if summary_data['no_retry'].empty:
                # Create empty DataFrame with headers
                empty_df = pd.DataFrame(columns=['Job ID', 'Job Name', 'Creator', 'Tasks Without Retry', 'Task Count'])
                empty_df.to_excel(writer, sheet_name='Jobs_Without_Retry', index=False)
            else:
                summary_data['no_retry'].to_excel(writer, sheet_name='Jobs_Without_Retry', index=False)
            
            # Auto-adjust column widths
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
        
        print(f"✅ Report generated successfully: {output_path}")
        print(f"   - Summary metrics")
        print(f"   - Long-running jobs: {len(long_running_df)} jobs")
        print(f"   - Failed jobs without alerts: {len(summary_data['failed_no_alert'])} jobs")
        print(f"   - Multi-task jobs: {len(summary_data['multi_task'])} jobs")
        print(f"   - Jobs without retry: {len(summary_data['no_retry'])} jobs")
        
        return output_path


def run_job_analysis(input_path: str, output_dir: str) -> Dict[str, Any]:
    """
    Analyze Databricks job scanner output and generate Excel report.
    
    Args:
        input_path: Path to job scanner JSON output file or directory containing JSON files
        output_dir: Directory where Excel report will be saved
        
    Returns:
        Dictionary containing:
            - output_file: Path to generated Excel report
            - summary_stats: High-level statistics
            
    Example:
        >>> # Using file path
        >>> result = run_job_analysis(
        ...     input_path='/path/to/jobs_output.json',
        ...     output_dir='/path/to/reports'
        ... )
        >>> # Using directory path (auto-detects JSON file)
        >>> result = run_job_analysis(
        ...     input_path='/dbfs/workspace/jobs/json',
        ...     output_dir='/path/to/reports'
        ... )
        >>> print(result['output_file'])
    """
    print("=" * 80)
    print("🚀 Starting Job Analysis")
    print("=" * 80)
    
    try:
        # Create analyzer and generate report
        analyzer = JobAnalyzer(input_path, output_dir)
        output_file = analyzer.generate_report()
        
        # Collect summary stats
        summary_stats = {
            'total_jobs': len(analyzer.jobs_data),
            'workspace_id': analyzer.metadata.get('workspace_id'),
            'scan_time': analyzer.metadata.get('scan_time'),
        }
        
        print("=" * 80)
        print("✅ Job Analysis Complete")
        print("=" * 80)
        
        return {
            'output_file': output_file,
            'summary_stats': summary_stats
        }
        
    except Exception as e:
        print(f"❌ Error during job analysis: {str(e)}")
        raise


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python job_analyzer.py <input_json_path> <output_directory>")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_dir = sys.argv[2]
    
    result = run_job_analysis(input_path, output_dir)
    print(f"\n📊 Report saved to: {result['output_file']}")
