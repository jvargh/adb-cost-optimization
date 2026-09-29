"""
Additional Analyzers Module for DBX Analysis Package
Includes specialized analyzers for network traffic, RI opportunities, and more.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import os
import glob
from typing import Optional, Dict, Any, List
warnings.filterwarnings('ignore')

from .storage_utils import StorageReader


class NetworkTrafficAnalyzer:
    """
    Analyzes network traffic patterns in cluster utilization data.
    Identifies clusters with high network activity that may be misclassified
    based on CPU/Memory metrics alone.
    """
    
    def __init__(self, input_path: str, output_dir: str = 'results'):
        """
        Initialize network traffic analyzer.
        
        Args:
            input_path: Path to cluster utilization CSV
            output_dir: Output directory for reports
        """
        self.input_path = input_path
        self.output_dir = output_dir
        self.reader = StorageReader()
        self.cluster_metrics = None
        self.high_network_received_threshold = None
        self.high_network_sent_threshold = None
        self.results = {}
        
    def analyze(self, save_excel: bool = True, output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Run network traffic analysis.
        
        Args:
            save_excel: Whether to save Excel output file (default: True)
            output_file: Optional custom path for output Excel file. If not provided,
                        auto-generates filename with timestamp in output_dir.
        
        Returns:
            Dictionary with analysis results
        """
        print("\n" + "="*80)
        print("NETWORK TRAFFIC ANALYSIS")
        print("="*80)
        
        # Resolve input path (directory -> file)
        file_path = self.reader.resolve_csv_path(self.input_path)
        
        # Load and process data
        df = self.reader.read_csv(file_path)
        print(f"✓ Loaded {len(df):,} records from {df['cluster_id'].nunique()} clusters")
        
        # Preprocess
        df = self._preprocess_data(df)
        
        # Aggregate metrics
        self.cluster_metrics = self._aggregate_metrics(df)
        
        # Calculate network thresholds (90th percentile)
        self.high_network_received_threshold = self.cluster_metrics['Avg_Network_MB_Received'].quantile(0.90)
        self.high_network_sent_threshold = self.cluster_metrics['Avg_Network_MB_Sent'].quantile(0.90)
        
        print(f"\nNetwork Thresholds (90th percentile):")
        print(f"  Received: {self.high_network_received_threshold:,.2f} MB/min")
        print(f"  Sent: {self.high_network_sent_threshold:,.2f} MB/min")
        
        # Flag high network clusters
        self.cluster_metrics['High_Network_Received'] = (
            self.cluster_metrics['Avg_Network_MB_Received'] >= self.high_network_received_threshold
        )
        self.cluster_metrics['High_Network_Sent'] = (
            self.cluster_metrics['Avg_Network_MB_Sent'] >= self.high_network_sent_threshold
        )
        self.cluster_metrics['High_Network_Activity'] = (
            self.cluster_metrics['High_Network_Received'] | self.cluster_metrics['High_Network_Sent']
        )
        
        # Identify problematic clusters (high network, low compute)
        problematic_categories = ['Idle', 'Low Utilization', 'Under-utilized']
        problematic_clusters = self.cluster_metrics[
            (self.cluster_metrics['Category'].isin(problematic_categories)) &
            (self.cluster_metrics['High_Network_Activity'])
        ].copy()
        
        print(f"\n⚠️  Found {len(problematic_clusters)} clusters with high network traffic in low utilization categories")
        
        # Store results
        self.results = {
            'total_clusters': len(self.cluster_metrics),
            'high_network_clusters': len(self.cluster_metrics[self.cluster_metrics['High_Network_Activity']]),
            'problematic_clusters': len(problematic_clusters),
            'network_thresholds': {
                'received_mb_min': self.high_network_received_threshold,
                'sent_mb_min': self.high_network_sent_threshold
            },
            'cluster_data': self.cluster_metrics,
            'problematic_data': problematic_clusters
        }
        
        if save_excel:
            excel_output = self._save_excel_report(problematic_clusters, output_file)
            self.results['output_file'] = excel_output
            print(f"\n✓ Report saved to: {excel_output}")
        
        return self.results
    
    def _preprocess_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Preprocess and clean data."""
        df['Avg CPU Utilization'] = df['Avg CPU Utilization'].fillna(0)
        df['Peak CPU Utilization'] = df['Peak CPU Utilization'].fillna(0)
        df['Avg Memory Utilization'] = df['Avg Memory Utilization'].fillna(0)
        df['Max Memory Utilization'] = df['Max Memory Utilization'].fillna(0)
        df['Avg Network MB Received'] = df.get('Avg Network MB Received', pd.Series([0]*len(df))).fillna(0)
        df['Avg Network MB Sent'] = df.get('Avg Network MB Sent', pd.Series([0]*len(df))).fillna(0)
        return df
    
    def _aggregate_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate metrics by cluster."""
        agg_dict = {
            'Avg CPU Utilization': 'mean',
            'Peak CPU Utilization': 'max',
            'Avg Memory Utilization': 'mean',
            'Max Memory Utilization': 'max',
            'Avg Network MB Received': 'mean',
            'Avg Network MB Sent': 'mean',
            'job_id': 'first',
            'worker_node_type': 'first'
        }
        
        cluster_metrics = df.groupby('cluster_id').agg(agg_dict).round(2)
        cluster_metrics.columns = [
            'Avg_CPU_Util', 'Peak_CPU_Util', 'Avg_Memory_Util', 'Max_Memory_Util',
            'Avg_Network_MB_Received', 'Avg_Network_MB_Sent', 'job_id', 'worker_node_type'
        ]
        cluster_metrics = cluster_metrics.reset_index()
        
        # Categorize
        def categorize(row):
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
        
        cluster_metrics['Category'] = cluster_metrics.apply(categorize, axis=1)
        return cluster_metrics
    
    def _save_excel_report(self, problematic_clusters: pd.DataFrame, output_file: Optional[str] = None) -> str:
        """
        Save network traffic analysis report.
        
        Args:
            problematic_clusters: DataFrame with problematic clusters
            output_file: Optional custom path for output Excel file
            
        Returns:
            Path to saved Excel file
        """
        # Determine output file path
        if output_file:
            # Use custom output file path
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
        else:
            # Auto-generate filename with timestamp
            os.makedirs(self.output_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(self.output_dir, f'Network_Traffic_Analysis_{timestamp}.xlsx')
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Summary
            summary = pd.DataFrame({
                'Metric': [
                    'Total Clusters',
                    'High Network Clusters',
                    'Problematic Clusters (High Network, Low Compute)',
                    'Network Received Threshold (90th %ile)',
                    'Network Sent Threshold (90th %ile)'
                ],
                'Value': [
                    self.results['total_clusters'],
                    self.results['high_network_clusters'],
                    self.results['problematic_clusters'],
                    f"{self.high_network_received_threshold:,.2f} MB/min",
                    f"{self.high_network_sent_threshold:,.2f} MB/min"
                ]
            })
            summary.to_excel(writer, sheet_name='Summary', index=False)
            
            # Problematic clusters
            if not problematic_clusters.empty:
                problematic_clusters.to_excel(writer, sheet_name='High_Network_Low_Compute', index=False)
            
            # All clusters
            self.cluster_metrics.to_excel(writer, sheet_name='All_Clusters', index=False)
        
        return output_file


class RIOpportunityAnalyzer:
    """
    Analyzes Reserved Instance (RI) opportunities for Azure Databricks clusters.
    Identifies clusters suitable for RI purchases based on utilization patterns.
    """
    
    def __init__(self, input_path: str, output_dir: str = 'results'):
        """
        Initialize RI opportunity analyzer.
        
        Args:
            input_path: Path to input data:
                       - Cluster_Analysis_Consolidated*.xlsx file (with 'utilization_All Clusters' sheet), OR
                       - Directory containing *_cluster_utilization.csv file, OR
                       - Direct path to *_cluster_utilization.csv file
            output_dir: Output directory for reports
        """
        self.input_path = input_path
        self.output_dir = output_dir
        self.reader = StorageReader()
        self.df = None
        self.results = {}
        
    def analyze(self, node_type: str = 'Standard_E16a_v4', save_excel: bool = True, output_file: Optional[str] = None, analyze_all_types: bool = False) -> Dict[str, Any]:
        """
        Run RI opportunity analysis.
        
        Args:
            node_type: Azure VM node type to focus on (default: Standard_E16a_v4)
            save_excel: Whether to save Excel report
            output_file: Optional custom path for output Excel file. If not provided,
                        auto-generates filename with timestamp in output_dir.
            analyze_all_types: If True, analyzes all RI candidates regardless of node type.
                              If False, filters by specific node_type (default: False)
            
        Returns:
            Dictionary with RI recommendations
        """
        print("\n" + "="*80)
        print("RESERVED INSTANCE (RI) OPPORTUNITY ANALYSIS")
        print("="*80)
        
        # Check if input is Cluster_Analysis_Consolidated file or raw CSV
        if self.input_path.endswith('.xlsx'):
            # Direct file path to consolidated file provided
            consolidated_file = self.input_path
            try:
                self.df = pd.read_excel(consolidated_file, sheet_name='utilization_All Clusters')
                print(f"✓ Loaded from sheet: 'utilization_All Clusters'")
            except Exception:
                try:
                    xl_file = pd.ExcelFile(consolidated_file)
                    sheet_names = xl_file.sheet_names
                    print(f"Available sheets: {', '.join(sheet_names)}")
                    
                    cluster_sheet = next((s for s in sheet_names if 'utilization' in s.lower() and 'cluster' in s.lower()), None)
                    if cluster_sheet:
                        self.df = pd.read_excel(consolidated_file, sheet_name=cluster_sheet)
                        print(f"✓ Loaded from sheet: '{cluster_sheet}'")
                    else:
                        self.df = pd.read_excel(consolidated_file, sheet_name=0)
                        print(f"⚠️  Could not find 'utilization_All Clusters' sheet, using first sheet: '{sheet_names[0]}'")
                except Exception as e:
                    raise Exception(f"Error loading Cluster_Analysis_Consolidated file: {e}")
        else:
            # Directory or CSV file - load raw cluster utilization data
            csv_path = self.reader.resolve_csv_path(self.input_path, '*_cluster_utilization.csv')
            self.df = self.reader.read_csv(csv_path)
            print(f"✓ Loaded from cluster utilization CSV")
            
            # Perform categorization if Category column doesn't exist
            if 'Category' not in self.df.columns:
                print(f"✓ Performing cluster categorization for RI analysis...")
                # First aggregate the data by cluster_id
                self.df = self._aggregate_cluster_data(self.df)
                # Then categorize
                self.df = self._categorize_for_ri_analysis()
        
        print(f"✓ Loaded {len(self.df):,} clusters")
        
        # Debug: Show category distribution
        if 'Category' in self.df.columns:
            print(f"\n📊 Category Distribution:")
            for cat, count in self.df['Category'].value_counts().items():
                print(f"  - {cat}: {count} ({count/len(self.df)*100:.1f}%)")
        else:
            print(f"\n⚠️  WARNING: 'Category' column not found in data!")
            print(f"   Available columns: {', '.join(self.df.columns.tolist()[:10])}")
        
        # Identify RI candidates
        ri_candidates = self._identify_ri_candidates()
        print(f"\n✓ Found {len(ri_candidates):,} RI candidates ({len(ri_candidates)/len(self.df)*100:.1f}%)")
        
        if len(ri_candidates) == 0:
            print(f"\n⚠️  No RI candidates found!")
            print(f"   RI candidates must have Category containing: 'High Utilization', 'Well-utilized', or 'Moderate'")
            return self.results
        
        # Debug: Show node types in RI candidates
        if 'driver_node_type' in ri_candidates.columns:
            unique_driver_types = ri_candidates['driver_node_type'].dropna().unique()
            print(f"\n🔍 Node types in RI candidates:")
            print(f"  Driver types: {', '.join(unique_driver_types[:5])}")
        if 'worker_node_type' in ri_candidates.columns:
            unique_worker_types = ri_candidates['worker_node_type'].dropna().unique()
            print(f"  Worker types: {', '.join(unique_worker_types[:5])}")
        
        # Analyze specific node type
        if analyze_all_types:
            print(f"\n📊 Analyzing ALL RI candidates (all node types)")
            node_analysis = self._analyze_all_node_types(ri_candidates)
        else:
            node_analysis = self._analyze_node_type(ri_candidates, node_type)
        
        if node_analysis['cluster_count'] == 0:
            print(f"\n⚠️  WARNING: No clusters found using node type '{node_type}'")
            print(f"   Consider using one of the node types listed above or set analyze_all_types=True")
            # Still continue to generate report with all RI candidates
        
        # Calculate RI recommendations
        ri_recommendations = self._calculate_ri_recommendations(node_analysis)
        
        # Store results
        self.results = {
            'total_clusters': len(self.df),
            'ri_candidates_count': len(ri_candidates),
            'ri_candidates_pct': len(ri_candidates)/len(self.df)*100,
            'node_type': node_type,
            'node_analysis': node_analysis,
            'ri_recommendations': ri_recommendations,
            'ri_candidates_data': ri_candidates
        }
        
        if save_excel:
            excel_output = self._save_excel_report(ri_candidates, node_analysis, ri_recommendations, output_file)
            self.results['output_file'] = excel_output
            print(f"\n✓ Report saved to: {excel_output}")
        
        return self.results
    
    def _identify_ri_candidates(self) -> pd.DataFrame:
        """Identify clusters suitable for RI purchase."""
        def is_ri_candidate(row):
            category = str(row.get('Category', '')).lower()
            if 'high utilization' in category or 'well-utilized' in category or 'moderate' in category:
                return True
            return False
        
        self.df['RI_Candidate'] = self.df.apply(is_ri_candidate, axis=1)
        return self.df[self.df['RI_Candidate'] == True].copy()
    
    def _categorize_for_ri_analysis(self) -> pd.DataFrame:
        """
        Categorize clusters for RI analysis when Category column doesn't exist.
        Uses simple thresholds based on CPU and Memory utilization.
        """
        def categorize(row):
            # Get utilization metrics
            cpu_avg = row.get('Avg_CPU_Util', 0)
            cpu_peak = row.get('Peak_CPU_Util', 0)
            mem_avg = row.get('Avg_Memory_Util', 0)
            mem_max = row.get('Max_Memory_Util', 0)
            
            # Calculate max utilization
            max_util = max(cpu_avg, cpu_peak, mem_avg, mem_max)
            
            # Categorize based on thresholds
            if max_util > 80:
                return 'High Utilization'
            elif max_util > 70:
                return 'Moderate'
            elif max_util >= 50:
                return 'Well-utilized'
            elif max_util >= 15:
                return 'Under-utilized'
            elif max_util >= 5:
                return 'Low Utilization'
            else:
                return 'Idle'
        
        self.df['Category'] = self.df.apply(categorize, axis=1)
        return self.df
    
    def _aggregate_cluster_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate raw cluster utilization data by cluster_id."""
        agg_dict = {
            'Avg CPU Utilization': 'mean',
            'Peak CPU Utilization': 'max',
            'Avg Memory Utilization': 'mean',
            'Max Memory Utilization': 'max',
            'job_id': 'first',
            'job_name': 'first',
            'driver_node_type': 'first',
            'worker_node_type': 'first',
            'min_autoscale_workers': 'first',
            'max_autoscale_workers': 'first'
        }
        
        # Add optional columns if they exist
        if 'worker_count' in df.columns:
            agg_dict['worker_count'] = 'first'
        
        # Group by cluster_id and aggregate
        aggregated = df.groupby('cluster_id').agg(agg_dict).round(2)
        
        # Rename columns to match expected format
        aggregated.rename(columns={
            'Avg CPU Utilization': 'Avg_CPU_Util',
            'Peak CPU Utilization': 'Peak_CPU_Util',
            'Avg Memory Utilization': 'Avg_Memory_Util',
            'Max Memory Utilization': 'Max_Memory_Util'
        }, inplace=True)
        
        aggregated.reset_index(inplace=True)
        print(f"✓ Aggregated {len(df)} records to {len(aggregated)} unique clusters")
        
        return aggregated
    
    def _analyze_node_type(self, ri_candidates: pd.DataFrame, node_type: str) -> Dict[str, Any]:
        """Analyze specific node type usage."""
        driver_col = 'driver_node_type' if 'driver_node_type' in ri_candidates.columns else 'worker_node_type'
        worker_col = 'worker_node_type'
        
        node_clusters = ri_candidates[
            (ri_candidates.get(driver_col, '') == node_type) | 
            (ri_candidates.get(worker_col, '') == node_type)
        ].copy()
        
        return {
            'node_type': node_type,
            'cluster_count': len(node_clusters),
            'unique_jobs': node_clusters.get('job_id', node_clusters.get('cluster_id')).nunique(),
            'clusters_data': node_clusters
        }
    
    def _analyze_all_node_types(self, ri_candidates: pd.DataFrame) -> Dict[str, Any]:
        """Analyze all RI candidates regardless of node type."""
        return {
            'node_type': 'All Types',
            'cluster_count': len(ri_candidates),
            'unique_jobs': ri_candidates.get('job_id', ri_candidates.get('cluster_id')).nunique(),
            'clusters_data': ri_candidates
        }
    
    def _calculate_ri_recommendations(self, node_analysis: Dict[str, Any]) -> Dict[str, int]:
        """Calculate RI purchase recommendations."""
        clusters = node_analysis['clusters_data']
        
        # Calculate driver and worker nodes
        driver_nodes = len(clusters)  # 1 driver per cluster
        
        # Worker nodes - calculate min, avg, max scenarios
        worker_min = 0
        worker_avg = 0
        worker_max = 0
        
        for _, row in clusters.iterrows():
            min_w = int(row.get('min_autoscale_workers', 1)) if pd.notna(row.get('min_autoscale_workers')) else 1
            max_w = int(row.get('max_autoscale_workers', min_w)) if pd.notna(row.get('max_autoscale_workers')) else min_w
            
            worker_min += min_w
            worker_max += max_w
            worker_avg += (min_w + max_w) // 2
        
        return {
            'driver_nodes': driver_nodes,
            'worker_nodes_conservative': worker_min,
            'worker_nodes_moderate': worker_avg,
            'worker_nodes_aggressive': worker_max,
            'total_conservative': driver_nodes + worker_min,
            'total_moderate': driver_nodes + worker_avg,
            'total_aggressive': driver_nodes + worker_max
        }
    
    def _save_excel_report(self, ri_candidates: pd.DataFrame, node_analysis: Dict[str, Any], 
                          ri_recommendations: Dict[str, int], output_file: Optional[str] = None) -> str:
        """
        Save RI opportunity report.
        
        Args:
            ri_candidates: DataFrame with RI candidates
            node_analysis: Node type analysis results
            ri_recommendations: RI purchase recommendations
            output_file: Optional custom path for output Excel file
            
        Returns:
            Path to saved Excel file
        """
        # Determine output file path
        if output_file:
            # Use custom output file path
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
        else:
            # Auto-generate filename with timestamp
            os.makedirs(self.output_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(self.output_dir, f'RI_Opportunities_{timestamp}.xlsx')
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Summary
            summary = pd.DataFrame({
                'Metric': [
                    'Total Clusters Analyzed',
                    'RI Candidates',
                    'RI Candidate %',
                    '',
                    f"{node_analysis['node_type']} Clusters",
                    f"{node_analysis['node_type']} Unique Jobs",
                    '',
                    'RI Recommendations:',
                    'Driver Nodes',
                    'Worker Nodes (Conservative)',
                    'Worker Nodes (Moderate)',
                    'Worker Nodes (Aggressive)',
                    'Total RIs (Conservative)',
                    'Total RIs (Moderate)',
                    'Total RIs (Aggressive)'
                ],
                'Value': [
                    self.results['total_clusters'],
                    self.results['ri_candidates_count'],
                    f"{self.results['ri_candidates_pct']:.1f}%",
                    '',
                    node_analysis['cluster_count'],
                    node_analysis['unique_jobs'],
                    '',
                    '',
                    ri_recommendations['driver_nodes'],
                    ri_recommendations['worker_nodes_conservative'],
                    ri_recommendations['worker_nodes_moderate'],
                    ri_recommendations['worker_nodes_aggressive'],
                    ri_recommendations['total_conservative'],
                    ri_recommendations['total_moderate'],
                    ri_recommendations['total_aggressive']
                ]
            })
            summary.to_excel(writer, sheet_name='Summary', index=False)
            
            # All RI candidates
            ri_candidates.to_excel(writer, sheet_name='RI_Candidates', index=False)
            
            # Specific node type
            if not node_analysis['clusters_data'].empty:
                node_analysis['clusters_data'].to_excel(writer, 
                    sheet_name=f"{node_analysis['node_type'][:20]}_Clusters", index=False)
        
        return output_file
