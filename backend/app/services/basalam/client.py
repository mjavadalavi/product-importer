from __future__ import annotations

import base64
import os
import socket
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.exceptions import BasalamError
from app.core.logging import get_logger

logger = get_logger(__name__)

LOCAL_PROXY_PORTS = (1087, 7890, 1080)


def _configured_proxy_url() -> str | None:
    for key in (
        "BASALAM_PROXY_URL",
        "HTTPS_PROXY",
        "https_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "ALL_PROXY",
        "all_proxy",
    ):
        value = os.getenv(key)
        if value:
            return value
    return None


def _is_local_port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def _proxy_candidates() -> list[str | None]:
    candidates: list[str | None] = []
    configured = _configured_proxy_url()
    if configured:
        candidates.append(configured)
    for port in LOCAL_PROXY_PORTS:
        if _is_local_port_open(port):
            proxy_url = f"http://127.0.0.1:{port}"
            if proxy_url not in candidates:
                candidates.append(proxy_url)
    candidates.append(None)
    return candidates


async def _send_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    json: Any | None,
    data: Any | None,
    files: Any | None,
    params: dict[str, Any] | None,
    timeout: float,
    proxy: str | None,
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout, proxy=proxy, trust_env=proxy is None) as client:
        return await client.request(
            method,
            url,
            headers=headers,
            json=json,
            data=data,
            files=files,
            params=params,
        )


def data_url_to_file(data_url: str, filename: str = "product.jpg") -> tuple[str, bytes, str]:
    if "," not in data_url:
        raise BasalamError("فرمت تصویر معتبر نیست.", 400)
    header, encoded = data_url.split(",", 1)
    mime_type = "image/jpeg"
    if header.startswith("data:") and ";" in header:
        mime_type = header[5 : header.index(";")]
    try:
        content = base64.b64decode(encoded)
    except ValueError as exc:
        raise BasalamError("base64 تصویر معتبر نیست.", 400) from exc
    return filename, content, mime_type


class BasalamClient:
    def __init__(self, token: str) -> None:
        self._token = token
        settings = get_settings()
        self._base_url = settings.basalam_openapi_base

    def _auth_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        data: Any | None = None,
        files: Any | None = None,
        params: dict[str, Any] | None = None,
        timeout: float = 35.0,
    ) -> Any:
        url = f"{self._base_url}{path}"
        headers = self._auth_headers()
        attempts: list[dict[str, str | None]] = []
        last_error: httpx.HTTPError | None = None
        for proxy in _proxy_candidates():
            attempts.append({"proxy": proxy or "direct"})
            try:
                response = await _send_request(
                    method,
                    url,
                    headers=headers,
                    json=json,
                    data=data,
                    files=files,
                    params=params,
                    timeout=timeout,
                    proxy=proxy,
                )
            except httpx.TimeoutException as exc:
                last_error = exc
                continue
            except httpx.HTTPError as exc:
                last_error = exc
                continue
            break
        else:
            if isinstance(last_error, httpx.TimeoutException):
                raise BasalamError(
                    "درخواست باسلام بیش از حد طول کشید.", 504, {"attempts": attempts}
                ) from last_error
            raise BasalamError(
                "اتصال به باسلام ناموفق بود.",
                502,
                {"attempts": attempts, "error": str(last_error) if last_error else None},
            ) from last_error

        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise BasalamError("خطای API باسلام", response.status_code, detail)

        if not response.content:
            return {}

        try:
            return response.json()
        except ValueError as exc:
            raise BasalamError("پاسخ باسلام JSON معتبر نبود.", 502, response.text) from exc

    async def get_current_user(self) -> dict[str, Any]:
        return await self._request("GET", "/v1/users/me")

    async def get_categories(self) -> dict[str, Any]:
        return await self._request("GET", "/v1/categories")

    async def get_category_attributes(
        self,
        category_id: int,
        vendor_id: int | None = None,
        exclude_multi_selects: bool = True,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"exclude_multi_selects": str(exclude_multi_selects).lower()}
        if vendor_id:
            params["vendor_id"] = vendor_id
        return await self._request("GET", f"/v1/categories/{category_id}/attributes", params=params)

    async def search_products(
        self,
        query: str,
        *,
        rows: int = 24,
        start: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> Any:
        payload = {"q": query, "rows": rows, "start": start, "filters": filters or {}}
        return await self._request("POST", "/v1/products/search", json=payload)

    async def list_products(
        self,
        vendor_id: int,
        page: int = 1,
        per_page: int = 50,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if filters:
            params.update(filters)
        raw = await self._request("GET", f"/v1/vendors/{vendor_id}/products", params=params)
        data = raw if isinstance(raw, dict) else {}
        items = data.get("data") or data.get("items") or data.get("products") or []
        total = data.get("total") or data.get("count") or len(items)
        total_pages = data.get("total_pages") or data.get("pages") or (
            (total + per_page - 1) // per_page if per_page else 1
        )
        return {
            "items": items,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "result_count": len(items),
            "has_more": page < total_pages,
        }

    async def get_product_detail(self, product_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/v1/products/{product_id}")

    async def update_product(self, product_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PATCH", f"/v1/products/{product_id}", json=payload, timeout=60.0)

    async def batch_update_products(
        self, vendor_id: int, updates: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/v1/vendors/{vendor_id}/products",
            json={"data": updates},
            timeout=60.0,
        )

    async def upload_product_photo(self, image_data_url: str, filename: str) -> dict[str, Any]:
        file_name, content, mime_type = data_url_to_file(image_data_url, filename)
        files = {"file": (file_name, content, mime_type)}
        data = {"file_type": "product.photo"}
        return await self._request("POST", "/v1/files", files=files, data=data, timeout=60.0)

    async def create_product(self, vendor_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        # v4: full schema with keywords/packaging_dimensions/shipping_data/etc.
        return await self._request(
            "POST", f"/v4/vendors/{vendor_id}/products", json=payload, timeout=60.0
        )
