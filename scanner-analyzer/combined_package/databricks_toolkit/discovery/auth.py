"""
Authentication module for Databricks Workspace Scanner.
Handles authentication using Databricks DefaultAuth for wheel deployment.
"""

import logging
from typing import Optional
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

logger = logging.getLogger(__name__)


class AuthManager:
    """
    Manages authentication for Databricks workspaces.
    Uses DefaultAuth to automatically select the best authentication method.
    This works seamlessly when deployed as a wheel and run from Databricks notebooks.
    """
    
    def __init__(self):
        """Initialize the authentication manager."""
        self._clients = {}  # Cache clients by workspace URL
    
    def get_client(self, workspace_url: str) -> WorkspaceClient:
        """
        Get or create an authenticated WorkspaceClient for the given workspace URL.
        
        Args:
            workspace_url: The Databricks workspace URL
            
        Returns:
            Authenticated WorkspaceClient instance
            
        Raises:
            Exception: If authentication fails
        """
        # Return cached client if available
        if workspace_url in self._clients:
            logger.debug(f"Using cached client for {workspace_url}")
            return self._clients[workspace_url]
        
        try:
            logger.info(f"Creating new client for workspace: {workspace_url}")
            
            # Create client with DefaultAuth
            # This will automatically use the most appropriate auth method:
            # - When running in Databricks: uses notebook credentials
            # - When running locally: uses Azure CLI or other configured methods
            config = Config(host=workspace_url)
            client = WorkspaceClient(config=config)
            
            # Verify authentication by making a simple API call
            current_user = client.current_user.me()
            logger.info(f"Successfully authenticated to {workspace_url} as: {current_user.user_name}")
            
            # Cache the client
            self._clients[workspace_url] = client
            
            return client
            
        except Exception as e:
            logger.error(f"Failed to authenticate to workspace {workspace_url}: {str(e)}")
            raise Exception(f"Authentication failed for {workspace_url}: {str(e)}")
    
    def verify_connection(self, client: WorkspaceClient) -> bool:
        """
        Verify that the client connection is working.
        
        Args:
            client: WorkspaceClient to verify
            
        Returns:
            True if connection is valid, False otherwise
        """
        try:
            user_info = client.current_user.me()
            logger.debug(f"Connection verified for user: {user_info.user_name}")
            return True
        except Exception as e:
            logger.error(f"Connection verification failed: {str(e)}")
            return False
    
    def clear_cache(self):
        """Clear all cached clients."""
        self._clients.clear()
        logger.debug("Client cache cleared")
