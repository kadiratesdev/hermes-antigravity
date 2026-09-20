"""Antigravity (Google Cloud Code Assist) provider profile.

Registers the `antigravity` provider so an Antigravity subscription can be
used from Hermes. The wire protocol is Gemini-style but wrapped in Google's
Cloud Code Assist envelope, so the profile supplies its own client via the
`create_client` hook — no core edits required.

Auth: Google OAuth. Log in with `python3 login.py` (or `hermes-antigravity-login`).
"""

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


class AntigravityProfile(ProviderProfile):
    """Google Antigravity — OAuth, Cloud Code Assist gateway."""

    def create_client(self, **client_kwargs: Any) -> Any:
        from .client import AntigravityClient

        # The core passes api_key/base_url meant for an OpenAI client; our
        # transport resolves the OAuth token itself and ignores a stray key.
        safe = {
            k: v
            for k, v in client_kwargs.items()
            if k in {"base_url", "timeout", "http_client", "default_headers"}
        }
        return AntigravityClient(**safe)

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        try:
            from .client import fetch_models

            return fetch_models(timeout=max(timeout, 15.0), base_url=base_url)
        except Exception:
            return None


antigravity = AntigravityProfile(
    name="antigravity",
    aliases=("google-antigravity", "cloudcode", "ag"),
    api_mode="chat_completions",
    display_name="Google Antigravity",
    description="Google Antigravity subscription (Gemini + Claude via Cloud Code Assist)",
    signup_url="https://antigravity.google/",
    env_vars=("ANTIGRAVITY_OAUTH",),  # placeholder: real auth is the OAuth token file
    base_url="https://daily-cloudcode-pa.sandbox.googleapis.com",
    # NOTE: must stay "api_key" — hermes_cli/auth.py only auto-registers
    # api_key/external_process profiles into PROVIDER_REGISTRY. With any other
    # auth_type the provider silently resolves as "custom", the create_client
    # hook never matches by name, and requests go to /chat/completions (404).
    auth_type="api_key",
    supports_health_check=False,  # no REST /models endpoint
    supports_vision=True,
    # Deliberately empty. The auxiliary-client path in core builds a plain
    # OpenAI client from base_url and never consults create_client(), so an
    # aux model here would POST /chat/completions to the gateway and 404.
    # Leaving it blank makes core skip antigravity for auxiliary work
    # (titling, compression, vision) and fall back to another configured
    # provider, while main turns still use this transport.
    default_aux_model="",
    # Live discovery is authoritative; do not resurrect retired tier aliases.
    fallback_models=(),
)


def register() -> None:
    """Entry point for hermes_agent.plugins."""
    register_provider(antigravity)


register_provider(antigravity)
