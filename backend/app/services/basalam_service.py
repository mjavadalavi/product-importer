from __future__ import annotations

from typing import Any

from app.services.basalam.categories import _extract_category_items, _flatten_categories
from app.services.basalam.client import BasalamClient
from app.services.basalam.payload import normalize_product_payload
from app.services.basalam.pricing import PriceSuggestion, build_price_suggestion
from app.utils.logging import LoggerMixin


class BasalamService(LoggerMixin):
    """Thin service layer over BasalamClient.

    Stateless except for the bearer token. Provides direct passthroughs to
    BasalamClient methods and a small set of convenience helpers that compose
    the lower-level basalam sub-package utilities.
    """

    def __init__(self, token: str | None = None) -> None:
        self.token = token
        self._client: BasalamClient | None = None

    @property
    def client(self) -> BasalamClient:
        if self._client is None:
            self._client = BasalamClient(token=self.token or "")
        return self._client

    # ------------------------------------------------------------------
    # Direct passthroughs to BasalamClient
    # ------------------------------------------------------------------

    async def get_current_user(self) -> dict[str, Any]:
        """Return the authenticated user profile from Basalam."""
        self.logger.debug("get_current_user called")
        return await self.client.get_current_user()

    async def get_categories(self) -> dict[str, Any]:
        """Return the full category tree from Basalam."""
        self.logger.debug("get_categories called")
        return await self.client.get_categories()

    async def get_category_attributes(
        self,
        category_id: int,
        vendor_id: int | None = None,
    ) -> dict[str, Any]:
        """Return attributes for a given category, optionally scoped to a vendor."""
        self.logger.debug("get_category_attributes category_id=%s vendor_id=%s", category_id, vendor_id)
        return await self.client.get_category_attributes(category_id, vendor_id)

    async def search_products(
        self,
        query: str,
        *,
        rows: int = 24,
        start: int = 0,
        filters: dict | None = None,
    ) -> Any:
        """Search Basalam products by query string."""
        self.logger.debug("search_products query=%r rows=%s start=%s", query, rows, start)
        return await self.client.search_products(query, rows=rows, start=start, filters=filters)

    async def list_products(
        self,
        vendor_id: int,
        *,
        page: int = 1,
        per_page: int = 50,
        filters: dict | None = None,
    ) -> dict[str, Any]:
        """List products for a vendor with pagination metadata."""
        self.logger.debug("list_products vendor_id=%s page=%s per_page=%s", vendor_id, page, per_page)
        return await self.client.list_products(vendor_id, page=page, per_page=per_page, filters=filters)

    async def get_product_detail(self, product_id: int) -> dict[str, Any]:
        """Return full detail for a single product."""
        self.logger.debug("get_product_detail product_id=%s", product_id)
        return await self.client.get_product_detail(product_id)

    async def update_product(self, product_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        """Patch a product by ID."""
        self.logger.info("update_product product_id=%s", product_id)
        return await self.client.update_product(product_id, payload)

    async def batch_update_products(
        self,
        vendor_id: int,
        updates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Apply a batch of product updates for a vendor."""
        self.logger.info("batch_update_products vendor_id=%s count=%s", vendor_id, len(updates))
        return await self.client.batch_update_products(vendor_id, updates)

    async def upload_product_photo(self, image_data_url: str, filename: str) -> dict[str, Any]:
        """Upload a product photo from a data-URL and return the file record."""
        self.logger.info("upload_product_photo filename=%r", filename)
        return await self.client.upload_product_photo(image_data_url, filename)

    async def create_product(self, vendor_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a new product under a vendor using the v4 schema."""
        self.logger.info("create_product vendor_id=%s name=%r", vendor_id, payload.get("name"))
        return await self.client.create_product(vendor_id, payload)

    # ------------------------------------------------------------------
    # Convenience helpers (re-export / compose sub-package utilities)
    # ------------------------------------------------------------------

    def flatten_categories(self, raw: Any) -> list[dict[str, Any]]:
        """Flatten the raw category tree response into a sorted list of dicts.

        Equivalent to: _flatten_categories(_extract_category_items(raw))
        """
        items = _extract_category_items(raw)
        return _flatten_categories(items)

    def build_price_suggestion(self, response: Any, **kwargs: Any) -> PriceSuggestion:
        """Delegate to pricing.build_price_suggestion."""
        return build_price_suggestion(response, **kwargs)

    def normalize_product_payload(self, product: dict[str, Any], photo_ids: list[int]) -> dict[str, Any]:
        """Delegate to payload.normalize_product_payload."""
        return normalize_product_payload(product, photo_ids)
