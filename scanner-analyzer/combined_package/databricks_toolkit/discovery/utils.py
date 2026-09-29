"""
Utility functions for Databricks Workspace Scanner.
Contains helper functions for file operations, JSON handling, and more.
"""

import json
import logging
import os
import time
import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)


def save_json(data: Dict[str, Any], file_path: str, workspace_name: str = None, artifact_type: str = None) -> str:
    """
    Save data to a JSON file with timestamp in organized folder structure.
    
    Args:
        data: Dictionary to save as JSON
        file_path: Base file path (can be directory or full path)
        workspace_name: Optional workspace name for filename
        artifact_type: Optional artifact type for folder organization (e.g., 'jobs', 'clusters')
        
    Returns:
        Full path to the saved file
    """
    try:
        # Generate timestamp for unique filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Determine output path
        if file_path:
            path = Path(file_path)
            
            # If it's a directory or doesn't have extension, generate filename
            if path.is_dir() or not path.suffix:
                # Create artifact-specific subdirectory if artifact_type is provided
                if artifact_type:
                    path = path / artifact_type / "json"
                
                # Create directory if it doesn't exist
                path.mkdir(parents=True, exist_ok=True)
                
                # Generate filename with workspace name and timestamp
                if workspace_name:
                    filename = f"{workspace_name}_{timestamp}.json"
                else:
                    filename = f"scan_results_{timestamp}.json"
                
                output_file = path / filename
            else:
                # Use provided filename, but ensure directory exists
                path.parent.mkdir(parents=True, exist_ok=True)
                output_file = path
        else:
            # Default to ./out directory
            out_dir = Path("./out")
            if artifact_type:
                out_dir = out_dir / artifact_type / "json"
            out_dir.mkdir(parents=True, exist_ok=True)
            
            if workspace_name:
                filename = f"{workspace_name}_{timestamp}.json"
            else:
                filename = f"scan_results_{timestamp}.json"
            
            output_file = out_dir / filename
        
        # Save JSON with proper formatting
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)
        
        logger.info(f"Results saved to: {output_file}")
        return str(output_file)
        
    except Exception as e:
        logger.error(f"Failed to save JSON file: {str(e)}")
        raise


def save_csv(data: List[Dict[str, Any]], file_path: str, workspace_name: str = None, headers: List[str] = None, artifact_type: str = None) -> str:
    """
    Save data to a CSV file with timestamp in organized folder structure.
    
    Args:
        data: List of dictionaries to save as CSV rows
        file_path: Base file path (can be directory or full path)
        workspace_name: Optional workspace name for filename
        headers: Optional list of column headers (if None, uses keys from first row)
        artifact_type: Optional artifact type for folder organization (e.g., 'jobs', 'clusters')
        
    Returns:
        Full path to the saved file
    """
    try:
        if not data:
            logger.warning("No data to save to CSV")
            return ""
        
        # Generate timestamp for unique filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Determine output path
        if file_path:
            path = Path(file_path)
            
            # If it's a directory or doesn't have extension, generate filename
            if path.is_dir() or not path.suffix:
                # Create artifact-specific subdirectory if artifact_type is provided
                if artifact_type:
                    path = path / artifact_type / "csv"
                
                # Create directory if it doesn't exist
                path.mkdir(parents=True, exist_ok=True)
                
                # Generate filename with workspace name and timestamp
                if workspace_name:
                    filename = f"{workspace_name}_{timestamp}.csv"
                else:
                    filename = f"scan_results_{timestamp}.csv"
                
                output_file = path / filename
            else:
                # Use provided filename, but ensure directory exists
                path.parent.mkdir(parents=True, exist_ok=True)
                output_file = path
        else:
            # Default to ./out directory
            out_dir = Path("./out")
            if artifact_type:
                out_dir = out_dir / artifact_type / "csv"
            out_dir.mkdir(parents=True, exist_ok=True)
            
            if workspace_name:
                filename = f"{workspace_name}_{timestamp}.csv"
            else:
                filename = f"scan_results_{timestamp}.csv"
            
            output_file = out_dir / filename
        
        # Determine headers
        if headers is None:
            headers = list(data[0].keys()) if data else []
        
        # Save CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(data)
        
        logger.info(f"CSV saved to: {output_file}")
        return str(output_file)
        
    except Exception as e:
        logger.error(f"Failed to save CSV file: {str(e)}")
        raise


def extract_workspace_id(workspace_url: str) -> str:
    """
    Extract workspace ID from workspace URL.
    
    Args:
        workspace_url: Full workspace URL
        
    Returns:
        Extracted workspace ID
    """
    try:
        # Remove protocol if present
        if '://' in workspace_url:
            url_without_protocol = workspace_url.split('://')[1]
        else:
            url_without_protocol = workspace_url
        
        # Extract the first part (workspace ID)
        workspace_id = url_without_protocol.split('.')[0]
        
        return workspace_id
        
    except Exception as e:
        logger.warning(f"Could not extract workspace ID from {workspace_url}: {str(e)}")
        return "workspace"


def format_bytes(bytes_value: Optional[int]) -> str:
    """
    Format bytes into human-readable string.
    
    Args:
        bytes_value: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 GB")
    """
    if bytes_value is None or bytes_value == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit_index = 0
    size = float(bytes_value)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    return f"{size:.2f} {units[unit_index]}"


def retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
    """
    Execute a function with exponential backoff retry logic.
    
    Args:
        func: Function to execute
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        
    Returns:
        Result of the function execution
        
    Raises:
        Exception: If all retries fail
    """
    import random
    
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return func()
            
        except Exception as e:
            last_exception = e
            
            if attempt < max_retries:
                # Calculate delay with jitter
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay:.1f}s...")
                time.sleep(delay)
            else:
                logger.error(f"All {max_retries + 1} attempts failed. Last error: {str(e)}")
    
    # If we get here, all retries failed
    if last_exception:
        raise last_exception
    else:
        raise Exception("Unknown error in retry_with_backoff")


def safe_get_attribute(obj, attr_path: str, default=None):
    """
    Safely get nested attributes from an object.
    
    Args:
        obj: Object to get attribute from
        attr_path: Dot-separated attribute path (e.g., "state.result_state.value")
        default: Default value if attribute not found
        
    Returns:
        Attribute value or default
    """
    try:
        attrs = attr_path.split('.')
        current = obj
        
        for attr in attrs:
            if hasattr(current, attr):
                current = getattr(current, attr)
            else:
                return default
        
        return current
        
    except Exception:
        return default


def get_timestamp() -> str:
    """
    Get current timestamp in ISO format.
    
    Returns:
        Timestamp string
    """
    return datetime.now().isoformat()


def safe_dict_conversion(obj, default=None) -> Dict[str, Any]:
    """
    Safely convert an object to dictionary.
    
    Args:
        obj: Object to convert
        default: Default value if conversion fails
        
    Returns:
        Dictionary representation or default
    """
    try:
        if obj is None:
            return default or {}
        
        if isinstance(obj, dict):
            return obj
        
        if hasattr(obj, '__dict__'):
            return {k: str(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
        
        return default or {}
        
    except Exception:
        return default or {}


def format_epoch_timestamp(epoch_ms: Optional[int]) -> Optional[str]:
    """
    Convert epoch milliseconds to mm/dd/yyyy hh:mm:ss format.
    
    Args:
        epoch_ms: Timestamp in milliseconds or None
        
    Returns:
        Formatted date string in mm/dd/yyyy hh:mm:ss format or None
    """
    if epoch_ms is None:
        return None
    
    try:
        # Handle both timestamp in milliseconds and seconds
        if epoch_ms > 10000000000:  # Likely milliseconds
            dt = datetime.fromtimestamp(epoch_ms / 1000)
        else:  # Likely seconds
            dt = datetime.fromtimestamp(epoch_ms)
        return dt.strftime('%m/%d/%Y %H:%M:%S')
    except Exception as e:
        logger.debug(f"Error formatting timestamp: {str(e)}")
        return None
