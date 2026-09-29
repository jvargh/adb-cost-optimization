# Databricks notebook source
# MAGIC %md
# MAGIC ## Generate Insights – Configuration
# MAGIC
# MAGIC This section defines the configuration used by the **Generate Insights** module to derive actionable insights from the scanned Databricks workspace metadata. The configuration controls **what insights are generated**, **how thresholds are applied**, and **how outputs are categorized** for downstream analysis and dashboards.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

# MAGIC %pip install openpyxl --quiet

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# Import required libraries
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import os
import glob
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

print("✅ Libraries imported successfully")

# COMMAND ----------

# Configuration - UPDATE THIS PATH
ANALYSIS_FOLDER_PATH = r"/Volumes/rkdbscannercatalog/default/rkdbscannervolumeout/output/analysis"


# Verify folder exists
if os.path.exists(ANALYSIS_FOLDER_PATH):
    print(f"✅ Analysis folder found: {ANALYSIS_FOLDER_PATH}")
    files = os.listdir(ANALYSIS_FOLDER_PATH)
    excel_files = [f for f in files if f.endswith('.xlsx')]
    print(f"\n📁 Found {len(excel_files)} Excel files:")
    for file in excel_files:
        print(f"  - {file}")
else:
    print(f"❌ Analysis folder not found: {ANALYSIS_FOLDER_PATH}")
    print("Please update ANALYSIS_FOLDER_PATH with the correct path")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Utility Functions

# COMMAND ----------

def load_excel_file(pattern: str) -> dict:
    """
    Load Excel file matching pattern and return all sheets as dict of DataFrames.
    
    Args:
        pattern: Filename pattern to match (e.g., 'Cluster_Analysis*')
    
    Returns:
        Dictionary with sheet names as keys and DataFrames as values
    """
    matching_files = glob.glob(os.path.join(ANALYSIS_FOLDER_PATH, pattern))
    
    if not matching_files:
        print(f"⚠️  No files found matching pattern: {pattern}")
        return {}
    
    file_path = matching_files[0]
    print(f"📖 Loading: {os.path.basename(file_path)}")
    
    try:
        # Read all sheets
        excel_file = pd.ExcelFile(file_path)
        sheets_dict = {}
        
        for sheet_name in excel_file.sheet_names:
            sheets_dict[sheet_name] = pd.read_excel(file_path, sheet_name=sheet_name)
            print(f"  ✓ Loaded sheet: {sheet_name} ({len(sheets_dict[sheet_name])} rows)")
        
        return sheets_dict
    
    except Exception as e:
        print(f"❌ Error loading file: {str(e)}")
        return {}

def safe_column_access(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    """
    Safely access columns, returning empty DataFrame if columns don't exist.
    """
    existing_cols = [col for col in columns if col in df.columns]
    if existing_cols:
        return df[existing_cols]
    return pd.DataFrame()

print("✅ Utility functions defined")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC
# MAGIC # 1. Cluster Analysis
# MAGIC
# MAGIC ## 1.1 Load Cluster Analysis Data

# COMMAND ----------

# Load Cluster Analysis file
cluster_data = load_excel_file('Cluster_Analysis*.xlsx')

if cluster_data:
    print(f"\n📊 Available sheets in Cluster Analysis:")
    for sheet_name in cluster_data.keys():
        print(f"  - {sheet_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.2 Cluster Utilization Distribution (Pie Chart)

# COMMAND ----------

# Check which utilization sheet exists and use it
if cluster_data:
    utilization_sheet = None
    
    # Try to find the utilization sheet
    for sheet in ['utilization_All Clusters', 'Utilization_Summary', 'Consolidated Summary']:
        if sheet in cluster_data:
            utilization_sheet = sheet
            break
    
    if utilization_sheet:
        df = cluster_data[utilization_sheet]
        print(f"📊 Using sheet: {utilization_sheet}")
        print(f"   Columns: {', '.join(df.columns[:5])}...")  # Show first 5 columns
        
        # Try to find utilization category column
        category_col = None
        for col in ['Utilization_Category', 'utilization_tier', 'Category', 'Tier', 'Utilization Tier']:
            if col in df.columns:
                category_col = col
                break
        
        if category_col and not df.empty:
            # Count clusters by category
            category_counts = df[category_col].value_counts().reset_index()
            category_counts.columns = ['Category', 'Count']
            
            # Use a vibrant color palette - assign colors based on actual categories
            vibrant_colors = [
                '#e74c3c',    # Bright red
                '#3498db',    # Bright blue
                '#27ae60',    # Emerald green
                '#f39c12',    # Golden yellow
                '#9b59b6',    # Purple
                '#ff6b35',    # Vibrant orange
                '#16a085',    # Teal
                '#e67e22',    # Carrot orange
                '#1abc9c',    # Turquoise
                '#8e44ad'     # Deep purple
            ]
            
            # Assign colors from the palette
            colors = vibrant_colors[:len(category_counts)]
            
            fig = go.Figure(data=[go.Pie(
                labels=category_counts['Category'],
                values=category_counts['Count'],
                hole=0.4,
                marker=dict(colors=colors, line=dict(color='white', width=2)),
                textinfo='label+percent+value',
                textposition='outside',
                hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
            )])
            
            total_clusters = category_counts['Count'].sum()
            
            fig.update_layout(
                title=dict(
                    text=f'Cluster Utilization Distribution ({total_clusters} Total Clusters)',
                    font=dict(size=20, color='#333333')
                ),
                showlegend=True,
                legend=dict(orientation='v', x=1.1, y=0.5),
                height=500,
                annotations=[dict(
                    text=f'Total<br>{total_clusters}<br>Clusters',
                    x=0.5, y=0.5,
                    font_size=14,
                    showarrow=False
                )]
            )
            
            fig.show()
            
            # Calculate waste metrics
            idle_low = category_counts[category_counts['Category'].isin(['Idle', 'Low'])]['Count'].sum()
            waste_pct = (idle_low / total_clusters * 100) if total_clusters > 0 else 0
            
            print(f"\n💡 Key Finding: {idle_low} clusters ({waste_pct:.1f}%) are Idle or Low utilization")
            print(f"💰 Potential Cost Savings: ~${idle_low * 500:,}/month (assuming $500/cluster/month)")
        else:
            print(f"⚠️  Could not find utilization category column")
            print(f"   Available columns: {', '.join(df.columns)}")
    else:
        print("⚠️  No utilization sheet found")
        print(f"   Available sheets: {', '.join(cluster_data.keys())}")
else:
    print("⚠️  Cluster data not loaded")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.3 Cluster CPU Utilization Heatmap

# COMMAND ----------

# Try to find the right sheet for cluster details
if cluster_data:
    detail_sheet = None
    
    for sheet in ['utilization_All Clusters', 'Cluster_Details', 'Consolidated Summary']:
        if sheet in cluster_data:
            detail_sheet = sheet
            break
    
    if detail_sheet:
        df = cluster_data[detail_sheet]
        print(f"📊 Using sheet: {detail_sheet}")
        
        # Find relevant columns
        cluster_col = None
        cpu_col = None
        
        for col in ['cluster_name', 'Cluster_Name', 'cluster_id', 'Cluster ID']:
            if col in df.columns:
                cluster_col = col
                break
        
        for col in ['Avg_CPU_Util', 'avg_cpu_utilization', 'avg_cpu_percent', 'CPU_Utilization', 'avg_cpu', 'CPU Avg %', 'Peak_CPU_Util']:
            if col in df.columns:
                cpu_col = col
                break
        
        if cluster_col and cpu_col and not df.empty:
            # Get top 20 clusters by CPU utilization
            df_plot = df[[cluster_col, cpu_col]].copy()
            df_plot = df_plot.dropna()
            df_plot = df_plot.sort_values(by=cpu_col, ascending=False).head(20)
            
            if not df_plot.empty:
                # Organize clusters into a grid (5 rows x 4 columns for 20 clusters)
                num_clusters = len(df_plot)
                cols = 4
                rows = int(np.ceil(num_clusters / cols))
                
                # Create grid with cluster names and CPU values
                cluster_names = []
                cpu_values = []
                
                for i in range(rows):
                    row_names = []
                    row_values = []
                    for j in range(cols):
                        idx = i * cols + j
                        if idx < num_clusters:
                            row_names.append(df_plot.iloc[idx][cluster_col][:30])  # Truncate long names
                            row_values.append(df_plot.iloc[idx][cpu_col])
                        else:
                            row_names.append('')
                            row_values.append(0)  # Empty cell
                    cluster_names.append(row_names)
                    cpu_values.append(row_values)
                
                # Create heatmap
                fig = go.Figure(data=go.Heatmap(
                    z=cpu_values,
                    text=[[f'{v:.1f}%' if v > 0 else '' for v in row] for row in cpu_values],
                    texttemplate='%{text}',
                    textfont={"size": 10},
                    colorscale=[
                        [0.0, '#d62728'],   # Red (idle)
                        [0.15, '#ff7f0e'],  # Orange (low)
                        [0.50, '#ffcc00'],  # Yellow (moderate)
                        [0.70, '#2ca02c'],  # Green (optimal)
                        [1.0, '#1f77b4']    # Blue (high)
                    ],
                    colorbar=dict(title='CPU %'),
                    hovertemplate='CPU: %{z:.1f}%<extra></extra>',
                    zmin=0,
                    zmax=100
                ))
                
                # Add cluster names as annotations
                annotations = []
                for i in range(rows):
                    for j in range(cols):
                        if cluster_names[i][j]:
                            annotations.append(
                                dict(
                                    x=j,
                                    y=i,
                                    text=cluster_names[i][j],
                                    showarrow=False,
                                    font=dict(size=8, color='white'),
                                    xanchor='center',
                                    yanchor='middle',
                                    yshift=-15
                                )
                            )
                
                fig.update_layout(
                    title=dict(
                        text='Cluster CPU Utilization Heatmap (Top 20)',
                        font=dict(size=20, color='#333333')
                    ),
                    xaxis=dict(showticklabels=False, showgrid=False),
                    yaxis=dict(showticklabels=False, showgrid=False),
                    annotations=annotations,
                    height=400 + (rows * 80),
                    width=900
                )
                
                fig.show()
                
                avg_cpu = df_plot[cpu_col].mean()
                print(f"\n📊 Average CPU utilization (top 20): {avg_cpu:.1f}%")
            else:
                print("⚠️  No valid data after filtering")
        else:
            print(f"⚠️  Required columns not found. Cluster: {cluster_col}, CPU: {cpu_col}")
            print(f"   Available columns: {', '.join(df.columns[:10])}")
    else:
        print("⚠️  No cluster details sheet found")
else:
    print("⚠️  Cluster data not loaded")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC
# MAGIC # 3. Security Analysis
# MAGIC
# MAGIC ## 3.1 Load Security Analysis Data

# COMMAND ----------

# Load Security Analysis file
security_data = load_excel_file('Security_Analysis*.xlsx')

if security_data:
    print(f"\n📊 Available sheets in Security Analysis:")
    for sheet_name in security_data.keys():
        print(f"  - {sheet_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3.2 Security Posture Radar Chart

# COMMAND ----------

# Try to find security category scores sheet
if security_data:
    scores_sheet = None
    
    for sheet in ['Category Scores', 'Category_Scores', 'Scores', 'Summary']:
        if sheet in security_data:
            scores_sheet = sheet
            break
    
    if scores_sheet:
        df = security_data[scores_sheet]
        print(f"📊 Using sheet: {scores_sheet}")
        print(f"   Available columns: {', '.join(df.columns)}")
        print(f"   Data shape: {df.shape}")
        
        # Show first few rows for debugging
        print(f"   First few rows:\n{df.head().to_string()}")
        
        # Find category and score columns
        category_col = None
        score_col = None
        
        # Debug: print all columns in lowercase for comparison
        print(f"   Column search debug:")
        for col in df.columns:
            print(f"     - '{col}' (type: {type(col).__name__})")
        
        for col in ['Category', 'category', 'CATEGORY', 'security_category', 'Security Category', 'Security_Category', 'Category Name', 'category_name']:
            if col in df.columns:
                category_col = col
                print(f"   Found category column: {col}")
                break
        
        for col in ['Percentage', 'percentage', 'PERCENTAGE', 'Score', 'score', 'SCORE', 'category_score', 'Category Score', 'Category_Score', '%', 'Score %', 'current_score', 'Current Score']:
            if col in df.columns:
                score_col = col
                print(f"   Found score column: {col}")
                break
        
        if category_col and score_col and not df.empty:
            categories = df[category_col].tolist()
            
            # Convert scores to numeric, handling percentage strings like "25.0%"
            # First, strip any '%' symbols, then convert to numeric
            score_values = df[score_col].astype(str).str.replace('%', '').str.strip()
            scores = pd.to_numeric(score_values, errors='coerce').tolist()
            
            # Filter out any NaN values along with their corresponding categories
            valid_data = [(cat, score) for cat, score in zip(categories, scores) if pd.notna(score)]
            
            if valid_data:
                categories = [item[0] for item in valid_data]
                scores = [item[1] for item in valid_data]
                fig = go.Figure()
                
                # Add current score trace
                fig.add_trace(go.Scatterpolar(
                    r=scores,
                    theta=categories,
                    fill='toself',
                    name='Current Score',
                    marker=dict(color='#1f77b4'),
                    line=dict(color='#1f77b4', width=2),
                    fillcolor='rgba(31, 119, 180, 0.5)',
                    hovertemplate='<b>%{theta}</b><br>Current: %{r:.1f}%<extra></extra>'
                ))
                
                # Add target (80%) trace
                target_scores = [80] * len(categories)
                fig.add_trace(go.Scatterpolar(
                    r=target_scores,
                    theta=categories,
                    name='Target (80%)',
                    marker=dict(color='#2ca02c'),
                    line=dict(color='#2ca02c', width=2, dash='dash'),
                    fillcolor='rgba(44, 160, 44, 0.1)',
                    hovertemplate='<b>%{theta}</b><br>Target: 80%<extra></extra>'
                ))
                
                fig.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True,
                            range=[0, 100],
                            showline=True,
                            linewidth=1,
                            gridcolor='lightgray'
                        ),
                        angularaxis=dict(
                            linewidth=1,
                            gridcolor='lightgray'
                        )
                    ),
                    title=dict(
                        text='Workspace Security Posture Analysis',
                        font=dict(size=20, color='#333333')
                    ),
                    showlegend=True,
                    legend=dict(
                        x=1.1,
                        y=0.5,
                        bgcolor='rgba(255,255,255,0.8)',
                        bordercolor='lightgray',
                        borderwidth=1
                    ),
                    height=600
                )
                
                fig.show()
                
                avg_score = sum(scores) / len(scores)
                min_score = min(scores)
                min_category = categories[scores.index(min_score)]
                
                print(f"\n🔒 Average Security Score: {avg_score:.1f}%")
                print(f"⚠️  Lowest Score: {min_score:.1f}% ({min_category})")
            else:
                print("⚠️  No security score data available")
        else:
            print(f"⚠️  Required columns not found. Category: {category_col}, Score: {score_col}")
            print(f"   Available columns: {', '.join(df.columns)}")
    else:
        print(f"⚠️  No category scores sheet found")
        print(f"   Available sheets: {', '.join(security_data.keys())}")
else:
    print("⚠️  Security data not loaded")

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC
# MAGIC # 4. SQL Query Analysis
# MAGIC
# MAGIC ## 4.1 Load SQL Query Analysis Data

# COMMAND ----------

# Load SQL Query Analysis file
sql_data = load_excel_file('SQL_Query_Analysis*.xlsx')

if sql_data:
    print(f"\n📊 Available sheets in SQL Query Analysis:")
    for sheet_name in sql_data.keys():
        print(f"  - {sheet_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4.3 Query Execution Time Distribution

# COMMAND ----------

# Try to find expensive queries sheet
if sql_data:
    expensive_sheet = None
    
    for sheet in ['Top 100 Expensive', 'Top_100_Expensive', 'Expensive_Queries', 'Top Queries']:
        if sheet in sql_data:
            expensive_sheet = sheet
            break
    
    if expensive_sheet:
        df = sql_data[expensive_sheet]
        print(f"📊 Using sheet: {expensive_sheet}")
        
        # Find execution time column
        time_col = None
        
        for col in ['total_duration_ms', 'execution_time_sec', 'execution_time', 'duration_sec', 'duration', 'runtime', 'duration_ms']:
            if col in df.columns:
                time_col = col
                break
        
        if time_col and not df.empty:
            # Convert milliseconds to seconds if needed
            if 'ms' in time_col.lower():
                df['duration_sec'] = df[time_col] / 1000
                time_col_display = 'duration_sec'
                time_unit = 'seconds'
            else:
                time_col_display = time_col
                time_unit = 'seconds'
            
            # Create histogram of execution times
            fig = go.Figure()
            
            fig.add_trace(go.Histogram(
                x=df[time_col_display],
                nbinsx=30,
                marker_color='#2ca02c',
                hovertemplate=f'Execution Time: %{{x:.1f}}{time_unit}<br>Count: %{{y}}<extra></extra>'
            ))
            
            fig.update_layout(
                title=dict(
                    text='SQL Query Execution Time Distribution',
                    font=dict(size=20, color='#333333')
                ),
                xaxis=dict(title=f'Execution Time ({time_unit})'),
                yaxis=dict(title='Number of Queries'),
                height=500
            )
            
            fig.show()
            
            avg_time = df[time_col_display].mean()
            median_time = df[time_col_display].median()
            max_time = df[time_col_display].max()
            
            print(f"\n⏱️  Average Query Time: {avg_time:.1f} {time_unit}")
            print(f"📊 Median Query Time: {median_time:.1f} {time_unit}")
            print(f"🔴 Longest Query Time: {max_time:.1f} {time_unit}")
        else:
            print(f"⚠️  Execution time column not found: {time_col}")
            print(f"   Available columns: {', '.join(df.columns)}")
    else:
        print(f"⚠️  No expensive queries sheet found")
        print(f"   Available sheets: {', '.join(sql_data.keys())}")
else:
    print("⚠️  SQL data not loaded")