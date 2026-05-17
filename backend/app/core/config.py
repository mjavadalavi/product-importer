from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://importer:importer@localhost:5432/importer"
    session_secret: str = "change-me"
    fernet_key: str = "change-me"

    basalam_client_id: str = ""
    basalam_client_secret: str = ""
    basalam_redirect_uri: str = "http://localhost:8000/api/v1/auth/basalam/callback"
    basalam_authorize_url: str = "https://basalam.com/accounts/oauth/authorize"
    basalam_token_url: str = "https://basalam.com/accounts/oauth/token"
    basalam_openapi_base: str = "https://openapi.basalam.com"
    basalam_scopes: str = "vendor.product.read vendor.product.write customer.profile.read"
    basalam_bridge_url: str = ""
    basalam_bridge_api_key: str = ""
    basalam_product_status: int = 2976

    openrouter_api_key: str = ""
    openrouter_text_model: str = "google/gemini-2.5-flash"
    openrouter_image_model: str = "google/gemini-2.5-flash-image"

    cost_per_product: int = 1
    enhance_cost_per_image: int = 5000  # toman, charged per manual image enhance
    signup_gift_amount: int = 0

    # ── Payment gateway ───────────────────────────────────────────────────
    # Adapter selection: "shopyaar" (pay.ejourney.ir bridge) | "basalam"
    # (Basalam OpenAPI /v1/pay/*).
    payment_provider: str = "shopyaar"

    # Shopyaar pay.ejourney.ir compatible bridge
    payment_bridge_url: str = ""
    payment_bridge_api_key: str = ""
    payment_bridge_callback_url: str = ""
    payment_bridge_timeout_ms: int = 15_000
    payment_bridge_enabled: bool = False
    payment_bridge_bypass: bool = False

    # Basalam OpenAPI pay gateway (uses `basalam_openapi_base` above)
    basalam_pay_gateway_secret: str = ""

    # File upload settings
    file_storage_dir: str = "./var/files"
    max_upload_mb: int = 50
    allowed_upload_kinds: list[str] = [
        "product_image",
        "bulk_sheet",
        "bulk_zip",
        "support_attachment",
        "misc",
    ]

    app_origin: str = "http://localhost:3000"
    session_cookie_name: str = "pi_session"
    session_ttl_days: int = 7
    cookie_secure: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
