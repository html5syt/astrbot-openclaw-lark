# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu IM message tools (send, reply, read history, search, resources)

from __future__ import annotations

import json
from typing import Any

from astrbot.api import FunctionTool

from ..lark_client import get_lark_client
from ._common import ok, make_tool


async def _feishu_message_action(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")

    try:
        if action == "search":
            query = kw.get("query", "")
            page_size = kw.get("page_size", 50)
            page_token = kw.get("page_token")
            chat_id = kw.get("chat_id")

            data = {"query": query}
            if chat_id:
                data["chat_ids"] = [chat_id]
            if kw.get("start_time"):
                data["start_time"] = kw["start_time"]
            if kw.get("end_time"):
                data["end_time"] = kw["end_time"]

            params = {"user_id_type": "open_id", "page_size": page_size}
            if page_token:
                params["page_token"] = page_token

            res = await client.post(
                "/open-apis/search/v1/message", data=data, params=params
            )
            client.check(res, "message.search")
            return ok(res.get("data", {}))

        elif action == "list":
            container_id = kw.get("container_id")
            if not container_id:
                return ok({"error": "container_id is required for 'list' action"})

            sort_type = kw.get("sort_type", "ByCreateTimeDesc")

            params = {
                "container_id_type": "chat",
                "container_id": container_id,
                "sort_type": sort_type,
                "page_size": kw.get("page_size", 50),
            }
            if kw.get("start_time"):
                params["start_time"] = kw["start_time"]
            if kw.get("end_time"):
                params["end_time"] = kw["end_time"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]

            res = await client.get("/open-apis/im/v1/messages", params=params)
            client.check(res, "message.list")
            return ok(res.get("data", {}))

        elif action == "send":
            receive_id = kw.get("receive_id")
            if not receive_id:
                return ok({"error": "receive_id is required for 'send' action"})

            msg_type = kw.get("msg_type", "text")
            content = kw.get("content")
            if not content:
                return ok({"error": "content is required for 'send' action"})

            # content payload must be a JSON string.
            content_str = content if isinstance(content, str) else json.dumps(content)

            params = {"receive_id_type": kw.get("receive_id_type", "chat_id")}
            data = {
                "receive_id": receive_id,
                "msg_type": msg_type,
                "content": content_str,
            }
            if kw.get("uuid"):
                data["uuid"] = kw["uuid"]

            res = await client.post(
                "/open-apis/im/v1/messages", data=data, params=params
            )
            client.check(res, "message.send")
            return ok(res.get("data", {}))

        elif action == "reply":
            message_id = kw.get("message_id")
            if not message_id:
                return ok({"error": "message_id is required for 'reply' action"})

            msg_type = kw.get("msg_type", "text")
            content = kw.get("content")
            if not content:
                return ok({"error": "content is required for 'reply' action"})

            content_str = content if isinstance(content, str) else json.dumps(content)

            data = {
                "msg_type": msg_type,
                "content": content_str,
            }
            if "reply_in_thread" in kw:
                data["reply_in_thread"] = kw["reply_in_thread"]
            if kw.get("uuid"):
                data["uuid"] = kw["uuid"]

            res = await client.post(
                f"/open-apis/im/v1/messages/{message_id}/reply", data=data
            )
            client.check(res, "message.reply")
            return ok(res.get("data", {}))

        elif action == "download_resource":
            message_id = kw.get("message_id")
            file_key = kw.get("file_key")
            resource_type = kw.get("resource_type", "image")

            if not message_id or not file_key:
                return ok(
                    {
                        "error": "message_id and file_key are required for 'download_resource' action"
                    }
                )

            res = await client.get(
                f"/open-apis/im/v1/messages/{message_id}/resources/{file_key}",
                params={"type": resource_type},
                raw=True,
            )
            # The API returns raw file bytes.
            # Convert binary data to hex/base64 or just tell user to output it / we return status
            # Because this is a function tool returning a JSON string for LLM, returning raw bytes isn't good.
            # We return success info and file sizes.
            # If AstrBot supports image sending, we might need a special protocol.
            return ok(
                {
                    "success": True,
                    "message": "Resource downloaded successfully. Length: "
                    + str(len(res))
                    + " bytes",
                    "binary_content_length": len(res),
                }
            )

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


MessageTool: FunctionTool = make_tool(
    name="feishu_im_message",
    description=(
        "飞书消息管理工具（群聊/单聊历史读取、消息发送、消息回复、消息搜索、资源下载）。"
        "Actions:\n"
        "- search: 搜索消息（需 query，可选 chat_id）\n"
        "- list: 获取聊天历史记录（需 container_id 此即 chat_id）\n"
        "- send: 发送消息\n"
        "- reply: 回复消息\n"
        "- download_resource: 下载消息里的图片/文件"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "list", "send", "reply", "download_resource"],
            },
            "query": {
                "type": "string",
                "description": "搜索关键词（对于 action=search）",
            },
            "chat_id": {"type": "string", "description": "群聊 ID（用于限制搜索范围）"},
            "container_id": {
                "type": "string",
                "description": "聊天 ID（对于 action=list，即 chat_id）",
            },
            "sort_type": {
                "type": "string",
                "description": "ByCreateTimeDesc 或 ByCreateTimeAsc（对于 action=list）",
            },
            "receive_id": {
                "type": "string",
                "description": "接收者 ID（对于 action=send）",
            },
            "receive_id_type": {
                "type": "string",
                "enum": ["open_id", "user_id", "union_id", "email", "chat_id"],
                "description": "默认 chat_id",
            },
            "message_id": {
                "type": "string",
                "description": "消息 ID（对于 reply 或 download_resource）",
            },
            "msg_type": {
                "type": "string",
                "description": "消息类型（text, post, image, interactive 等）",
            },
            "content": {
                "type": "string",
                "description": 'JSON 字符串格式的消息体，例如 \'{"text":"hello"}\'',
            },
            "reply_in_thread": {
                "type": "boolean",
                "description": "是否作为话题回复（对于 action=reply，默认 false）",
            },
            "file_key": {
                "type": "string",
                "description": "文件/图片 Key（对于 download_resource）",
            },
            "resource_type": {
                "type": "string",
                "enum": ["image", "file"],
                "description": "媒体类型（对于 download_resource）",
            },
            "page_size": {"type": "number", "description": "每页数量"},
            "page_token": {"type": "string", "description": "分页标记"},
        },
        "required": ["action"],
    },
    handler=_feishu_message_action,
)
