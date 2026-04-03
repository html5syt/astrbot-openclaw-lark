# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu user lookup and chat management tools.

from __future__ import annotations

from typing import Any

from astrbot.api import FunctionTool

from ..lark_client import get_lark_client
from ._common import ok, make_tool


# ---------------------------------------------------------------------------
# feishu_get_user
# ---------------------------------------------------------------------------


async def _get_user(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    user_id = kw.get("user_id", "")
    uid_type = kw.get("user_id_type", "open_id")

    if not user_id:
        return ok({"error": "user_id is required"})

    try:
        res = await client.get(
            f"/open-apis/contact/v3/users/{user_id}",
            params={"user_id_type": uid_type},
        )
        client.check(res, "get_user")
        return ok(res.get("data", {}))

    except Exception as e:
        return ok({"error": str(e)})


GetUserTool: FunctionTool = make_tool(
    name="feishu_get_user",
    description=(
        "获取飞书用户信息（以机器人身份）。"
        "通过 open_id、union_id 或 user_id 查询用户的姓名、头像、邮箱、手机号等基本信息。"
    ),
    parameters={
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
    },
    handler=_get_user,
)


# ---------------------------------------------------------------------------
# feishu_search_user
# ---------------------------------------------------------------------------


async def _search_user(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    query = kw.get("query", "")
    if not query:
        return ok({"error": "query is required"})

    try:
        params: dict = {
            "query": query,
            "user_id_type": kw.get("user_id_type", "open_id"),
        }
        if kw.get("page_size"):
            params["page_size"] = kw["page_size"]
        if kw.get("page_token"):
            params["page_token"] = kw["page_token"]

        res = await client.get("/open-apis/search/v1/user", params=params)
        client.check(res, "search_user")
        return ok(res.get("data", {}))

    except Exception as e:
        return ok({"error": str(e)})


SearchUserTool: FunctionTool = make_tool(
    name="feishu_search_user",
    description=(
        "搜索飞书用户（以机器人身份）。"
        "通过姓名、邮箱、手机号等关键词搜索用户。"
    ),
    parameters={
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
    },
    handler=_search_user,
)


# ---------------------------------------------------------------------------
# feishu_chat
# ---------------------------------------------------------------------------


async def _chat(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")
    uid_type = kw.get("user_id_type", "open_id")

    try:
        if action == "search":
            query = kw.get("query", "")
            if not query:
                return ok({"error": "query is required for 'search' action"})
            params: dict = {
                "query": query,
                "user_id_type": uid_type,
            }
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            res = await client.get(
                "/open-apis/im/v1/chats/search", params=params
            )
            client.check(res, "chat.search")
            return ok(res.get("data", {}))

        elif action == "get":
            chat_id = kw.get("chat_id", "")
            if not chat_id:
                return ok({"error": "chat_id is required for 'get' action"})
            res = await client.get(
                f"/open-apis/im/v1/chats/{chat_id}",
                params={"user_id_type": uid_type},
            )
            client.check(res, "chat.get")
            return ok(res.get("data", {}))

        elif action == "list_members":
            chat_id = kw.get("chat_id", "")
            if not chat_id:
                return ok({"error": "chat_id is required for 'list_members' action"})
            params = {"member_id_type": uid_type}
            if kw.get("page_size"):
                params["page_size"] = str(kw["page_size"])
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            res = await client.get(
                f"/open-apis/im/v1/chats/{chat_id}/members",
                params=params,
            )
            client.check(res, "chat.list_members")
            return ok(res.get("data", {}))

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


ChatTool: FunctionTool = make_tool(
    name="feishu_chat",
    description=(
        "飞书群聊管理工具（以机器人身份）。"
        "Actions: search（搜索对机器人可见的群列表）, get（获取指定群的详细信息）, "
        "list_members（列出群成员）。"
        "⚠️ 仅返回机器人已加入的群。"
    ),
    parameters={
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
    },
    handler=_chat,
)

