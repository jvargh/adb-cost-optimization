"""
Databricks Utilization Analyzer Module
Provides programmatic API for cluster and query utilization analysis.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import os
import json
from typing import Optional, Dict, Any, List
warnings.filterwarnings('ignore')

from .storage_utils import StorageReader, auto_detect_input_files


class ClusterUtilizationAnalyzer:
    """
    Analyzer for Databricks cluster utilization data.
    Generates cost optimization recommendations and performance insights.
    """
    
    def __init__(self, input_path: str, output_dir: str = 'results', rules_path: Optional[str] = None):
        """
        Initialize cluster utilization analyzer.

        Args:
            input_path: Path to cluster utilization CSV file or directory.
                        Can be a local path or Azure Storage URL.
            output_dir: Directory to save output Excel files (default: 'results').
            rules_path: Full path to analyzer_rules.json.
                        Must be provided when running on Databricks so the code
                        can locate the JSON file placed alongside the wheel.
                        Example: '/Volumes/catalog/schema/volume/script/analyzer_rules.json'
                        If not provided, built-in default thresholds are used.
        """
        self.input_path = input_path
        self.output_dir = output_dir
        self.reader = StorageReader()
        self.cluster_metrics = None
        self.results = {}

        # Load analyzer rules from the path supplied by the caller.
        # analyzer_rules.json is intentionally NOT bundled inside the wheel
        # so users can edit thresholds without rebuilding.
        rules_loaded = False
        if rules_path:
            if os.path.exists(rules_path):
                try:
                    with open(rules_path, 'r') as f:
                        self.rules = json.load(f)
                    print(f"✓ Loaded analyzer rules from: {rules_path}")
                    rules_loaded = True
                except Exception as e:
                    print(f"⚠️  Warning: Could not load rules from {rules_path}: {str(e)}")
            else:
                print(f"⚠️  Warning: rules_path not found: {rules_path}")

        if not rules_loaded:
            print("⚠️  Warning: analyzer_rules.json not loaded. Using built-in default thresholds.")
            print("   Pass rules_path='<full path to analyzer_rules.json>' to load custom rules.")
            # Built-in default fallback rules
            self.rules = {
                'utilization_categorization': {
                    'thresholds': {'high': 80, 'moderate_high': 70, 'well_utilized': 50, 'under_utilized': 15, 'low': 5},
                    'categories': {
                        'idle': {'label': 'Idle'},
                        'low': {'label': 'Low Utilization'},
                        'under_utilized': {'label': 'Under-utilized'},
                        'well_utilized': {'label': 'Well-utilized'},
                        'moderate': {'label': 'Moderate (70-80%)'},
                        'high': {'label': 'High Utilization'}
                    }
                },
                'autoscaling_range_classification': {'narrow_threshold': 2, 'moderate_threshold': 5},
                'network_thresholds': {'quantile': 0.90},
                'autoscaling_recommendations': {'utilization_breakpoints': {'idle': 5, 'low': 15, 'under_utilized': 50, 'well_utilized': 80}},
                'fixed_size_recommendations': {}
            }
        
    def load_data(self) -> pd.DataFrame:
        """
        Load cluster utilization data from input path.
        
        Returns:
            pandas DataFrame with cluster utilization data
        """
        # Check if input_path is a directory or file
        if self.reader.is_azure_path(self.input_path):
            # For Azure paths, try to list files if it's a directory-like path
            if not self.input_path.endswith('.csv'):
                files = auto_detect_input_files(self.input_path, '*_cluster_utilization.csv')
                if not files:
                    raise FileNotFoundError(f"No cluster utilization CSV files found in: {self.input_path}")
                file_path = files[0]
            else:
                file_path = self.input_path
        else:
            # Local path
            if os.path.isdir(self.input_path):
                files = auto_detect_input_files(self.input_path, '*_cluster_utilization.csv')
                if not files:
                    raise FileNotFoundError(f"No cluster utilization CSV files found in: {self.input_path}")
                file_path = files[0]
            else:
                file_path = self.input_path
        
        print(f"Loading cluster utilization data from: {os.path.basename(file_path)}")
        df = self.reader.read_csv(file_path)
        print(f"✓ Loaded {len(df):,} records")
        
        return df
    
    def analyze(self, save_excel: bool = True, output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Run complete cluster utilization analysis.
        
        Args:
            save_excel: Whether to save Excel output file (default: True)
            output_file: Optional custom path for output Excel file. If not provided,
                        auto-generates filename with timestamp in output_dir.
            
        Returns:
            Dictionary with analysis results containing:
                - total_clusters: Number of clusters analyzed
                - categories: Breakdown by utilization category
                - cluster_data: DataFrame with detailed metrics
                - network_thresholds: Network traffic thresholds
                - output_file: Path to saved Excel report
        """
        print("\n" + "="*80)
        print("CLUSTER UTILIZATION ANALYSIS")
        print("="*80)
        
        # Load data
        df = self.load_data()
        
        # Preprocess and aggregate
        df = self._preprocess_data(df)
        self.cluster_metrics = self._aggregate_metrics(df)
        
        # Perform analysis
        self._parse_vm_types()
        self._analyze_autoscaling()
        self._calculate_network_thresholds()
        self._categorize_clusters()
        self._generate_recommendations()
        
        # Create results summary
        self.results = {
            'total_clusters': len(self.cluster_metrics),
            'categories': self.cluster_metrics['Category'].value_counts().to_dict(),
            'cluster_data': self.cluster_metrics,
            'network_thresholds': {
                'received_mb': getattr(self, 'NETWORK_THRESHOLD_RECEIVED', 0),
                'sent_mb': getattr(self, 'NETWORK_THRESHOLD_SENT', 0)
            }
        }
        
        # Save Excel output
        if save_excel:
            excel_output = self._save_excel_report(output_file)
            self.results['output_file'] = excel_output
            print(f"\n✓ Analysis complete! Report saved to: {excel_output}")
        
        return self.results
    
    def _preprocess_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Preprocess and clean data."""
        # Fill NaN values
        numeric_cols = ['Avg CPU Utilization', 'Peak CPU Utilization', 'Avg Memory Utilization',
                       'Max Memory Utilization', 'Avg CPU Wait', 'Max CPU Wait',
                       'Avg Network MB Received', 'Max Network MB Received',
                       'Avg Network MB Sent', 'Max Network MB Sent']
        
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].fillna(0)
        
        return df
    
    def _aggregate_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate metrics by cluster_id."""
        agg_dict = {
            'Avg CPU Utilization': 'mean',
            'Peak CPU Utilization': 'max',
            'Avg Memory Utilization': 'mean',
            'Max Memory Utilization': 'max',
            'Avg CPU Wait': 'mean',
            'Max CPU Wait': 'max',
            'Avg Network MB Received': 'mean',
            'Avg Network MB Sent': 'mean',
            'driver': 'count',
            'job_id': 'first',
            'job_name': 'first',
            'driver_node_type': 'first',
            'worker_node_type': 'first',
            'min_autoscale_workers': 'first',
            'max_autoscale_workers': 'first'
        }
        
        # Add max network metrics if available
        if 'Max Network MB Received' in df.columns:
            agg_dict['Max Network MB Received'] = 'max'
        if 'Max Network MB Sent' in df.columns:
            agg_dict['Max Network MB Sent'] = 'max'
        if 'worker_count' in df.columns:
            agg_dict['worker_count'] = 'first'
        
        cluster_metrics = df.groupby('cluster_id').agg(agg_dict).round(2)
        
        # Rename columns
        new_cols = {
            'Avg CPU Utilization': 'Avg_CPU_Util',
            'Peak CPU Utilization': 'Peak_CPU_Util',
            'Avg Memory Utilization': 'Avg_Memory_Util',
            'Max Memory Utilization': 'Max_Memory_Util',
            'Avg CPU Wait': 'Avg_CPU_Wait',
            'Max CPU Wait': 'Max_CPU_Wait',
            'Avg Network MB Received': 'Avg_Network_MB_Received',
            'Avg Network MB Sent': 'Avg_Network_MB_Sent',
            'driver': 'Node_Count_Records'
        }
        
        if 'Max Network MB Received' in cluster_metrics.columns:
            new_cols['Max Network MB Received'] = 'Max_Network_MB_Received'
        if 'Max Network MB Sent' in cluster_metrics.columns:
            new_cols['Max Network MB Sent'] = 'Max_Network_MB_Sent'
        
        cluster_metrics.rename(columns=new_cols, inplace=True)
        cluster_metrics.reset_index(inplace=True)
        
        print(f"✓ Aggregated to {len(cluster_metrics)} unique clusters")
        
        return cluster_metrics
    
    def _parse_vm_types(self):
        """Parse VM types for driver and worker nodes."""
        # Simplified VM parsing - add full implementation as needed
        self.cluster_metrics['VM_Series'] = self.cluster_metrics['worker_node_type'].str.extract(r'Standard_([A-Z])', expand=False)
        print("✓ VM types parsed")
    
    def _analyze_autoscaling(self):
        """Analyze autoscaling configurations."""
        # Get thresholds from JSON config
        narrow_threshold = self.rules['autoscaling_range_classification']['narrow_threshold']
        moderate_threshold = self.rules['autoscaling_range_classification']['moderate_threshold']
        
        def analyze_config(row):
            min_w = row.get('min_autoscale_workers')
            max_w = row.get('max_autoscale_workers')
            worker_count = row.get('worker_count')
            
            if pd.isna(min_w) or pd.isna(max_w) or min_w == '' or max_w == '':
                if not pd.isna(worker_count) and worker_count != '' and worker_count != 0:
                    return 'N/A', f'Fixed cluster with {int(worker_count)} worker(s)'
                # If worker_count is also zero or missing, return N/A
                return 'N/A', 'Autoscaling configuration not available'
            
            min_w = int(min_w)
            max_w = int(max_w)
            
            if min_w == max_w:
                return 'Fixed Size', f'Fixed at {min_w} workers'
            
            range_size = max_w - min_w
            if range_size <= narrow_threshold:
                return 'Narrow Range', f'{min_w}-{max_w} workers'
            elif range_size <= moderate_threshold:
                return 'Moderate Range', f'{min_w}-{max_w} workers'
            else:
                return 'Wide Range', f'{min_w}-{max_w} workers'
        
        self.cluster_metrics[['autoscaling_status', 'autoscaling_pattern']] = \
            self.cluster_metrics.apply(analyze_config, axis=1, result_type='expand')
        
        print("✓ Autoscaling configurations analyzed")
    
    def _calculate_network_thresholds(self):
        """Calculate network traffic thresholds using configured percentile."""
        quantile_value = self.rules['network_thresholds']['quantile']
        
        # Calculate thresholds for average network metrics
        self.NETWORK_THRESHOLD_RECEIVED_AVG = self.cluster_metrics['Avg_Network_MB_Received'].quantile(quantile_value)
        self.NETWORK_THRESHOLD_SENT_AVG = self.cluster_metrics['Avg_Network_MB_Sent'].quantile(quantile_value)
        
        # Calculate thresholds for max network metrics if available
        if 'Max_Network_MB_Received' in self.cluster_metrics.columns:
            max_received_values = self.cluster_metrics['Max_Network_MB_Received'].dropna()
            if len(max_received_values) > 0 and max_received_values.max() > 0:
                self.NETWORK_THRESHOLD_RECEIVED_MAX = max_received_values.quantile(quantile_value)
            else:
                self.NETWORK_THRESHOLD_RECEIVED_MAX = self.NETWORK_THRESHOLD_RECEIVED_AVG
        else:
            self.NETWORK_THRESHOLD_RECEIVED_MAX = self.NETWORK_THRESHOLD_RECEIVED_AVG
            
        if 'Max_Network_MB_Sent' in self.cluster_metrics.columns:
            max_sent_values = self.cluster_metrics['Max_Network_MB_Sent'].dropna()
            if len(max_sent_values) > 0 and max_sent_values.max() > 0:
                self.NETWORK_THRESHOLD_SENT_MAX = max_sent_values.quantile(quantile_value)
            else:
                self.NETWORK_THRESHOLD_SENT_MAX = self.NETWORK_THRESHOLD_SENT_AVG
        else:
            self.NETWORK_THRESHOLD_SENT_MAX = self.NETWORK_THRESHOLD_SENT_AVG
        
        print(f"✓ Network thresholds ({int(quantile_value*100)}th percentile):")
        print(f"  Avg - Received={self.NETWORK_THRESHOLD_RECEIVED_AVG:.2f} MB, Sent={self.NETWORK_THRESHOLD_SENT_AVG:.2f} MB")
        print(f"  Max - Received={self.NETWORK_THRESHOLD_RECEIVED_MAX:.2f} MB, Sent={self.NETWORK_THRESHOLD_SENT_MAX:.2f} MB")
        
        # Count how many clusters exceed thresholds
        high_net_avg_rx = (self.cluster_metrics['Avg_Network_MB_Received'] > self.NETWORK_THRESHOLD_RECEIVED_AVG).sum()
        high_net_avg_tx = (self.cluster_metrics['Avg_Network_MB_Sent'] > self.NETWORK_THRESHOLD_SENT_AVG).sum()
        print(f"  Clusters exceeding Avg thresholds: RX={high_net_avg_rx}, TX={high_net_avg_tx}")
        
        if 'Max_Network_MB_Received' in self.cluster_metrics.columns:
            high_net_max_rx = (self.cluster_metrics['Max_Network_MB_Received'] > self.NETWORK_THRESHOLD_RECEIVED_MAX).sum()
            high_net_max_tx = (self.cluster_metrics['Max_Network_MB_Sent'] > self.NETWORK_THRESHOLD_SENT_MAX).sum()
            print(f"  Clusters exceeding Max thresholds: RX={high_net_max_rx}, TX={high_net_max_tx}")
    
    def _categorize_clusters(self):
        """Categorize clusters by utilization using configured thresholds including CPU, Memory, and Network."""
        # Get thresholds from JSON config
        thresholds = self.rules['utilization_categorization']['thresholds']
        categories = self.rules['utilization_categorization']['categories']
        
        def categorize(row):
            cpu_avg = row['Avg_CPU_Util']
            cpu_peak = row['Peak_CPU_Util']
            mem_avg = row['Avg_Memory_Util']
            mem_max = row['Max_Memory_Util']
            net_received_avg = row['Avg_Network_MB_Received']
            net_sent_avg = row['Avg_Network_MB_Sent']
            
            # Get max network values if available - handle missing/NaN properly
            net_received_max = row.get('Max_Network_MB_Received', 0)
            net_sent_max = row.get('Max_Network_MB_Sent', 0)
            
            # Convert to float and handle NaN/None
            if pd.isna(net_received_max) or net_received_max == '':
                net_received_max = 0
            else:
                net_received_max = float(net_received_max)
                
            if pd.isna(net_sent_max) or net_sent_max == '':
                net_sent_max = 0
            else:
                net_sent_max = float(net_sent_max)
            
            # Calculate max utilization from CPU and Memory (already uses max OR avg)
            max_compute_util = max(cpu_avg, cpu_peak, mem_avg, mem_max)
            
            # Get absolute threshold from config
            absolute_threshold_mb = self.rules['network_thresholds'].get('absolute_threshold_mb', 100000)
            
            # Check if network is high (compare avg to avg threshold, max to max threshold)
            network_high_avg_rx = net_received_avg > self.NETWORK_THRESHOLD_RECEIVED_AVG
            network_high_avg_tx = net_sent_avg > self.NETWORK_THRESHOLD_SENT_AVG
            network_high_max_rx = net_received_max > self.NETWORK_THRESHOLD_RECEIVED_MAX
            network_high_max_tx = net_sent_max > self.NETWORK_THRESHOLD_SENT_MAX
            
            # Fallback: Extremely high absolute network values from config
            extremely_high_network = (net_received_avg > absolute_threshold_mb or 
                                     net_sent_avg > absolute_threshold_mb or 
                                     net_received_max > absolute_threshold_mb or 
                                     net_sent_max > absolute_threshold_mb)
            
            network_high = network_high_avg_rx or network_high_avg_tx or network_high_max_rx or network_high_max_tx or extremely_high_network
            
            # Build reasons list for remark
            reasons = []
            
            # Add high CPU/Memory reasons
            if cpu_peak > thresholds['high']:
                reasons.append(f"Peak CPU {cpu_peak:.1f}%")
            elif cpu_avg > thresholds['high']:
                reasons.append(f"Avg CPU {cpu_avg:.1f}%")
            
            if mem_max > thresholds['high']:
                reasons.append(f"Max Memory {mem_max:.1f}%")
            elif mem_avg > thresholds['high']:
                reasons.append(f"Avg Memory {mem_avg:.1f}%")
            
            # Add network reasons if high (check all: avg and max, received and sent)
            if network_high_avg_rx:
                reasons.append(f"High Network RX Avg {net_received_avg:.2f} MB")
            if network_high_max_rx:
                reasons.append(f"High Network RX Max {net_received_max:.2f} MB")
            if network_high_avg_tx:
                reasons.append(f"High Network TX Avg {net_sent_avg:.2f} MB")
            if network_high_max_tx:
                reasons.append(f"High Network TX Max {net_sent_max:.2f} MB")
            
            # Determine base category from compute utilization
            if max_compute_util > thresholds['high']:
                base_category = 'high'
            elif max_compute_util > thresholds['moderate_high']:
                base_category = 'moderate'
            elif max_compute_util >= thresholds['well_utilized']:
                base_category = 'well_utilized'
            elif max_compute_util >= thresholds['under_utilized']:
                base_category = 'under_utilized'
            elif max_compute_util >= thresholds['low']:
                base_category = 'low'
            else:
                base_category = 'idle'
            
            # CRITICAL FIX: Upgrade category if network is high
            # Network-intensive workloads are HIGH utilization clusters
            if network_high and base_category in ['idle', 'low', 'under_utilized', 'well_utilized', 'moderate']:
                category = categories['high']['label']
                # Ensure network reason is captured
                if not any('Network' in r for r in reasons):
                    reasons.append(f"Network-intensive workload")
            else:
                category = categories[base_category]['label']
            
            # Add default remark if reasons list is empty
            if not reasons:
                if base_category == 'high':
                    if cpu_peak == max_compute_util:
                        reasons.append(f"Peak CPU {cpu_peak:.1f}%")
                    elif mem_max == max_compute_util:
                        reasons.append(f"Max Memory {mem_max:.1f}%")
                    else:
                        reasons.append(f"Max Util {max_compute_util:.1f}%")
                elif base_category == 'moderate':
                    reasons.append(f"Max Util {max_compute_util:.1f}%")
                elif base_category == 'well_utilized':
                    reasons.append(f"Max Util {max_compute_util:.1f}%")
                elif base_category == 'under_utilized':
                    reasons.append(f"Util {max_compute_util:.1f}% below optimal")
                elif base_category == 'low':
                    reasons.append(f"Low util {max_compute_util:.1f}%")
                else:  # idle
                    reasons.append(f"Idle {max_compute_util:.1f}%")
            
            remark = ' | '.join(reasons)
            return category, remark
        
        self.cluster_metrics[['Category', 'Remark']] = \
            self.cluster_metrics.apply(categorize, axis=1, result_type='expand')
        
        print("\n✓ Cluster Categorization (including CPU, Memory, and Network):")
        print(self.cluster_metrics['Category'].value_counts().to_string())
    
    def _generate_recommendations(self):
        """Generate intelligent VM sizing and autoscaling recommendations based on utilization."""
        # Get thresholds from JSON config
        as_util_breakpoints = self.rules['autoscaling_recommendations']['utilization_breakpoints']
        as_range_thresholds = self.rules['autoscaling_range_classification']
        fixed_util_thresholds = self.rules['utilization_categorization']['thresholds']
        
        def generate_autoscaling_recommendation(row):
            """Generate recommendation for autoscaling clusters."""
            status = row.get('autoscaling_status', 'Unknown')
            min_w = row.get('min_autoscale_workers')
            max_w = row.get('max_autoscale_workers')
            max_util = max(
                row.get('Avg_CPU_Util', 0),
                row.get('Peak_CPU_Util', 0),
                row.get('Avg_Memory_Util', 0),
                row.get('Max_Memory_Util', 0)
            )
            
            # Handle non-autoscaling clusters
            if status in ['N/A', 'Unknown', 'Fixed Size']:
                return None
            
            # Ensure we have valid min/max values
            if pd.isna(min_w) or pd.isna(max_w):
                return "Review autoscaling configuration"
            
            min_w = int(min_w)
            max_w = int(max_w)
            range_size = max_w - min_w
            
            # Determine range classification using JSON thresholds
            if range_size <= as_range_thresholds['narrow_threshold']:
                range_class = 'Narrow'
            elif range_size <= as_range_thresholds['moderate_threshold']:
                range_class = 'Moderate'
            else:
                range_class = 'Wide'
            
            # Generate recommendations based on range + utilization using JSON breakpoints
            if max_util < as_util_breakpoints['idle']:  # IDLE
                if range_class == 'Narrow':
                    return f"CRITICAL: Idle cluster. Reduce to {min_w}-{min(min_w+1, max_w)} or terminate if unused"
                elif range_class == 'Moderate':
                    return f"CRITICAL: Idle cluster. Reduce to {min_w}-{min(min_w+1, max_w)} (potential 60-80% savings)"
                else:  # Wide
                    return f"CRITICAL: Idle cluster with wide range. Reduce to {min_w}-{min(min_w+2, max_w)} or terminate (potential 70-90% savings)"
            
            elif max_util < as_util_breakpoints['low']:  # LOW
                if range_class == 'Narrow':
                    return f"HIGH: Low utilization. Consider reducing to {min_w}-{min(min_w+1, max_w)} or review workload necessity"
                elif range_class == 'Moderate':
                    new_max = max(min_w + 2, int((min_w + max_w) / 2))
                    return f"HIGH: Low utilization. Reduce max to {new_max} ({min_w}-{new_max})"
                else:  # Wide
                    new_max = max(min_w + 3, int(max_w * 0.5))
                    return f"CRITICAL: Low utilization with wide range. Reduce to {min_w}-{new_max} (potential 40-60% savings)"
            
            elif max_util < as_util_breakpoints['under_utilized']:  # UNDER-UTILIZED
                if range_class == 'Narrow':
                    return f"LOW: Under-utilized but narrow range is acceptable. Monitor or reduce max to {min(min_w+1, max_w)}"
                elif range_class == 'Moderate':
                    new_max = max(min_w + 2, int(max_w * 0.8))
                    return f"MEDIUM: Under-utilized. Consider reducing max to {new_max} ({min_w}-{new_max})"
                else:  # Wide
                    new_max = max(min_w + 4, int(max_w * 0.7))
                    return f"HIGH: Under-utilized with wide range. Reduce to {min_w}-{new_max} for better cost efficiency"
            
            elif max_util <= as_util_breakpoints['well_utilized']:  # WELL-UTILIZED
                if range_class == 'Narrow':
                    return f"LOW: Well-configured. Optionally expand to {min_w}-{max_w+1} for more flexibility"
                elif range_class == 'Moderate':
                    return f"LOW: Well-configured and appropriately sized. No action needed"
                else:  # Wide
                    return f"LOW: Well-utilized. Wide range provides good elasticity. No action needed"
            
            else:  # HIGH (>80%)
                if range_class == 'Narrow':
                    new_max = max_w + 2
                    return f"HIGH: High utilization with narrow range. Increase to {min_w}-{new_max} to handle peaks"
                elif range_class == 'Moderate':
                    new_max = int(max_w * 1.3)
                    return f"HIGH: High utilization. Increase max to {new_max} ({min_w}-{new_max}) to prevent bottlenecks"
                else:  # Wide
                    new_max = int(max_w * 1.2)
                    return f"MEDIUM: High utilization but wide range should handle peaks. Consider increasing to {min_w}-{new_max} if consistent"
        
        def generate_fixed_size_recommendation(row):
            """Generate recommendation for fixed-size clusters."""
            status = row.get('autoscaling_status', 'Unknown')
            worker_count = row.get('worker_count')
            
            # Only handle fixed-size clusters
            if status not in ['N/A', 'Fixed Size']:
                # Check if it's truly fixed by looking at min==max
                min_w = row.get('min_autoscale_workers')
                max_w = row.get('max_autoscale_workers')
                if not (pd.notna(min_w) and pd.notna(max_w) and int(min_w) == int(max_w)):
                    return None
                worker_count = int(min_w)
            
            if pd.isna(worker_count) or worker_count == 0:
                return "Review cluster configuration"
            
            worker_count = int(worker_count)
            max_util = max(
                row.get('Avg_CPU_Util', 0),
                row.get('Peak_CPU_Util', 0),
                row.get('Avg_Memory_Util', 0),
                row.get('Max_Memory_Util', 0)
            )
            
            # Generate recommendations based on worker count + utilization using JSON thresholds
            if max_util < fixed_util_thresholds['low']:  # IDLE
                if worker_count == 1:
                    return "CRITICAL: Idle cluster. Terminate if unused or keep for on-demand dev work"
                elif worker_count <= 4:
                    savings = int((worker_count - 1) / worker_count * 100)
                    return f"CRITICAL: Idle. Reduce from {worker_count} to 1 worker ({savings}% savings) or terminate"
                else:
                    return f"CRITICAL: Idle. Reduce from {worker_count} to 1-2 workers OR enable autoscaling 1-2 (70-85% savings)"
            
            elif max_util < fixed_util_thresholds['under_utilized']:  # LOW
                if worker_count == 1:
                    return "LOW: Light usage appropriate for dev/test. Keep as-is"
                elif worker_count <= 4:
                    target = max(1, worker_count - 2)
                    savings = int(2 / worker_count * 100)
                    return f"HIGH: Low utilization. Reduce from {worker_count} to {target} workers ({savings}% savings)"
                elif worker_count <= 8:
                    target = max(2, worker_count // 2)
                    as_max = worker_count // 2
                    return f"HIGH: Over-provisioned. Reduce to {target} workers OR enable autoscaling 1-{as_max}"
                else:
                    target = max(3, worker_count // 3)
                    as_max = min(worker_count // 2, 8)
                    return f"CRITICAL: Severely over-provisioned. Reduce to {target} workers OR enable autoscaling 2-{as_max}"
            
            elif max_util < fixed_util_thresholds['well_utilized']:  # UNDER-UTILIZED
                if worker_count <= 3:
                    return f"LOW: Acceptable for small cluster. Consider autoscaling 1-{worker_count+1} for cost flexibility"
                elif worker_count <= 6:
                    target = max(2, worker_count - 2)
                    return f"MEDIUM: Under-utilized. Reduce to {target} workers OR enable autoscaling {target}-{worker_count}"
                else:
                    target = max(4, int(worker_count * 0.6))
                    return f"HIGH: Under-utilized. Reduce from {worker_count} to {target} workers OR enable autoscaling {target}-{worker_count}"
            
            elif max_util <= fixed_util_thresholds['high']:  # WELL-UTILIZED
                if worker_count <= 4:
                    return "LOW: Optimal sizing for workload. No action needed"
                elif worker_count <= 8:
                    as_min = max(2, worker_count - 2)
                    as_max = worker_count + 2
                    return f"LOW: Well-sized. Optional: Enable autoscaling {as_min}-{as_max} for flexibility"
                else:
                    as_min = max(int(worker_count * 0.6), 4)
                    as_max = int(worker_count * 1.3)
                    return f"MEDIUM: Well-utilized. Consider autoscaling {as_min}-{as_max} to optimize costs during low-demand"
            
            else:  # HIGH (>80%)
                if worker_count == 1:
                    return "HIGH: Under-provisioned. Add 1 worker (fixed 2) OR enable autoscaling 1-3"
                elif worker_count <= 3:
                    target = worker_count + 1
                    as_max = worker_count * 2
                    return f"HIGH: Under-provisioned. Add 1 worker (fixed {target}) OR enable autoscaling {worker_count}-{as_max}"
                elif worker_count <= 6:
                    add_nodes = 2
                    as_max = int(worker_count * 1.5)
                    return f"HIGH: Under-provisioned. Add {add_nodes} workers (fixed {worker_count + add_nodes}) OR enable autoscaling {worker_count}-{as_max}"
                elif worker_count <= 10:
                    add_nodes = 3
                    as_max = int(worker_count * 1.4)
                    return f"HIGH: Under-provisioned. Add {add_nodes} workers (fixed {worker_count + add_nodes}) OR enable autoscaling {worker_count}-{as_max}"
                else:
                    add_nodes = int(worker_count * 0.25)
                    as_max = int(worker_count * 1.3)
                    return f"CRITICAL: Under-provisioned. Add {add_nodes} workers (fixed {worker_count + add_nodes}) OR enable autoscaling {worker_count}-{as_max}"
        
        # Apply recommendations based on cluster type
        def apply_recommendation(row):
            status = row.get('autoscaling_status', 'Unknown')
            
            # Try fixed-size recommendation first
            if status in ['N/A', 'Fixed Size']:
                rec = generate_fixed_size_recommendation(row)
                if rec:
                    return rec
            
            # Try autoscaling recommendation
            if status in ['Narrow Range', 'Moderate Range', 'Wide Range']:
                rec = generate_autoscaling_recommendation(row)
                if rec:
                    return rec
            
            # Fallback for unknown configurations
            return "Review cluster configuration"
        
        self.cluster_metrics['Autoscaling_Recommendation'] = self.cluster_metrics.apply(
            apply_recommendation, axis=1
        )
        
        # Generate VM size recommendations based on utilization and VM series
        def generate_vm_size_recommendation(row):
            """Generate VM sizing recommendation based on utilization category and VM series."""
            category = row.get('Category', 'Unknown')
            
            # Parse VM series from worker_node_type
            worker_type = str(row.get('worker_node_type', ''))
            vm_series = ''
            if 'Standard_E' in worker_type:
                vm_series = 'E'
            elif 'Standard_F' in worker_type:
                vm_series = 'F'
            elif 'Standard_L' in worker_type:
                vm_series = 'L'
            elif 'Standard_D' in worker_type:
                vm_series = 'D'
            
            recommendations = []
            
            # Get VM size recommendations from JSON config
            vm_recs = self.rules.get('vm_size_recommendations', {})
            category_recs = vm_recs.get('category_recommendations', {})
            vm_series_guidance = vm_recs.get('vm_series_guidance', {})
            fallback = vm_recs.get('fallback_recommendation', 'Review utilization patterns and adjust VM size if needed')
            
            # Get recommendations for this category
            if category in category_recs:
                cat_rec = category_recs[category]
                recommendations.append(cat_rec.get('primary', ''))
                recommendations.extend(cat_rec.get('secondary', []))
            else:
                recommendations.append('Review utilization patterns')
            
            # Add VM series-specific guidance from JSON
            if vm_series and vm_series in vm_series_guidance:
                recommendations.append(vm_series_guidance[vm_series])
            
            return ' | '.join([r for r in recommendations if r]) if recommendations else fallback
        
        self.cluster_metrics['VM_Size_Recommendation'] = self.cluster_metrics.apply(
            generate_vm_size_recommendation, axis=1
        )
        
        print("✓ Intelligent recommendations generated for fixed-size and autoscaling clusters")
    
    def _save_excel_report(self, output_file: Optional[str] = None) -> str:
        """
        Save analysis results to Excel file.
        
        Args:
            output_file: Optional custom path for output Excel file. If not provided,
                        auto-generates filename with timestamp in output_dir.
        
        Returns:
            Path to saved Excel file
        """
        # Determine output file path
        if output_file:
            # Use custom output file path
            # Ensure directory exists
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
        else:
            # Create output directory and auto-generate filename
            os.makedirs(self.output_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(self.output_dir, f'Cluster_Utilization_Analysis_{timestamp}.xlsx')
        
        # Select output columns
        output_cols = [
            'cluster_id', 'job_id', 'job_name', 'Category', 'Remark',
            'Avg_CPU_Util', 'Peak_CPU_Util', 'Avg_Memory_Util', 'Max_Memory_Util',
            'driver_node_type', 'worker_node_type',
            'autoscaling_status', 'autoscaling_pattern',
            'VM_Size_Recommendation', 'Autoscaling_Recommendation'
        ]
        
        # Add optional columns if they exist
        if 'worker_count' in self.cluster_metrics.columns:
            output_cols.insert(5, 'worker_count')
        if 'min_autoscale_workers' in self.cluster_metrics.columns:
            output_cols.insert(6, 'min_autoscale_workers')
        if 'max_autoscale_workers' in self.cluster_metrics.columns:
            output_cols.insert(7, 'max_autoscale_workers')
        if 'Avg_Network_MB_Received' in self.cluster_metrics.columns:
            output_cols.append('Avg_Network_MB_Received')
        if 'Max_Network_MB_Received' in self.cluster_metrics.columns:
            output_cols.append('Max_Network_MB_Received')
        if 'Avg_Network_MB_Sent' in self.cluster_metrics.columns:
            output_cols.append('Avg_Network_MB_Sent')
        if 'Max_Network_MB_Sent' in self.cluster_metrics.columns:
            output_cols.append('Max_Network_MB_Sent')
        
        # Filter to existing columns
        output_cols = [col for col in output_cols if col in self.cluster_metrics.columns]
        output_df = self.cluster_metrics[output_cols].copy()
        
        # Save to Excel
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = pd.DataFrame({
                'Metric': ['Total Clusters', 'Idle', 'Low Utilization', 'Under-utilized', 
                          'Well-utilized', 'High Utilization'],
                'Count': [
                    len(output_df),
                    len(output_df[output_df['Category'] == 'Idle']),
                    len(output_df[output_df['Category'] == 'Low Utilization']),
                    len(output_df[output_df['Category'] == 'Under-utilized']),
                    len(output_df[output_df['Category'] == 'Well-utilized']),
                    len(output_df[output_df['Category'] == 'High Utilization'])
                ]
            })
            summary_data.to_excel(writer, sheet_name='Summary', index=False)
            
            # All clusters
            output_df.to_excel(writer, sheet_name='All Clusters', index=False)
        
        return output_file


class QueryUtilizationAnalyzer:
    """
    Analyzer for Databricks SQL query utilization data.
    Identifies optimization opportunities and cost insights.
    """
    
    def __init__(self, input_path: str, output_dir: str = 'results'):
        """
        Initialize query utilization analyzer.
        
        Args:
            input_path: Path to SQL query usage CSV file or directory
                       Can be local path or Azure Storage URL
            output_dir: Directory to save output Excel files (default: 'results')
        """
        self.input_path = input_path
        self.output_dir = output_dir
        self.reader = StorageReader()
        self.query_data = None
        self.results = {}
        
    def load_data(self) -> pd.DataFrame:
        """
        Load SQL query utilization data from input path.
        
        Returns:
            pandas DataFrame with query utilization data
        """
        # Check if input_path is a directory or file
        if self.reader.is_azure_path(self.input_path):
            if not self.input_path.endswith('.csv'):
                files = auto_detect_input_files(self.input_path, '*_sql_query_usage.csv')
                if not files:
                    raise FileNotFoundError(f"No SQL query usage CSV files found in: {self.input_path}")
                file_path = files[0]
            else:
                file_path = self.input_path
        else:
            if os.path.isdir(self.input_path):
                files = auto_detect_input_files(self.input_path, '*_sql_query_usage.csv')
                if not files:
                    raise FileNotFoundError(f"No SQL query usage CSV files found in: {self.input_path}")
                file_path = files[0]
            else:
                file_path = self.input_path
        
        print(f"Loading SQL query utilization data from: {os.path.basename(file_path)}")
        df = self.reader.read_csv(file_path)
        print(f"✓ Loaded {len(df):,} queries")
        
        return df
    
    def analyze(self, save_excel: bool = True, output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Run complete SQL query utilization analysis.
        
        Args:
            save_excel: Whether to save Excel output file (default: True)
            output_file: Optional custom path for output Excel file. If not provided,
                        auto-generates filename with timestamp in output_dir.
            
        Returns:
            Dictionary with analysis results containing:
                - total_queries: Total number of queries analyzed
                - unique_users: Number of unique users
                - unique_warehouses: Number of unique warehouses
                - failed_queries: Count of failed queries
                - total_dbu_cost: Total estimated DBU cost
                - avg_duration_seconds: Average query duration
                - user_stats: Per-user statistics
                - warehouse_stats: Per-warehouse statistics
                - insights: Generated insights and recommendations
                - output_file: Path to saved Excel report
        """
        print("\n" + "="*80)
        print("SQL QUERY UTILIZATION ANALYSIS")
        print("="*80)
        
        # Load data
        df = self.load_data()
        
        # Preprocess
        df = self._preprocess_data(df)
        self.query_data = df
        
        # Perform analysis
        user_stats = self._analyze_users()
        warehouse_stats = self._analyze_warehouses()
        insights = self._generate_insights()
        
        # Create results summary
        self.results = {
            'total_queries': len(df),
            'unique_users': df['executed_by'].nunique(),
            'unique_warehouses': df['warehouse_id'].nunique(),
            'failed_queries': df['is_failed'].sum(),
            'total_dbu_cost': df['estimated_dbu_cost'].sum(),
            'avg_duration_seconds': df['duration_seconds'].mean(),
            'user_stats': user_stats,
            'warehouse_stats': warehouse_stats,
            'insights': insights
        }
        
        # Save Excel output
        if save_excel:
            excel_output = self._save_excel_report(output_file)
            self.results['output_file'] = excel_output
            print(f"\n✓ Analysis complete! Report saved to: {excel_output}")
        
        return self.results
    
    def _preprocess_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Preprocess and clean query data."""
        # Fill NaN values
        df['total_duration_ms'] = df['total_duration_ms'].fillna(0)
        df['estimated_dbu_cost'] = df['estimated_dbu_cost'].fillna(0)
        df['error_message'] = df['error_message'].fillna('')
        
        # Convert duration to seconds
        df['duration_seconds'] = df['total_duration_ms'] / 1000
        
        # Identify failed queries
        df['is_failed'] = df['error_message'].apply(lambda x: len(str(x).strip()) > 0)
        
        print(f"✓ Preprocessed {len(df)} queries")
        print(f"  - Failed: {df['is_failed'].sum()} ({df['is_failed'].sum()/len(df)*100:.1f}%)")
        print(f"  - Successful: {(~df['is_failed']).sum()} ({(~df['is_failed']).sum()/len(df)*100:.1f}%)")
        
        return df
    
    def _analyze_users(self) -> pd.DataFrame:
        """Analyze query patterns by user."""
        user_stats = self.query_data.groupby('executed_by').agg({
            'query_id': 'count',
            'total_duration_ms': ['sum', 'mean'],
            'estimated_dbu_cost': 'sum',
            'is_failed': 'sum'
        }).round(2)
        
        user_stats.columns = ['Query_Count', 'Total_Duration_ms', 'Avg_Duration_ms', 
                              'Total_DBU_Cost', 'Failed_Queries']
        user_stats['Success_Rate_%'] = ((user_stats['Query_Count'] - user_stats['Failed_Queries']) / 
                                         user_stats['Query_Count'] * 100).round(2)
        user_stats.reset_index(inplace=True)
        user_stats.sort_values('Total_DBU_Cost', ascending=False, inplace=True)
        
        print(f"✓ Analyzed {len(user_stats)} users")
        
        return user_stats
    
    def _analyze_warehouses(self) -> pd.DataFrame:
        """Analyze query patterns by warehouse."""
        warehouse_stats = self.query_data.groupby('warehouse_id').agg({
            'query_id': 'count',
            'estimated_dbu_cost': 'sum',
            'duration_seconds': 'mean'
        }).round(2)
        
        warehouse_stats.columns = ['Query_Count', 'Total_DBU_Cost', 'Avg_Duration_Sec']
        warehouse_stats.reset_index(inplace=True)
        warehouse_stats.sort_values('Total_DBU_Cost', ascending=False, inplace=True)
        
        print(f"✓ Analyzed {len(warehouse_stats)} warehouses")
        
        return warehouse_stats
    
    def _generate_insights(self) -> List[str]:
        """Generate optimization insights."""
        insights = []
        
        # Top expensive user
        top_user = self.results.get('user_stats')
        if top_user is not None and not top_user.empty:
            insights.append(f"Top user by cost: {top_user.iloc[0]['executed_by']}")
        
        # Failed queries
        failed_count = self.results.get('failed_queries', 0)
        if failed_count > 0:
            insights.append(f"{failed_count} failed queries need investigation")
        
        # Long-running queries
        long_running = self.query_data[self.query_data['duration_seconds'] > 300]
        if not long_running.empty:
            insights.append(f"{len(long_running)} queries running >5 minutes")
        
        print(f"✓ Generated {len(insights)} insights")
        
        return insights
    
    def _save_excel_report(self, output_file: Optional[str] = None) -> str:
        """
        Save analysis results to Excel file.
        
        Args:
            output_file: Optional custom path for output Excel file. If not provided,
                        auto-generates filename with timestamp in output_dir.
        
        Returns:
            Path to saved Excel file
        """
        # Determine output file path
        if output_file:
            # Use custom output file path
            # Ensure directory exists
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
        else:
            # Create output directory and auto-generate filename
            os.makedirs(self.output_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(self.output_dir, f'SQL_Query_Analysis_{timestamp}.xlsx')
        
        # Save to Excel
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = pd.DataFrame({
                'Metric': [
                    'Total Queries',
                    'Unique Users',
                    'Unique Warehouses',
                    'Failed Queries',
                    'Total DBU Cost',
                    'Avg Duration (sec)'
                ],
                'Value': [
                    self.results['total_queries'],
                    self.results['unique_users'],
                    self.results['unique_warehouses'],
                    self.results['failed_queries'],
                    f"{self.results['total_dbu_cost']:.2f}",
                    f"{self.results['avg_duration_seconds']:.2f}"
                ]
            })
            summary_data.to_excel(writer, sheet_name='Summary', index=False)
            
            # User analysis
            self.results['user_stats'].to_excel(writer, sheet_name='User Analysis', index=False)
            
            # Warehouse analysis
            self.results['warehouse_stats'].to_excel(writer, sheet_name='Warehouse Analysis', index=False)
            
            # Top expensive queries
            top_expensive = self.query_data.nlargest(100, 'estimated_dbu_cost')[
                ['query_id', 'execution_date', 'executed_by', 'warehouse_id', 
                 'total_duration_ms', 'estimated_dbu_cost', 'statement_type']
            ]
            top_expensive.to_excel(writer, sheet_name='Top 100 Expensive', index=False)
            
            # Failed queries
            failed = self.query_data[self.query_data['is_failed']][
                ['query_id', 'execution_date', 'executed_by', 'warehouse_id',
                 'error_message', 'statement_type']
            ]
            if not failed.empty:
                failed.to_excel(writer, sheet_name='Failed Queries', index=False)
        
        return output_file


def run_all_analysis(
    cluster_input_path: Optional[str] = None,
    query_input_path: Optional[str] = None,
    output_dir: str = 'results'
) -> Dict[str, Any]:
    """
    Run both cluster and query utilization analysis.
    
    Args:
        cluster_input_path: Path to cluster utilization CSV (local or Azure Storage)
        query_input_path: Path to SQL query usage CSV (local or Azure Storage)
        output_dir: Output directory for Excel reports (default: 'results')
        
    Returns:
        Dictionary with combined results from both analyses
    """
    print("="*80)
    print("DATABRICKS UTILIZATION ANALYSIS - MASTER SCRIPT")
    print("="*80)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    results = {
        'cluster_analysis': None,
        'query_analysis': None,
        'errors': []
    }
    
    # Run cluster analysis
    if cluster_input_path:
        try:
            print("\n[1/2] RUNNING CLUSTER UTILIZATION ANALYSIS")
            print("="*80)
            analyzer = ClusterUtilizationAnalyzer(cluster_input_path, output_dir)
            results['cluster_analysis'] = analyzer.analyze()
            print("✅ Cluster analysis completed successfully!")
        except Exception as e:
            error_msg = f"Cluster analysis failed: {str(e)}"
            print(f"❌ {error_msg}")
            results['errors'].append(error_msg)
    else:
        print("\n⚠️  Skipping cluster analysis - No input path provided")
    
    # Run query analysis
    if query_input_path:
        try:
            print("\n[2/2] RUNNING SQL QUERY UTILIZATION ANALYSIS")
            print("="*80)
            analyzer = QueryUtilizationAnalyzer(query_input_path, output_dir)
            results['query_analysis'] = analyzer.analyze()
            print("✅ Query analysis completed successfully!")
        except Exception as e:
            error_msg = f"Query analysis failed: {str(e)}"
            print(f"❌ {error_msg}")
            results['errors'].append(error_msg)
    else:
        print("\n⚠️  Skipping query analysis - No input path provided")
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print(f"\nFinished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # List generated reports
    if os.path.exists(output_dir):
        excel_files = [f for f in os.listdir(output_dir) if f.endswith('.xlsx')]
        if excel_files:
            print(f"\n📊 Generated {len(excel_files)} report(s) in '{output_dir}/' directory")
    
    return results


def run_consolidated_cluster_analysis(
    cluster_input_path: str,
    output_dir: str,
    temp_dir: Optional[str] = None,
    job_input_path: Optional[str] = None,
    rules_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run all cluster analyzers and consolidate results into a single Excel file.
    Optionally runs job analyzer to produce a separate job analysis Excel file.
    
    This function runs all 7 cluster analyzers and combines their outputs into
    a single Excel workbook with multiple tabs, including a consolidated summary.
    If job_input_path is provided, it also runs the job analyzer separately.
    The output files are automatically named with timestamp patterns.
    
    Args:
        cluster_input_path: Path to cluster utilization CSV file or directory
        output_dir: Directory where the consolidated Excel files will be saved
        temp_dir: Temporary directory for intermediate files (default: same as output_dir)
        job_input_path: Optional path to job scanner JSON output file or directory
        rules_path: Full path to analyzer_rules.json.
                    Passed to ClusterUtilizationAnalyzer so custom thresholds are applied.
                    Example: '/Volumes/catalog/schema/volume/script/analyzer_rules.json'
                    If not provided, built-in default thresholds are used.
        
    Returns:
        Dictionary with analysis results and metadata
        
    Example:
        >>> from databricks_toolkit.analysis import run_consolidated_cluster_analysis
        >>> # Cluster analysis only
        >>> results = run_consolidated_cluster_analysis(
        ...     cluster_input_path='/dbfs/workspace_discovery/utilization/cluster',
        ...     output_dir='/tmp/workspace_analysis'
        ... )
        >>> # Cluster + Job analysis (using directory paths)
        >>> results = run_consolidated_cluster_analysis(
        ...     cluster_input_path='/dbfs/workspace_discovery/utilization/cluster',
        ...     output_dir='/tmp/workspace_analysis',
        ...     job_input_path='/dbfs/workspace_discovery/jobs/json'
        ... )
        >>> # Creates files like:
        >>> # - /tmp/workspace_analysis/Cluster_Analysis_Consolidated_20251125_143022.xlsx
        >>> # - /tmp/workspace_analysis/Job_Analysis_workspace_20251125_143022.xlsx
    """
    # Import additional analyzers
    from .additional_analyzers import NetworkTrafficAnalyzer, RIOpportunityAnalyzer
    from .specialized_analyzers import (
        WorkerNodeAnalyzer, 
        SingleNodeClusterAnalyzer,
        AutoscalingAnalyzer,
        ClusterRecommendationGenerator
    )
    
    # Generate timestamped filename
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(output_dir, f'Cluster_Analysis_Consolidated_{timestamp}.xlsx')
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    print("="*80)
    print("CONSOLIDATED CLUSTER ANALYSIS")
    print("="*80)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Input: {cluster_input_path}")
    print(f"Output: {output_file}\n")
    
    # Setup temp directory for individual analyzer outputs
    if temp_dir is None:
        temp_dir = output_dir
    
    # Ensure temp_dir exists and is a directory
    os.makedirs(temp_dir, exist_ok=True)
    
    # Create a unique subdirectory within temp_dir for individual analyzer outputs
    temp_subdir = os.path.join(temp_dir, f'analyzer_temp_{timestamp}')
    os.makedirs(temp_subdir, exist_ok=True)
    
    # Dictionary to store all analysis results
    all_results = {}
    
    # Run all 7 cluster analyzers
    analyzers = [
        ('utilization', ClusterUtilizationAnalyzer, "Cluster Utilization Analyzer"),
        ('network', NetworkTrafficAnalyzer, "Network Traffic Analyzer"),
        ('ri_opportunities', RIOpportunityAnalyzer, "RI Opportunity Analyzer"),
        ('worker_nodes', WorkerNodeAnalyzer, "Worker Node Analyzer"),
        ('single_node', SingleNodeClusterAnalyzer, "Single Node Cluster Analyzer"),
        ('autoscaling', AutoscalingAnalyzer, "Autoscaling Analyzer"),
        ('recommendations', ClusterRecommendationGenerator, "Cluster Recommendation Generator")
    ]
    
    for idx, (key, AnalyzerClass, name) in enumerate(analyzers, 1):
        try:
            print(f"[{idx}/7] Running {name}...")
            if key == 'utilization':
                analyzer = AnalyzerClass(cluster_input_path, temp_subdir, rules_path=rules_path)
            else:
                analyzer = AnalyzerClass(cluster_input_path, temp_subdir)
            all_results[key] = analyzer.analyze()
            print(f"  ✓ Completed\n")
        except Exception as e:
            print(f"  ❌ Error: {str(e)}\n")
            all_results[key] = {'error': str(e)}
    
    # Create consolidated Excel file
    print("="*80)
    print("Creating consolidated Excel report with multiple tabs...")
    
    try:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Tab 1: Consolidated Summary with detailed metrics
            summary_sections = []
            
            # === UTILIZATION SUMMARY ===
            if 'error' not in all_results.get('utilization', {}):
                util = all_results['utilization']
                summary_sections.append({
                    'Section': 'CLUSTER UTILIZATION',
                    'Metric': 'Total Clusters',
                    'Value': util.get('total_clusters', 0),
                    'Details': ''
                })
                summary_sections.append({
                    'Section': 'CLUSTER UTILIZATION',
                    'Metric': 'Critical Issues',
                    'Value': util.get('critical_count', 0),
                    'Details': 'Clusters with severe resource issues'
                })
                summary_sections.append({
                    'Section': 'CLUSTER UTILIZATION',
                    'Metric': 'High Priority Issues',
                    'Value': util.get('high_priority_count', 0),
                    'Details': 'Clusters requiring attention'
                })
                summary_sections.append({
                    'Section': 'CLUSTER UTILIZATION',
                    'Metric': 'Average CPU Utilization',
                    'Value': f"{util.get('avg_cpu', 0):.1f}%",
                    'Details': 'Across all clusters'
                })
                summary_sections.append({
                    'Section': 'CLUSTER UTILIZATION',
                    'Metric': 'Average Memory Utilization',
                    'Value': f"{util.get('avg_memory', 0):.1f}%",
                    'Details': 'Across all clusters'
                })
                summary_sections.append({'Section': '', 'Metric': '', 'Value': '', 'Details': ''})  # Blank row
            
            # === NETWORK TRAFFIC SUMMARY ===
            if 'error' not in all_results.get('network', {}):
                net = all_results['network']
                summary_sections.append({
                    'Section': 'NETWORK TRAFFIC',
                    'Metric': 'Total Clusters Analyzed',
                    'Value': net.get('total_clusters', 0),
                    'Details': ''
                })
                summary_sections.append({
                    'Section': 'NETWORK TRAFFIC',
                    'Metric': 'High Network Activity',
                    'Value': net.get('high_network_clusters', 0),
                    'Details': 'Clusters with intensive network traffic'
                })
                summary_sections.append({
                    'Section': 'NETWORK TRAFFIC',
                    'Metric': 'Network vs Compute Issues',
                    'Value': net.get('problematic_clusters', 0),
                    'Details': 'High network traffic in low utilization clusters'
                })
                if 'network_thresholds' in net:
                    thresholds = net['network_thresholds']
                    summary_sections.append({
                        'Section': 'NETWORK TRAFFIC',
                        'Metric': 'Threshold (Received)',
                        'Value': f"{thresholds.get('received_mb_min', 0):.2f} MB/min",
                        'Details': '90th percentile'
                    })
                    summary_sections.append({
                        'Section': 'NETWORK TRAFFIC',
                        'Metric': 'Threshold (Sent)',
                        'Value': f"{thresholds.get('sent_mb_min', 0):.2f} MB/min",
                        'Details': '90th percentile'
                    })
                summary_sections.append({'Section': '', 'Metric': '', 'Value': '', 'Details': ''})  # Blank row
            
            # === RI OPPORTUNITIES SUMMARY ===
            if 'error' not in all_results.get('ri_opportunities', {}):
                ri = all_results['ri_opportunities']
                summary_sections.append({
                    'Section': 'RESERVED INSTANCES',
                    'Metric': 'Total Clusters',
                    'Value': ri.get('total_clusters', 0),
                    'Details': ''
                })
                summary_sections.append({
                    'Section': 'RESERVED INSTANCES',
                    'Metric': 'RI Candidates',
                    'Value': ri.get('ri_candidate_count', 0),
                    'Details': 'Clusters suitable for Reserved Instances'
                })
                summary_sections.append({
                    'Section': 'RESERVED INSTANCES',
                    'Metric': 'Potential Savings',
                    'Value': f"${ri.get('potential_savings', 0):,.2f}",
                    'Details': 'Estimated annual savings'
                })
                summary_sections.append({'Section': '', 'Metric': '', 'Value': '', 'Details': ''})  # Blank row
            
            # === WORKER NODE SUMMARY ===
            if 'error' not in all_results.get('worker_nodes', {}):
                wn = all_results['worker_nodes']
                summary_sections.append({
                    'Section': 'WORKER NODES',
                    'Metric': 'Total Clusters',
                    'Value': wn.get('total_clusters', 0),
                    'Details': ''
                })
                summary_sections.append({
                    'Section': 'WORKER NODES',
                    'Metric': 'Unique Node Types',
                    'Value': wn.get('unique_node_types', 0),
                    'Details': 'Different worker node configurations'
                })
                summary_sections.append({'Section': '', 'Metric': '', 'Value': '', 'Details': ''})  # Blank row
            
            # === SINGLE NODE SUMMARY ===
            if 'error' not in all_results.get('single_node', {}):
                sn = all_results['single_node']
                summary_sections.append({
                    'Section': 'SINGLE NODE CLUSTERS',
                    'Metric': 'Total Clusters',
                    'Value': sn.get('total_clusters', 0),
                    'Details': ''
                })
                summary_sections.append({
                    'Section': 'SINGLE NODE CLUSTERS',
                    'Metric': 'Single Node Count',
                    'Value': sn.get('single_node_count', 0),
                    'Details': 'Clusters running without workers'
                })
                summary_sections.append({
                    'Section': 'SINGLE NODE CLUSTERS',
                    'Metric': 'Percentage',
                    'Value': f"{(sn.get('single_node_count', 0) / max(sn.get('total_clusters', 1), 1) * 100):.1f}%",
                    'Details': 'Of total clusters'
                })
                summary_sections.append({'Section': '', 'Metric': '', 'Value': '', 'Details': ''})  # Blank row
            
            # === AUTOSCALING SUMMARY ===
            if 'error' not in all_results.get('autoscaling', {}):
                asc = all_results['autoscaling']
                summary_sections.append({
                    'Section': 'AUTOSCALING',
                    'Metric': 'Total Clusters',
                    'Value': asc.get('total_clusters', 0),
                    'Details': ''
                })
                summary_sections.append({
                    'Section': 'AUTOSCALING',
                    'Metric': 'Autoscaling Enabled',
                    'Value': asc.get('autoscaling_enabled', 0),
                    'Details': 'Clusters with autoscaling configured'
                })
                summary_sections.append({
                    'Section': 'AUTOSCALING',
                    'Metric': 'Fixed Size',
                    'Value': asc.get('fixed_size', 0),
                    'Details': 'Clusters without autoscaling'
                })
                summary_sections.append({
                    'Section': 'AUTOSCALING',
                    'Metric': 'Percentage Autoscaled',
                    'Value': f"{(asc.get('autoscaling_enabled', 0) / max(asc.get('total_clusters', 1), 1) * 100):.1f}%",
                    'Details': 'Of total clusters'
                })
                summary_sections.append({'Section': '', 'Metric': '', 'Value': '', 'Details': ''})  # Blank row
            
            # === RECOMMENDATIONS SUMMARY ===
            if 'error' not in all_results.get('recommendations', {}):
                rec = all_results['recommendations']
                summary_sections.append({
                    'Section': 'RECOMMENDATIONS',
                    'Metric': 'Total Recommendations',
                    'Value': rec.get('total_recommendations', 0),
                    'Details': ''
                })
                summary_sections.append({
                    'Section': 'RECOMMENDATIONS',
                    'Metric': 'High Priority',
                    'Value': rec.get('high_priority_recs', 0),
                    'Details': 'Immediate action recommended'
                })
                summary_sections.append({
                    'Section': 'RECOMMENDATIONS',
                    'Metric': 'Medium Priority',
                    'Value': rec.get('medium_priority_recs', 0),
                    'Details': 'Should be addressed soon'
                })
                summary_sections.append({
                    'Section': 'RECOMMENDATIONS',
                    'Metric': 'Low Priority',
                    'Value': rec.get('low_priority_recs', 0),
                    'Details': 'Optional optimizations'
                })
            
            # Define allowed tabs to keep (only 2 tabs)
            allowed_tabs = {
                'utilization_All Clusters',
                'ri_opportunities_RI_Candidates'
            }
            
            # No tab renaming needed - removed All_Reco tab
            tab_rename_map = {}
            
            print("\nCopying sheets to consolidated Excel file...")
            # Copy only allowed tabs from individual analyzer outputs
            for analyzer_name, result in all_results.items():
                if 'error' in result or 'output_file' not in result:
                    continue
                
                output_file_path = result['output_file']
                if os.path.exists(output_file_path):
                    try:
                        source_excel = pd.ExcelFile(output_file_path)
                        for sheet_name in source_excel.sheet_names:
                            # Create unique sheet name (max 31 chars for Excel)
                            new_sheet_name = f"{analyzer_name[:20]}_{sheet_name}"[:31]
                            
                            print(f"  Checking: {analyzer_name} -> {sheet_name} -> {new_sheet_name}")
                            
                            # Only include allowed tabs
                            if new_sheet_name not in allowed_tabs:
                                print(f"    ✗ Skipped (not in allowed list)")
                                continue
                            
                            df = pd.read_excel(source_excel, sheet_name=sheet_name)
                            
                            # Rename tab if needed
                            final_sheet_name = tab_rename_map.get(new_sheet_name, new_sheet_name)
                            
                            print(f"    ✓ Added sheet: {final_sheet_name}")
                            df.to_excel(writer, sheet_name=final_sheet_name, index=False)
                    except Exception as e:
                        print(f"  ⚠️ Warning: Could not copy sheets from {analyzer_name}: {str(e)}")
        
        print(f"  ✓ Consolidated report created: {os.path.basename(output_file)}")
        
        # Clean up individual analyzer Excel files
        print("\nCleaning up individual analyzer files...")
        for result in all_results.values():
            if 'output_file' in result and os.path.exists(result['output_file']):
                try:
                    os.remove(result['output_file'])
                    print(f"  ✓ Removed: {os.path.basename(result['output_file'])}")
                except Exception as e:
                    print(f"  ⚠️ Could not remove {result['output_file']}: {str(e)}")
        
        # Clean up temp subdirectory
        try:
            import shutil
            if os.path.exists(temp_subdir):
                shutil.rmtree(temp_subdir)
                print(f"  ✓ Removed temp directory: {temp_subdir}")
        except Exception as e:
            print(f"  ⚠️ Could not remove temp directory: {str(e)}")
        
        print(f"\n{'='*80}")
        print("✓ CONSOLIDATED CLUSTER ANALYSIS COMPLETE")
        print(f"{'='*80}")
        print(f"\nFinished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Cluster Report: {output_file}\n")
        
        # Run job analysis if job_input_path is provided
        job_output_file = None
        job_stats = None
        if job_input_path:
            print(f"\n{'='*80}")
            print("RUNNING JOB ANALYSIS")
            print(f"{'='*80}\n")
            try:
                from .job_analyzer import run_job_analysis
                job_result = run_job_analysis(
                    input_path=job_input_path,
                    output_dir=output_dir
                )
                job_output_file = job_result.get('output_file')
                job_stats = job_result.get('summary_stats')
                print(f"\n✅ Job analysis complete!")
                print(f"Job Report: {job_output_file}\n")
            except Exception as job_error:
                print(f"\n⚠️  Job analysis failed: {str(job_error)}")
                import traceback
                traceback.print_exc()
        
        result = {
            'cluster_output_file': output_file,
            'analysis_results': all_results,
            'summary_count': len(summary_sections),
            'status': 'success'
        }
        
        if job_output_file:
            result['job_output_file'] = job_output_file
            result['job_stats'] = job_stats
        
        return result
        
    except Exception as e:
        print(f"  ❌ Error creating consolidated report: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Clean up temp subdirectory even on error
        try:
            import shutil
            if os.path.exists(temp_subdir):
                shutil.rmtree(temp_subdir)
        except:
            pass
        
        return {
            'cluster_output_file': output_file,
            'analysis_results': all_results,
            'error': str(e),
            'status': 'failed'
        }
