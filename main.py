# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# AstrBot 飞书工具插件 (Feishu Tools Plugin)
#
# 将飞书/Lark OpenAPI 工具注册为 AstrBot LLM 工具（FunctionTool），
# 让 AI 助手能够直接操作飞书的日历、任务、多维表格、文档、云盘、知识库、电子表格等。
# 支持以租户（机器人）或用户 OAuth 身份操作飞书资源。

from __future__ import annotations

import asyncio
import json
from typing import Any

import astrbot.api.event.filter as filter
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context, Star

from .openclaw_lark import LarkAPIClient, set_lark_client, get_lark_client
from .openclaw_lark.tools import (
    CalendarCalendarTool,
    CalendarEventTool,
    CalendarEventAttendeeTool,
    CalendarFreebusyTool,
    TaskTaskTool,
    TaskTasklistTool,
    TaskCommentTool,
    TaskSubtaskTool,
    TaskSectionTool,
    TaskTaskAgentTool,
    TaskAttachmentTool,
    BitableAppTool,
    BitableTableTool,
    BitableRecordTool,
    BitableFieldTool,
    BitableViewTool,
    FetchDocTool,
    CreateDocTool,
    UpdateDocTool,
    DriveFileTool,
    DocCommentsTool,
    DocMediaTool,
    WikiSpaceTool,
    WikiSpaceNodeTool,
    SheetTool,
    SearchDocWikiTool,
    GetUserTool,
    SearchUserTool,
    ChatTool,
    MessageTool,
)

_ALL_TOOLS = (
    # 日历
    CalendarCalendarTool,
    CalendarEventTool,
    CalendarEventAttendeeTool,
    CalendarFreebusyTool,
    # 任务
    TaskTaskTool,
    TaskTasklistTool,
    TaskCommentTool,
    TaskSubtaskTool,
    TaskSectionTool,
    TaskTaskAgentTool,
    TaskAttachmentTool,
    # 多维表格
    BitableAppTool,
    BitableTableTool,
    BitableRecordTool,
    BitableFieldTool,
    BitableViewTool,
    # 文档
    FetchDocTool,
    CreateDocTool,
    UpdateDocTool,
    # 云盘
    DriveFileTool,
    DocCommentsTool,
    DocMediaTool,
    # 知识库
    WikiSpaceTool,
    WikiSpaceNodeTool,
    # 电子表格
    SheetTool,
    # 搜索
    SearchDocWikiTool,
    # 用户/群聊/消息
    GetUserTool,
    SearchUserTool,
    ChatTool,
    MessageTool,
)


class FeishuToolsPlugin(Star):
    """飞书工具 AstrBot 插件。

    将飞书 Open API 核心功能封装为 LLM 工具，注册到 AstrBot 工具系统中。
    支持以租户（机器人）或用户 OAuth 身份操作飞书资源。

    用户 OAuth 支持两种授权流程：
      - 设备流（Device Flow）：auth_mode=user 且未配置 oauth_callback_port 时使用。
        用户在任意设备上访问授权链接完成授权。
      - Web 流（Authorization Code）：auth_mode=user 且配置了 oauth_callback_port 时使用。
        插件在宿主机启动 HTTP 回调服务器（监听 0.0.0.0），飞书将授权结果重定向回本机。

    命令：
      /feishu           - 查看当前认证状态
      /feishu auth tenant - 切换为租户（机器人）模式（默认）
      /feishu auth user   - 切换为用户 OAuth 模式
      /feishu login     - 发起 OAuth 授权
      /feishu logout    - 撤销当前用户的 OAuth 授权
    """

    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context, config)
        cfg = config or {}

        app_id: str = cfg.get("app_id", "")
        app_secret: str = cfg.get("app_secret", "")
        domain: str = cfg.get("domain", "feishu")
        auth_mode: str = cfg.get("auth_mode", "tenant")
        oauth_callback_port_raw = cfg.get("oauth_callback_port", 0)
        try:
            oauth_callback_port: int = int(oauth_callback_port_raw) if oauth_callback_port_raw else 0
        except (ValueError, TypeError):
            oauth_callback_port = 0
        oauth_callback_host: str = cfg.get("oauth_callback_host", "localhost") or "localhost"
        oauth_callback_bind: str = cfg.get("oauth_callback_bind", "0.0.0.0") or "0.0.0.0"

        if not app_id or not app_secret:
            logger.warning(
                "[feishu_tools] app_id 或 app_secret 未配置，飞书工具将无法正常工作。"
                "请在插件管理面板中填写飞书应用凭据。"
            )

        client = LarkAPIClient(
            app_id=app_id,
            app_secret=app_secret,
            domain=domain,
            auth_mode=auth_mode,
            oauth_callback_port=oauth_callback_port,
            oauth_callback_host=oauth_callback_host,
            oauth_callback_bind=oauth_callback_bind,
        )

        # Wire token persistence to AstrBot KV store
        client.persist_token = self._persist_user_token
        client.load_token = self._load_user_token

        set_lark_client(client)

        self.context.add_llm_tools(*_ALL_TOOLS)

        logger.info(
            f"[feishu_tools] 插件已加载，共注册 {len(_ALL_TOOLS)} 个飞书工具。"
            f"域名：{domain}，认证模式：{auth_mode}。"
        )

        # Start OAuth callback server if user mode and port configured
        if auth_mode == "user" and oauth_callback_port:
            asyncio.create_task(self._start_oauth_server())

    async def _start_oauth_server(self) -> None:
        client = get_lark_client()
        ok = await client.start_oauth_callback_server()
        if ok:
            logger.info(
                f"[feishu_tools] OAuth 回调服务器已启动，"
                f"监听 {client.oauth_callback_bind}:{client.oauth_callback_port}，"
                f"回调地址 {client._callback_redirect_uri()}"
            )
        else:
            logger.warning(
                f"[feishu_tools] OAuth 回调服务器启动失败，"
                f"端口 {client.oauth_callback_port} 可能已被占用。"
                "将回退到设备流（Device Flow）授权。"
            )

    # ------------------------------------------------------------------
    # Token persistence helpers (wired to AstrBot KV store)
    # ------------------------------------------------------------------

    async def _persist_user_token(self, user_id: str, data: dict | None) -> None:
        """Persist or delete a user's OAuth token via AstrBot KV store."""
        key = f"uat:{user_id}"
        if data is None:
            await self.delete_kv_data(key)
        else:
            await self.put_kv_data(key, json.dumps(data))

    async def _load_user_token(self, user_id: str) -> dict | None:
        """Load a user's OAuth token from AstrBot KV store."""
        key = f"uat:{user_id}"
        raw = await self.get_kv_data(key, None)
        if raw and isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception:
                return None
        return None

    # ------------------------------------------------------------------
    # Commands: /feishu [auth [tenant|user] | login | logout]
    # ------------------------------------------------------------------

    @filter.command_group("feishu")
    def feishu(self) -> None:
        """飞书工具插件命令组。"""

    @feishu.command("auth")
    async def feishu_auth(self, event: AstrMessageEvent, mode: str = "") -> Any:
        """查看或切换认证模式。用法：/feishu auth [tenant|user]"""
        client = get_lark_client()
        uid = event.get_sender_id()

        if mode == "tenant":
            client.auth_mode = "tenant"
            yield event.plain_result(
                "✅ 已切换为租户（机器人）认证模式。AI 工具将以机器人身份调用飞书 API。"
            )
            return

        if mode == "user":
            client.auth_mode = "user"
            # Start callback server if port is configured and not yet running
            if client.oauth_callback_port and client._oauth_server is None:
                asyncio.create_task(self._start_oauth_server())
            uat = await client.get_user_access_token(uid)
            if uat:
                yield event.plain_result(
                    "✅ 已切换为用户 OAuth 认证模式。当前用户已授权，AI 工具将以您的身份调用飞书 API。\n"
                    "如需重新授权，请发送 /feishu login。"
                )
            else:
                yield event.plain_result(
                    "✅ 已切换为用户 OAuth 认证模式。\n"
                    "⚠️ 当前用户尚未授权，请发送 /feishu login 完成授权。"
                )
            return

        # No mode specified: show status
        has_uat = bool(await client.get_user_access_token(uid))
        web_mode = bool(client.oauth_callback_port)
        flow_desc = f"Web 回调流（端口 {client.oauth_callback_port}）" if web_mode else "设备流（Device Flow）"
        yield event.plain_result(
            f"飞书工具 - 当前认证模式：{client.auth_mode}\n"
            f"{'✅ 用户已授权 OAuth' if has_uat else '（用户未授权）'}\n"
            f"OAuth 授权流：{flow_desc}\n\n"
            "切换模式：\n"
            "  /feishu auth tenant  - 租户（机器人）模式（默认）\n"
            "  /feishu auth user    - 用户 OAuth 模式"
        )

    @feishu.command("login")
    async def feishu_login(self, event: AstrMessageEvent) -> Any:
        """发起飞书 OAuth 授权。用户模式下自动选择 Web 流或设备流。"""
        client = get_lark_client()
        uid = event.get_sender_id()

        if not client.app_id or not client.app_secret:
            yield event.plain_result(
                "❌ 飞书应用凭据未配置，无法发起授权。请先在插件管理面板中填写 app_id 和 app_secret。"
            )
            return

        # Check if already authorized
        uat = await client.get_user_access_token(uid)
        if uat:
            yield event.plain_result(
                "✅ 您已授权飞书 OAuth。如需重新授权，请先发送 /feishu logout 后重试。"
            )
            return

        # Use web flow if callback port is configured
        use_web_flow = bool(client.oauth_callback_port)
        if use_web_flow:
            # Ensure server is running
            if client._oauth_server is None:
                started = await client.start_oauth_callback_server()
                if not started:
                    logger.warning("[feishu_tools] OAuth 回调服务器启动失败，回退到设备流")
                    use_web_flow = False

        if use_web_flow:
            auth_url, _state = client.generate_web_auth_url(uid)
            yield event.plain_result(
                "🔑 请点击以下链接完成飞书 OAuth 授权：\n\n"
                f"{auth_url}\n\n"
                "在飞书页面确认授权后，回调页面会提示授权成功。\n"
                "授权成功后 AI 工具将以您的身份操作飞书资源。"
            )
            return

        # Device flow (RFC 8628)
        async for msg in self._feishu_device_flow(event, client, uid):
            yield msg

    async def _feishu_device_flow(
        self, event: AstrMessageEvent, client: LarkAPIClient, uid: str
    ) -> Any:
        """Execute RFC 8628 device authorization flow for the given user."""
        try:
            flow = await client.start_device_flow()
        except Exception as e:
            yield event.plain_result(
                f"❌ 发起 OAuth 授权失败：{e}\n"
                "请检查飞书应用配置是否正确，以及应用是否已开启 OAuth2 授权（设备流）。"
            )
            return

        verify_url = flow.get("verification_uri_complete") or flow.get("verification_uri", "")
        expires_in = flow.get("expires_in", 300)
        interval = flow.get("interval", 5)
        device_code = flow.get("device_code", "")

        yield event.plain_result(
            f"🔑 请在 {expires_in} 秒内点击以下链接完成飞书授权（设备流）：\n\n"
            f"{verify_url}\n\n"
            "授权完成后机器人将自动获取令牌（无需额外操作）。\n"
            "授权成功后 AI 工具将以您的身份操作飞书资源。"
        )

        async def _poll() -> None:
            data = await client.poll_device_token(
                device_code=device_code,
                interval=interval,
                max_wait=expires_in,
            )
            if data and data.get("access_token"):
                await client.store_oauth_token(
                    user_id=uid,
                    access_token=data["access_token"],
                    refresh_token=data.get("refresh_token", ""),
                    expires_in=int(data.get("expires_in", 7200)),
                    refresh_expires_in=int(data.get("refresh_expires_in", 2592000)),
                    scope=data.get("scope", ""),
                )
                logger.info(f"[feishu_tools] 用户 {uid} OAuth 授权成功（设备流）。")
            else:
                logger.warning(
                    f"[feishu_tools] 用户 {uid} OAuth 授权未完成（超时或用户拒绝）。"
                )

        asyncio.create_task(_poll())

    @feishu.command("logout")
    async def feishu_logout(self, event: AstrMessageEvent) -> Any:
        """撤销当前用户的飞书 OAuth 授权。"""
        client = get_lark_client()
        uid = event.get_sender_id()
        await client.revoke_user_token(uid)
        yield event.plain_result(
            "✅ 已撤销您的飞书 OAuth 授权。\n"
            "切换回租户模式请使用：/feishu auth tenant"
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def terminate(self) -> None:
        """插件卸载时清理资源。"""
        try:
            client = get_lark_client()
            await client.stop_oauth_callback_server()
        except Exception:
            pass
        logger.info("[feishu_tools] 插件已卸载。")

