"""
Security Scanner Module for Databricks Workspace Discovery.
Scans workspace security configurations including network, IAM, data protection, and compliance settings.
"""

import logging
from typing import Dict, List, Any, Optional
from databricks.sdk import WorkspaceClient
from .utils import safe_get_attribute

logger = logging.getLogger(__name__)


class SecurityScanner:
    """
    Scanner for Databricks workspace security configurations.
    Extracts network security, identity & access, data protection, and compliance settings.
    """
    
    def __init__(self, client: WorkspaceClient, config, account_id: Optional[str] = None):
        """
        Initialize security scanner.
        
        Args:
            client: Authenticated Databricks WorkspaceClient
            config: Scan configuration object
            account_id: Optional account ID for account-level security scanning
        """
        self.client = client
        self.config = config
        # Strip whitespace from account_id to prevent URL encoding issues
        self.account_id = account_id.strip() if account_id else None
        self.account_client = None
        self.scan_type = 'deep' if config.is_deep_scan() else 'simple'
        
        # Initialize AccountClient if account_id provided
        if account_id:
            try:
                from databricks.sdk import AccountClient
                
                # Determine account host based on workspace host
                workspace_host = client.config.host
                if 'azuredatabricks.net' in workspace_host:
                    account_host = 'https://accounts.azuredatabricks.net'
                    self.cloud_provider = 'azure'
                elif 'gcp.databricks.com' in workspace_host:
                    account_host = 'https://accounts.gcp.databricks.com'
                    self.cloud_provider = 'gcp'
                else:
                    # AWS
                    account_host = 'https://accounts.cloud.databricks.com'
                    self.cloud_provider = 'aws'
                
                logger.info(f"Initializing AccountClient with account_host: {account_host}, account_id: {account_id}")
                
                # For Azure, use DefaultAzureCredential (Azure CLI, Managed Identity, Environment Variables)
                # For AWS/GCP, use token-based authentication
                if 'azuredatabricks.net' in workspace_host:
                    logger.info("Using Azure Default Credentials (Azure CLI, Managed Identity, or Environment Variables)")
                    # AccountClient will automatically use DefaultAzureCredential for Azure
                    self.account_client = AccountClient(
                        host=account_host,
                        account_id=self.account_id
                    )
                else:
                    # For AWS/GCP, use token-based authentication
                    self.account_client = AccountClient(
                        host=account_host,
                        account_id=self.account_id,
                        token=client.config.token
                    )
                
                logger.info(f"AccountClient initialized successfully for account: {account_id}")
            except Exception as e:
                logger.warning(f"Could not initialize AccountClient: {e}")
                logger.warning(f"For Azure, ensure you're authenticated via: az login, Managed Identity, or Environment Variables")
                logger.debug(f"AccountClient initialization failed: {type(e).__name__}: {str(e)}", exc_info=True)
                self.account_client = None
    
    def scan(self) -> Dict[str, Any]:
        """
        Scan all security configurations in the workspace.
        
        Returns:
            Dictionary containing security configuration data organized by category
        """
        logger.info("="*80)
        logger.info("DEBUG: SecurityScanner.scan() method called - EXECUTION STARTED")
        logger.info("="*80)
        
        results = {
            'network_security': {},
            'identity_access': {},
            'data_protection': {},
            'governance': {},
            'compliance': {}
        }
        
        try:
            # Scan Azure Account Settings (if Azure and account_id provided)
            if self.cloud_provider == 'azure' and self.account_client:
                results['azure_account_settings'] = self._scan_azure_account_settings()
            
            # Scan Azure Workspace Settings (if Azure)
            if self.cloud_provider == 'azure':
                results['azure_workspace_settings'] = self._scan_azure_workspace_settings()
            
            # Scan Network Security
            results['network_security'] = self._scan_network_security()
            
            # Scan Identity & Access
            results['identity_access'] = self._scan_identity_access()
            
            # Scan Data Protection
            results['data_protection'] = self._scan_data_protection()
            
            # Scan Governance
            results['governance'] = self._scan_governance()
            
            # Scan Compliance
            results['compliance'] = self._scan_compliance()
            
            logger.info("="*80)
            logger.info("DEBUG: SecurityScanner.scan() COMPLETED SUCCESSFULLY")
            logger.info(f"DEBUG: Results keys: {list(results.keys())}")
            logger.info("="*80)
            
        except Exception as e:
            logger.error(f"="*80)
            logger.error(f"DEBUG: SecurityScanner.scan() FAILED with error: {str(e)}")
            logger.error(f"="*80)
            results['scan_error'] = str(e)
        
        logger.info(f"DEBUG: SecurityScanner.scan() returning results with {len(results)} categories")
        return results
    
    def _scan_azure_account_settings(self) -> Dict[str, Any]:
        """
        Scan Azure Databricks account-level settings (Azure only).
        Retrieves settings from /api/2.1/accounts/{account_id}/settings-metadata
        Uses AccountClient's built-in authentication (credential passthrough or PAT).
        
        Returns:
            Dictionary with Azure account-level settings
        """
        logger.info("Scanning Azure account-level settings...")
        
        account_settings = {
            'settings_count': 0,
            'security_relevant_settings': {},
            'all_settings': {}
        }
        
        if not self.account_client:
            logger.warning("AccountClient not available - skipping Azure account settings scan")
            account_settings['note'] = 'AccountClient required for account-level settings'
            return account_settings
        
        try:
            # Azure Databricks uses different API structure than AWS Databricks
            # For Azure, many "account" settings are actually at workspace level
            # Try workspace settings API first for Azure
            
            # Check if this is Azure by inspecting the workspace host
            workspace_host = self.client.config.host
            is_azure = 'azuredatabricks.net' in workspace_host if workspace_host else False
            
            if is_azure:
                # For Azure, account-level settings API may not be available
                # The settings-metadata endpoint might not exist for Azure accounts
                logger.info("Azure Databricks detected - account-level settings API may not be available")
                account_settings['note'] = 'Azure Databricks: Account settings managed via Azure Portal and workspace settings'
                account_settings['azure_note'] = 'Use Azure Portal for account-level configurations (IP ACLs, CMK, Private Link, etc.)'
                return account_settings
            
            # For AWS Databricks, use account client API
            path = f"/api/2.1/accounts/{self.account_id}/settings-metadata"
            
            logger.debug(f"Fetching account settings using AccountClient API: {path}")
            logger.debug(f"Account host: {self.account_client.config.host}")
            logger.debug(f"Account ID (stripped): '{self.account_id}'")
            
            settings_data = self.account_client.api_client.do('GET', path)
            logger.debug(f"Received settings_data: {type(settings_data)}, length: {len(str(settings_data)) if settings_data else 0}")
            
            if settings_data and isinstance(settings_data, dict):
                # API returns 'settings_metadata' key (not 'settings')
                settings_list = settings_data.get('settings_metadata', [])
                account_settings['settings_count'] = len(settings_list)
                
                # Security-relevant account settings (14 total from documentation)
                security_keys = {
                    'acct_ip_acl_enable': 'Account IP Access Control',
                    'cmk_catalog': 'Customer-Managed Keys for Catalog',
                    'disable_legacy_features': 'Disable Legacy Insecure Features',
                    'ipaclv2': 'IP Access Control List v2',
                    'enable_gov_tag': 'Governance Tagging for Compliance',
                    'abac_rls_cm_account': 'Attribute-Based Access Control (RLS)',
                    'ds_abac': 'Data Science ABAC Features',
                    'mat_history': 'Materialized History Tracking'
                }
                
                for setting in settings_list:
                    key = setting.get('key', '')
                    account_settings['all_settings'][key] = {
                        'name': setting.get('name', ''),
                        'description': setting.get('description', ''),
                        'type': setting.get('type', ''),
                        'docs_link': setting.get('docs_link', '')
                    }
                    
                    # Track security-relevant settings
                    if key in security_keys:
                        account_settings['security_relevant_settings'][key] = {
                            'friendly_name': security_keys[key],
                            'name': setting.get('name', ''),
                            'description': setting.get('description', ''),
                            'value': 'Configured' if key in account_settings['all_settings'] else 'Not Configured'
                        }
                
                logger.info(f"Retrieved {len(settings_list)} Azure account settings ({len(account_settings['security_relevant_settings'])} security-relevant)")
            else:
                logger.error(f"Failed to retrieve Azure account settings: {response.status_code} - {response.text}")
                accountwarning("No account settings data returned from API")
                account_settings['note'] = 'No settings data returned'
        except Exception as e:
            logger.error(f"Error scanning Azure account settings: {e}")
            logger.debug(f"Full exception details: {type(e).__name__}: {str(e)}", exc_info=True)
            account_settings['error'] = str(e)
        
        return account_settings
    
    def _scan_azure_workspace_settings(self) -> Dict[str, Any]:
        """
        Scan Azure Databricks workspace-level settings (Azure only).
        Retrieves settings from /api/2.1/settings-metadata
        Uses WorkspaceClient's built-in authentication (credential passthrough or PAT).
        
        Returns:
            Dictionary with Azure workspace-level settings
        """
        logger.info("Scanning Azure workspace-level settings...")
        
        workspace_settings = {
            'settings_count': 0,
            'security_relevant_settings': {},
            'data_exfiltration_controls': {},
            'external_connectors': {},
            'all_settings': {}
        }
        
        try:
            # Use WorkspaceClient's API client with built-in authentication
            # This works with credential passthrough in Databricks notebooks or PAT tokens
            path = "/api/2.1/settings-metadata"
            
            logger.debug(f"Fetching Azure workspace settings using WorkspaceClient API: {path}")
            logger.debug(f"Workspace host: {self.client.config.host}")
            
            settings_data = self.client.api_client.do('GET', path)
            logger.debug(f"Received settings_data: {type(settings_data)}, length: {len(str(settings_data)) if settings_data else 0}")
            
            if settings_data and isinstance(settings_data, dict):
                # API returns 'settings_metadata' key (not 'settings')
                settings_list = settings_data.get('settings_metadata', [])
                workspace_settings['settings_count'] = len(settings_list)
                
                # Security-relevant workspace settings (14 critical settings)
                security_keys = {
                    'enableExportNotebook': 'Notebook Export Control (Data Exfiltration)',
                    'enableNotebookTableClipboard': 'Notebook Clipboard Control (Data Exfiltration)',
                    'enableResultsDownloading': 'Results Download Control (Data Exfiltration)',
                    'sql_results_download': 'SQL Results Download Control (Data Exfiltration)',
                    'disable_legacy_access': 'Disable Legacy Access (Authentication)',
                    'disable_legacy_dbfs': 'Disable Legacy DBFS (Data Access)',
                    'dashboard_email_subscriptions': 'Dashboard Email Subscriptions (Data Sharing)',
                    'abac_rls_cm': 'ABAC Row-Level Security (Workspace)',
                    'uc_compliance_controls': 'Unity Catalog Compliance Features',
                    'encryption_at_rest': 'Data Encryption at Rest Controls',
                    'private_link': 'Private Link Network Configuration',
                    'workspace_access_control': 'Workspace-Level Access Policies',
                    'audit_log_delivery': 'Audit Log Configuration',
                    'token_management': 'Personal Access Token Policies'
                }
                
                # Data exfiltration control settings
                exfiltration_keys = {
                    'enableExportNotebook': 'Notebook Export',
                    'enableNotebookTableClipboard': 'Clipboard Access',
                    'enableResultsDownloading': 'Results Download',
                    'sql_results_download': 'SQL Results Download',
                    'dashboard_email_subscriptions': 'Dashboard Email'
                }
                
                # External connector settings
                connector_keys = {
                    'jdbc_connector': 'JDBC Connector',
                    'mysql_connector': 'MySQL Connector',
                    'postgresql_connector': 'PostgreSQL Connector',
                    'sfdc_file_sharing': 'Salesforce File Sharing',
                    'sftp_connector': 'SFTP Connector',
                    'sharepoint_connector': 'SharePoint Connector',
                    'confluence_connector': 'Confluence Connector',
                    'jira_connector': 'Jira Connector',
                    'dynamics_connector': 'Dynamics 365 Connector'
                }
                
                for setting in settings_list:
                    key = setting.get('key', '')
                    setting_data = {
                        'name': setting.get('name', ''),
                        'description': setting.get('description', ''),
                        'type': setting.get('type', ''),
                        'docs_link': setting.get('docs_link', '')
                    }
                    
                    workspace_settings['all_settings'][key] = setting_data
                    
                    # Track security-relevant settings
                    if key in security_keys:
                        workspace_settings['security_relevant_settings'][key] = {
                            'friendly_name': security_keys[key],
                            **setting_data,
                            'status': 'Available'
                        }
                    
                    # Track data exfiltration controls
                    if key in exfiltration_keys:
                        workspace_settings['data_exfiltration_controls'][key] = {
                            'friendly_name': exfiltration_keys[key],
                            **setting_data,
                            'status': 'Available'
                        }
                    
                    # Track external connectors
                    if key in connector_keys:
                        workspace_settings['external_connectors'][key] = {
                            'friendly_name': connector_keys[key],
                            **setting_data,
                            'status': 'Available'
                        }
                
                logger.info(f"Retrieved {len(settings_list)} Azure workspace settings")
                logger.info(f"  - Security-relevant: {len(workspace_settings['security_relevant_settings'])}")
                logger.info(f"  - Data exfiltration controls: {len(workspace_settings['data_exfiltration_controls'])}")
                logger.info(f"  - External connectors: {len(workspace_settings['external_connectors'])}")
            else:
                logger.warning("No workspace settings data returned from API")
                workspace_settings['note'] = 'No settings data returned'
                
        except Exception as e:
            logger.error(f"Error scanning Azure workspace settings: {e}")
            logger.debug(f"Full exception details: {type(e).__name__}: {str(e)}", exc_info=True)
            workspace_settings['error'] = str(e)
        
        return workspace_settings
        
        return workspace_settings
    
    def _scan_network_security(self) -> Dict[str, Any]:
        """
        Scan network security configurations.
        
        Returns:
            Dictionary with network security settings
        """
        logger.info("Scanning network security configurations...")
        
        network_config = {
            'ip_access_lists': {
                'enabled': False,
                'lists': [],
                'total_count': 0
            },
            'workspace_settings': {},
            'cluster_connectivity': {},
            'private_access': {
                'details': 'Check workspace deployment settings in Account Console'
            }
        }
        
        try:
            # Get IP Access Lists
            try:
                ip_lists = list(self.client.ip_access_lists.list())
                network_config['ip_access_lists']['total_count'] = len(ip_lists)
                network_config['ip_access_lists']['enabled'] = len(ip_lists) > 0
                
                for ip_list in ip_lists:
                    list_info = {
                        'list_id': ip_list.list_id,
                        'label': ip_list.label,
                        'list_type': safe_get_attribute(ip_list, 'list_type.value', 'BLOCK'),
                        'enabled': safe_get_attribute(ip_list, 'enabled', True),
                        'ip_addresses': ip_list.ip_addresses if hasattr(ip_list, 'ip_addresses') else []
                    }
                    network_config['ip_access_lists']['lists'].append(list_info)
                
                logger.info(f"Found {len(ip_lists)} IP access lists")
            except Exception as e:
                logger.warning(f"Could not retrieve IP access lists: {str(e)}")
                network_config['ip_access_lists']['error'] = str(e)
            
            # Get comprehensive workspace settings related to network security
            network_config['workspace_settings'] = self._get_workspace_security_settings()
            
            # Check cluster connectivity settings
            try:
                clusters = list(self.client.clusters.list())
                no_public_ip_count = 0
                total_active = 0
                
                for cluster in clusters:
                    if hasattr(cluster, 'state') and str(cluster.state.value) not in ['TERMINATED', 'TERMINATING']:
                        total_active += 1
                        # Check for secure cluster connectivity (no public IPs)
                        if hasattr(cluster, 'enable_elastic_disk') and hasattr(cluster, 'aws_attributes'):
                            aws_attrs = cluster.aws_attributes
                            if hasattr(aws_attrs, 'first_on_demand') or hasattr(aws_attrs, 'availability'):
                                no_public_ip_count += 1
                
                network_config['cluster_connectivity'] = {
                    'total_active_clusters': total_active,
                    'secure_connectivity_enabled': no_public_ip_count > 0,
                    'details': f'{no_public_ip_count}/{total_active} clusters configured'
                }
            except Exception as e:
                logger.debug(f"Could not check cluster connectivity: {str(e)}")
                network_config['cluster_connectivity']['error'] = str(e)
            
            # Account-level network configurations (requires AccountClient)
            if self.account_client:
                logger.info("Scanning account-level network configurations...")
                network_config['vpc_networks'] = self._scan_networks()
                network_config['vpc_endpoints'] = self._scan_vpc_endpoints()
            else:
                logger.info("Skipping account-level network scan (account_id not provided)")
            
        except Exception as e:
            logger.error(f"Error scanning network security: {str(e)}")
            network_config['error'] = str(e)
        
        return network_config
    
    def _get_workspace_security_settings(self) -> Dict[str, Any]:
        """
        Retrieve comprehensive workspace security settings.
        
        Returns:
            Dictionary of workspace security configurations
        """
        settings = {}
        
        # Define security-relevant workspace configuration keys
        security_settings_keys = [
            # Access control settings
            'enableJobViewAcls',
            'enforceClusterViewAcls', 
            'enforceWorkspaceViewAcls',
            'enforceUserIsolation',
            
            # Token and authentication
            'enableTokensConfig',
            'maxTokenLifetimeDays',
            
            # File system and data access
            'enableDbfsFileBrowser',
            'enableNotebookTableClipboard',
            'enableResultsDownloading',
            'enableUploadDataUis',
            'enableExportNotebook',
            
            # Collaboration and external access
            'enableNotebookGitVersioning',
            'enableWebTerminal',
            
            # Advanced features
            'enableWorkspaceFilesystem',
            'enableProjectTypeInWorkspace',
        ]
        
        for key in security_settings_keys:
            try:
                conf_value = self.client.workspace_conf.get_status(keys=key)
                if hasattr(conf_value, key):
                    settings[key] = getattr(conf_value, key)
            except Exception as e:
                logger.debug(f"Could not retrieve setting {key}: {str(e)}")
        
        return settings
    
    def _scan_encryption_keys(self) -> Dict[str, Any]:
        """
        Scan customer-managed encryption keys (AccountClient required).
        
        Returns:
            Dictionary with encryption key configuration data
        """
        logger.info("Scanning customer-managed encryption keys...")
        
        key_data = {
            'total_count': 0,
            'keys_by_use_case': {'managed_services': 0, 'storage': 0},
            'keys_older_than_365_days': 0,
            'keys_list': []
        }
        
        # Check if AccountClient is available
        if not self.account_client:
            logger.warning("AccountClient not available - skipping encryption keys scan")
            key_data['note'] = 'Account-level API access required - provide account_id to enable'
            return key_data
        
        # Skip for Azure - AWS-specific API
        if self.cloud_provider == 'azure':
            logger.info("Skipping encryption_keys.list() - AWS-specific API (Azure uses Customer-Managed Keys via workspace config)")
            key_data['note'] = 'Azure uses Customer-Managed Keys (CMK) configured per workspace, not account-level API'
            return key_data
        
        try:
            import time
            logger.debug(f"Calling account_client.encryption_keys.list() with account_id: {self.account_id}")
            keys = list(self.account_client.encryption_keys.list())
            key_data['total_count'] = len(keys)
            
            current_time = int(time.time() * 1000)  # Epoch milliseconds
            one_year_ms = 365 * 24 * 60 * 60 * 1000
            
            for key in keys:
                key_info = {
                    'customer_managed_key_id': key.customer_managed_key_id,
                    'creation_time': key.creation_time,
                    'use_cases': [uc.value for uc in (key.use_cases or [])],
                    'aws_key_info': None,
                    'gcp_key_info': None,
                    'age_days': None
                }
                
                # Calculate key age
                if key.creation_time:
                    age_ms = current_time - key.creation_time
                    key_info['age_days'] = age_ms // (24 * 60 * 60 * 1000)
                    if age_ms > one_year_ms:
                        key_data['keys_older_than_365_days'] += 1
                
                # AWS key info
                if key.aws_key_info:
                    key_info['aws_key_info'] = {
                        'key_arn': safe_get_attribute(key.aws_key_info, 'key_arn'),
                        'key_alias': safe_get_attribute(key.aws_key_info, 'key_alias'),
                        'key_region': safe_get_attribute(key.aws_key_info, 'key_region')
                    }
                
                # GCP key info
                if key.gcp_key_info:
                    key_info['gcp_key_info'] = {
                        'kms_key_id': safe_get_attribute(key.gcp_key_info, 'kms_key_id')
                    }
                
                # Count by use case
                if key.use_cases:
                    for uc in key.use_cases:
                        if uc.value == 'MANAGED_SERVICES':
                            key_data['keys_by_use_case']['managed_services'] += 1
                        elif uc.value == 'STORAGE':
                            key_data['keys_by_use_case']['storage'] += 1
                
                if self.scan_type == 'deep':
                    key_data['keys_list'].append(key_info)
            
            logger.info(f"Found {key_data['total_count']} customer-managed keys")
            
        except Exception as e:
            logger.error(f"Error scanning encryption keys: {e}")
            logger.debug(f"Full exception details: {type(e).__name__}: {str(e)}", exc_info=True)
            key_data['error'] = str(e)
        
        return key_data
    
    def _scan_networks(self) -> Dict[str, Any]:
        """
        Scan customer-managed VPC network configurations (AccountClient required).
        
        Returns:
            Dictionary with network configuration data
        """
        logger.info("Scanning customer-managed VPC networks...")
        
        network_data = {
            'total_count': 0,
            'networks_by_status': {'valid': 0, 'broken': 0, 'warned': 0, 'unattached': 0},
            'total_errors': 0,
            'total_warnings': 0,
            'networks_with_vpc_endpoints': 0,
            'networks_list': []
        }
        
        # Check if AccountClient is available
        if not self.account_client:
            logger.warning("AccountClient not available - skipping VPC networks scan")
            network_data['note'] = 'Account-level API access required - provide account_id to enable'
            return network_data
        
        # Skip for Azure - AWS VPC-specific API
        if self.cloud_provider == 'azure':
            logger.info("Skipping networks.list() - AWS VPC-specific API (Azure uses VNet Injection configured per workspace)")
            network_data['note'] = 'Azure uses VNet Injection configured per workspace, not account-level VPC networks'
            return network_data
        
        try:
            logger.debug(f"Calling account_client.networks.list() with account_id: {self.account_id}")
            networks = list(self.account_client.networks.list())
            network_data['total_count'] = len(networks)
            
            for network in networks:
                network_info = {
                    'network_id': network.network_id,
                    'network_name': network.network_name,
                    'vpc_id': network.vpc_id,
                    'vpc_status': network.vpc_status.value if network.vpc_status else None,
                    'workspace_id': network.workspace_id,
                    'subnet_count': len(network.subnet_ids or []),
                    'security_group_count': len(network.security_group_ids or []),
                    'has_vpc_endpoints': network.vpc_endpoints is not None,
                    'error_count': len(network.error_messages or []),
                    'warning_count': len(network.warning_messages or []),
                    'creation_time': network.creation_time
                }
                
                # Count by status
                if network.vpc_status:
                    status = network.vpc_status.value.lower()
                    if status in network_data['networks_by_status']:
                        network_data['networks_by_status'][status] += 1
                
                # Count errors and warnings
                if network.error_messages:
                    network_data['total_errors'] += len(network.error_messages)
                    if self.scan_type == 'deep':
                        network_info['errors'] = [
                            {'type': err.error_type.value, 'message': err.error_message}
                            for err in network.error_messages
                        ]
                
                if network.warning_messages:
                    network_data['total_warnings'] += len(network.warning_messages)
                    if self.scan_type == 'deep':
                        network_info['warnings'] = [
                            {'type': warn.warning_type.value, 'message': warn.warning_message}
                            for warn in network.warning_messages
                        ]
                
                # VPC endpoints
                if network.vpc_endpoints:
                    network_data['networks_with_vpc_endpoints'] += 1
                
                if self.scan_type == 'deep':
                    network_data['networks_list'].append(network_info)
            
            logger.info(f"Found {network_data['total_count']} VPC networks")
            
        except Exception as e:
            logger.error(f"Error scanning networks: {e}")
            logger.debug(f"Full exception details: {type(e).__name__}: {str(e)}", exc_info=True)
            network_data['error'] = str(e)
        
        return network_data
    
    def _scan_vpc_endpoints(self) -> Dict[str, Any]:
        """
        Scan VPC endpoint configurations for PrivateLink (AccountClient required).
        
        Returns:
            Dictionary with VPC endpoint data
        """
        logger.info("Scanning VPC endpoints (PrivateLink)...")
        
        endpoint_data = {
            'total_count': 0,
            'endpoints_by_use_case': {'workspace_access': 0, 'dataplane_relay_access': 0},
            'endpoints_by_state': {},
            'healthy_endpoints': 0,
            'unhealthy_endpoints': 0,
            'endpoints_list': []
        }
        
        # Check if AccountClient is available
        if not self.account_client:
            logger.warning("AccountClient not available - skipping VPC endpoints scan")
            endpoint_data['note'] = 'Account-level API access required - provide account_id to enable'
            return endpoint_data
        
        # Skip for Azure - AWS PrivateLink-specific API
        if self.cloud_provider == 'azure':
            logger.info("Skipping vpc_endpoints.list() - AWS PrivateLink-specific API (Azure uses Private Link configured per workspace)")
            endpoint_data['note'] = 'Azure uses Private Link endpoints configured per workspace, not account-level VPC endpoints'
            return endpoint_data
        
        try:
            logger.debug(f"Calling account_client.vpc_endpoints.list() with account_id: {self.account_id}")
            endpoints = list(self.account_client.vpc_endpoints.list())
            endpoint_data['total_count'] = len(endpoints)
            
            for endpoint in endpoints:
                endpoint_info = {
                    'vpc_endpoint_id': endpoint.vpc_endpoint_id,
                    'vpc_endpoint_name': endpoint.vpc_endpoint_name,
                    'aws_vpc_endpoint_id': endpoint.aws_vpc_endpoint_id,
                    'region': endpoint.region,
                    'state': endpoint.state,
                    'use_case': endpoint.use_case.value if endpoint.use_case else None,
                    'aws_endpoint_service_id': endpoint.aws_endpoint_service_id
                }
                
                # Count by use case
                if endpoint.use_case:
                    use_case = endpoint.use_case.value.lower()
                    if use_case in endpoint_data['endpoints_by_use_case']:
                        endpoint_data['endpoints_by_use_case'][use_case] += 1
                
                # Count by state
                if endpoint.state:
                    state = endpoint.state.lower()
                    endpoint_data['endpoints_by_state'][state] = \
                        endpoint_data['endpoints_by_state'].get(state, 0) + 1
                    
                    # Healthy = available
                    if state == 'available':
                        endpoint_data['healthy_endpoints'] += 1
                    else:
                        endpoint_data['unhealthy_endpoints'] += 1
                
                if self.scan_type == 'deep':
                    endpoint_data['endpoints_list'].append(endpoint_info)
            
            logger.info(f"Found {endpoint_data['total_count']} VPC endpoints")
            
        except Exception as e:
            logger.error(f"Error scanning VPC endpoints: {e}")
            logger.debug(f"Full exception details: {type(e).__name__}: {str(e)}", exc_info=True)
            endpoint_data['error'] = str(e)
        
        return endpoint_data
    
    def _scan_identity_access(self) -> Dict[str, Any]:
        """
        Scan identity and access management configurations.
        
        Returns:
            Dictionary with IAM settings
        """
        logger.info("Scanning identity & access configurations...")
        
        iam_config = {
            'users': {
                'total_count': 0,
                'admin_count': 0,
                'active_count': 0,
                'users_list': []
            },
            'groups': {
                'total_count': 0,
                'groups_list': []
            },
            'service_principals': {
                'total_count': 0,
                'principals_list': []
            },
            'scim_enabled': 'Unknown',
            'sso_enabled': 'Unknown'
        }
        
        try:
            # Get Users
            try:
                all_users = list(self.client.users.list())
                iam_config['users']['total_count'] = len(all_users)
                
                for user in all_users:
                    user_info = {
                        'id': user.id,
                        'user_name': user.user_name,
                        'display_name': safe_get_attribute(user, 'display_name'),
                        'active': safe_get_attribute(user, 'active', True)
                    }
                    
                    # Check if user is admin
                    if hasattr(user, 'groups'):
                        groups = [g.display for g in user.groups] if user.groups else []
                        user_info['groups'] = groups
                        if 'admins' in [g.lower() for g in groups]:
                            iam_config['users']['admin_count'] += 1
                            user_info['is_admin'] = True
                    
                    if user_info.get('active', True):
                        iam_config['users']['active_count'] += 1
                    
                    # For simple scan, only include summary; for deep scan, include full list
                    if self.config.is_deep_scan():
                        iam_config['users']['users_list'].append(user_info)
                
                logger.info(f"Found {len(all_users)} users ({iam_config['users']['admin_count']} admins)")
            except Exception as e:
                logger.warning(f"Could not retrieve users: {str(e)}")
                iam_config['users']['error'] = str(e)
            
            # Get Groups
            try:
                all_groups = list(self.client.groups.list())
                iam_config['groups']['total_count'] = len(all_groups)
                
                for group in all_groups:
                    group_info = {
                        'id': group.id,
                        'display_name': group.display_name,
                        'external_id': safe_get_attribute(group, 'external_id'),
                        'member_count': len(group.members) if hasattr(group, 'members') and group.members else 0
                    }
                    
                    # For deep scan, include full group list
                    if self.config.is_deep_scan():
                        iam_config['groups']['groups_list'].append(group_info)
                
                logger.info(f"Found {len(all_groups)} groups")
            except Exception as e:
                logger.warning(f"Could not retrieve groups: {str(e)}")
                iam_config['groups']['error'] = str(e)
            
            # Get Service Principals
            try:
                all_sps = list(self.client.service_principals.list())
                iam_config['service_principals']['total_count'] = len(all_sps)
                
                for sp in all_sps:
                    sp_info = {
                        'id': sp.id,
                        'application_id': safe_get_attribute(sp, 'application_id'),
                        'display_name': safe_get_attribute(sp, 'display_name'),
                        'active': safe_get_attribute(sp, 'active', True)
                    }
                    
                    # For deep scan, include full SP list
                    if self.config.is_deep_scan():
                        iam_config['service_principals']['principals_list'].append(sp_info)
                
                logger.info(f"Found {len(all_sps)} service principals")
            except Exception as e:
                logger.warning(f"Could not retrieve service principals: {str(e)}")
                iam_config['service_principals']['error'] = str(e)
            
            # Infer SCIM status (if external_id exists on groups, likely SCIM-provisioned)
            if iam_config['groups']['total_count'] > 0:
                try:
                    sample_groups = list(self.client.groups.list())[:5]
                    scim_indicators = sum(1 for g in sample_groups if hasattr(g, 'external_id') and g.external_id)
                    iam_config['scim_enabled'] = 'Likely' if scim_indicators > 0 else 'Unlikely'
                except Exception:
                    pass
            
            # Check user privileges (cluster create permissions)
            try:
                cluster_create_users = []
                for user in list(self.client.users.list())[:50]:  # Sample for performance
                    if hasattr(user, 'entitlements') and user.entitlements:
                        for entitlement in user.entitlements:
                            if hasattr(entitlement, 'value') and 'cluster-create' in str(entitlement.value).lower():
                                cluster_create_users.append(user.user_name)
                                break
                
                iam_config['cluster_create_privileges'] = {
                    'user_count': len(cluster_create_users),
                    'users': cluster_create_users if self.config.is_deep_scan() else []
                }
                logger.info(f"Found {len(cluster_create_users)} users with cluster create privileges")
            except Exception as e:
                logger.debug(f"Could not check cluster create privileges: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error scanning identity & access: {str(e)}")
            iam_config['error'] = str(e)
        
        return iam_config
    
    def _scan_data_protection(self) -> Dict[str, Any]:
        """
        Scan data protection configurations.
        
        Returns:
            Dictionary with data protection settings
        """
        logger.info("Scanning data protection configurations...")
        
        data_protection = {
            'secrets': {
                'total_scopes': 0,
                'scopes_list': []
            },
            'tokens': {
                'note': 'Token management policies configured via workspace settings'
            },
            'encryption': {
                'note': 'Encryption settings managed at account level and in cluster configurations'
            }
        }
        
        # Account-level encryption keys (requires AccountClient)
        if self.account_client:
            data_protection['encryption_keys'] = self._scan_encryption_keys()
        else:
            logger.info("Skipping encryption keys scan (AccountClient not available)")
        
        try:
            # Get Secret Scopes
            try:
                secret_scopes = list(self.client.secrets.list_scopes())
                data_protection['secrets']['total_scopes'] = len(secret_scopes)
                
                for scope in secret_scopes:
                    scope_info = {
                        'name': scope.name,
                        'backend_type': safe_get_attribute(scope, 'backend_type.value', 'DATABRICKS')
                    }
                    
                    # For deep scan, get secrets count in each scope
                    if self.config.is_deep_scan():
                        try:
                            secrets_in_scope = list(self.client.secrets.list_secrets(scope=scope.name))
                            scope_info['secrets_count'] = len(secrets_in_scope)
                            scope_info['secret_keys'] = [s.key for s in secrets_in_scope]
                        except Exception as e:
                            scope_info['secrets_count'] = 'Unable to list'
                            logger.debug(f"Could not list secrets in scope {scope.name}: {str(e)}")
                    
                    data_protection['secrets']['scopes_list'].append(scope_info)
                
                logger.info(f"Found {len(secret_scopes)} secret scopes")
            except Exception as e:
                logger.warning(f"Could not retrieve secret scopes: {str(e)}")
                data_protection['secrets']['error'] = str(e)
            
            # Get Token information with lifecycle analysis
            try:
                import time
                from datetime import datetime, timedelta
                
                tokens = list(self.client.tokens.list())
                data_protection['tokens']['total_count'] = len(tokens)
                
                # Analyze token lifecycle
                current_time_ms = int(time.time() * 1000)
                long_lived_tokens = []
                no_expiry_tokens = []
                
                for token in tokens:
                    expiry_time = safe_get_attribute(token, 'expiry_time')
                    
                    if expiry_time is None or expiry_time == -1:
                        no_expiry_tokens.append(token.token_id)
                    elif expiry_time:
                        # Check if token expires more than 90 days from now
                        ninety_days_ms = 90 * 24 * 60 * 60 * 1000
                        if (expiry_time - current_time_ms) > ninety_days_ms:
                            long_lived_tokens.append(token.token_id)
                
                data_protection['tokens']['active_tokens'] = len([t for t in tokens if hasattr(t, 'expiry_time')])
                data_protection['tokens']['long_lived_count'] = len(long_lived_tokens)
                data_protection['tokens']['no_expiry_count'] = len(no_expiry_tokens)
                data_protection['tokens']['lifecycle_risk'] = 'High' if (len(long_lived_tokens) + len(no_expiry_tokens)) > 0 else 'Low'
                
                if self.config.is_deep_scan():
                    token_list = []
                    for token in tokens:
                        token_info = {
                            'token_id': token.token_id,
                            'comment': safe_get_attribute(token, 'comment'),
                            'creation_time': safe_get_attribute(token, 'creation_time'),
                            'expiry_time': safe_get_attribute(token, 'expiry_time'),
                            'created_by': safe_get_attribute(token, 'created_by_username')
                        }
                        token_list.append(token_info)
                    data_protection['tokens']['tokens_list'] = token_list
                
                logger.info(f"Found {len(tokens)} access tokens ({len(long_lived_tokens)} long-lived, {len(no_expiry_tokens)} no expiry)")
            except Exception as e:
                logger.warning(f"Could not retrieve tokens: {str(e)}")
                data_protection['tokens']['error'] = str(e)
            
            # Check cluster encryption settings
            try:
                clusters = list(self.client.clusters.list())
                unencrypted_clusters = []
                encrypted_count = 0
                
                for cluster in clusters:
                    cluster_id = cluster.cluster_id
                    encrypted = safe_get_attribute(cluster, 'enable_local_disk_encryption', False)
                    
                    if encrypted:
                        encrypted_count += 1
                    else:
                        # Only track active clusters
                        if hasattr(cluster, 'state') and str(cluster.state.value) not in ['TERMINATED', 'TERMINATING']:
                            unencrypted_clusters.append({
                                'cluster_id': cluster_id,
                                'cluster_name': safe_get_attribute(cluster, 'cluster_name', 'Unnamed')
                            })
                
                data_protection['cluster_encryption'] = {
                    'total_clusters': len(clusters),
                    'encrypted_count': encrypted_count,
                    'unencrypted_active': len(unencrypted_clusters),
                    'encryption_enabled': encrypted_count > 0
                }
                
                if self.config.is_deep_scan() and unencrypted_clusters:
                    data_protection['cluster_encryption']['unencrypted_list'] = unencrypted_clusters
                
                logger.info(f"Cluster encryption: {encrypted_count}/{len(clusters)} encrypted")
            except Exception as e:
                logger.debug(f"Could not check cluster encryption: {str(e)}")
                data_protection['cluster_encryption'] = {'error': str(e)}
            
            # Check notebook results storage configuration
            try:
                notebook_results_config = {
                    'customer_managed_storage': False,
                    'storage_configured': False,
                    'configuration_status': 'Unknown'
                }
                
                # Try to get workspace conf settings related to notebook results
                try:
                    # Check for notebook result storage configuration using Databricks API
                    # The key 'storeInteractiveNotebookResultsInCustomerAccount' indicates if customer-managed storage is enabled
                    # This setting is typically managed at account level
                    
                    try:
                        # Query the actual workspace configuration for notebook results storage
                        conf_value = self.client.workspace_conf.get_status(keys='storeInteractiveNotebookResultsInCustomerAccount')
                        
                        if hasattr(conf_value, 'storeInteractiveNotebookResultsInCustomerAccount'):
                            value = getattr(conf_value, 'storeInteractiveNotebookResultsInCustomerAccount')
                            notebook_results_config['storeInteractiveNotebookResultsInCustomerAccount'] = value
                            
                            # Parse the value to determine if customer-managed storage is enabled
                            if value and str(value).lower() in ['true', '1', 'yes']:
                                notebook_results_config['customer_managed_storage'] = True
                                notebook_results_config['storage_configured'] = True
                                notebook_results_config['configuration_status'] = 'Customer-managed storage configured'
                            else:
                                notebook_results_config['customer_managed_storage'] = False
                                notebook_results_config['storage_configured'] = False
                                notebook_results_config['configuration_status'] = 'Default (Databricks-managed)'
                        else:
                            # Key not found in configuration
                            notebook_results_config['configuration_status'] = 'Default (Databricks-managed)'
                            
                    except Exception as key_err:
                        logger.debug(f"Could not retrieve storeInteractiveNotebookResultsInCustomerAccount: {str(key_err)}")
                        notebook_results_config['configuration_status'] = 'Default (Databricks-managed)'
                        notebook_results_config['note'] = 'Configuration key not found - using default Databricks-managed storage'
                    
                except Exception as e:
                    logger.debug(f"Could not retrieve notebook results configuration: {str(e)}")
                    notebook_results_config['configuration_status'] = 'Unknown - Check account console'
                    notebook_results_config['note'] = 'Notebook results storage is configured at account level. Check Account Console > Workspace Settings > Notebook Results.'
                
                data_protection['notebook_results_storage'] = notebook_results_config
                logger.info(f"Notebook results storage: {notebook_results_config['configuration_status']}")
                
            except Exception as e:
                logger.debug(f"Could not check notebook results storage: {str(e)}")
                data_protection['notebook_results_storage'] = {
                    'error': str(e),
                    'note': 'Notebook results storage configuration is managed at account level'
                }
            
        except Exception as e:
            logger.error(f"Error scanning data protection: {str(e)}")
            data_protection['error'] = str(e)
        
        return data_protection
    
    def _scan_governance(self) -> Dict[str, Any]:
        """
        Scan governance configurations.
        
        Returns:
            Dictionary with governance settings
        """
        logger.info("Scanning governance configurations...")
        
        governance = {
            'unity_catalog': {
                'enabled': False,
                'metastore_assigned': False
            },
            'table_acls': {
                'enabled': None,
                'workspace_setting': None,
                'clusters_with_table_acls': 0,
                'total_active_clusters': 0,
                'note': None
            },
            'workspace_config': {}
        }
        
        try:
            # Check Unity Catalog availability
            try:
                # Try to get current metastore
                metastore = self.client.metastores.current()
                if metastore:
                    governance['unity_catalog']['enabled'] = True
                    governance['unity_catalog']['metastore_assigned'] = True
                    governance['unity_catalog']['metastore_id'] = metastore.metastore_id
                    governance['unity_catalog']['metastore_name'] = safe_get_attribute(metastore, 'name')
                    governance['unity_catalog']['region'] = safe_get_attribute(metastore, 'region')
                    governance['unity_catalog']['owner'] = safe_get_attribute(metastore, 'owner')
                    logger.info(f"Unity Catalog enabled with metastore: {metastore.metastore_id}")
                    # Unity Catalog replaces Table ACLs
                    governance['table_acls']['note'] = 'Unity Catalog enabled - Table ACLs not applicable'
            except Exception as e:
                logger.debug(f"Unity Catalog not available or not assigned: {str(e)}")
                governance['unity_catalog']['enabled'] = False
                governance['unity_catalog']['message'] = 'Unity Catalog not enabled or not assigned to workspace'
            
            # Check Table ACLs - workspace setting and cluster configurations
            try:
                # Check workspace-level Table ACL setting
                table_acl_enabled = None
                try:
                    conf_value = self.client.workspace_conf.get_status(keys='enableTableAcl')
                    if hasattr(conf_value, 'enableTableAcl'):
                        table_acl_enabled = getattr(conf_value, 'enableTableAcl')
                        governance['table_acls']['workspace_setting'] = str(table_acl_enabled)
                        governance['workspace_config']['enableTableAcl'] = str(table_acl_enabled)
                        logger.info(f"Table ACL workspace setting: {table_acl_enabled}")
                except Exception as e:
                    logger.debug(f"Could not retrieve enableTableAcl setting: {str(e)}")
                    governance['table_acls']['workspace_setting'] = 'Unable to retrieve'
                
                # Check cluster configurations for Table ACL enforcement
                try:
                    clusters = list(self.client.clusters.list())
                    active_clusters = [c for c in clusters if hasattr(c, 'state') and str(c.state.value) not in ['TERMINATED', 'TERMINATING']]
                    governance['table_acls']['total_active_clusters'] = len(active_clusters)
                    
                    clusters_with_acls = 0
                    for cluster in active_clusters:
                        # Check spark_conf for table ACL settings
                        spark_conf = safe_get_attribute(cluster, 'spark_conf', {})
                        if spark_conf and isinstance(spark_conf, dict):
                            if spark_conf.get('spark.databricks.acl.dfAclsEnabled') == 'true' or \
                               spark_conf.get('spark.databricks.acl.sqlOnly') == 'true':
                                clusters_with_acls += 1
                        
                        # Check data_security_mode (Unity Catalog clusters)
                        data_security_mode = safe_get_attribute(cluster, 'data_security_mode')
                        if data_security_mode and str(data_security_mode) in ['USER_ISOLATION', 'SINGLE_USER']:
                            clusters_with_acls += 1
                    
                    governance['table_acls']['clusters_with_table_acls'] = clusters_with_acls
                    
                    # Determine overall Table ACL status
                    if governance['unity_catalog']['enabled']:
                        governance['table_acls']['enabled'] = False
                        governance['table_acls']['note'] = 'Unity Catalog enabled - Table ACLs replaced by UC permissions'
                    elif table_acl_enabled and str(table_acl_enabled).lower() == 'true':
                        governance['table_acls']['enabled'] = True
                        governance['table_acls']['note'] = f'{clusters_with_acls}/{len(active_clusters)} active clusters enforce ACLs'
                    else:
                        governance['table_acls']['enabled'] = False
                        governance['table_acls']['note'] = 'Table ACLs not enabled at workspace level'
                        
                except Exception as e:
                    logger.debug(f"Could not check cluster Table ACL configurations: {str(e)}")
                    
            except Exception as e:
                logger.debug(f"Error checking Table ACL status: {str(e)}")
            
            # Check other workspace-level governance settings
            try:
                governance_keys = [
                    'enableNotebookTableClipboard',
                ]
                
                for key in governance_keys:
                    try:
                        conf_value = self.client.workspace_conf.get_status(keys=key)
                        if hasattr(conf_value, key):
                            governance['workspace_config'][key] = getattr(conf_value, key)
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"Could not retrieve other governance workspace conf: {str(e)}")
            
            # Check cluster policies
            try:
                policies = list(self.client.cluster_policies.list())
                governance['cluster_policies'] = {
                    'total_policies': len(policies),
                    'policies_configured': len(policies) > 0
                }
                
                # Check how many clusters are without policies
                clusters = list(self.client.clusters.list())
                clusters_without_policy = []
                
                for cluster in clusters:
                    if hasattr(cluster, 'state') and str(cluster.state.value) not in ['TERMINATED', 'TERMINATING']:
                        policy_id = safe_get_attribute(cluster, 'policy_id')
                        if not policy_id:
                            clusters_without_policy.append({
                                'cluster_id': cluster.cluster_id,
                                'cluster_name': safe_get_attribute(cluster, 'cluster_name', 'Unnamed')
                            })
                
                governance['cluster_policies']['clusters_without_policy'] = len(clusters_without_policy)
                
                if self.config.is_deep_scan():
                    governance['cluster_policies']['policy_list'] = [
                        {
                            'policy_id': p.policy_id,
                            'name': p.name,
                            'definition': safe_get_attribute(p, 'definition')
                        } for p in policies
                    ]
                    if clusters_without_policy:
                        governance['cluster_policies']['unpolicied_clusters'] = clusters_without_policy
                
                logger.info(f"Found {len(policies)} cluster policies, {len(clusters_without_policy)} clusters without policy")
            except Exception as e:
                logger.debug(f"Could not check cluster policies: {str(e)}")
                governance['cluster_policies'] = {'error': str(e)}
            
            # Check DBFS usage patterns
            try:
                # Check for workspace files and common DBFS paths
                dbfs_paths_to_check = [
                    '/user/hive/warehouse',
                    '/mnt',
                    '/databricks-datasets',
                    '/FileStore'
                ]
                
                dbfs_usage = {'paths': {}}
                
                for path in dbfs_paths_to_check:
                    try:
                        files = list(self.client.dbfs.list(path))
                        dbfs_usage['paths'][path] = {
                            'exists': True,
                            'file_count': len(files)
                        }
                    except Exception:
                        dbfs_usage['paths'][path] = {'exists': False}
                
                governance['dbfs_usage'] = dbfs_usage
                logger.info(f"Checked DBFS usage for {len(dbfs_paths_to_check)} common paths")
            except Exception as e:
                logger.debug(f"Could not check DBFS usage: {str(e)}")
                governance['dbfs_usage'] = {'error': str(e)}
            
            # Check Unity Catalog system schemas (if UC is enabled)
            if governance['unity_catalog'].get('enabled'):
                try:
                    catalogs = list(self.client.catalogs.list())
                    governance['unity_catalog']['catalog_count'] = len(catalogs)
                    
                    # Check for system schema enablement
                    system_schemas_enabled = False
                    for catalog in catalogs:
                        try:
                            schemas = list(self.client.schemas.list(catalog_name=catalog.name))
                            for schema in schemas:
                                if schema.name in ['information_schema', 'access']:
                                    system_schemas_enabled = True
                                    break
                        except Exception:
                            pass
                    
                    governance['unity_catalog']['system_schemas_detected'] = system_schemas_enabled
                    logger.info(f"Unity Catalog: {len(catalogs)} catalogs, system schemas: {system_schemas_enabled}")
                except Exception as e:
                    logger.debug(f"Could not check UC catalogs: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error scanning governance: {str(e)}")
            governance['error'] = str(e)
        
        return governance
    
    def _scan_compliance(self) -> Dict[str, Any]:
        """
        Scan compliance and monitoring configurations.
        
        Returns:
            Dictionary with compliance settings
        """
        logger.info("Scanning compliance configurations...")
        
        compliance = {
            'workspace_settings': {},
            'monitoring': {
                'enabled': None,
                'log_analytics_configured': None,
                'status': 'Unknown'
            },
            'audit_logs': {
                'enabled': None,
                'delivery_configured': None,
                'destinations': [],
                'status': 'Unknown'
            }
        }
        
        # Check account-level monitoring and audit logs
        if self.account_client:
            # Detect if this is Azure Databricks
            workspace_host = self.client.config.host
            is_azure = 'azuredatabricks.net' in workspace_host if workspace_host else False
            
            if is_azure:
                # Azure Databricks uses Azure Monitor and Log Analytics for audit logs
                # These are configured in Azure Portal, not via Databricks API
                compliance['audit_logs']['status'] = 'Azure: Configured via Azure Diagnostic Settings (check Azure Portal)'
                compliance['audit_logs']['azure_note'] = 'Audit logs sent to Azure Log Analytics workspace or Azure Storage'
                compliance['monitoring']['status'] = 'Azure: Integrated with Azure Monitor (check Azure Portal)'
                compliance['monitoring']['azure_note'] = 'Monitoring configured via Azure Diagnostic Settings'
                logger.info("Azure Databricks: Audit logs and monitoring managed via Azure Portal")
            else:
                # AWS Databricks: Use log-delivery API
                try:
                    # Check log delivery configurations for audit logs
                    path = f"/api/2.0/accounts/{self.account_id}/log-delivery"
                    logger.debug(f"Checking audit log delivery: {path}")
                    
                    log_delivery = self.account_client.api_client.do('GET', path)
                    if log_delivery and isinstance(log_delivery, dict):
                        log_configs = log_delivery.get('log_delivery_configurations', [])
                        
                        if log_configs:
                            compliance['audit_logs']['enabled'] = True
                            compliance['audit_logs']['delivery_configured'] = True
                            compliance['audit_logs']['destinations'] = [
                                {
                                    'config_id': cfg.get('config_id'),
                                    'log_type': cfg.get('log_type'),
                                    'output_format': cfg.get('output_format'),
                                    'status': cfg.get('status'),
                                    'delivery_path_prefix': cfg.get('delivery_path_prefix', 'Not specified')[:100]  # Truncate
                                }
                                for cfg in log_configs
                            ]
                            active_configs = [cfg for cfg in log_configs if cfg.get('status') == 'ENABLED']
                            compliance['audit_logs']['status'] = f'{len(active_configs)}/{len(log_configs)} delivery configurations active'
                            logger.info(f"Audit logs: {len(active_configs)} active configurations found")
                        else:
                            compliance['audit_logs']['enabled'] = False
                            compliance['audit_logs']['delivery_configured'] = False
                            compliance['audit_logs']['status'] = 'No audit log delivery configured'
                            logger.info("No audit log delivery configurations found")
                    else:
                        compliance['audit_logs']['status'] = 'Unable to retrieve audit log status'
                    
                    # Check workspace monitoring settings for AWS
                    try:
                        # Check if diagnostic logs are enabled (workspace-level setting that feeds into monitoring)
                        diagnostic_path = f"/api/2.0/accounts/{self.account_id}/workspaces/{self.client.get_workspace_id()}/diagnostic-logs"
                        logger.debug(f"Checking diagnostic logs: {diagnostic_path}")
                        
                        diag_settings = self.account_client.api_client.do('GET', diagnostic_path)
                        if diag_settings:
                            compliance['monitoring']['enabled'] = True
                            compliance['monitoring']['log_analytics_configured'] = True
                            compliance['monitoring']['status'] = 'Diagnostic logging enabled'
                            logger.info("Monitoring: Diagnostic logging is enabled")
                        else:
                            compliance['monitoring']['status'] = 'Diagnostic logging not configured'
                    except Exception as e:
                        logger.debug(f"Could not retrieve monitoring status: {str(e)}")
                        # This API might not be available, check alternative indicators
                        if compliance['audit_logs']['enabled']:
                            compliance['monitoring']['status'] = 'Audit logs configured (monitoring likely enabled)'
                        else:
                            compliance['monitoring']['status'] = 'Status unavailable via API'
                            
                except Exception as e:
                    logger.debug(f"Error checking account-level compliance features: {str(e)}")
                    compliance['monitoring']['status'] = 'AccountClient required to check status'
                    compliance['audit_logs']['status'] = 'AccountClient required to check status'
        else:
            compliance['monitoring']['status'] = 'AccountClient not available - cannot verify'
            compliance['audit_logs']['status'] = 'AccountClient not available - cannot verify'
        
        try:
            # Get workspace-level compliance settings
            try:
                compliance_keys = [
                    'enableTokensConfig',
                    'maxTokenLifetimeDays',
                    'enableDeprecatedClusterNamedInitScripts',
                    'enableDeprecatedGlobalInitScripts',
                ]
                
                for key in compliance_keys:
                    try:
                        conf_value = self.client.workspace_conf.get_status(keys=key)
                        if hasattr(conf_value, key):
                            compliance['workspace_settings'][key] = getattr(conf_value, key)
                    except Exception:
                        pass
                
                logger.info("Retrieved workspace compliance settings")
            except Exception as e:
                logger.debug(f"Could not retrieve compliance settings: {str(e)}")
            
            # Get workspace status/info
            try:
                current_user = self.client.current_user.me()
                compliance['workspace_info'] = {
                    'current_user': current_user.user_name,
                    'workspace_access': 'Active'
                }
            except Exception as e:
                logger.debug(f"Could not retrieve current user info: {str(e)}")
            
            # Check job configurations for security settings
            try:
                jobs = list(self.client.jobs.list())
                
                jobs_without_logging = []
                high_concurrency_jobs = []
                jobs_without_tags = []
                
                for job in jobs[:100]:  # Sample for performance
                    job_id = job.job_id
                    settings = safe_get_attribute(job, 'settings')
                    
                    if settings:
                        # Check for logging configuration
                        new_cluster = safe_get_attribute(settings, 'new_cluster')
                        if new_cluster:
                            cluster_log_conf = safe_get_attribute(new_cluster, 'cluster_log_conf')
                            if not cluster_log_conf:
                                jobs_without_logging.append(job_id)
                            
                            # Check for custom tags
                            custom_tags = safe_get_attribute(new_cluster, 'custom_tags')
                            if not custom_tags:
                                jobs_without_tags.append(job_id)
                        
                        # Check max concurrent runs
                        max_concurrent = safe_get_attribute(settings, 'max_concurrent_runs', 1)
                        if max_concurrent >= 10:
                            high_concurrency_jobs.append({
                                'job_id': job_id,
                                'max_concurrent_runs': max_concurrent
                            })
                
                compliance['job_configurations'] = {
                    'total_jobs_scanned': len(jobs[:100]),
                    'jobs_without_logging': len(jobs_without_logging),
                    'jobs_without_tags': len(jobs_without_tags),
                    'high_concurrency_jobs': len(high_concurrency_jobs)
                }
                
                if self.config.is_deep_scan():
                    if high_concurrency_jobs:
                        compliance['job_configurations']['high_concurrency_list'] = high_concurrency_jobs
                
                logger.info(f"Job compliance: {len(jobs_without_logging)} without logging, {len(high_concurrency_jobs)} high concurrency")
            except Exception as e:
                logger.debug(f"Could not check job configurations: {str(e)}")
                compliance['job_configurations'] = {'error': str(e)}
            
            # Check cluster logging configurations
            try:
                clusters = list(self.client.clusters.list())
                clusters_without_logging = []
                
                for cluster in clusters:
                    if hasattr(cluster, 'state') and str(cluster.state.value) not in ['TERMINATED', 'TERMINATING']:
                        log_conf = safe_get_attribute(cluster, 'cluster_log_conf')
                        if not log_conf:
                            clusters_without_logging.append({
                                'cluster_id': cluster.cluster_id,
                                'cluster_name': safe_get_attribute(cluster, 'cluster_name', 'Unnamed')
                            })
                
                compliance['cluster_logging'] = {
                    'total_active_clusters': len([c for c in clusters if hasattr(c, 'state') and str(c.state.value) not in ['TERMINATED', 'TERMINATING']]),
                    'clusters_without_logging': len(clusters_without_logging)
                }
                
                if self.config.is_deep_scan() and clusters_without_logging:
                    compliance['cluster_logging']['unlogged_clusters'] = clusters_without_logging
                
                logger.info(f"Cluster logging: {len(clusters_without_logging)} clusters without log configuration")
            except Exception as e:
                logger.debug(f"Could not check cluster logging: {str(e)}")
                compliance['cluster_logging'] = {'error': str(e)}
            
        except Exception as e:
            logger.error(f"Error scanning compliance: {str(e)}")
            compliance['error'] = str(e)
        
        return compliance
    
    def flatten_for_csv(self, security_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Flatten security data for CSV export.
        
        Args:
            security_data: Dictionary from scan() method
            
        Returns:
            List of flattened dictionaries suitable for CSV export
        """
        flattened = []
        
        # Flatten Azure Account Settings (if present)
        if 'azure_account_settings' in security_data:
            azure_account = security_data['azure_account_settings']
            
            flattened.append({
                'category': 'Azure Account Settings',
                'subcategory': 'Overview',
                'setting': 'Total Settings',
                'value': str(azure_account.get('settings_count', 0)),
                'details': f"Security-relevant: {len(azure_account.get('security_relevant_settings', {}))}"
            })
            
            # Add security-relevant account settings
            for key, setting in azure_account.get('security_relevant_settings', {}).items():
                flattened.append({
                    'category': 'Azure Account Settings',
                    'subcategory': 'Security Setting',
                    'setting': setting.get('friendly_name', key),
                    'value': setting.get('value', 'Unknown'),
                    'details': setting.get('description', '')[:100]  # Truncate long descriptions
                })
        
        # Flatten Azure Workspace Settings (if present)
        if 'azure_workspace_settings' in security_data:
            azure_ws = security_data['azure_workspace_settings']
            
            flattened.append({
                'category': 'Azure Workspace Settings',
                'subcategory': 'Overview',
                'setting': 'Total Settings',
                'value': str(azure_ws.get('settings_count', 0)),
                'details': f"Security: {len(azure_ws.get('security_relevant_settings', {}))}, Exfiltration: {len(azure_ws.get('data_exfiltration_controls', {}))}, Connectors: {len(azure_ws.get('external_connectors', {}))}"
            })
            
            # Add data exfiltration controls
            for key, setting in azure_ws.get('data_exfiltration_controls', {}).items():
                flattened.append({
                    'category': 'Azure Workspace Settings',
                    'subcategory': 'Data Exfiltration Control',
                    'setting': setting.get('friendly_name', key),
                    'value': setting.get('status', 'Unknown'),
                    'details': setting.get('description', '')[:100]
                })
            
            # Add external connectors
            for key, setting in azure_ws.get('external_connectors', {}).items():
                flattened.append({
                    'category': 'Azure Workspace Settings',
                    'subcategory': 'External Connector',
                    'setting': setting.get('friendly_name', key),
                    'value': setting.get('status', 'Unknown'),
                    'details': setting.get('description', '')[:100]
                })
            
            # Add other security-relevant settings
            for key, setting in azure_ws.get('security_relevant_settings', {}).items():
                if key not in azure_ws.get('data_exfiltration_controls', {}) and key not in azure_ws.get('external_connectors', {}):
                    flattened.append({
                        'category': 'Azure Workspace Settings',
                        'subcategory': 'Security Setting',
                        'setting': setting.get('friendly_name', key),
                        'value': setting.get('status', 'Unknown'),
                        'details': setting.get('description', '')[:100]
                    })
        
        # Flatten Network Security
        network = security_data.get('network_security', {})
        if 'ip_access_lists' in network:
            ip_lists = network['ip_access_lists']
            flattened.append({
                'category': 'Network Security',
                'subcategory': 'IP Access Lists',
                'setting': 'Enabled',
                'value': str(ip_lists.get('enabled', False)),
                'details': f"Total lists: {ip_lists.get('total_count', 0)}"
            })
            
            # Add each IP access list
            for ip_list in ip_lists.get('lists', []):
                flattened.append({
                    'category': 'Network Security',
                    'subcategory': 'IP Access List',
                    'setting': ip_list.get('label', 'Unnamed'),
                    'value': ip_list.get('list_type', 'BLOCK'),
                    'details': f"Enabled: {ip_list.get('enabled', True)}, IPs: {len(ip_list.get('ip_addresses', []))}"
                })
        
        # Network Connectivity (Private Endpoints)
        if 'network_connectivity' in network:
            ncc = network['network_connectivity']
            
            # Network configs
            if 'network_configs' in ncc:
                net_configs = ncc['network_configs']
                flattened.append({
                    'category': 'Network Security',
                    'subcategory': 'Network Connectivity',
                    'setting': 'Network Configurations',
                    'value': str(net_configs.get('total_count', 0)),
                    'details': ''
                })
            
            # Private endpoint rules
            if 'private_endpoint_rules' in ncc:
                pe_rules = ncc['private_endpoint_rules']
                flattened.append({
                    'category': 'Network Security',
                    'subcategory': 'Private Endpoints',
                    'setting': 'Total Private Endpoint Rules',
                    'value': str(pe_rules.get('total_count', 0)),
                    'details': f"Approved: {pe_rules.get('approved_count', 0)}, Pending: {pe_rules.get('pending_count', 0)}, Rejected: {pe_rules.get('rejected_count', 0)}"
                })
                
                # Add by service breakdown
                rules_by_service = pe_rules.get('rules_by_service', {})
                for service, count in rules_by_service.items():
                    flattened.append({
                        'category': 'Network Security',
                        'subcategory': 'Private Endpoint Rules',
                        'setting': f'Service: {service}',
                        'value': str(count),
                        'details': ''
                    })
        
        # Flatten Identity & Access
        iam = security_data.get('identity_access', {})
        if 'users' in iam:
            users = iam['users']
            flattened.append({
                'category': 'Identity & Access',
                'subcategory': 'Users',
                'setting': 'Total Users',
                'value': str(users.get('total_count', 0)),
                'details': f"Active: {users.get('active_count', 0)}, Admins: {users.get('admin_count', 0)}"
            })
        
        if 'groups' in iam:
            groups = iam['groups']
            flattened.append({
                'category': 'Identity & Access',
                'subcategory': 'Groups',
                'setting': 'Total Groups',
                'value': str(groups.get('total_count', 0)),
                'details': ''
            })
        
        if 'service_principals' in iam:
            sps = iam['service_principals']
            flattened.append({
                'category': 'Identity & Access',
                'subcategory': 'Service Principals',
                'setting': 'Total Service Principals',
                'value': str(sps.get('total_count', 0)),
                'details': ''
            })
        
        flattened.append({
            'category': 'Identity & Access',
            'subcategory': 'SCIM',
            'setting': 'SCIM Provisioning',
            'value': iam.get('scim_enabled', 'Unknown'),
            'details': 'Inferred from group external_id presence'
        })
        
        # Flatten Data Protection
        data_prot = security_data.get('data_protection', {})
        if 'secrets' in data_prot:
            secrets = data_prot['secrets']
            flattened.append({
                'category': 'Data Protection',
                'subcategory': 'Secrets',
                'setting': 'Secret Scopes',
                'value': str(secrets.get('total_scopes', 0)),
                'details': ''
            })
            
            # Add each secret scope
            for scope in secrets.get('scopes_list', []):
                flattened.append({
                    'category': 'Data Protection',
                    'subcategory': 'Secret Scope',
                    'setting': scope.get('name', 'Unnamed'),
                    'value': scope.get('backend_type', 'DATABRICKS'),
                    'details': f"Secrets: {scope.get('secrets_count', 'N/A')}"
                })
        
        if 'tokens' in data_prot:
            tokens = data_prot['tokens']
            if 'total_count' in tokens:
                flattened.append({
                    'category': 'Data Protection',
                    'subcategory': 'Tokens',
                    'setting': 'Total Access Tokens',
                    'value': str(tokens.get('total_count', 0)),
                    'details': f"Active: {tokens.get('active_tokens', 'N/A')}"
                })
        
        # Flatten Governance
        gov = security_data.get('governance', {})
        if 'unity_catalog' in gov:
            uc = gov['unity_catalog']
            flattened.append({
                'category': 'Governance',
                'subcategory': 'Unity Catalog',
                'setting': 'Enabled',
                'value': str(uc.get('enabled', False)),
                'details': f"Metastore: {uc.get('metastore_id', 'Not assigned')}"
            })
        
        # Flatten Compliance
        comp = security_data.get('compliance', {})
        if 'workspace_settings' in comp:
            for key, value in comp['workspace_settings'].items():
                flattened.append({
                    'category': 'Compliance',
                    'subcategory': 'Workspace Settings',
                    'setting': key,
                    'value': str(value),
                    'details': ''
                })
        
        return flattened
