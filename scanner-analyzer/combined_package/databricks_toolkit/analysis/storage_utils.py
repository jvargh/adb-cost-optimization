"""
Storage Utilities for Reading Files from Local or Azure Storage
Supports both local file system and Azure Blob Storage paths.
"""

import os
import sys
import pandas as pd
from typing import List, Optional, Tuple
from io import StringIO

# Try importing Azure Storage SDK (optional dependency)
try:
    from azure.storage.blob import BlobServiceClient
    from azure.identity import DefaultAzureCredential
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    print("⚠️  Azure Storage SDK not installed. Only local file paths are supported.")
    print("   To enable Azure Storage support, run: pip install azure-storage-blob azure-identity")


class StorageReader:
    """
    Universal storage reader for local and Azure Blob Storage.
    
    Supports:
    - Local paths: /path/to/file.csv or C:\\path\\to\\file.csv
    - Azure Storage: https://<account>.blob.core.windows.net/<container>/<path>
    - Azure Storage: wasbs://<container>@<account>.blob.core.windows.net/<path>
    """
    
    def __init__(self):
        """Initialize storage reader with Azure authentication if available."""
        self.azure_available = AZURE_AVAILABLE
        self.credential = None
        
        if self.azure_available:
            try:
                self.credential = DefaultAzureCredential()
            except Exception as e:
                print(f"⚠️  Azure authentication failed: {str(e)}")
                print("   Only local file paths will be supported.")
                self.azure_available = False
    
    def is_azure_path(self, path: str) -> bool:
        """
        Check if the path is an Azure Storage path.
        
        Args:
            path: File path to check
            
        Returns:
            True if Azure Storage path, False otherwise
        """
        if not isinstance(path, str):
            return False
        
        path_lower = path.lower()
        return (path_lower.startswith('https://') and '.blob.core.windows.net' in path_lower) or \
               path_lower.startswith('wasbs://') or \
               path_lower.startswith('abfss://')
    
    def parse_azure_path(self, path: str) -> Tuple[str, str, str]:
        """
        Parse Azure Storage path into components.
        
        Args:
            path: Azure Storage path
            
        Returns:
            Tuple of (account_url, container_name, blob_path)
        """
        if path.startswith('https://'):
            # Format: https://<account>.blob.core.windows.net/<container>/<blob_path>
            parts = path.replace('https://', '').split('/')
            account_name = parts[0].split('.')[0]
            account_url = f"https://{parts[0]}"
            container_name = parts[1] if len(parts) > 1 else ''
            blob_path = '/'.join(parts[2:]) if len(parts) > 2 else ''
            
        elif path.startswith('wasbs://'):
            # Format: wasbs://<container>@<account>.blob.core.windows.net/<blob_path>
            path = path.replace('wasbs://', '')
            container_part, rest = path.split('@', 1)
            container_name = container_part
            account_part, blob_path = rest.split('/', 1) if '/' in rest else (rest, '')
            account_name = account_part.split('.')[0]
            account_url = f"https://{account_part}"
            
        elif path.startswith('abfss://'):
            # Format: abfss://<container>@<account>.dfs.core.windows.net/<blob_path>
            path = path.replace('abfss://', '')
            container_part, rest = path.split('@', 1)
            container_name = container_part
            account_part, blob_path = rest.split('/', 1) if '/' in rest else (rest, '')
            # Convert dfs to blob endpoint
            account_name = account_part.split('.')[0]
            account_url = f"https://{account_name}.blob.core.windows.net"
        else:
            raise ValueError(f"Unsupported Azure path format: {path}")
        
        return account_url, container_name, blob_path
    
    def list_files(self, directory_path: str, pattern: str = '*.csv') -> List[str]:
        """
        List files in a directory (local or Azure).
        
        Args:
            directory_path: Directory path (local or Azure)
            pattern: File pattern to match (e.g., '*.csv', '*_cluster_utilization.csv')
            
        Returns:
            List of file paths matching the pattern
        """
        if self.is_azure_path(directory_path):
            return self._list_azure_files(directory_path, pattern)
        else:
            return self._list_local_files(directory_path, pattern)
    
    def _list_local_files(self, directory_path: str, pattern: str) -> List[str]:
        """List files from local directory."""
        if not os.path.exists(directory_path):
            return []
        
        import fnmatch
        files = []
        for filename in os.listdir(directory_path):
            if fnmatch.fnmatch(filename, pattern):
                files.append(os.path.join(directory_path, filename))
        
        return sorted(files)
    
    def _list_azure_files(self, directory_path: str, pattern: str) -> List[str]:
        """List files from Azure Blob Storage directory."""
        if not self.azure_available:
            raise RuntimeError("Azure Storage SDK not available. Install: pip install azure-storage-blob azure-identity")
        
        try:
            account_url, container_name, prefix = self.parse_azure_path(directory_path)
            
            # Ensure prefix ends with / for directory listing
            if prefix and not prefix.endswith('/'):
                prefix += '/'
            
            blob_service_client = BlobServiceClient(account_url=account_url, credential=self.credential)
            container_client = blob_service_client.get_container_client(container_name)
            
            import fnmatch
            files = []
            
            # List blobs with prefix
            blob_list = container_client.list_blobs(name_starts_with=prefix)
            
            for blob in blob_list:
                # Skip directories (blobs ending with /)
                if blob.name.endswith('/'):
                    continue
                
                # Extract filename from full path
                filename = blob.name.split('/')[-1]
                
                # Check if filename matches pattern
                if fnmatch.fnmatch(filename, pattern):
                    # Reconstruct full Azure path
                    full_path = f"{account_url}/{container_name}/{blob.name}"
                    files.append(full_path)
            
            return sorted(files)
            
        except Exception as e:
            print(f"❌ Error listing Azure files: {str(e)}")
            return []
    
    def resolve_csv_path(self, input_path: str, pattern: str = '*_cluster_utilization.csv') -> str:
        """
        Resolve input path to actual CSV file path.
        If input_path is a directory, finds the first matching CSV file.
        
        Args:
            input_path: Path to CSV file or directory
            pattern: Glob pattern to match CSV files (for directory inputs)
            
        Returns:
            Path to CSV file
            
        Raises:
            FileNotFoundError: If no matching files found in directory
        """
        # For Azure paths, check if it ends with .csv
        if self.is_azure_path(input_path):
            if not input_path.endswith('.csv'):
                files = auto_detect_input_files(input_path, pattern)
                if not files:
                    raise FileNotFoundError(f"No CSV files matching '{pattern}' found in: {input_path}")
                return files[0]
            return input_path
        
        # For local paths, check if it's a directory
        if os.path.isdir(input_path):
            files = auto_detect_input_files(input_path, pattern)
            if not files:
                raise FileNotFoundError(f"No CSV files matching '{pattern}' found in: {input_path}")
            return files[0]
        
        # It's a file path, return as-is
        return input_path
    
    def read_csv(self, file_path: str) -> pd.DataFrame:
        """
        Read CSV file from local or Azure Storage.
        
        Args:
            file_path: Path to CSV file (local or Azure)
            
        Returns:
            pandas DataFrame
        """
        if self.is_azure_path(file_path):
            return self._read_azure_csv(file_path)
        else:
            return self._read_local_csv(file_path)
    
    def _read_local_csv(self, file_path: str) -> pd.DataFrame:
        """Read CSV from local file system."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        print(f"   Reading local CSV: {file_path}")
        return pd.read_csv(file_path)
    
    def _read_azure_csv(self, file_path: str) -> pd.DataFrame:
        """Read CSV from Azure Blob Storage."""
        if not self.azure_available:
            raise RuntimeError("Azure Storage SDK not available. Install: pip install azure-storage-blob azure-identity")
        
        try:
            account_url, container_name, blob_path = self.parse_azure_path(file_path)
            
            print(f"   Reading Azure Blob: {blob_path}")
            print(f"   Storage Account: {account_url}")
            print(f"   Container: {container_name}")
            
            blob_service_client = BlobServiceClient(account_url=account_url, credential=self.credential)
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_path)
            
            # Download blob content
            blob_data = blob_client.download_blob()
            content = blob_data.readall().decode('utf-8')
            
            # Read CSV from string
            df = pd.read_csv(StringIO(content))
            print(f"   ✓ Loaded {len(df):,} rows from Azure Storage")
            
            return df
            
        except Exception as e:
            raise RuntimeError(f"Failed to read Azure blob: {str(e)}")


def auto_detect_input_files(base_path: str, file_pattern: str) -> List[str]:
    """
    Auto-detect input files from local or Azure Storage path.
    
    Args:
        base_path: Base directory path (local or Azure)
        file_pattern: File pattern to match (e.g., '*_cluster_utilization.csv')
        
    Returns:
        List of matching file paths
    """
    reader = StorageReader()
    files = reader.list_files(base_path, file_pattern)
    
    if not files:
        print(f"\n❌ No files matching pattern '{file_pattern}' found in:")
        print(f"   {base_path}")
        return []
    
    print(f"\n✓ Found {len(files)} file(s) matching pattern '{file_pattern}':")
    for i, file in enumerate(files, 1):
        # Show only filename for clarity
        if reader.is_azure_path(file):
            display_name = file.split('/')[-1]
            print(f"   {i}. {display_name} (Azure Storage)")
        else:
            display_name = os.path.basename(file)
            print(f"   {i}. {display_name} (Local)")
    
    return files


# Example usage
if __name__ == "__main__":
    print("="*80)
    print("Storage Utils - Testing Local and Azure Storage Support")
    print("="*80)
    
    reader = StorageReader()
    
    # Test local path
    print("\n1. Testing Local Path:")
    local_path = r'..\..\scanner\out\utilization\cluster'
    files = reader.list_files(local_path, '*_cluster_utilization.csv')
    print(f"   Found {len(files)} files")
    
    # Test Azure path example
    print("\n2. Azure Path Examples:")
    azure_paths = [
        "https://mystorageaccount.blob.core.windows.net/container/path/file.csv",
        "wasbs://container@mystorageaccount.blob.core.windows.net/path/file.csv",
        "abfss://container@mystorageaccount.dfs.core.windows.net/path/file.csv"
    ]
    
    for path in azure_paths:
        print(f"\n   Path: {path}")
        print(f"   Is Azure: {reader.is_azure_path(path)}")
        if reader.is_azure_path(path):
            try:
                account_url, container, blob = reader.parse_azure_path(path)
                print(f"   Account URL: {account_url}")
                print(f"   Container: {container}")
                print(f"   Blob Path: {blob}")
            except Exception as e:
                print(f"   Parse Error: {str(e)}")
    
    print("\n" + "="*80)
    print("Azure Storage Support Status:")
    print(f"   SDK Available: {AZURE_AVAILABLE}")
    if AZURE_AVAILABLE:
        print("   ✓ Can read from Azure Blob Storage")
    else:
        print("   ✗ Install azure-storage-blob and azure-identity for Azure support")
    print("="*80)
