# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu/Lark REST API client using app access token.

from __future__ import annotations

import json
import time
from typing import Any, Optional

import httpx

DOMAIN_MAP: dict[str, str] = {
    "feishu": "https://open.feishu.cn",
    "lark": "https://open.larksuite.com",
}

# Module-level singleton
_default_client: Optional["LarkAPIClient"] = None


def set_lark_client(client: "LarkAPIClient") -> None:
    global _default_client
    _default_client = client


def get_lark_client() -> "LarkAPIClient":
    if _default_client is None:
        raise RuntimeError(
            "LarkAPIClient not initialized. "
            "Please configure app_id and app_secret in the plugin settings."
        )
    return _default_client


class LarkAPIClient:
    """Feishu/Lark REST API client.

    Uses app_access_token for all requests.
    Optionally supports MCP-based doc operations via mcp_base_url.
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        domain: str = "feishu",
        mcp_base_url: str = "",
        mcp_user_access_token: str = "",
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = DOMAIN_MAP.get(domain, f"https://{domain}")
        self.mcp_base_url = mcp_base_url.rstrip("/")
        self.mcp_user_access_token = mcp_user_access_token

        self._app_access_token: Optional[str] = None
        self._token_expires_at: float = 0

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    async def _refresh_app_access_token(self) -> None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.base_url}/open-apis/auth/v3/app_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            resp.raise_for_status()
            data: dict = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(
                    f"Failed to get app access token: code={data.get('code')}, "
                    f"msg={data.get('msg')}"
                )
            self._app_access_token = data["app_access_token"]
            self._token_expires_at = time.time() + int(data.get("expire", 7200)) - 60

    async def _get_token(self) -> str:
        if (
            self._app_access_token is None
            or time.time() >= self._token_expires_at
        ):
            await self._refresh_app_access_token()
        return self._app_access_token  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Generic request helper
    # ------------------------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_data: Optional[Any] = None,
        extra_headers: Optional[dict] = None,
        raw_response: bool = False,
    ) -> Any:
        token = await self._get_token()
        headers: dict[str, str] = {
            "Authorization": f"Bearer {token}",
        }
        if not raw_response:
            headers["Content-Type"] = "application/json; charset=utf-8"
        if extra_headers:
            headers.update(extra_headers)

        url = f"{self.base_url}{path}"

        # Strip None values from params
        if params:
            params = {k: v for k, v in params.items() if v is not None}

        async with httpx.AsyncClient(timeout=60.0) as client:
            if raw_response:
                resp = await client.request(
                    method, url, params=params, json=json_data, headers=headers
                )
                resp.raise_for_status()
                return resp.content
            else:
                resp = await client.request(
                    method, url, params=params, json=json_data, headers=headers
                )
                resp.raise_for_status()
                return resp.json()

    async def get(
        self,
        path: str,
        params: Optional[dict] = None,
        raw_response: bool = False,
    ) -> Any:
        return await self.request(
            "GET", path, params=params, raw_response=raw_response
        )

    async def post(
        self, path: str, data: Optional[Any] = None, params: Optional[dict] = None
    ) -> Any:
        return await self.request("POST", path, json_data=data, params=params)

    async def patch(
        self, path: str, data: Optional[Any] = None, params: Optional[dict] = None
    ) -> Any:
        return await self.request("PATCH", path, json_data=data, params=params)

    async def put(
        self, path: str, data: Optional[Any] = None, params: Optional[dict] = None
    ) -> Any:
        return await self.request("PUT", path, json_data=data, params=params)

    async def delete(
        self, path: str, params: Optional[dict] = None
    ) -> Any:
        return await self.request("DELETE", path, params=params)

    # ------------------------------------------------------------------
    # Response validation
    # ------------------------------------------------------------------

    @staticmethod
    def check(result: dict, action: str = "") -> None:
        """Raise RuntimeError if result.code != 0."""
        code = result.get("code", -1)
        if code != 0:
            msg = result.get("msg", "unknown error")
            err = result.get("error", {})
            prefix = f"[{action}] " if action else ""
            raise RuntimeError(
                f"Feishu API error {prefix}code={code}, msg={msg}"
                + (f", error={err}" if err else "")
            )

    # ------------------------------------------------------------------
    # MCP Doc operations (optional)
    # ------------------------------------------------------------------

    async def mcp_call(self, tool_name: str, arguments: dict) -> Any:
        """Call a Feishu MCP server tool and return the result content."""
        if not self.mcp_base_url:
            raise RuntimeError(
                "MCP base URL not configured. "
                "Please set mcp_base_url in plugin settings."
            )
        token = self.mcp_user_access_token or await self._get_token()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.mcp_base_url}/mcp",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"MCP error: {data['error']}")
            result = data.get("result", {})
            # Extract text content from MCP response
            content = result.get("content", [])
            if content and isinstance(content, list) and content[0].get("type") == "text":
                return content[0]["text"]
            return result

    def has_mcp(self) -> bool:
        return bool(self.mcp_base_url)
