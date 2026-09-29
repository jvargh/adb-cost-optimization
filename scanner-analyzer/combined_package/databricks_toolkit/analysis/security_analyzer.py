"""
Security Analyzer Module - Integrates with Databricks Security Analysis Tool (SAT)
Analyzes workspace security configurations and provides actionable recommendations.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import os
import shutil
import tempfile
import json
import logging
from typing import Optional, Dict, Any, List, Tuple
warnings.filterwarnings('ignore')

from .storage_utils import StorageReader

# Initialize logger
logger = logging.getLogger(__name__)


class SecurityAnalyzer:
    """
    Security analyzer that integrates with Databricks Security Analysis Tool (SAT).
    Analyzes workspace configurations against security best practices and generates
    comprehensive security reports with prioritized recommendations.
    
    Security Categories Analyzed:
    - Network Security (VPC peering, private links, IP access lists)
    - Identity & Access (SCIM, SSO, workspace access controls)
    - Data Protection (encryption, credential management, secrets)
    - Governance (table ACLs, Unity Catalog, audit logging)
    - Compliance (security profiles, monitoring, policies)
    
    Configuration:
    Security checks are defined in security_checks_metadata.json which can be modified
    without changing code. Each category and check can be enabled/disabled using Y/N flags.
    """
    
    # Legacy structure kept for backward compatibility
    SECURITY_CATEGORIES = {}  # Will be loaded from metadata file
    
    SEVERITY_LEVELS = {
        'HIGH': {'emoji': '', 'score': 10, 'priority': 1},
        'MEDIUM': {'emoji': '', 'score': 5, 'priority': 2},
        'LOW': {'emoji': '', 'score': 2, 'priority': 3},
        'INFO': {'emoji': '', 'score': 0, 'priority': 4}
    }
    
    def __init__(self, discovery_path: str, workspace_id: Optional[str] = None, 
                 output_dir: str = 'results', metadata_file: Optional[str] = None):
        """
        Initialize security analyzer.
        
        Args:
            discovery_path: Path to discovery output directory containing workspace configs
            workspace_id: Optional specific workspace ID to analyze
            output_dir: Output directory for security reports
            metadata_file: Optional path to custom metadata file. If None, uses default.
        """
        self.discovery_path = discovery_path
        self.workspace_id = workspace_id
        self.output_dir = output_dir
        self.reader = StorageReader()
        
        # Load metadata from file
        if metadata_file is None:
            # Use default metadata file in same directory
            metadata_file = os.path.join(os.path.dirname(__file__), 'security_checks_metadata.json')
        
        self.metadata = self._load_metadata(metadata_file)
        self.SECURITY_CATEGORIES = self._convert_metadata_to_legacy_format()
        
        # Analysis results storage
        self.workspace_config = None
        self.security_findings = []
        self.security_score = 0
        self.category_scores = {}
        self.results = {}
    
    def _load_metadata(self, metadata_file: str) -> Dict[str, Any]:
        """Load security checks metadata from JSON file."""
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            print(f"✓ Loaded security checks metadata from: {os.path.basename(metadata_file)}")
            
            # Validate metadata structure
            if 'categories' not in metadata or 'checks' not in metadata:
                raise ValueError("Invalid metadata structure: missing 'categories' or 'checks' keys")
            
            return metadata
            
        except FileNotFoundError:
            print(f"⚠ Warning: Metadata file not found: {metadata_file}")
            print("  Using minimal default configuration")
            # Fallback to minimal default
            return {
                "categories": {
                    "network": {"name": "Network Security", "weight": 0.25, "enabled": "Y"},
                    "identity": {"name": "Identity and Access Management", "weight": 0.25, "enabled": "Y"},
                    "data_protection": {"name": "Data Protection", "weight": 0.20, "enabled": "Y"},
                    "governance": {"name": "Governance and Compliance", "weight": 0.20, "enabled": "Y"},
                    "compliance": {"name": "Security Compliance", "weight": 0.10, "enabled": "Y"}
                },
                "checks": {}
            }
        except Exception as e:
            print(f"⚠ Warning: Error loading metadata: {str(e)}")
            print("  Using minimal default configuration")
            # Fallback to minimal default
            return {
                "categories": {
                    "network": {"name": "Network Security", "weight": 0.25, "enabled": "Y"},
                    "identity": {"name": "Identity and Access Management", "weight": 0.25, "enabled": "Y"},
                    "data_protection": {"name": "Data Protection", "weight": 0.20, "enabled": "Y"},
                    "governance": {"name": "Governance and Compliance", "weight": 0.20, "enabled": "Y"},
                    "compliance": {"name": "Security Compliance", "weight": 0.10, "enabled": "Y"}
                },
                "checks": {}
            }
    
    def _convert_metadata_to_legacy_format(self) -> Dict[str, Any]:
        """Convert metadata to legacy SECURITY_CATEGORIES format for compatibility."""
        legacy_format = {}
        categories = self.metadata.get('categories', {})
        #checks_meta = self.metadata.get('checks', {})
        checks_meta = self.metadata.get('checks', {})
        
        for cat_key, cat_data in categories.items():
            # Get all checks for this category
            cat_checks = [
                check_id for check_id, check_data in checks_meta.items()
                if check_data.get('category') == cat_key
            ]
            
            legacy_format[cat_key] = {
                'name': cat_data.get('name', cat_key.title()),
                'weight': int(cat_data.get('weight', 0) * 100) if cat_data.get('weight', 0) <= 1 else cat_data.get('weight', 0),
                'checks': cat_checks,
                'enabled': cat_data.get('enabled', 'Y')
            }
        
        return legacy_format
    
    def _detect_cloud_type(self) -> str:
        """
        Detect cloud provider based on workspace configuration.
        
        Returns:
            Cloud provider: 'AWS', 'Azure', 'GCP', or 'Unknown'
        """
        # Try to detect from discovery path if it's a file
        if os.path.isfile(self.discovery_path):
            try:
                with open(self.discovery_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Check metadata for workspace URL
                    if 'metadata' in data:
                        workspace_url = data['metadata'].get('workspace_url', '')
                        if 'azuredatabricks.net' in workspace_url:
                            return 'Azure'
                        elif 'cloud.databricks.com' in workspace_url:
                            return 'AWS'
                        elif 'gcp.databricks.com' in workspace_url:
                            return 'GCP'
                    
                    # Check security data for cloud-specific indicators
                    if 'security' in data:
                        security = data['security']
                        # Azure-specific indicators
                        if 'azure_workspace_settings' in security or 'azure_account_settings' in security:
                            return 'Azure'
                        # AWS-specific indicators (VPC peering, etc.)
                        if 'network_security' in security:
                            network = security.get('network_security', {})
                            if 'vpc_peering' in str(network).lower():
                                return 'AWS'
            except Exception as e:
                logger.debug(f"Could not detect cloud type from file: {str(e)}")
        
        # Default to Unknown if detection fails
        return 'Unknown'
    
    def analyze(self, save_csv: bool = True, output_prefix: Optional[str] = None) -> Dict[str, Any]:
        """
        Run comprehensive security analysis.
        
        Args:
            save_csv: Whether to save CSV output files (default: True)
            output_prefix: Optional custom prefix for output CSV files
            
        Returns:
            Dictionary with security analysis results
        """
        print("\n" + "="*80)
        print("SECURITY ANALYSIS - Databricks Workspace Security Assessment")
        print("="*80)
        
        # Step 1: Load workspace configuration
        self._load_workspace_config()
        
        # Step 2: Run security checks by category
        self._analyze_network_security()
        self._analyze_identity_access()
        self._analyze_data_protection()
        self._analyze_governance()
        self._analyze_compliance()
        
        # Step 3: Calculate security scores
        self._calculate_security_score()
        
        # Step 4: Generate recommendations
        self._generate_recommendations()
        
        # Step 5: Print summary
        self._print_summary()
        
        # Step 6: Save to files if requested
        if save_csv:
            output_files = self._save_to_excel(output_prefix)
            self.results['output_files'] = output_files
        
        return self.results
    
    def _load_workspace_config(self):
        """Load workspace configuration from discovery data."""
        print("\n📥 Loading workspace configuration...")
        
        import glob
        
        # Try to load discovery JSON files
        json_files = []
        if os.path.isdir(self.discovery_path):
            json_files = glob.glob(os.path.join(self.discovery_path, '*.json'))
        elif os.path.isfile(self.discovery_path):
            json_files = [self.discovery_path]
        
        config_data = {
            'workspace_id': self.workspace_id or 'unknown',
            'workspace_name': 'workspace_analysis',
            'cloud_type': self._detect_cloud_type(),
            'timestamp': datetime.now().isoformat(),
            'security_data': None,
            'clusters_data': None,
            'unity_catalog_data': None
        }
        
        # Try to load discovery JSON
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Extract workspace metadata
                    if 'metadata' in data:
                        metadata = data['metadata']
                        config_data['workspace_id'] = metadata.get('workspace_id', config_data['workspace_id'])
                        config_data['workspace_url'] = metadata.get('workspace_url', '')
                    
                    # Extract security data from discovery
                    if 'security' in data:
                        config_data['security_data'] = data['security']
                        print(f"  ✓ Loaded security data from discovery")
                    
                    # Extract cluster data for network security analysis
                    if 'clusters' in data:
                        config_data['clusters_data'] = data['clusters']
                        print(f"  ✓ Loaded cluster data")
                    
                    # Extract Unity Catalog data for governance analysis
                    if 'unity_catalog' in data:
                        config_data['unity_catalog_data'] = data['unity_catalog']
                        print(f"  ✓ Loaded Unity Catalog data")
                    
                    break
                    
            except Exception as e:
                logger.debug(f"Could not load JSON file {json_file}: {str(e)}")
                continue
        
        self.workspace_config = config_data
        print(f"✓ Loaded configuration for workspace: {config_data['workspace_id']}")
        print(f"  Cloud Type: {config_data['cloud_type']}")
        print(f"  Security data available: {config_data['security_data'] is not None}")
    
    def _analyze_network_security(self):
        """Analyze network security configuration."""
        print("\nAnalyzing Network Security...")
        
        category = 'network'
        categories = self.metadata.get('categories', {})
        
        # Check if network security analysis is enabled
        if categories.get('network', {}).get('enabled', 'Y').upper() != 'Y':
            print("  ⊗ Skipping Network Security analysis (disabled in metadata)")
            return
        
        # Get network security data
        network_data = {}
        if self.workspace_config and self.workspace_config.get('security_data'):
            network_data = self.workspace_config['security_data'].get('network_security', {})
        
        checks_meta = self.metadata.get('checks', {})        
        # Check NET-001: IP Access Lists
        check_meta = checks_meta.get('SEC-NET-001', {})
        if check_meta.get('enabled', 'Y').upper() == 'Y':
            ip_lists = network_data.get('ip_access_lists', {})
            ip_count = ip_lists.get('total_count', 0)
            
            if ip_count > 0:
                status = 'PASS'
                current_value = f'{ip_count} IP access list(s) configured'
                severity = 'LOW'
                recommendation = f'IP access lists are configured. Review the {ip_count} configured list(s) to ensure they cover all required IP ranges.'
            else:
                status = 'FAIL'
                current_value = 'No IP access lists configured'
                severity = check_meta.get('severity', 'MEDIUM')
                recommendation = check_meta.get('recommendation', 'Configure IP access lists to restrict workspace access to known IP ranges only.')
            
            self._add_finding(
                category=category,
                check_id=check_meta.get('check_id', 'SEC-NET-001'),
                check_name=check_meta.get('check_name', 'IP Access List Configuration'),
                severity=severity,
                status=status,
                current_value=current_value,
                expected_value=check_meta.get('expected_value', 'IP allowlist configured'),
                recommendation=recommendation,
                doc_url=check_meta.get('doc_url', 'https://docs.databricks.com/security/network/ip-access-list.html')
            )
        
        # Check NET-002: VPC Peering/Private Access
        check_meta = checks_meta.get('SEC-NET-002', {})
        if check_meta.get('enabled', 'Y').upper() == 'Y':
            private_access = network_data.get('private_access', {})
            enabled = private_access.get('enabled', False)
            
            if enabled:
                status = 'PASS'
                current_value = private_access.get('details', 'VPC peering/Private Access configured')
                severity = 'LOW'
                recommendation = 'Private access is configured. Continue monitoring VPC peering connections for security.'
            else:
                status = 'FAIL'
                current_value = private_access.get('details', 'No VPC peering configured')
                severity = check_meta.get('severity', 'MEDIUM')
                recommendation = check_meta.get('recommendation', 'Configure VPC peering to enable secure, private network connections.')
            
            self._add_finding(
                category=category,
                check_id=check_meta.get('check_id', 'SEC-NET-002'),
                check_name=check_meta.get('check_name', 'VPC Peering Configuration'),
                severity=severity,
                status=status,
                current_value=current_value,
                expected_value=check_meta.get('expected_value', 'VPC peering configured'),
                recommendation=recommendation,
                doc_url=check_meta.get('doc_url', 'https://docs.databricks.com/security/network/classic/vpc-peering.html')
            )
        
        # Check NET-003: Private Link
        check_meta = checks_meta.get('SEC-NET-003', {})
        if check_meta.get('enabled', 'Y').upper() == 'Y':
            private_link = network_data.get('private_link', {})
            enabled = private_link.get('enabled', False)
            
            if enabled:
                status = 'PASS'
                current_value = private_link.get('details', 'Private Link configured')
                severity = 'LOW'
                recommendation = 'Private Link is configured. Ensure it is properly secured and monitored.'
            else:
                status = 'FAIL'
                current_value = private_link.get('details', 'Private Link not configured')
                severity = check_meta.get('severity', 'HIGH')
                recommendation = check_meta.get('recommendation', 'Enable Private Link for secure access to Databricks workspace.')
            
            self._add_finding(
                category=category,
                check_id=check_meta.get('check_id', 'SEC-NET-003'),
                check_name=check_meta.get('check_name', 'Private Link/Service Endpoint'),
                severity=severity,
                status=status,
                current_value=current_value,
                expected_value=check_meta.get('expected_value', 'Private Link enabled'),
                recommendation=recommendation,
                doc_url=check_meta.get('doc_url', 'https://docs.databricks.com/security/network/classic/private-link.html')
            )
        
        # Check NET-004: Secure Cluster Connectivity
        check_meta = checks_meta.get('SEC-NET-004', {})
        if check_meta.get('enabled', 'Y').upper() == 'Y':
            cluster_conn = network_data.get('cluster_connectivity', {})
        
        if cluster_conn:
            total_active = cluster_conn.get('total_active_clusters', 0)
            scc_enabled = cluster_conn.get('secure_connectivity_enabled', False)
            details = cluster_conn.get('details', 'Unknown')
            
            if total_active > 0:
                if scc_enabled:
                    status = 'PASS'
                    current_value = f'Enabled ({details})'
                    severity = 'LOW'
                    recommendation = 'Secure Cluster Connectivity is enabled. Clusters do not have public IPs.'
                else:
                    status = 'FAIL'
                    current_value = f'Not enabled - {details}'
                    severity = 'HIGH'
                    recommendation = 'Enable Secure Cluster Connectivity to prevent clusters from having public IPs.'
            else:
                status = 'INFO'
                current_value = 'No active clusters to evaluate'
                severity = 'LOW'
                recommendation = 'Ensure Secure Cluster Connectivity is enabled when creating new clusters.'
        else:
            # Fallback to cluster data analysis
            clusters_data = self.workspace_config.get('clusters_data', {})
            if clusters_data and isinstance(clusters_data, dict):
                clusters_list = clusters_data.get('clusters', [])
                total_clusters = len(clusters_list)
                
                if total_clusters > 0:
                    status = 'NEEDS_REVIEW'
                    current_value = f'Analyzed {total_clusters} cluster(s) - Verify in cluster network configs'
                    severity = 'MEDIUM'
                    recommendation = 'Verify that Secure Cluster Connectivity is enabled. Check cluster configurations.'
                else:
                    status = 'NEEDS_REVIEW'
                    current_value = 'No cluster data available'
                    severity = 'MEDIUM'
                    recommendation = 'Enable Secure Cluster Connectivity to prevent clusters from having public IPs.'
            else:
                status = 'NEEDS_REVIEW'
                current_value = 'Unknown'
                severity = 'MEDIUM'
                recommendation = 'Enable Secure Cluster Connectivity to prevent clusters from having public IPs.'
        
            self._add_finding(
                category=category,
                check_id=check_meta.get('check_id', 'SEC-NET-004'),
                check_name=check_meta.get('check_name', 'Secure Cluster Connectivity'),
                severity=severity,
                status=status,
                current_value=current_value,
                expected_value=check_meta.get('expected_value', 'No public IPs on cluster nodes'),
                recommendation=recommendation,
                doc_url=check_meta.get('doc_url', 'https://docs.databricks.com/security/network/classic/secure-cluster-connectivity.html')
            )
        
        # Check NET-005: Private Endpoint Configuration
        check_meta = checks_meta.get('SEC-NET-005', {})
        if check_meta.get('enabled', 'Y').upper() == 'Y':
            ncc_data = network_data.get('network_connectivity', {})
            pe_rules = ncc_data.get('private_endpoint_rules', {})
            total_pe_rules = pe_rules.get('total_count', 0)
            approved = pe_rules.get('approved_count', 0)
            pending = pe_rules.get('pending_count', 0)
            rejected = pe_rules.get('rejected_count', 0)
            deactivated = pe_rules.get('deactivated_count', 0)
            
            if total_pe_rules > 0 and approved == total_pe_rules:
                status = 'PASS'
                severity = 'LOW'
                current_value = f'{approved} private endpoint rules configured and approved'
                recommendation = 'Private endpoint configuration is healthy. Continue monitoring connection states.'
            elif total_pe_rules > 0 and pending > 0:
                status = 'FAIL'
                severity = 'HIGH'
                current_value = f'{pending} private endpoint rules pending approval (total: {total_pe_rules})'
                recommendation = f'Approve {pending} pending private endpoint connections immediately to ensure secure connectivity.'
            elif total_pe_rules > 0 and rejected > 0:
                status = 'FAIL'
                severity = 'HIGH'
                current_value = f'{rejected} private endpoint rules rejected (total: {total_pe_rules})'
                recommendation = 'Review and fix rejected private endpoint connections. Check resource permissions and network configs.'
            elif total_pe_rules > 0 and deactivated > 0:
                status = 'FAIL'
                severity = 'MEDIUM'
                current_value = f'{deactivated} private endpoint rules deactivated (total: {total_pe_rules})'
                recommendation = f'Review and reactivate {deactivated} deactivated private endpoint rules to maintain secure connectivity.'
            else:
                status = 'NEEDS_REVIEW'
                severity = 'MEDIUM'
                current_value = 'No private endpoint rules found'
                recommendation = 'Configure private endpoint rules for Azure Storage, SQL, and other services to prevent data exfiltration via public internet.'
            
            self._add_finding(
                category=category,
                check_id=check_meta.get('check_id', 'SEC-NET-005'),
                check_name=check_meta.get('check_name', 'Private Endpoint Configuration'),
                severity=severity,
                status=status,
                current_value=current_value,
                expected_value=check_meta.get('expected_value', 'Private endpoints configured and approved'),
                recommendation=recommendation,
                doc_url=check_meta.get('doc_url', 'https://docs.databricks.com/security/network/classic/private-link.html')
            )
        print(f"  ✓ Completed {len([f for f in self.security_findings if f['category'] == category])} network security checks")
    
    def _analyze_identity_access(self):
        """Analyze identity and access management."""
        print("\nAnalyzing Identity & Access Management...")
        
        category = 'identity'
        checks_meta = self.metadata.get('checks', {})
        
        # Check 1: SSO
        sso_status = 'Unknown'
        if self.workspace_config and self.workspace_config.get('security_data'):
            identity_access = self.workspace_config['security_data'].get('identity_access', {})
            sso_enabled = identity_access.get('sso_enabled', 'Unknown')
            sso_status = sso_enabled if sso_enabled != 'Unknown' else 'Unknown'
        
        self._add_finding(
            category=category,
            check_id='SEC-IAM-001',
            check_name='Single Sign-On (SSO)',
            severity='HIGH',
            status='NEEDS_REVIEW',
            current_value=sso_status,
            expected_value='SSO enabled with corporate IdP',
            recommendation='Enable SSO integration with your corporate identity provider (SAML 2.0) for centralized authentication.',
            doc_url='https://docs.databricks.com/security/auth/sso.html'
        )
        
        # Check 2: SCIM Provisioning
        scim_status = 'Unknown'
        if self.workspace_config and self.workspace_config.get('security_data'):
            identity_access = self.workspace_config['security_data'].get('identity_access', {})
            scim_enabled = identity_access.get('scim_enabled', 'Unknown')
            scim_status = scim_enabled if scim_enabled != 'Unknown' else 'Unknown'
        
        self._add_finding(
            category=category,
            check_id='SEC-IAM-002',
            check_name='SCIM User Provisioning',
            severity='HIGH',
            status='NEEDS_REVIEW',
            current_value=scim_status,
            expected_value='SCIM provisioning enabled',
            recommendation='Enable SCIM provisioning to automate user and group management from your IdP.',
            doc_url='https://docs.databricks.com/security/auth/scim/index.html'
        )
        
        # Check 3: MFA
        mfa_status = 'Not configured'
        if self.workspace_config and self.workspace_config.get('security_data'):
            identity_access = self.workspace_config['security_data'].get('identity_access', {})
            mfa_enabled = identity_access.get('mfa_enabled', None)
            if mfa_enabled is not None:
                mfa_status = 'Enabled' if mfa_enabled else 'Disabled'
        
        self._add_finding(
            category=category,
            check_id='SEC-IAM-003',
            check_name='Multi-Factor Authentication',
            severity='HIGH',
            status='NEEDS_REVIEW',
            current_value=mfa_status,
            expected_value='MFA enforced for all users',
            recommendation='Enforce MFA through your IdP for all workspace users, especially admins.',
            doc_url='https://docs.databricks.com/security/auth/index.html'
        )
        
        # Check 4: Admin Access
        status = 'NEEDS_REVIEW'
        severity = 'MEDIUM'
        current_value = 'Unknown'
        
        if self.workspace_config and self.workspace_config.get('security_data'):
            identity_access = self.workspace_config['security_data'].get('identity_access', {})
            users_data = identity_access.get('users', {})
            
            if 'admin_count' in users_data:
                admin_count = users_data['admin_count']
                total_users = users_data.get('total_count', 'Unknown')
                
                # Calculate percentage
                if isinstance(admin_count, int) and isinstance(total_users, int) and total_users > 0:
                    admin_percentage = round((admin_count / total_users) * 100, 1)
                    current_value = f"{admin_count} admins ({admin_percentage}% of {total_users} total)"
                    
                    # Determine status based on percentage
                    if admin_percentage < 5:
                        status = 'PASS'
                        severity = 'LOW'
                    elif admin_percentage <= 15:
                        status = 'NEEDS_REVIEW'
                        severity = 'MEDIUM'
                    else:
                        status = 'FAIL'
                        severity = 'HIGH'
                else:
                    current_value = f"{admin_count} admins"
            else:
                # Try counting users with is_admin flag
                users_list = users_data.get('users_list', [])
                admin_users = [u for u in users_list if u.get('is_admin') or 'admins' in u.get('groups', [])]
                if admin_users:
                    admin_count = len(admin_users)
                    total_users = len(users_list)
                    admin_percentage = round((admin_count / total_users) * 100, 1) if total_users > 0 else 0
                    current_value = f"{admin_count} admins ({admin_percentage}% of {total_users} total)"
                    
                    # Determine status based on percentage
                    if admin_percentage < 5:
                        status = 'PASS'
                        severity = 'LOW'
                    elif admin_percentage <= 15:
                        status = 'NEEDS_REVIEW'
                        severity = 'MEDIUM'
                    else:
                        status = 'FAIL'
                        severity = 'HIGH'
                else:
                    current_value = 'Unknown'
        else:
            current_value = 'Unknown'
        
        self._add_finding(
            category=category,
            check_id='SEC-IAM-004',
            check_name='Admin User Count',
            severity=severity,
            status=status,
            current_value=current_value,
            expected_value='Minimal admin users (<5% of total)',
            recommendation='Review and minimize the number of workspace admin users. Follow principle of least privilege.',
            doc_url='https://docs.databricks.com/security/auth/users-groups/index.html'
        )
        
        print(f"  ✓ Completed {len([f for f in self.security_findings if f['category'] == category])} identity & access checks")
    
    def _analyze_data_protection(self):
        """Analyze data protection configuration."""
        print("\nAnalyzing Data Protection...")
        
        category = 'data_protection'
        
        # Check 1: Storage Encryption
        encryption_info = 'Unknown'
        status = 'NEEDS_REVIEW'
        severity = 'HIGH'
        
        if self.workspace_config and self.workspace_config.get('security_data'):
            data_protection = self.workspace_config['security_data'].get('data_protection', {})
            cluster_enc = data_protection.get('cluster_encryption', {})
            
            if 'encryption_enabled' in cluster_enc:
                enc_enabled = cluster_enc.get('encryption_enabled', False)
                encrypted_count = cluster_enc.get('encrypted_count', 0)
                total_clusters = cluster_enc.get('total_clusters', 0)
                unencrypted_active = cluster_enc.get('unencrypted_active', 0)
                
                if enc_enabled and encrypted_count == total_clusters:
                    encryption_info = f"Enabled: All {total_clusters} clusters encrypted"
                    status = 'PASS'
                    severity = 'LOW'
                elif enc_enabled:
                    encryption_info = f"Partial: {encrypted_count}/{total_clusters} clusters encrypted"
                    status = 'NEEDS_REVIEW'
                    severity = 'MEDIUM'
                else:
                    encryption_info = f"Not enabled ({unencrypted_active} active unencrypted cluster(s))"
                    status = 'FAIL'
                    severity = 'HIGH'
            
            # Also check encryption keys
            enc_keys = data_protection.get('encryption_keys', {})
            keys_count = enc_keys.get('total_count', 0)
            if keys_count > 0:
                managed_keys = enc_keys.get('keys_by_use_case', {}).get('managed_services', 0)
                storage_keys = enc_keys.get('keys_by_use_case', {}).get('storage', 0)
                encryption_info += f" | CMK keys: {managed_keys} managed services, {storage_keys} storage"
                if managed_keys > 0 or storage_keys > 0:
                    if status == 'FAIL':
                        status = 'NEEDS_REVIEW'
                        severity = 'MEDIUM'
        
        self._add_finding(
            category=category,
            check_id='SEC-DATA-001',
            check_name='Object Storage Encryption',
            severity=severity,
            status=status,
            current_value=encryption_info,
            expected_value='Storage encrypted with CMK',
            recommendation='Enable encryption for DBFS root bucket/container using customer-managed keys (CMK).',
            doc_url='https://docs.databricks.com/security/keys/customer-managed-keys.html'
        )
        
        # Check 2: Secrets Management
        secrets_info = 'Unknown'
        status = 'NEEDS_REVIEW'
        severity = 'HIGH'
        
        if self.workspace_config and self.workspace_config.get('security_data'):
            data_protection = self.workspace_config['security_data'].get('data_protection', {})
            secrets_data = data_protection.get('secrets', {})
            total_scopes = secrets_data.get('total_scopes', 0)
            scopes_list = secrets_data.get('scopes_list', [])
            
            if total_scopes > 0:
                databricks_scopes = sum(1 for s in scopes_list if s.get('backend_type') == 'DATABRICKS')
                external_scopes = sum(1 for s in scopes_list if s.get('backend_type') in ['AZURE_KEYVAULT', 'AWS_SECRETS_MANAGER'])
                secrets_info = f"{total_scopes} secret scope(s): {databricks_scopes} Databricks-backed, {external_scopes} external"
                
                # Determine status
                if external_scopes > 0:
                    status = 'PASS'
                    severity = 'LOW'
                elif databricks_scopes > 0:
                    status = 'NEEDS_REVIEW'
                    severity = 'MEDIUM'
            else:
                secrets_info = 'No secret scopes configured'
                status = 'FAIL'
                severity = 'HIGH'
        
        self._add_finding(
            category=category,
            check_id='SEC-DATA-002',
            check_name='Secrets Management',
            severity=severity,
            status=status,
            current_value=secrets_info,
            expected_value='Secrets in backed secret scopes',
            recommendation='Store all credentials in Databricks-backed or external secret scopes (Azure Key Vault, AWS Secrets Manager).',
            doc_url='https://docs.databricks.com/security/secrets/index.html'
        )
        
        # Check 3: Credential Passthrough
        passthrough_status = 'Not configured'
        if self.workspace_config and self.workspace_config.get('security_data'):
            data_protection = self.workspace_config['security_data'].get('data_protection', {})
            passthrough_enabled = data_protection.get('credential_passthrough_enabled', None)
            if passthrough_enabled is not None:
                passthrough_status = 'Enabled' if passthrough_enabled else 'Disabled'
        
        self._add_finding(
            category=category,
            check_id='SEC-DATA-003',
            check_name='Credential Passthrough',
            severity='MEDIUM',
            status='NEEDS_REVIEW',
            current_value=passthrough_status,
            expected_value='Credential passthrough enabled',
            recommendation='Enable Azure AD credential passthrough or AWS IAM passthrough for data access.',
            doc_url='https://docs.databricks.com/security/credential-passthrough/index.html'
        )
        
        # Check SEC-DATA-004: Notebook Results in Customer-Managed Storage
        checks_meta = self.metadata.get('checks', {})
        check_meta = checks_meta.get('SEC-DATA-004', {})
        if check_meta.get('enabled', 'Y').upper() == 'Y':
            notebook_results = data_protection.get('notebook_results_storage', {})
            customer_managed = notebook_results.get('customer_managed_storage', False)
            config_status = notebook_results.get('configuration_status', 'Unknown')
            storage_configured = notebook_results.get('storage_configured', False)
            
            if customer_managed and storage_configured:
                status = 'PASS'
                severity = 'LOW'
                current_value = f'Customer-managed storage configured ({config_status})'
                recommendation = 'Notebook results are stored in customer-managed storage. Continue to monitor and maintain this configuration.'
            elif config_status == 'Default (Databricks-managed)':
                status = 'FAIL'
                severity = check_meta.get('severity', 'MEDIUM')
                current_value = 'Using Databricks-managed storage (default)'
                recommendation = check_meta.get('recommendation', 'Configure notebook results to be stored in your customer-managed storage account for better data control and compliance.')
            else:
                status = 'NEEDS_REVIEW'
                severity = check_meta.get('severity', 'MEDIUM')
                current_value = f'{config_status}'
                note = notebook_results.get('note', '')
                recommendation = f"{check_meta.get('recommendation', 'Configure notebook results storage.')} {note}".strip()
            
            self._add_finding(
                category=category,
                check_id=check_meta.get('check_id', 'SEC-DATA-004'),
                check_name=check_meta.get('check_name', 'Notebook Results in Customer-Managed Storage'),
                severity=severity,
                status=status,
                current_value=current_value,
                expected_value=check_meta.get('expected_value', 'Customer-managed storage configured'),
                recommendation=recommendation,
                doc_url=check_meta.get('doc_url', 'https://learn.microsoft.com/en-gb/azure/databricks/admin/workspace-settings/notebook-results')
            )
        
        print(f"  ✓ Completed {len([f for f in self.security_findings if f['category'] == category])} data protection checks")
    
    def _analyze_governance(self):
        """Analyze governance and compliance controls."""
        print("\nAnalyzing Governance & Compliance...")
        
        category = 'governance'
        checks_meta = self.metadata.get('checks', {})
        
        # Check 1: Table Access Control
        table_acl_status = 'Not configured'
        if self.workspace_config and self.workspace_config.get('security_data'):
            governance = self.workspace_config['security_data'].get('governance', {})
            table_acls_enabled = governance.get('table_acls_enabled', None)
            if table_acls_enabled is not None:
                table_acl_status = 'Enabled' if table_acls_enabled else 'Disabled'
        
        self._add_finding(
            category=category,
            check_id='SEC-GOV-001',
            check_name='Table Access Control',
            severity='HIGH',
            status='NEEDS_REVIEW',
            current_value=table_acl_status,
            expected_value='Table ACLs enabled',
            recommendation='Enable Table Access Control to enforce SQL-based permissions on tables and views.',
            doc_url='https://docs.databricks.com/security/auth/table-acls/index.html'
        )
        
        # Check 2: Unity Catalog
        uc_status = 'Unknown'
        status = 'NEEDS_REVIEW'
        severity = 'HIGH'
        
        if self.workspace_config and self.workspace_config.get('security_data'):
            governance = self.workspace_config['security_data'].get('governance', {})
            uc_data = governance.get('unity_catalog', {})
            
            if 'enabled' in uc_data:
                uc_enabled = uc_data.get('enabled', False)
                metastore_assigned = uc_data.get('metastore_assigned', False)
                catalog_count = uc_data.get('catalog_count', 0)
                
                if uc_enabled and metastore_assigned:
                    uc_status = f"Enabled with metastore ({catalog_count} catalog(s))"
                    status = 'PASS'
                    severity = 'LOW'
                elif uc_enabled:
                    uc_status = "Enabled but no metastore assigned"
                    status = 'NEEDS_REVIEW'
                    severity = 'MEDIUM'
                else:
                    uc_status = "Not enabled"
                    status = 'FAIL'
                    severity = 'HIGH'
        
        self._add_finding(
            category=category,
            check_id='SEC-GOV-002',
            check_name='Unity Catalog Adoption',
            severity=severity,
            status=status,
            current_value=uc_status,
            expected_value='Unity Catalog enabled',
            recommendation='Migrate to Unity Catalog for unified governance across all workspaces and clouds.',
            doc_url='https://docs.databricks.com/data-governance/unity-catalog/index.html'
        )
        
        # Check 3: Audit Logging
        audit_log_status = 'Not configured'
        if self.workspace_config and self.workspace_config.get('security_data'):
            governance = self.workspace_config['security_data'].get('governance', {})
            audit_logs = governance.get('audit_logs', {})
            if audit_logs.get('enabled'):
                delivery_status = audit_logs.get('delivery_status', 'Unknown')
                audit_log_status = f"Enabled - {delivery_status}"
            else:
                audit_log_status = 'Disabled'
        
        self._add_finding(
            category=category,
            check_id='SEC-GOV-003',
            check_name='Audit Logging',
            severity='HIGH',
            status='NEEDS_REVIEW',
            current_value=audit_log_status,
            expected_value='Audit logs delivered to external storage',
            recommendation='Configure audit log delivery to external storage (S3/ADLS) for compliance and security monitoring.',
            doc_url='https://docs.databricks.com/administration-guide/account-settings/audit-logs.html'
        )
        
        # Check 4: Workspace Isolation
        isolation_status = 'Not configured'
        if self.workspace_config and self.workspace_config.get('security_data'):
            governance = self.workspace_config['security_data'].get('governance', {})
            uc_data = governance.get('unity_catalog', {})
            if uc_data.get('enabled'):
                catalog_count = uc_data.get('catalog_count', 0)
                isolation_status = f"{catalog_count} catalog(s) - review isolation"
            else:
                isolation_status = 'Unity Catalog not enabled'
        
        self._add_finding(
            category=category,
            check_id='SEC-GOV-004',
            check_name='Workspace Catalog Isolation',
            severity='MEDIUM',
            status='NEEDS_REVIEW',
            current_value=isolation_status,
            expected_value='Catalog-level isolation configured',
            recommendation='Implement catalog-level isolation in Unity Catalog to separate sensitive data by environment.',
            doc_url='https://docs.databricks.com/data-governance/unity-catalog/manage-privileges/index.html'
        )
        
        print(f"  ✓ Completed {len([f for f in self.security_findings if f['category'] == category])} governance checks")
    
    def _analyze_compliance(self):
        """Analyze compliance and monitoring configuration."""
        print("\nAnalyzing Compliance & Monitoring...")
        
        category = 'compliance'
        checks_meta = self.metadata.get('checks', {})
        
        # Check 1: Compliance Security Profile
        security_profile_status = 'Not configured'
        if self.workspace_config and self.workspace_config.get('security_data'):
            compliance = self.workspace_config['security_data'].get('compliance', {})
            security_profile = compliance.get('security_profile', None)
            if security_profile is not None:
                security_profile_status = security_profile if security_profile else 'Standard'
        
        self._add_finding(
            category=category,
            check_id='SEC-COMP-001',
            check_name='Compliance Security Profile',
            severity='MEDIUM',
            status='NEEDS_REVIEW',
            current_value=security_profile_status,
            expected_value='Enhanced security profile enabled',
            recommendation='Enable compliance security profile for workspaces handling regulated data.',
            doc_url='https://docs.databricks.com/security/privacy/security-profile.html'
        )
        
        # Check 2: Enhanced Security Monitoring
        esm_status = 'Not configured'
        if self.workspace_config and self.workspace_config.get('security_data'):
            compliance = self.workspace_config['security_data'].get('compliance', {})
            esm_enabled = compliance.get('enhanced_security_monitoring', None)
            if esm_enabled is not None:
                esm_status = 'Enabled' if esm_enabled else 'Disabled'
        
        self._add_finding(
            category=category,
            check_id='SEC-COMP-002',
            check_name='Enhanced Security Monitoring',
            severity='MEDIUM',
            status='NEEDS_REVIEW',
            current_value=esm_status,
            expected_value='ESM enabled',
            recommendation='Enable Enhanced Security Monitoring for advanced threat detection.',
            doc_url='https://docs.databricks.com/security/privacy/esm.html'
        )
        
        # Check 3: Security Analysis Tool
        self._add_finding(
            category=category,
            check_id='SEC-COMP-003',
            check_name='Security Analysis Tool Deployment',
            severity='LOW',
            status='RECOMMENDATION',
            current_value='Manual verification required',
            expected_value='SAT deployed and scheduled',
            recommendation='Deploy and schedule Databricks Security Analysis Tool (SAT) for continuous security monitoring.',
            doc_url='https://github.com/databricks-industry-solutions/security-analysis-tool'
        )
        
        # Check 4: Regular Security Scans
        self._add_finding(
            category=category,
            check_id='SEC-COMP-004',
            check_name='Regular Security Scanning',
            severity='LOW',
            status='RECOMMENDATION',
            current_value='Manual verification required',
            expected_value='Weekly security scans',
            recommendation='Schedule SAT to run at least weekly for proactive security posture monitoring.',
            doc_url='https://databricks-industry-solutions.github.io/security-analysis-tool/'
        )
        
        print(f"  ✓ Completed {len([f for f in self.security_findings if f['category'] == category])} compliance checks")
    
    def _add_finding(self, category: str, check_id: str, check_name: str, 
                     severity: str, status: str, current_value: str, 
                     expected_value: str, recommendation: str, doc_url: str):
        """Add a security finding to results."""
        finding = {
            'category': category,
            'category_name': self.SECURITY_CATEGORIES[category]['name'],
            'check_id': check_id,
            'check_name': check_name,
            'severity': severity,
            'severity_emoji': self.SEVERITY_LEVELS[severity]['emoji'],
            'severity_score': self.SEVERITY_LEVELS[severity]['score'],
            'status': status,
            'current_value': current_value,
            'expected_value': expected_value,
            'recommendation': recommendation,
            'doc_url': doc_url,
            'timestamp': datetime.now().isoformat()
        }
        self.security_findings.append(finding)
    
    def _calculate_security_score(self):
        """Calculate overall security score and category breakdowns."""
        print("\n📊 Calculating Security Scores...")
        
        # Calculate score per category
        for cat_key, cat_info in self.SECURITY_CATEGORIES.items():
            cat_findings = [f for f in self.security_findings if f['category'] == cat_key]
            
            if not cat_findings:
                self.category_scores[cat_key] = {
                    'name': cat_info['name'],
                    'score': 0,
                    'max_score': 0,
                    'percentage': 0,
                    'findings_count': 0
                }
                continue
            
            # Score: Higher severity issues reduce score more
            total_possible = len(cat_findings) * 10
            deductions = sum(f['severity_score'] for f in cat_findings 
                           if f['status'] != 'PASS')
            category_score = max(0, total_possible - deductions)
            percentage = (category_score / total_possible * 100) if total_possible > 0 else 0
            
            self.category_scores[cat_key] = {
                'name': cat_info['name'],
                'score': category_score,
                'max_score': total_possible,
                'percentage': percentage,
                'findings_count': len(cat_findings),
                'high_severity': len([f for f in cat_findings if f['severity'] == 'HIGH']),
                'medium_severity': len([f for f in cat_findings if f['severity'] == 'MEDIUM']),
                'low_severity': len([f for f in cat_findings if f['severity'] == 'LOW'])
            }
        
        # Calculate weighted overall score
        total_score = 0
        total_weight = 0
        
        for cat_key, cat_info in self.SECURITY_CATEGORIES.items():
            if cat_key in self.category_scores:
                cat_score = self.category_scores[cat_key]
                weighted_score = cat_score['percentage'] * (cat_info['weight'] / 100)
                total_score += weighted_score
                total_weight += cat_info['weight']
        
        self.security_score = round(total_score, 1) if total_weight > 0 else 0
        
        print(f"  ✓ Overall Security Score: {self.security_score}/100")
    
    def _generate_recommendations(self):
        """Generate prioritized recommendations."""
        print("\n🎯 Generating Prioritized Recommendations...")
        
        # Sort findings by severity and category
        priority_findings = sorted(
            self.security_findings,
            key=lambda x: (
                self.SEVERITY_LEVELS[x['severity']]['priority'],
                self.SECURITY_CATEGORIES[x['category']]['weight']
            )
        )
        
        # Group into action plan
        high_priority = [f for f in priority_findings if f['severity'] == 'HIGH']
        medium_priority = [f for f in priority_findings if f['severity'] == 'MEDIUM']
        low_priority = [f for f in priority_findings if f['severity'] == 'LOW']
        
        self.results = {
            'workspace_id': self.workspace_config['workspace_id'],
            'analysis_timestamp': datetime.now().isoformat(),
            'security_score': self.security_score,
            'grade': self._get_security_grade(self.security_score),
            'category_scores': self.category_scores,
            'total_findings': len(self.security_findings),
            'high_severity_count': len(high_priority),
            'medium_severity_count': len(medium_priority),
            'low_severity_count': len(low_priority),
            'findings': self.security_findings,
            'high_priority_actions': high_priority[:5],  # Top 5
            'medium_priority_actions': medium_priority[:5],
            'low_priority_actions': low_priority[:3]
        }
        
        print(f"  ✓ Generated {len(self.security_findings)} findings")
        print(f"  🔴 High Priority: {len(high_priority)}")
        print(f"  🟡 Medium Priority: {len(medium_priority)}")
        print(f"  🟢 Low Priority: {len(low_priority)}")
    
    def _get_security_grade(self, score: float) -> str:
        """Convert score to letter grade."""
        if score >= 90:
            return 'A (Excellent)'
        elif score >= 80:
            return 'B (Good)'
        elif score >= 70:
            return 'C (Fair)'
        elif score >= 60:
            return 'D (Poor)'
        else:
            return 'F (Critical)'
    
    def _print_summary(self):
        """Print analysis summary to console."""
        print("\n" + "="*80)
        print("SECURITY ANALYSIS SUMMARY")
        print("="*80)
        
        print(f"\n📋 Workspace: {self.workspace_config['workspace_id']}")
        print(f"🏆 Overall Security Score: {self.security_score}/100 - Grade: {self.results['grade']}")
        
        print("\n📊 Category Breakdown:")
        for cat_key, cat_score in self.category_scores.items():
            print(f"  {cat_score['name']}: {cat_score['percentage']:.1f}% "
                  f"({cat_score['high_severity']} high, {cat_score['medium_severity']} medium, "
                  f"{cat_score['low_severity']} low)")
        
        print(f"\n⚠️  Total Findings: {self.results['total_findings']}")
        print(f"  🔴 High Severity: {self.results['high_severity_count']}")
        print(f"  🟡 Medium Severity: {self.results['medium_severity_count']}")
        print(f"  🟢 Low Severity: {self.results['low_severity_count']}")
        
        print("\n🎯 Top Priority Actions:")
        for i, finding in enumerate(self.results['high_priority_actions'][:3], 1):
            print(f"  {i}. [{finding['check_id']}] {finding['check_name']}")
            print(f"     → {finding['recommendation']}")
    
    def _save_to_csv(self, output_prefix: Optional[str] = None) -> Dict[str, str]:
        """
        Save security analysis to CSV files.
        
        Args:
            output_prefix: Optional custom prefix for output files
            
        Returns:
            Dictionary with paths to saved CSV files
        """
        # Generate output prefix
        if output_prefix is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            ws_id = self.workspace_config['workspace_id'].replace('/', '_')
            output_prefix = f'Security_Analysis_{ws_id}_{timestamp}'
        
        print(f"\n💾 Saving security analysis reports...")
        
        # Ensure output directory exists
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
        base_path = f"{self.output_dir}/{output_prefix}"
        saved_files = {}
        
        # File 1: Executive Summary
        summary_data = {
            'Metric': [
                'Workspace ID',
                'Analysis Date',
                'Overall Security Score',
                'Security Grade',
                'Total Findings',
                'High Severity Issues',
                'Medium Severity Issues',
                'Low Severity Issues'
            ],
            'Value': [
                self.workspace_config['workspace_id'],
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                f"{self.security_score}/100",
                self.results['grade'],
                self.results['total_findings'],
                self.results['high_severity_count'],
                self.results['medium_severity_count'],
                self.results['low_severity_count']
            ]
        }
        summary_file = f"{base_path}_executive_summary.csv"
        pd.DataFrame(summary_data).to_csv(summary_file, index=False)
        saved_files['executive_summary'] = summary_file
        print(f"  ✓ Executive Summary: {os.path.basename(summary_file)}")
            
        
        # File 2: Category Scores
        cat_data = []
        for cat_key, cat_score in self.category_scores.items():
            cat_data.append({
                'Category': cat_score['name'],
                'Score': f"{cat_score['score']}/{cat_score['max_score']}",
                'Percentage': f"{cat_score['percentage']:.1f}%",
                'Total Checks': cat_score['findings_count'],
                'High Severity': cat_score['high_severity'],
                'Medium Severity': cat_score['medium_severity'],
                'Low Severity': cat_score['low_severity']
            })
        category_file = f"{base_path}_category_scores.csv"
        pd.DataFrame(cat_data).to_csv(category_file, index=False)
        saved_files['category_scores'] = category_file
        print(f"  ✓ Category Scores: {os.path.basename(category_file)}")
        
        # File 3: All Findings
        findings_df = pd.DataFrame(self.security_findings)
        findings_df = findings_df[[
            'check_id', 'category_name', 'check_name', 'severity', 
            'status', 'current_value', 'expected_value', 
            'recommendation', 'doc_url'
        ]]
        findings_df.columns = [
            'Check ID', 'Category', 'Check Name', 'Severity',
            'Status', 'Current', 'Expected',
            'Recommendation', 'Documentation'
        ]
        findings_file = f"{base_path}_all_findings.csv"
        findings_df.to_csv(findings_file, index=False)
        saved_files['all_findings'] = findings_file
        print(f"  ✓ All Findings: {os.path.basename(findings_file)}")
        
        # File 4: High Priority Actions
        if self.results['high_priority_actions']:
            high_df = pd.DataFrame(self.results['high_priority_actions'])
            high_df = high_df[[
                'check_id', 'check_name', 'recommendation', 'doc_url'
            ]]
            high_df.columns = ['Check ID', 'Issue', 'Recommended Action', 'Documentation']
            high_priority_file = f"{base_path}_high_priority.csv"
            high_df.to_csv(high_priority_file, index=False)
            saved_files['high_priority'] = high_priority_file
            print(f"  ✓ High Priority Actions: {os.path.basename(high_priority_file)}")
        
        # File 5: Remediation Roadmap
        roadmap_data = []
        
        # Phase 1: Critical (High severity)
        for finding in self.results['high_priority_actions']:
            roadmap_data.append({
                'Phase': 'Phase 1 - Critical',
                'Timeline': 'Immediate (0-30 days)',
                'Check ID': finding['check_id'],
                'Issue': finding['check_name'],
                'Action': finding['recommendation'],
                'Category': finding['category_name'],
                'Severity': finding['severity'],
                'Documentation': finding['doc_url']
            })
        
        # Phase 2: Important (Medium severity)
        for finding in self.results['medium_priority_actions']:
            roadmap_data.append({
                'Phase': 'Phase 2 - Important',
                'Timeline': 'Short-term (30-90 days)',
                'Check ID': finding['check_id'],
                'Issue': finding['check_name'],
                'Action': finding['recommendation'],
                'Category': finding['category_name'],
                'Severity': finding['severity'],
                'Documentation': finding['doc_url']
            })
        
        # Phase 3: Enhancement (Low severity)
        for finding in self.results['low_priority_actions']:
            roadmap_data.append({
                'Phase': 'Phase 3 - Enhancement',
                'Timeline': 'Long-term (90+ days)',
                'Check ID': finding['check_id'],
                'Issue': finding['check_name'],
                'Action': finding['recommendation'],
                'Category': finding['category_name'],
                'Severity': finding['severity'],
                'Documentation': finding['doc_url']
            })
        
        if roadmap_data:
            roadmap_file = f"{base_path}_remediation_roadmap.csv"
            pd.DataFrame(roadmap_data).to_csv(roadmap_file, index=False)
            saved_files['remediation_roadmap'] = roadmap_file
            print(f"  ✓ Remediation Roadmap: {os.path.basename(roadmap_file)}")
        
        print(f"\n✓ Security analysis reports saved successfully")
        print(f"  Location: {self.output_dir}")
        print(f"  Files: {len(saved_files)} CSV files")
        
        return saved_files
    
    def _save_to_excel(self, output_prefix: Optional[str] = None) -> Dict[str, str]:
        """
        Save security analysis to a single Excel file with multiple tabs.
        Uses temp directory for initial creation to avoid Databricks Volumes limitations.
        
        Args:
            output_prefix: Optional custom prefix for output file
            
        Returns:
            Dictionary with path to saved Excel file
        """
        # Generate output prefix
        if output_prefix is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            ws_id = self.workspace_config['workspace_id'].replace('/', '_')
            output_prefix = f'Security_Analysis_{ws_id}_{timestamp}'
        
        print(f"\n💾 Saving security analysis report to Excel...")
        
        # Ensure output directory exists
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
        
        # Create temp directory for Excel file creation
        temp_dir = tempfile.mkdtemp()
        temp_excel_path = os.path.join(temp_dir, f"{output_prefix}.xlsx")
        
        try:
            # Create Excel file in temp location
            with pd.ExcelWriter(temp_excel_path, engine='openpyxl') as writer:
                
                # Tab 1: Executive Summary
                summary_data = pd.DataFrame({
                    'Metric': [
                        'Workspace ID',
                        'Analysis Date',
                        'Overall Security Score',
                        'Security Grade',
                        'Total Findings',
                        'High Severity Issues',
                        'Medium Severity Issues',
                        'Low Severity Issues'
                    ],
                    'Value': [
                        self.workspace_config['workspace_id'],
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        f"{self.security_score} of 100",
                        self.results['grade'],
                        self.results['total_findings'],
                        self.results['high_severity_count'],
                        self.results['medium_severity_count'],
                        self.results['low_severity_count']
                    ]
                })
                summary_data.to_excel(writer, sheet_name='Executive Summary', index=False)
                print(f"  ✓ Created tab: Executive Summary")
                
                # Tab 2: Category Scores
                cat_data = []
                for cat_key, cat_score in self.category_scores.items():
                    cat_data.append({
                        'Category': cat_score['name'],
                        'Score': f"{cat_score['score']} of {cat_score['max_score']}",
                        'Percentage': f"{cat_score['percentage']:.1f}%",
                        'Total Checks': cat_score['findings_count'],
                        'High Severity': cat_score['high_severity'],
                        'Medium Severity': cat_score['medium_severity'],
                        'Low Severity': cat_score['low_severity']
                    })
                cat_df = pd.DataFrame(cat_data)
                cat_df.to_excel(writer, sheet_name='Category Scores', index=False)
                print(f"  ✓ Created tab: Category Scores")
                
                # Tab 3: All Findings
                findings_df = pd.DataFrame(self.security_findings)
                findings_df = findings_df[[
                    'check_id', 'category_name', 'check_name', 'severity', 
                    'status', 'current_value', 'expected_value', 
                    'recommendation', 'doc_url'
                ]]
                findings_df.columns = [
                    'Check ID', 'Category', 'Check Name', 'Severity',
                    'Status', 'Current', 'Expected',
                    'Recommendation', 'Documentation'
                ]
                findings_df.to_excel(writer, sheet_name='All Findings', index=False)
                print(f"  ✓ Created tab: All Findings")
                
                # Tab 4: High Priority Actions
                if self.results['high_priority_actions']:
                    high_df = pd.DataFrame(self.results['high_priority_actions'])
                    high_df = high_df[[
                        'check_id', 'check_name', 'recommendation', 'doc_url'
                    ]]
                    high_df.columns = ['Check ID', 'Issue', 'Recommended Action', 'Documentation']
                    high_df.to_excel(writer, sheet_name='High Priority', index=False)
                    print(f"  ✓ Created tab: High Priority")
                
                # Tab 5: Remediation Roadmap
                roadmap_data = []
                
                # Phase 1: Critical (High severity)
                for finding in self.results['high_priority_actions']:
                    roadmap_data.append({
                        'Phase': 'Phase 1 - Critical',
                        'Timeline': 'Immediate (0-30 days)',
                        'Check ID': finding['check_id'],
                        'Issue': finding['check_name'],
                        'Action': finding['recommendation'],
                        'Category': finding['category_name'],
                        'Severity': finding['severity'],
                        'Documentation': finding['doc_url']
                    })
                
                # Phase 2: Important (Medium severity)
                for finding in self.results['medium_priority_actions']:
                    roadmap_data.append({
                        'Phase': 'Phase 2 - Important',
                        'Timeline': 'Short-term (30-90 days)',
                        'Check ID': finding['check_id'],
                        'Issue': finding['check_name'],
                        'Action': finding['recommendation'],
                        'Category': finding['category_name'],
                        'Severity': finding['severity'],
                        'Documentation': finding['doc_url']
                    })
                
                # Phase 3: Enhancement (Low severity)
                for finding in self.results['low_priority_actions']:
                    roadmap_data.append({
                        'Phase': 'Phase 3 - Enhancement',
                        'Timeline': 'Long-term (90+ days)',
                        'Check ID': finding['check_id'],
                        'Issue': finding['check_name'],
                        'Action': finding['recommendation'],
                        'Category': finding['category_name'],
                        'Severity': finding['severity'],
                        'Documentation': finding['doc_url']
                    })
                
                if roadmap_data:
                    roadmap_df = pd.DataFrame(roadmap_data)
                    roadmap_df.to_excel(writer, sheet_name='Remediation Roadmap', index=False)
                    print(f"  ✓ Created tab: Remediation Roadmap")
            
            # Copy Excel file from temp to actual output directory
            final_excel_path = f"{self.output_dir}/{output_prefix}.xlsx"
            shutil.copy2(temp_excel_path, final_excel_path)
            
            print(f"\n✓ Security analysis report saved successfully")
            print(f"  Location: {final_excel_path}")
            print(f"  Format: Single Excel file with multiple tabs")
            
            return {'excel_report': final_excel_path}
            
        except Exception as e:
            print(f"\n❌ Error creating Excel report: {str(e)}")
            raise
        
        finally:
            # Clean up temp directory
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    print(f"  ✓ Cleaned up temporary files")
            except Exception as cleanup_error:
                print(f"  ⚠️  Warning: Could not clean up temp directory: {str(cleanup_error)}")


def run_security_analysis(discovery_path: str, workspace_id: Optional[str] = None,
                         output_dir: str = 'results', 
                         output_prefix: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to run security analysis with single call.
    
    Args:
        discovery_path: Path to discovery output directory
        workspace_id: Optional specific workspace ID
        output_dir: Output directory for reports
        output_prefix: Optional custom prefix for output files
        
    Returns:
        Dictionary with analysis results
        
    Example:
        >>> results = run_security_analysis(
        ...     discovery_path='/path/to/discovery',
        ...     workspace_id='1234567890',
        ...     output_dir='/path/to/output'
        ... )
        >>> print(f"Security Score: {results['security_score']}/100")
        >>> print(f"Files: {results['output_files']}")
    """
    analyzer = SecurityAnalyzer(
        discovery_path=discovery_path,
        workspace_id=workspace_id,
        output_dir=output_dir
    )
    
    return analyzer.analyze(save_csv=True, output_prefix=output_prefix)
