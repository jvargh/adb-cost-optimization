"""
Specialized Databricks Cluster Analyzers

This module provides specialized analyzers for Databricks cluster configurations:
- WorkerNodeAnalyzer: Analyzes actual worker node counts vs. configured counts
- SingleNodeClusterAnalyzer: Identifies clusters running on single nodes
- AutoscalingAnalyzer: Analyzes autoscaling configurations and patterns
- ClusterRecommendationGenerator: Generates VM sizing and configuration recommendations

All analyzers use a parameter-based API and support both local and Azure Storage paths.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, Optional
import warnings
import os

from .storage_utils import StorageReader

warnings.filterwarnings('ignore')


class WorkerNodeAnalyzer:
    """
    Analyzes actual worker node counts in cluster utilization data.
    
    This analyzer examines worker node configurations and actual usage patterns
    to identify discrepancies between configured and actual worker counts.
    """
    
    def __init__(self, input_path: str, output_dir: str = 'results'):
        """
        Initialize WorkerNodeAnalyzer.
        
        Args:
            input_path: Path to cluster CSV file (local or Azure Storage)
            output_dir: Directory for output files (default: 'results')
        """
        self.input_path = input_path
        self.output_dir = output_dir
        self.reader = StorageReader()
        
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def analyze(self, save_excel: bool = True, output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze worker node counts and configurations.
        
        Args:
            save_excel: Whether to save results to Excel (default: True)
            output_file: Optional custom path for output Excel file. If not provided,
                        auto-generates filename with timestamp in output_dir.
        
        Returns:
            Dictionary containing:
                - total_clusters: Total number of clusters analyzed
                - clusters_with_workers: Count of clusters with worker nodes
                - single_node_clusters: Count of single-node clusters
                - worker_stats: Statistics on worker node counts
                - cluster_data: DataFrame with worker node analysis
                - output_file: Path to Excel report (if saved)
        """
        print("="*100)
        print("DATABRICKS WORKER NODE ANALYSIS")
        print("="*100)
        
        # Read data
        print(f"[1/4] Loading data from: {self.input_path}")
        file_path = self.reader.resolve_csv_path(self.input_path)
        df = self.reader.read_csv(file_path)
        print(f"   ✓ Loaded {len(df):,} records")
        
        # Preprocess data
        print("\n[2/4] Analyzing worker node configurations...")
        df['driver'] = df['driver'].astype(bool)
        
        # Separate driver and worker nodes
        drivers = df[df['driver'] == True].copy()
        workers = df[df['driver'] == False].copy()
        
        print(f"   ✓ Driver nodes: {len(drivers):,}")
        print(f"   ✓ Worker nodes: {len(workers):,}")
        
        # Analyze by cluster
        cluster_analysis = df.groupby('cluster_id').agg({
            'driver': lambda x: (~x).sum(),  # Count of worker nodes
            'worker_node_type': 'first',
            'min_autoscale_workers': 'first',
            'max_autoscale_workers': 'first'
        }).reset_index()
        
        cluster_analysis.columns = [
            'cluster_id',
            'actual_worker_count',
            'worker_node_type',
            'min_autoscale_workers',
            'max_autoscale_workers'
        ]
        
        # Categorize clusters
        def categorize_worker_config(row):
            actual = row['actual_worker_count']
            min_w = row['min_autoscale_workers']
            max_w = row['max_autoscale_workers']
            
            if actual == 0:
                return 'Single-Node (No Workers)'
            elif pd.isna(min_w) or pd.isna(max_w):
                return 'Unknown Configuration'
            elif actual < min_w:
                return 'Below Minimum'
            elif actual > max_w:
                return 'Above Maximum'
            elif min_w == max_w and actual == min_w:
                return 'Fixed Size (Matching)'
            else:
                return 'Within Autoscaling Range'
        
        cluster_analysis['worker_status'] = cluster_analysis.apply(categorize_worker_config, axis=1)
        
        # Calculate statistics
        print("\n[3/4] Generating worker node statistics...")
        total_clusters = len(cluster_analysis)
        clusters_with_workers = len(cluster_analysis[cluster_analysis['actual_worker_count'] > 0])
        single_node_clusters = len(cluster_analysis[cluster_analysis['actual_worker_count'] == 0])
        
        worker_stats = {
            'mean': cluster_analysis['actual_worker_count'].mean(),
            'median': cluster_analysis['actual_worker_count'].median(),
            'min': cluster_analysis['actual_worker_count'].min(),
            'max': cluster_analysis['actual_worker_count'].max(),
            'total': cluster_analysis['actual_worker_count'].sum()
        }
        
        print(f"\n{'WORKER NODE SUMMARY':-<100}")
        print(f"Total clusters: {total_clusters}")
        print(f"Clusters with workers: {clusters_with_workers}")
        print(f"Single-node clusters: {single_node_clusters}")
        print(f"Average workers per cluster: {worker_stats['mean']:.2f}")
        print(f"Median workers per cluster: {worker_stats['median']:.0f}")
        print(f"Total worker nodes: {worker_stats['total']:.0f}")
        
        # Save to Excel
        excel_output = None
        if save_excel:
            print("\n[4/4] Saving results to Excel...")
            # Determine output file path
            if output_file:
                excel_output = output_file
                output_dir = os.path.dirname(excel_output)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
            else:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                excel_output = os.path.join(self.output_dir, f'Worker_Node_Analysis_{timestamp}.xlsx')
            
            with pd.ExcelWriter(excel_output, engine='openpyxl') as writer:
                cluster_analysis.to_excel(writer, sheet_name='Worker_Analysis', index=False)
                
                # Summary sheet
                summary = pd.DataFrame({
                    'Metric': ['Total Clusters', 'Clusters with Workers', 'Single-Node Clusters',
                              'Avg Workers', 'Median Workers', 'Total Workers'],
                    'Value': [total_clusters, clusters_with_workers, single_node_clusters,
                             f"{worker_stats['mean']:.2f}", f"{worker_stats['median']:.0f}",
                             f"{worker_stats['total']:.0f}"]
                })
                summary.to_excel(writer, sheet_name='Summary', index=False)
            
            print(f"   ✓ Report saved to: {excel_output}")
        
        return {
            'total_clusters': total_clusters,
            'clusters_with_workers': clusters_with_workers,
            'single_node_clusters': single_node_clusters,
            'worker_stats': worker_stats,
            'cluster_data': cluster_analysis,
            'output_file': excel_output
        }


class SingleNodeClusterAnalyzer:
    """
    Identifies and analyzes single-node clusters (driver-only, no workers).
    
    Single-node clusters run both driver and executors on the same machine,
    which may indicate inefficient resource usage or misconfiguration.
    """
    
    def __init__(self, input_path: str, output_dir: str = 'results'):
        """
        Initialize SingleNodeClusterAnalyzer.
        
        Args:
            input_path: Path to cluster CSV file (local or Azure Storage)
            output_dir: Directory for output files (default: 'results')
        """
        self.input_path = input_path
        self.output_dir = output_dir
        self.reader = StorageReader()
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def analyze(self, save_excel: bool = True, output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Identify and analyze single-node clusters.
        
        Args:
            save_excel: Whether to save results to Excel (default: True)
            output_file: Optional custom path for output Excel file. If not provided,
                        auto-generates filename with timestamp in output_dir.
        
        Returns:
            Dictionary containing:
                - total_clusters: Total number of clusters
                - single_node_count: Count of single-node clusters
                - single_node_pct: Percentage of single-node clusters
                - single_node_data: DataFrame with single-node cluster details
                - utilization_stats: Utilization statistics for single-node clusters
                - output_file: Path to Excel report (if saved)
        """
        print("="*100)
        print("DATABRICKS SINGLE-NODE CLUSTER ANALYSIS")
        print("="*100)
        
        # Load data
        print(f"\n[1/5] Loading data from: {self.input_path}")
        file_path = self.reader.resolve_csv_path(self.input_path)
        df = self.reader.read_csv(file_path)
        print(f"   ✓ Loaded {len(df):,} records")
        
        # Identify single-node clusters
        print("\n[2/4] Identifying single-node clusters...")
        df['driver'] = df['driver'].astype(bool)
        
        # Count workers per cluster
        worker_counts = df.groupby('cluster_id').agg({
            'driver': lambda x: (~x).sum()  # Count workers (not drivers)
        }).reset_index()
        worker_counts.columns = ['cluster_id', 'worker_count']
        
        # Identify single-node clusters (worker_count == 0)
        single_node_clusters = worker_counts[worker_counts['worker_count'] == 0]['cluster_id'].tolist()
        
        print(f"   ✓ Found {len(single_node_clusters)} single-node clusters")
        
        # Get details for single-node clusters
        print("\n[3/4] Analyzing single-node cluster characteristics...")
        single_node_df = df[df['cluster_id'].isin(single_node_clusters)].copy()
        
        # Aggregate metrics
        single_node_analysis = single_node_df.groupby('cluster_id').agg({
            'Avg CPU Utilization': 'mean',
            'Peak CPU Utilization': 'max',
            'Avg Memory Utilization': 'mean',
            'Max Memory Utilization': 'max',
            'driver_node_type': 'first',
            'job_id': 'first',
            'job_name': 'first'
        }).reset_index()
        
        single_node_analysis.columns = [
            'cluster_id', 'Avg_CPU_Util', 'Peak_CPU_Util',
            'Avg_Memory_Util', 'Max_Memory_Util',
            'driver_node_type', 'job_id', 'job_name'
        ]
        
        # Calculate utilization stats
        utilization_stats = {
            'avg_cpu_mean': single_node_analysis['Avg_CPU_Util'].mean(),
            'avg_memory_mean': single_node_analysis['Avg_Memory_Util'].mean(),
            'peak_cpu_mean': single_node_analysis['Peak_CPU_Util'].mean(),
            'max_memory_mean': single_node_analysis['Max_Memory_Util'].mean()
        }
        
        total_clusters = df['cluster_id'].nunique()
        single_node_count = len(single_node_clusters)
        single_node_pct = (single_node_count / total_clusters * 100) if total_clusters > 0 else 0
        
        print(f"\n{'SINGLE-NODE CLUSTER SUMMARY':-<100}")
        print(f"Total clusters: {total_clusters}")
        print(f"Single-node clusters: {single_node_count} ({single_node_pct:.1f}%)")
        print(f"Average CPU utilization: {utilization_stats['avg_cpu_mean']:.2f}%")
        print(f"Average memory utilization: {utilization_stats['avg_memory_mean']:.2f}%")
        
        # Save to Excel
        excel_output = None
        if save_excel:
            print("\\n[4/4] Saving results to Excel...")
            # Determine output file path
            if output_file:
                excel_output = output_file
                output_dir = os.path.dirname(excel_output)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
            else:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                excel_output = os.path.join(self.output_dir, f'Single_Node_Clusters_{timestamp}.xlsx')
            
            with pd.ExcelWriter(excel_output, engine='openpyxl') as writer:
                single_node_analysis.to_excel(writer, sheet_name='Single_Node_Clusters', index=False)
                
                # Summary
                summary = pd.DataFrame({
                    'Metric': ['Total Clusters', 'Single-Node Clusters', 'Percentage',
                              'Avg CPU Util', 'Avg Memory Util'],
                    'Value': [total_clusters, single_node_count, f"{single_node_pct:.1f}%",
                             f"{utilization_stats['avg_cpu_mean']:.2f}%",
                             f"{utilization_stats['avg_memory_mean']:.2f}%"]
                })
                summary.to_excel(writer, sheet_name='Summary', index=False)
            
            print(f"   ✓ Report saved to: {excel_output}")
        
        return {
            'total_clusters': total_clusters,
            'single_node_count': single_node_count,
            'single_node_pct': single_node_pct,
            'single_node_data': single_node_analysis,
            'utilization_stats': utilization_stats,
            'output_file': excel_output
        }


class AutoscalingAnalyzer:
    """
    Analyzes autoscaling configurations and patterns across clusters.
    
    This analyzer examines autoscaling settings (min/max workers) and provides
    recommendations based on Databricks best practices.
    """
    
    def __init__(self, input_path: str, output_dir: str = 'results'):
        """
        Initialize AutoscalingAnalyzer.
        
        Args:
            input_path: Path to cluster CSV file (local or Azure Storage)
            output_dir: Directory for output files (default: 'results')
        """
        self.input_path = input_path
        self.output_dir = output_dir
        self.reader = StorageReader()
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def analyze(self, save_excel: bool = True, output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze autoscaling configurations.
        
        Args:
            save_excel: Whether to save results to Excel (default: True)
            output_file: Optional custom path for output Excel file. If not provided,
                        auto-generates filename with timestamp in output_dir.
        
        Returns:
            Dictionary containing:
                - total_clusters: Total number of clusters
                - autoscaling_summary: Breakdown by autoscaling type
                - cluster_data: DataFrame with autoscaling analysis
                - recommendations: List of recommendations
                - output_file: Path to Excel report (if saved)
        """
        print("="*100)
        print("DATABRICKS AUTOSCALING CONFIGURATION ANALYSIS")
        print("="*100)
        
        # Load data
        print(f"\n[1/5] Loading data from: {self.input_path}")
        file_path = self.reader.resolve_csv_path(self.input_path)
        df = self.reader.read_csv(file_path)
        print(f"   ✓ Loaded {len(df):,} cluster records")
        print(f"   ✓ Loaded {len(df):,} records")
        
        # Analyze autoscaling configs
        print("\n[2/4] Analyzing autoscaling configurations...")
        cluster_autoscaling = df.groupby('cluster_id').agg({
            'min_autoscale_workers': 'first',
            'max_autoscale_workers': 'first',
            'worker_node_type': 'first',
            'Avg CPU Utilization': 'mean',
            'Peak CPU Utilization': 'max',
            'Avg Memory Utilization': 'mean',
            'Max Memory Utilization': 'max'
        }).reset_index()
        
        cluster_autoscaling.columns = [
            'cluster_id', 'min_workers', 'max_workers', 'worker_node_type',
            'Avg_CPU_Util', 'Peak_CPU_Util', 'Avg_Memory_Util', 'Max_Memory_Util'
        ]
        
        # Categorize autoscaling patterns
        def categorize_autoscaling(row):
            min_w = row['min_workers']
            max_w = row['max_workers']
            
            if pd.isna(min_w) or pd.isna(max_w):
                return 'Not Configured'
            
            min_w = int(min_w)
            max_w = int(max_w)
            
            if min_w == max_w:
                if min_w == 0:
                    return 'No Workers'
                else:
                    return 'Fixed Size'
            
            range_size = max_w - min_w
            
            if range_size <= 2:
                return 'Narrow Range'
            elif range_size <= 5:
                return 'Moderate Range'
            else:
                return 'Wide Range'
        
        cluster_autoscaling['autoscaling_type'] = cluster_autoscaling.apply(categorize_autoscaling, axis=1)
        
        # Generate recommendations
        print("\n[3/4] Generating autoscaling recommendations...")
        
        def get_autoscaling_recommendation(row):
            autoscaling_type = row['autoscaling_type']
            avg_cpu = row['Avg_CPU_Util']
            peak_cpu = row['Peak_CPU_Util']
            max_util = max(avg_cpu, peak_cpu, row['Avg_Memory_Util'], row['Max_Memory_Util'])
            
            is_bursty = (peak_cpu > 80 and avg_cpu < 50)
            
            if autoscaling_type == 'Not Configured':
                return 'Enable autoscaling - Not configured'
            elif autoscaling_type == 'Fixed Size':
                if max_util < 50:
                    return 'Enable autoscaling to reduce idle costs'
                elif is_bursty:
                    return 'Enable autoscaling to handle bursts'
                else:
                    return 'Consider enabling autoscaling for flexibility'
            elif autoscaling_type == 'Narrow Range':
                if is_bursty:
                    return 'Widen autoscaling range to handle bursts'
                else:
                    return 'Current narrow range acceptable'
            elif autoscaling_type in ['Moderate Range', 'Wide Range']:
                return 'Autoscaling well configured'
            else:
                return 'Review configuration'
        
        cluster_autoscaling['recommendation'] = cluster_autoscaling.apply(get_autoscaling_recommendation, axis=1)
        
        # Summary statistics
        autoscaling_summary = cluster_autoscaling['autoscaling_type'].value_counts().to_dict()
        total_clusters = len(cluster_autoscaling)
        
        print(f"\n{'AUTOSCALING SUMMARY':-<100}")
        for config_type, count in sorted(autoscaling_summary.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_clusters * 100) if total_clusters > 0 else 0
            print(f"{config_type}: {count} ({pct:.1f}%)")
        
        # Save to Excel
        excel_output = None
        if save_excel:
            print("\\n[4/4] Saving results to Excel...")
            # Determine output file path
            if output_file:
                excel_output = output_file
                output_dir = os.path.dirname(excel_output)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
            else:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                excel_output = os.path.join(self.output_dir, f'Autoscaling_Analysis_{timestamp}.xlsx')
            
            with pd.ExcelWriter(excel_output, engine='openpyxl') as writer:
                cluster_autoscaling.to_excel(writer, sheet_name='Autoscaling_Details', index=False)
                
                # Summary
                summary_df = pd.DataFrame(list(autoscaling_summary.items()),
                                         columns=['Configuration_Type', 'Count'])
                summary_df['Percentage'] = (summary_df['Count'] / total_clusters * 100).round(1)
                summary_df = summary_df.sort_values('Count', ascending=False)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            print(f"   ✓ Report saved to: {excel_output}")
        
        return {
            'total_clusters': total_clusters,
            'autoscaling_summary': autoscaling_summary,
            'cluster_data': cluster_autoscaling,
            'recommendations': cluster_autoscaling[['cluster_id', 'autoscaling_type', 'recommendation']],
            'output_file': excel_output
        }


class ClusterRecommendationGenerator:
    """
    Generates comprehensive cluster sizing and configuration recommendations.
    
    This analyzer combines utilization metrics, VM types, and autoscaling configs
    to provide actionable recommendations following Databricks best practices.
    """
    
    def __init__(self, input_path: str, output_dir: str = 'results'):
        """
        Initialize ClusterRecommendationGenerator.
        
        Args:
            input_path: Path to cluster CSV file (local or Azure Storage)
            output_dir: Directory for output files (default: 'results')
        """
        self.input_path = input_path
        self.output_dir = output_dir
        self.reader = StorageReader()
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def _parse_vm_type(self, vm_type_str):
        """Parse Azure VM type to extract series, size, and generation."""
        if pd.isna(vm_type_str) or vm_type_str == '':
            return {'series': None, 'size': None, 'generation': None, 'feature': None}
        
        try:
            vm_type = str(vm_type_str).replace('Standard_', '')
            series = vm_type[0] if vm_type else None
            
            size_str = ''
            i = 1
            while i < len(vm_type) and vm_type[i].isdigit():
                size_str += vm_type[i]
                i += 1
            
            size = int(size_str) if size_str else None
            remaining = vm_type[i:] if i < len(vm_type) else ''
            
            feature = ''
            generation = None
            if remaining:
                parts = remaining.split('_')
                if len(parts) > 0:
                    feature = parts[0] if parts[0] else ''
                if len(parts) > 1:
                    generation = parts[1] if parts[1] else None
            
            return {'series': series, 'size': size, 'generation': generation, 'feature': feature}
        except Exception:
            return {'series': None, 'size': None, 'generation': None, 'feature': None}
    
    def analyze(self, save_excel: bool = True, output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate comprehensive cluster recommendations.
        
        Args:
            save_excel: Whether to save results to Excel (default: True)
            output_file: Optional custom path for output Excel file. If not provided,
                        auto-generates filename with timestamp in output_dir.
        
        Returns:
            Dictionary containing:
                - total_clusters: Total number of clusters
                - recommendations_by_category: Breakdown of recommendations
                - cluster_data: DataFrame with detailed recommendations
                - high_priority_actions: List of high-priority recommendations
                - output_file: Path to Excel report (if saved)
        """
        print("="*100)
        print("DATABRICKS CLUSTER OPTIMIZATION RECOMMENDATIONS")
        print("="*100)
        
        # Read and process data
        print(f"\n[1/5] Loading data from: {self.input_path}")
        # Resolve path if directory
        csv_path = self.reader.resolve_csv_path(self.input_path, '*_cluster_utilization.csv')
        df = self.reader.read_csv(csv_path)
        print(f"   ✓ Loaded {len(df):,} records")
        
        # Aggregate cluster metrics
        print("\n[2/5] Aggregating cluster metrics...")
        cluster_metrics = df.groupby('cluster_id').agg({
            'Avg CPU Utilization': 'mean',
            'Peak CPU Utilization': 'max',
            'Avg Memory Utilization': 'mean',
            'Max Memory Utilization': 'max',
            'worker_node_type': 'first',
            'driver_node_type': 'first',
            'min_autoscale_workers': 'first',
            'max_autoscale_workers': 'first',
            'job_id': 'first',
            'job_name': 'first'
        }).reset_index()
        
        cluster_metrics.columns = [
            'cluster_id', 'Avg_CPU_Util', 'Peak_CPU_Util',
            'Avg_Memory_Util', 'Max_Memory_Util',
            'worker_node_type', 'driver_node_type',
            'min_workers', 'max_workers', 'job_id', 'job_name'
        ]
        
        # Categorize clusters
        print("\n[3/5] Categorizing clusters...")
        
        def categorize_cluster(row):
            max_util = max(row['Avg_CPU_Util'], row['Peak_CPU_Util'],
                          row['Avg_Memory_Util'], row['Max_Memory_Util'])
            
            if max_util > 80:
                return 'High Utilization'
            elif max_util > 70:
                return 'Moderate (70-80%)'
            elif max_util >= 50:
                return 'Well-utilized'
            elif max_util >= 15:
                return 'Under-utilized'
            elif max_util >= 5:
                return 'Low Utilization'
            else:
                return 'Idle'
        
        cluster_metrics['category'] = cluster_metrics.apply(categorize_cluster, axis=1)
        
        # Parse VM types
        cluster_metrics['vm_info'] = cluster_metrics['worker_node_type'].apply(self._parse_vm_type)
        
        # Generate recommendations
        print("\n[4/5] Generating recommendations...")
        
        def generate_recommendations(row):
            category = row['category']
            max_util = max(row['Avg_CPU_Util'], row['Peak_CPU_Util'],
                          row['Avg_Memory_Util'], row['Max_Memory_Util'])
            vm_info = row['vm_info']
            
            recommendations = []
            
            if category == 'Idle':
                recommendations.append('TERMINATE - Cluster is idle (<5% utilization)')
                priority = 'Critical'
            elif category == 'Low Utilization':
                recommendations.append('DOWNSIZE - Reduce VM size by 50-75%')
                recommendations.append('Consider converting to job cluster instead of interactive')
                priority = 'High'
            elif category == 'Under-utilized':
                recommendations.append('RIGHT-SIZE - Reduce VM size by 25-50%')
                recommendations.append('Enable autoscaling if not already enabled')
                priority = 'Medium'
            elif category == 'Well-utilized':
                recommendations.append('OPTIMAL - Continue monitoring')
                recommendations.append('Consider enabling Photon for performance boost')
                priority = 'Low'
            elif category == 'Moderate (70-80%)':
                recommendations.append('MONITOR - Watch for scale-up needs')
                recommendations.append('Enable autoscaling for flexibility')
                priority = 'Low'
            else:  # High Utilization
                recommendations.append('SCALE UP - Increase VM size by 50%')
                recommendations.append('Enable autoscaling to handle bursts')
                recommendations.append('Enable Photon + AQE for better performance')
                priority = 'High'
            
            # Add instance type guidance
            if vm_info['series'] == 'E':
                recommendations.append('Instance: Memory-optimized (E-series) - Good for shuffle-heavy workloads')
            elif vm_info['series'] == 'F':
                recommendations.append('Instance: Compute-optimized (F-series) - Ideal for streaming & full-scan ELT')
            elif vm_info['series'] == 'L':
                recommendations.append('Instance: Storage-optimized (L-series) - Use for Delta Cache workloads')
            elif vm_info['series'] == 'D':
                recommendations.append('Instance: General purpose (D-series) - Standard workloads')
            
            return {
                'priority': priority,
                'recommendations': ' | '.join(recommendations)
            }
        
        cluster_metrics[['priority', 'recommendations']] = cluster_metrics.apply(
            generate_recommendations, axis=1, result_type='expand'
        )
        
        # Summary statistics
        recommendations_by_category = cluster_metrics['category'].value_counts().to_dict()
        total_clusters = len(cluster_metrics)
        
        print(f"\n{'RECOMMENDATION SUMMARY':-<100}")
        for category, count in sorted(recommendations_by_category.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_clusters * 100) if total_clusters > 0 else 0
            print(f"{category}: {count} ({pct:.1f}%)")
        
        # High priority actions
        high_priority = cluster_metrics[cluster_metrics['priority'].isin(['Critical', 'High'])].copy()
        print(f"\nHigh Priority Actions: {len(high_priority)} clusters")
        
        # Save to Excel
        excel_output = None
        if save_excel:
            print("\\n[5/5] Saving recommendations to Excel...")
            # Determine output file path
            if output_file:
                excel_output = output_file
                output_dir = os.path.dirname(excel_output)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
            else:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                excel_output = os.path.join(self.output_dir, f'Cluster_Recommendations_{timestamp}.xlsx')
            
            with pd.ExcelWriter(excel_output, engine='openpyxl') as writer:
                # All recommendations
                output_cols = ['cluster_id', 'category', 'priority', 'worker_node_type',
                              'Avg_CPU_Util', 'Peak_CPU_Util', 'Avg_Memory_Util', 'Max_Memory_Util',
                              'recommendations']
                cluster_metrics[output_cols].to_excel(writer, sheet_name='All_Recommendations', index=False)
                
                # High priority only
                high_priority[output_cols].to_excel(writer, sheet_name='High_Priority', index=False)
                
                # Summary
                summary_df = pd.DataFrame(list(recommendations_by_category.items()),
                                         columns=['Category', 'Count'])
                summary_df['Percentage'] = (summary_df['Count'] / total_clusters * 100).round(1)
                summary_df = summary_df.sort_values('Count', ascending=False)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            print(f"   ✓ Report saved to: {excel_output}")
        
        print("\\n" + "="*100)
        print("✅ RECOMMENDATION GENERATION COMPLETE")
        print("="*100)
        
        return {
            'total_clusters': total_clusters,
            'recommendations_by_category': recommendations_by_category,
            'cluster_data': cluster_metrics,
            'high_priority_actions': high_priority,
            'output_file': excel_output
        }
