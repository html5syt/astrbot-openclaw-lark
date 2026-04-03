# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu user lookup and chat management tools.

from __future__ import annotations

import json
from typing import Any

from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext

from ..lark_client import get_lark_client


def _ok(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# feishu_get_user
# ---------------------------------------------------------------------------


@dataclass
class GetUserTool(FunctionTool[AstrAgentContext]):
    """获取飞书用户信息。"""

    name: str = "feishu_get_user"
    description: str = (
        "获取飞书用户信息（以机器人身份）。"
        "通过 open_id、union_id 或 user_id 查询用户的姓名、头像、邮箱、手机号等基本信息。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户 ID（必填）",
                },
                "user_id_type": {
                    "type": "string",
                    "enum": ["open_id", "union_id", "user_id"],
                    "description": "用户 ID 类型（默认 open_id）",
                },
            },
            "required": ["user_id"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        user_id = kwargs.get("user_id", "")
        uid_type = kwargs.get("user_id_type", "open_id")

        if not user_id:
            return _ok({"error": "user_id is required"})

        try:
            res = await client.get(
                f"/open-apis/contact/v3/users/{user_id}",
                params={"user_id_type": uid_type},
            )
            client.check(res, "get_user")
            return _ok(res.get("data", {}))

        except Exception as e:
            return _ok({"error": str(e)})


# ---------------------------------------------------------------------------
# feishu_search_user
# ---------------------------------------------------------------------------


@dataclass
class SearchUserTool(FunctionTool[AstrAgentContext]):
    """搜索飞书用户。"""

    name: str = "feishu_search_user"
    description: str = (
        "搜索飞书用户（以机器人身份）。"
        "通过姓名、邮箱、手机号等关键词搜索用户。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词（必填），支持姓名、邮箱、手机号",
                },
                "page_size": {
                    "type": "number",
                    "description": "每页数量（默认 20，最大 200）",
                },
                "page_token": {"type": "string", "description": "分页标记"},
                "user_id_type": {
                    "type": "string",
                    "enum": ["open_id", "union_id", "user_id"],
                    "description": "用户 ID 类型（默认 open_id）",
                },
            },
            "required": ["query"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        query = kwargs.get("query", "")
        if not query:
            return _ok({"error": "query is required"})

        try:
            params: dict = {
                "query": query,
                "user_id_type": kwargs.get("user_id_type", "open_id"),
            }
            if kwargs.get("page_size"):
                params["page_size"] = kwargs["page_size"]
            if kwargs.get("page_token"):
                params["page_token"] = kwargs["page_token"]

            res = await client.get("/open-apis/search/v1/user", params=params)
            client.check(res, "search_user")
            return _ok(res.get("data", {}))

        except Exception as e:
            return _ok({"error": str(e)})


# ---------------------------------------------------------------------------
# feishu_chat
# ---------------------------------------------------------------------------


@dataclass
class ChatTool(FunctionTool[AstrAgentContext]):
    """飞书群聊管理工具：搜索群聊、获取群聊详情。"""

    name: str = "feishu_chat"
    description: str = (
        "飞书群聊管理工具（以机器人身份）。"
        "Actions: search（搜索对机器人可见的群列表）, get（获取指定群的详细信息）, "
        "list_members（列出群成员）。"
        "⚠️ 仅返回机器人已加入的群。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "get", "list_members"],
                    "description": "操作类型",
                },
                "query": {
                    "type": "string",
                    "description": "搜索关键词（action=search 时必填），支持群名称、成员名称等模糊搜索",
                },
                "chat_id": {
                    "type": "string",
                    "description": "群 ID（action=get/list_members 时必填，格式如 oc_xxx）",
                },
                "page_size": {
                    "type": "number",
                    "description": "每页数量（action=search/list_members，默认 20）",
                },
                "page_token": {"type": "string", "description": "分页标记"},
                "user_id_type": {
                    "type": "string",
                    "enum": ["open_id", "union_id", "user_id"],
                    "description": "用户 ID 类型（默认 open_id）",
                },
            },
            "required": ["action"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        action = kwargs.get("action")
        uid_type = kwargs.get("user_id_type", "open_id")

        try:
            if action == "search":
                query = kwargs.get("query", "")
                if not query:
                    return _ok({"error": "query is required for 'search' action"})
                params: dict = {
                    "query": query,
                    "user_id_type": uid_type,
                }
                if kwargs.get("page_size"):
                    params["page_size"] = kwargs["page_size"]
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                res = await client.get(
                    "/open-apis/im/v1/chats/search", params=params
                )
                client.check(res, "chat.search")
                return _ok(res.get("data", {}))

            elif action == "get":
                chat_id = kwargs.get("chat_id", "")
                if not chat_id:
                    return _ok({"error": "chat_id is required for 'get' action"})
                res = await client.get(
                    f"/open-apis/im/v1/chats/{chat_id}",
                    params={"user_id_type": uid_type},
                )
                client.check(res, "chat.get")
                return _ok(res.get("data", {}))

            elif action == "list_members":
                chat_id = kwargs.get("chat_id", "")
                if not chat_id:
                    return _ok({"error": "chat_id is required for 'list_members' action"})
                params = {"member_id_type": uid_type}
                if kwargs.get("page_size"):
                    params["page_size"] = str(kwargs["page_size"])
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                res = await client.get(
                    f"/open-apis/im/v1/chats/{chat_id}/members",
                    params=params,
                )
                client.check(res, "chat.list_members")
                return _ok(res.get("data", {}))

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})
