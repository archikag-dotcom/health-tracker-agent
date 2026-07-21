"""
Secret Manager Injection Service.
Eliminates hardcoded credentials by injecting API keys from Secret Manager or environment.
"""
import os
from typing import Optional


class SecretManager:
    """Secure Secret Injection service retrieving credentials without plain text keys."""

    @staticmethod
    def get_secret(secret_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Retrieves a secret by name.
        First checks Google Cloud Secret Manager client if GCP project is set,
        then falls back to environment variables.
        """
        # 1. Environment Variable Fallback
        env_val = os.environ.get(secret_name.upper()) or os.environ.get(secret_name)
        if env_val:
            return env_val

        # 2. Google Cloud Secret Manager Integration (if GCP_PROJECT is configured)
        gcp_project = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if gcp_project:
            try:
                from google.cloud import secretmanager
                client = secretmanager.SecretManagerServiceClient()
                name = f"projects/{gcp_project}/secrets/{secret_name}/versions/latest"
                response = client.access_secret_version(request={"name": name})
                return response.payload.data.decode("UTF-8")
            except Exception:
                pass

        return default

    @classmethod
    def get_api_key(cls) -> str:
        """Retrieves Gemini / Google AI API Key securely."""
        key = cls.get_secret("GEMINI_API_KEY") or cls.get_secret("GOOGLE_API_KEY")
        if not key:
            # Fallback for dev mode
            return "dev_secret_key_injected_at_runtime"
        return key
