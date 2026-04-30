# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu/Lark REST API client.
# Supports both tenant (app) access token and user (OAuth) access token modes.
# User auth supports:
#   - RFC 8628 Device Authorization Grant (device flow)
#   - OAuth 2.0 Authorization Code flow with local HTTP callback server

from __future__ import annotations

import asyncio
import secrets
import time
from typing import Any, Optional
from urllib.parse import parse_qs, quote, urlparse

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DOMAIN_MAP: dict[str, str] = {
    "feishu": "https://open.feishu.cn",
    "lark": "https://open.larksuite.com",
}

ACCOUNTS_MAP: dict[str, str] = {
    "feishu": "https://accounts.feishu.cn",
    "lark": "https://accounts.larksuite.com",
}

# Feishu API error codes that indicate permission/auth issues
LARK_ERR_APP_SCOPE_MISSING = 99991672
LARK_ERR_USER_SCOPE_INSUFFICIENT = 99991679
LARK_ERR_TOKEN_INVALID = 99991668
LARK_ERR_TOKEN_EXPIRED = 99991677

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# UserToken
# ---------------------------------------------------------------------------


class UserToken:
    """Stores OAuth user access token and metadata for one user."""

    __slots__ = (
        "access_token",
        "refresh_token",
        "expires_at",
        "refresh_expires_at",
        "scope",
    )

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        refresh_expires_in: int,
        scope: str = "",
    ) -> None:
        now = time.time()
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = now + expires_in - 60
        self.refresh_expires_at = now + refresh_expires_in - 60
        self.scope = scope

    def is_access_valid(self) -> bool:
        return bool(self.access_token) and time.time() < self.expires_at

    def can_refresh(self) -> bool:
        return bool(self.refresh_token) and time.time() < self.refresh_expires_at

    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "refresh_expires_at": self.refresh_expires_at,
            "scope": self.scope,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "UserToken":
        obj = cls.__new__(cls)
        obj.access_token = d.get("access_token", "")
        obj.refresh_token = d.get("refresh_token", "")
        obj.expires_at = d.get("expires_at", 0.0)
        obj.refresh_expires_at = d.get("refresh_expires_at", 0.0)
        obj.scope = d.get("scope", "")
        return obj


# ---------------------------------------------------------------------------
# LarkAPIClient
# ---------------------------------------------------------------------------


class LarkAPIClient:
    """Feishu/Lark REST API client.

    Supports two auth modes:
    - tenant (default): Uses app_access_token (bot identity).
    - user: Uses per-user OAuth user_access_tokens.

    User auth supports two flows:
    - Device flow (RFC 8628): user visits a verification URL on any device.
    - Web flow (Authorization Code): user visits an auth URL, Feishu redirects
      to a local HTTP callback server whose bind address and external hostname
      are configurable (oauth_callback_bind / oauth_callback_host).
      Requires oauth_callback_port to be set.

    Token persistence callbacks (persist_token / load_token) should be wired
    to AstrBot's KV store by the plugin after creating this client.
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        domain: str = "feishu",
        auth_mode: str = "tenant",
        oauth_callback_port: int = 0,
        oauth_callback_host: str = "localhost",
        oauth_callback_bind: str = "0.0.0.0",
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.domain = domain
        self.base_url = DOMAIN_MAP.get(domain, f"https://{domain}")
        self.accounts_url = ACCOUNTS_MAP.get(domain, f"https://accounts.{domain}")
        self.auth_mode = auth_mode
        self.oauth_callback_port = oauth_callback_port
        self.oauth_callback_host = oauth_callback_host or "localhost"
        # Bind address for the callback HTTP server. Use "0.0.0.0" for all
        # IPv4 interfaces, "::" for all IPv6 interfaces (on Linux/macOS this
        # also accepts IPv4-mapped connections unless IPV6_V6ONLY is set), or
        # a specific address such as "192.168.1.10" / "fe80::1%eth0".
        self.oauth_callback_bind = oauth_callback_bind or "0.0.0.0"

        # Tenant token cache
        self._app_access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

        # In-memory user token cache: user_id -> UserToken
        self._user_tokens: dict[str, UserToken] = {}

        # Pending web OAuth states: state -> user_id
        self._pending_states: dict[str, str] = {}

        # asyncio.Server for the OAuth callback HTTP server
        self._oauth_server: Optional[asyncio.Server] = None

        # Callbacks for persisting tokens (injected by plugin)
        # persist_token: async (user_id: str, data: dict | None) -> None
        # load_token:    async (user_id: str) -> dict | None
        self.persist_token: Optional[Any] = None
        self.load_token: Optional[Any] = None

    # ------------------------------------------------------------------
    # Tenant token
    # ------------------------------------------------------------------

    async def _refresh_app_access_token(self) -> None:
        async with httpx.AsyncClient(timeout=15.0) as hc:
            resp = await hc.post(
                f"{self.base_url}/open-apis/auth/v3/app_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            resp.raise_for_status()
            data: dict = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(
                f"Failed to get app access token: code={data.get('code')}, msg={data.get('msg')}"
            )
        self._app_access_token = data["app_access_token"]
        self._token_expires_at = time.time() + int(data.get("expire", 7200)) - 60

    async def _get_tenant_token(self) -> str:
        if not self._app_access_token or time.time() >= self._token_expires_at:
            await self._refresh_app_access_token()
        return self._app_access_token  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # User token (OAuth)
    # ------------------------------------------------------------------

    async def _load_user_token(self, user_id: str) -> Optional[UserToken]:
        if user_id in self._user_tokens:
            return self._user_tokens[user_id]
        if self.load_token:
            data = await self.load_token(user_id)
            if data:
                tok = UserToken.from_dict(data)
                self._user_tokens[user_id] = tok
                return tok
        return None

    async def _save_user_token(self, user_id: str, token: UserToken) -> None:
        self._user_tokens[user_id] = token
        if self.persist_token:
            await self.persist_token(user_id, token.to_dict())

    async def _refresh_user_token(self, user_id: str, token: UserToken) -> bool:
        """Try to refresh the user access token. Returns True on success."""
        if not token.can_refresh():
            return False
        url = f"{self.base_url}/open-apis/authen/v2/oauth/token"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
            "client_id": self.app_id,
            "client_secret": self.app_secret,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as hc:
                resp = await hc.post(url, data=payload)
                resp.raise_for_status()
                data = resp.json()
            if data.get("error") or data.get("code", 0) != 0:
                return False
            new_token = UserToken(
                access_token=data.get("access_token", ""),
                refresh_token=data.get("refresh_token", token.refresh_token),
                expires_in=int(data.get("expires_in", 7200)),
                refresh_expires_in=int(data.get("refresh_expires_in", 2592000)),
                scope=data.get("scope", token.scope),
            )
            await self._save_user_token(user_id, new_token)
            return True
        except Exception:
            return False

    async def get_user_access_token(self, user_id: str) -> Optional[str]:
        """Return a valid user access token, refreshing if necessary."""
        token = await self._load_user_token(user_id)
        if token is None:
            return None
        if token.is_access_valid():
            return token.access_token
        if await self._refresh_user_token(user_id, token):
            return self._user_tokens[user_id].access_token
        # Token fully expired
        del self._user_tokens[user_id]
        return None

    def has_user_token_cached(self, user_id: str) -> bool:
        return user_id in self._user_tokens

    async def store_oauth_token(
        self,
        user_id: str,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        refresh_expires_in: int,
        scope: str = "",
    ) -> None:
        tok = UserToken(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            refresh_expires_in=refresh_expires_in,
            scope=scope,
        )
        await self._save_user_token(user_id, tok)

    async def revoke_user_token(self, user_id: str) -> None:
        self._user_tokens.pop(user_id, None)
        if self.persist_token:
            await self.persist_token(user_id, None)

    # ------------------------------------------------------------------
    # Device Authorization Flow (RFC 8628)
    # ------------------------------------------------------------------

    async def start_device_flow(self) -> dict:
        """Start device authorization flow.

        Returns a dict with keys:
            device_code, user_code, verification_uri,
            verification_uri_complete, expires_in, interval.
        """
        url = f"{self.accounts_url}/oauth/v1/device_authorization"
        payload = {
            "client_id": self.app_id,
            "scope": "offline_access",
        }
        async with httpx.AsyncClient(timeout=15.0) as hc:
            resp = await hc.post(url, data=payload)
            resp.raise_for_status()
            data = resp.json()
        if data.get("error"):
            raise RuntimeError(
                f"Device flow initiation failed: {data.get('error')} - "
                f"{data.get('error_description', '')}"
            )
        return {
            "device_code": data.get("device_code", ""),
            "user_code": data.get("user_code", ""),
            "verification_uri": data.get("verification_uri", ""),
            "verification_uri_complete": data.get("verification_uri_complete", ""),
            "expires_in": int(data.get("expires_in", 300)),
            "interval": int(data.get("interval", 5)),
        }

    async def poll_device_token(
        self,
        device_code: str,
        interval: int = 5,
        max_wait: int = 300,
    ) -> Optional[dict]:
        """Poll token endpoint until user authorises or timeout.

        Returns the raw token response dict on success, or None.
        """
        url = f"{self.base_url}/open-apis/authen/v2/oauth/token"
        deadline = time.time() + max_wait
        current_interval = max(interval, 5)

        while time.time() < deadline:
            await asyncio.sleep(current_interval)
            payload = {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
                "client_id": self.app_id,
                "client_secret": self.app_secret,
            }
            try:
                async with httpx.AsyncClient(timeout=15.0) as hc:
                    resp = await hc.post(url, data=payload)
                    resp.raise_for_status()
                    data = resp.json()
            except Exception:
                continue

            err = data.get("error", "")
            if err == "authorization_pending":
                continue
            if err == "slow_down":
                current_interval = min(current_interval + 5, 30)
                continue
            if err in ("access_denied", "expired_token"):
                return None
            if data.get("access_token"):
                return data
        return None

    # ------------------------------------------------------------------
    # Web OAuth Flow (Authorization Code Grant)
    # ------------------------------------------------------------------

    def generate_web_auth_url(self, user_id: str) -> tuple[str, str]:
        """Generate a Feishu OAuth authorization URL.

        Registers a pending state -> user_id mapping so the callback server
        can associate the redirect back to the correct chat user.

        Returns:
            (auth_url, state) - the URL to send to the user and the state token.
        """
        state = secrets.token_urlsafe(24)
        self._pending_states[state] = user_id
        redirect_uri = self._callback_redirect_uri()
        scope = "offline_access"
        auth_url = (
            f"{self.base_url}/open-apis/authen/v1/authorize"
            f"?app_id={quote(self.app_id)}"
            f"&redirect_uri={quote(redirect_uri, safe='')}"
            f"&scope={quote(scope)}"
            f"&state={quote(state)}"
        )
        return auth_url, state

    def _callback_redirect_uri(self) -> str:
        host = self.oauth_callback_host
        # Wrap bare IPv6 addresses in brackets for a valid URI
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"http://{host}:{self.oauth_callback_port}/feishu/oauth/callback"

    async def exchange_auth_code(self, code: str) -> Optional[dict]:
        """Exchange an authorization code for tokens.

        Returns the raw token response dict on success, or None.
        """
        url = f"{self.base_url}/open-apis/authen/v2/oauth/token"
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.app_id,
            "client_secret": self.app_secret,
            "redirect_uri": self._callback_redirect_uri(),
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as hc:
                resp = await hc.post(url, data=payload)
                resp.raise_for_status()
                data = resp.json()
            if data.get("error") or not data.get("access_token"):
                return None
            return data
        except Exception:
            return None

    # ------------------------------------------------------------------
    # OAuth Callback HTTP Server
    # ------------------------------------------------------------------

    async def start_oauth_callback_server(self) -> bool:
        """Start the OAuth callback HTTP server.

        Listens on ``self.oauth_callback_bind``:`self.oauth_callback_port`.
        Bind address supports both IPv4 (e.g. ``0.0.0.0``) and IPv6
        (e.g. ``::``).  On most Linux/macOS systems binding to ``::`` also
        accepts IPv4-mapped connections (dual-stack) unless the kernel has
        ``IPV6_V6ONLY`` forced to 1.  You may also bind to a specific address
        such as ``192.168.1.10`` or ``fe80::1``.

        Returns True if the server was started (or was already running),
        False on failure or when no port is configured.
        The server handles GET /feishu/oauth/callback?code=...&state=...
        """
        if not self.oauth_callback_port:
            return False
        if self._oauth_server is not None:
            return True

        async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            try:
                raw = b""
                while True:
                    try:
                        chunk = await asyncio.wait_for(reader.read(4096), timeout=5.0)
                    except asyncio.TimeoutError:
                        break
                    if not chunk:
                        break
                    raw += chunk
                    if b"\r\n\r\n" in raw or len(raw) > 8192:
                        break

                request = raw.decode("utf-8", errors="replace")
                first_line = request.split("\r\n")[0] if request else ""
                # e.g. "GET /feishu/oauth/callback?code=xxx&state=yyy HTTP/1.1"
                parts = first_line.split(" ")
                path = parts[1] if len(parts) >= 2 else "/"

                parsed = urlparse(path)
                qs = parse_qs(parsed.query)
                code = (qs.get("code") or [None])[0]
                state = (qs.get("state") or [None])[0]
                error = (qs.get("error") or [None])[0]

                html_ok = (
                    "<html><head><meta charset='utf-8'>"
                    "<title>飞书授权</title></head><body>"
                    "<h2>✅ 飞书授权成功！</h2>"
                    "<p>您已成功完成授权，可以关闭此页面并返回聊天窗口。</p>"
                    "</body></html>"
                )
                html_err = (
                    "<html><head><meta charset='utf-8'>"
                    "<title>飞书授权</title></head><body>"
                    "<h2>❌ 飞书授权失败</h2>"
                    "<p>{msg}</p>"
                    "<p>请关闭此页面，在聊天窗口重新发送 /feishu login 重试。</p>"
                    "</body></html>"
                )

                if error:
                    body = html_err.format(msg=f"错误：{error}").encode("utf-8")
                    _write_http(writer, 400, body)
                    return

                if not code or not state:
                    body = html_err.format(msg="缺少 code 或 state 参数").encode("utf-8")
                    _write_http(writer, 400, body)
                    return

                uid = self._pending_states.pop(state, None)
                if uid is None:
                    body = html_err.format(msg="state 无效或已过期，请重新授权").encode("utf-8")
                    _write_http(writer, 400, body)
                    return

                token_data = await self.exchange_auth_code(code)
                if token_data and token_data.get("access_token"):
                    await self.store_oauth_token(
                        user_id=uid,
                        access_token=token_data["access_token"],
                        refresh_token=token_data.get("refresh_token", ""),
                        expires_in=int(token_data.get("expires_in", 7200)),
                        refresh_expires_in=int(token_data.get("refresh_expires_in", 2592000)),
                        scope=token_data.get("scope", ""),
                    )
                    body = html_ok.encode("utf-8")
                    _write_http(writer, 200, body)
                else:
                    body = html_err.format(msg="Token 交换失败，请重新授权").encode("utf-8")
                    _write_http(writer, 500, body)
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

        try:
            self._oauth_server = await asyncio.start_server(
                _handle, host=self.oauth_callback_bind, port=self.oauth_callback_port
            )
            return True
        except Exception:
            self._oauth_server = None
            return False

    async def stop_oauth_callback_server(self) -> None:
        """Stop the OAuth callback HTTP server if running."""
        if self._oauth_server is not None:
            self._oauth_server.close()
            await self._oauth_server.wait_closed()
            self._oauth_server = None

    # ------------------------------------------------------------------
    # Request helper
    # ------------------------------------------------------------------

    async def _resolve_token(self, user_id: Optional[str] = None) -> str:
        if self.auth_mode == "user" and user_id:
            uat = await self.get_user_access_token(user_id)
            if uat:
                return uat
        return await self._get_tenant_token()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_data: Optional[Any] = None,
        extra_headers: Optional[dict] = None,
        raw_response: bool = False,
        user_id: Optional[str] = None,
    ) -> Any:
        token = await self._resolve_token(user_id)
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}
        if not raw_response:
            headers["Content-Type"] = "application/json; charset=utf-8"
        if extra_headers:
            headers.update(extra_headers)

        url = f"{self.base_url}{path}"
        if params:
            params = {k: v for k, v in params.items() if v is not None}

        async with httpx.AsyncClient(timeout=60.0) as hc:
            resp = await hc.request(
                method, url, params=params, json=json_data, headers=headers
            )
            resp.raise_for_status()
            return resp.content if raw_response else resp.json()

    async def get(
        self,
        path: str,
        params: Optional[dict] = None,
        raw_response: bool = False,
        user_id: Optional[str] = None,
    ) -> Any:
        return await self.request(
            "GET", path, params=params, raw_response=raw_response, user_id=user_id
        )

    async def post(
        self,
        path: str,
        data: Optional[Any] = None,
        params: Optional[dict] = None,
        user_id: Optional[str] = None,
    ) -> Any:
        return await self.request("POST", path, json_data=data, params=params, user_id=user_id)

    async def patch(
        self,
        path: str,
        data: Optional[Any] = None,
        params: Optional[dict] = None,
        user_id: Optional[str] = None,
    ) -> Any:
        return await self.request("PATCH", path, json_data=data, params=params, user_id=user_id)

    async def put(
        self,
        path: str,
        data: Optional[Any] = None,
        params: Optional[dict] = None,
        user_id: Optional[str] = None,
    ) -> Any:
        return await self.request("PUT", path, json_data=data, params=params, user_id=user_id)

    async def delete(
        self,
        path: str,
        params: Optional[dict] = None,
        data: Optional[Any] = None,
        user_id: Optional[str] = None,
    ) -> Any:
        return await self.request(
            "DELETE", path, params=params, json_data=data, user_id=user_id
        )

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

    @staticmethod
    def needs_user_auth(code: int) -> bool:
        """Return True if error code indicates a need for user authorization."""
        return code in (
            LARK_ERR_APP_SCOPE_MISSING,
            LARK_ERR_USER_SCOPE_INSUFFICIENT,
            LARK_ERR_TOKEN_INVALID,
            LARK_ERR_TOKEN_EXPIRED,
        )


# ---------------------------------------------------------------------------
# Internal HTTP helper
# ---------------------------------------------------------------------------

def _write_http(writer: asyncio.StreamWriter, status: int, body: bytes) -> None:
    status_text = {200: "OK", 400: "Bad Request", 500: "Internal Server Error"}.get(status, "OK")
    response = (
        f"HTTP/1.1 {status} {status_text}\r\n"
        f"Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode("utf-8") + body
    writer.write(response)
