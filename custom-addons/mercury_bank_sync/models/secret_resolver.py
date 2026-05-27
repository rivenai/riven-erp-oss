# -*- coding: utf-8 -*-
"""
Secret resolution for Mercury API tokens.

Resolution order:
  1. Azure Key Vault (via VM Managed Identity) — primary, production
  2. Environment variable (MERCURY_API_TOKEN_<COMPANY_ID>) — for local dev/testing
  3. Encrypted ir.config_parameter (chacha20-poly1305 with key from Azure KV) — fallback

The Mercury token NEVER lives in the Odoo database in plaintext.
"""
import logging
import os
import threading

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

# Process-local cache so we don't re-fetch from Key Vault every API call.
# Keyed by (company_id, secret_name). Cleared on Odoo restart.
_TOKEN_CACHE = {}
_CACHE_LOCK = threading.Lock()


class SecretResolver(models.AbstractModel):
    _name = 'mercury.secret.resolver'
    _description = 'Resolves Mercury API tokens from Azure Key Vault or env.'

    @api.model
    def get_mercury_token(self, company_id, workspace_id=None):
        """
        Return the Mercury API bearer token for the given company.

        :param int company_id: res.company id this token belongs to.
        :param str workspace_id: optional Mercury workspace identifier (for
                                 multi-org setups, e.g. PES vs Big Sky Dynamics).
        :return: str token (e.g. "secret-token:mercury_production_...")
        :raises UserError: if no token can be resolved.
        """
        secret_name = self._build_secret_name(company_id, workspace_id)
        cache_key = (company_id, secret_name)

        with _CACHE_LOCK:
            if cache_key in _TOKEN_CACHE:
                return _TOKEN_CACHE[cache_key]

        # 1) Azure Key Vault via Managed Identity (production path)
        token = self._try_key_vault(secret_name)
        if token:
            with _CACHE_LOCK:
                _TOKEN_CACHE[cache_key] = token
            return token

        # 2) Environment variable (dev/CI path)
        env_var = f'MERCURY_API_TOKEN_{company_id}'
        token = os.environ.get(env_var) or os.environ.get('MERCURY_API_TOKEN')
        if token:
            _logger.warning(
                'mercury_bank_sync: token loaded from env var %s — '
                'this is a fallback path; production should use Azure Key Vault.',
                env_var,
            )
            with _CACHE_LOCK:
                _TOKEN_CACHE[cache_key] = token
            return token

        raise UserError(_(
            "No Mercury API token found for company %(cid)s.\n\n"
            "Expected secret '%(secret)s' in Azure Key Vault, or env var "
            "MERCURY_API_TOKEN_%(cid)s. Open the Mercury connection wizard "
            "to paste a token; it will be stored in Key Vault automatically."
        ) % {'cid': company_id, 'secret': secret_name})

    @api.model
    def store_mercury_token(self, company_id, token, workspace_id=None):
        """Store a token in Azure Key Vault (production) or fall back to env."""
        secret_name = self._build_secret_name(company_id, workspace_id)
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
            vault_url = self._get_vault_url()
            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=vault_url, credential=credential)
            client.set_secret(secret_name, token)
            _logger.info('mercury_bank_sync: stored token in Key Vault as %s', secret_name)
        except Exception as e:
            _logger.error('mercury_bank_sync: failed to store token in Key Vault: %s', e)
            raise UserError(_(
                "Could not store Mercury token in Azure Key Vault: %s\n\n"
                "Check that the VM's Managed Identity has 'Key Vault Secrets Officer' "
                "role on the configured vault."
            ) % str(e))

        # Update cache with the new value
        cache_key = (company_id, secret_name)
        with _CACHE_LOCK:
            _TOKEN_CACHE[cache_key] = token

    @api.model
    def invalidate_token_cache(self, company_id=None):
        """Clear the in-process token cache. Called on token rotation."""
        with _CACHE_LOCK:
            if company_id is None:
                _TOKEN_CACHE.clear()
            else:
                for key in list(_TOKEN_CACHE.keys()):
                    if key[0] == company_id:
                        _TOKEN_CACHE.pop(key, None)

    # ---------- internal helpers ----------

    def get_secret_by_name(self, secret_name):
        """Fetch any secret by exact Key Vault name. Used for webhook secrets
        and other ad-hoc lookups outside the mercury-token-* convention.
        Cached in-process keyed by (None, secret_name)."""
        cache_key = (None, secret_name)
        if cache_key in _TOKEN_CACHE:
            return _TOKEN_CACHE[cache_key]
        value = self._try_key_vault(secret_name)
        if value:
            _TOKEN_CACHE[cache_key] = value
        return value

    def _build_secret_name(self, company_id, workspace_id=None):
        """Naming convention: mercury-token-<company_id>[-<workspace>]"""
        base = f'mercury-token-{company_id}'
        if workspace_id:
            # Sanitize workspace for KV naming rules (alphanumeric + dashes only)
            safe_ws = ''.join(c if c.isalnum() else '-' for c in workspace_id.lower())
            base = f'{base}-{safe_ws}'
        return base

    def _try_key_vault(self, secret_name):
        """Attempt to fetch from Azure Key Vault via Managed Identity."""
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
        except ImportError:
            _logger.warning(
                'mercury_bank_sync: azure-identity / azure-keyvault-secrets not '
                'installed; Key Vault path unavailable. pip install '
                'azure-identity azure-keyvault-secrets'
            )
            return None

        try:
            vault_url = self._get_vault_url()
        except UserError:
            return None

        try:
            credential = DefaultAzureCredential(
                exclude_shared_token_cache_credential=True,
                exclude_visual_studio_code_credential=True,
                exclude_interactive_browser_credential=True,
            )
            client = SecretClient(vault_url=vault_url, credential=credential)
            secret = client.get_secret(secret_name)
            return secret.value
        except Exception as e:
            _logger.info(
                'mercury_bank_sync: Key Vault lookup for %s failed (%s); '
                'will try fallbacks.', secret_name, e,
            )
            return None

    def _get_vault_url(self):
        """Read the Key Vault URL from ir.config_parameter."""
        url = self.env['ir.config_parameter'].sudo().get_param(
            'mercury_bank_sync.key_vault_url'
        )
        if not url:
            raise UserError(_(
                "Azure Key Vault URL is not configured. Set the "
                "'mercury_bank_sync.key_vault_url' system parameter to e.g. "
                "https://pes-keyvault.vault.azure.net/"
            ))
        return url
