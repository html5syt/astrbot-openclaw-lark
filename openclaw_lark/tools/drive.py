# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu Drive / Doc media / Doc comments tools.

from __future__ import annotations

import base64
from typing import Any

from astrbot.api import FunctionTool

from ..lark_client import get_lark_client
from ._common import ok, make_tool


# ---------------------------------------------------------------------------
# feishu_drive_file
# ---------------------------------------------------------------------------


async def _drive_file(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")

    try:
        if action == "list":
            params: dict = {}
            if kw.get("folder_token"):
                params["folder_token"] = kw["folder_token"]
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            if kw.get("order_by"):
                params["order_by"] = kw["order_by"]
            if kw.get("direction"):
                params["direction"] = kw["direction"]
            res = await client.get("/open-apis/drive/v1/files", params=params)
            client.check(res, "drive_file.list")
            return ok(res.get("data", {}))

        elif action == "get_meta":
            docs = kw.get("request_docs", [])
            if not docs:
                return ok({"error": "request_docs is required for 'get_meta' action"})
            res = await client.post(
                "/open-apis/drive/v1/metas/batch_query",
                {"request_docs": docs},
            )
            client.check(res, "drive_file.get_meta")
            return ok(res.get("data", {}))

        elif action == "copy":
            file_token = kw.get("file_token", "")
            if not file_token:
                return ok({"error": "file_token is required for 'copy' action"})
            data: dict = {}
            if kw.get("name"):
                data["name"] = kw["name"]
            if kw.get("target_parent_token"):
                data["target_parent_token"] = kw["target_parent_token"]
            res = await client.post(
                f"/open-apis/drive/v1/files/{file_token}/copy", data
            )
            client.check(res, "drive_file.copy")
            return ok(res.get("data", {}))

        elif action == "move":
            file_token = kw.get("file_token", "")
            if not file_token:
                return ok({"error": "file_token is required for 'move' action"})
            data = {}
            if kw.get("target_parent_token"):
                data["target_parent_token"] = kw["target_parent_token"]
            res = await client.post(
                f"/open-apis/drive/v1/files/{file_token}/move", data
            )
            client.check(res, "drive_file.move")
            return ok(res.get("data", {}))

        elif action == "delete":
            file_token = kw.get("file_token", "")
            file_type = kw.get("file_type", "")
            if not file_token:
                return ok({"error": "file_token is required for 'delete' action"})
            if not file_type:
                return ok({"error": "file_type is required for 'delete' action"})
            res = await client.delete(
                f"/open-apis/drive/v1/files/{file_token}",
                params={"type": file_type},
            )
            client.check(res, "drive_file.delete")
            return ok({"success": True, "task_id": res.get("data", {}).get("task_id")})

        elif action == "create_folder":
            data = {}
            if kw.get("name"):
                data["name"] = kw["name"]
            if kw.get("folder_token"):
                data["folder_token"] = kw["folder_token"]
            res = await client.post("/open-apis/drive/v1/files/create_folder", data)
            client.check(res, "drive_file.create_folder")
            return ok(res.get("data", {}))

        elif action == "download":
            file_token = kw.get("file_token", "")
            if not file_token:
                return ok({"error": "file_token is required for 'download' action"})
            raw = await client.get(
                f"/open-apis/drive/v1/files/{file_token}/download",
                raw_response=True,
            )
            encoded = base64.b64encode(raw).decode("utf-8")
            return ok({"file_token": file_token, "content_base64": encoded})

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


DriveFileTool: FunctionTool = make_tool(
    name="feishu_drive_file",
    description=(
        "飞书云空间文件管理工具（以机器人身份）。"
        "Actions: list（列出文件/文件夹内容）, get_meta（批量获取文件元数据）, "
        "copy（复制文件）, move（移动文件）, delete（删除文件）, "
        "create_folder（创建文件夹）, download（下载文件，返回 base64 内容）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "get_meta", "copy", "move", "delete", "create_folder", "download"],
                "description": "操作类型",
            },
            "folder_token": {
                "type": "string",
                "description": "文件夹 token（action=list/create_folder 时可选，默认我的空间根目录）",
            },
            "file_token": {
                "type": "string",
                "description": "文件 token（action=copy/move/delete/download 时必填）",
            },
            "file_type": {
                "type": "string",
                "description": "文件类型（action=delete 时必填）：doc, docx, sheet, bitable, file, folder, mindnote, slides",
            },
            "name": {
                "type": "string",
                "description": "文件/文件夹名称（action=copy/create_folder 时可选）",
            },
            "target_parent_token": {
                "type": "string",
                "description": "目标文件夹 token（action=copy/move 时可选）",
            },
            "request_docs": {
                "type": "array",
                "description": "文档列表（action=get_meta 时必填）",
                "items": {
                    "type": "object",
                    "properties": {
                        "doc_token": {"type": "string"},
                        "doc_type": {"type": "string"},
                    },
                },
            },
            "page_size": {"type": "number", "description": "每页数量（action=list，默认 200，最大 200）"},
            "page_token": {"type": "string", "description": "分页标记"},
            "order_by": {
                "type": "string",
                "enum": ["EditedTime", "CreatedTime"],
                "description": "排序方式（action=list）",
            },
            "direction": {
                "type": "string",
                "enum": ["ASC", "DESC"],
                "description": "排序方向（action=list）",
            },
        },
        "required": ["action"],
    },
    handler=_drive_file,
)


# ---------------------------------------------------------------------------
# feishu_doc_comments
# ---------------------------------------------------------------------------


async def _doc_comments(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")
    file_token = kw.get("file_token", "")
    file_type = kw.get("file_type", "")

    try:
        if action == "create":
            if not kw.get("content"):
                return ok({"error": "content is required for 'create' action"})
            data = {
                "file_token": file_token,
                "file_type": file_type,
                "comment_list": [
                    {
                        "reply_list": {
                            "replies": [
                                {
                                    "content": {
                                        "elements": [{"type": "text_run", "text_run": {"text": kw["content"]}}]
                                    }
                                }
                            ]
                        }
                    }
                ],
            }
            res = await client.post("/open-apis/drive/v1/files/comments", data)
            client.check(res, "doc_comments.create")
            return ok(res.get("data", {}))

        elif action == "list":
            params: dict = {
                "file_token": file_token,
                "file_type": file_type,
            }
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            res = await client.get("/open-apis/drive/v1/files/comments", params=params)
            client.check(res, "doc_comments.list")
            return ok(res.get("data", {}))

        elif action == "delete":
            comment_id = kw.get("comment_id", "")
            if not comment_id:
                return ok({"error": "comment_id is required for 'delete' action"})
            res = await client.delete(
                f"/open-apis/drive/v1/files/{file_token}/comments/{comment_id}",
                params={"file_type": file_type},
            )
            client.check(res, "doc_comments.delete")
            return ok({"success": True})

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


DocCommentsTool: FunctionTool = make_tool(
    name="feishu_doc_comments",
    description=(
        "飞书文档评论管理工具（以机器人身份）。"
        "Actions: create（添加评论）, list（获取评论列表）, delete（删除评论）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "delete"],
                "description": "操作类型",
            },
            "file_token": {
                "type": "string",
                "description": "文档 token（必填）",
            },
            "file_type": {
                "type": "string",
                "description": "文档类型（必填）：docx, doc, sheet, bitable, mindnote, slides, file",
            },
            "comment_id": {
                "type": "string",
                "description": "评论 ID（action=delete 时必填）",
            },
            "content": {
                "type": "string",
                "description": "评论内容（action=create 时必填）",
            },
            "page_size": {"type": "number", "description": "每页数量"},
            "page_token": {"type": "string", "description": "分页标记"},
        },
        "required": ["action", "file_token", "file_type"],
    },
    handler=_doc_comments,
)


# ---------------------------------------------------------------------------
# feishu_doc_media
# ---------------------------------------------------------------------------


async def _doc_media(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")
    file_token = kw.get("file_token", "")

    try:
        if action == "download":
            if not file_token:
                return ok({"error": "file_token is required for 'download' action"})

            params: dict = {}
            if kw.get("extra"):
                params["extra"] = kw["extra"]

            raw = await client.get(
                f"/open-apis/drive/v1/medias/{file_token}/download",
                params=params,
                raw_response=True,
            )
            encoded = base64.b64encode(raw).decode("utf-8")
            return ok({"file_token": file_token, "content_base64": encoded})

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


DocMediaTool: FunctionTool = make_tool(
    name="feishu_doc_media",
    description=(
        "飞书文档媒体资源工具（以机器人身份）。"
        "Actions: download（下载文档中的图片/文件资源）。"
        "返回资源的 base64 编码内容。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["download"],
                "description": "操作类型（固定为 download）",
            },
            "file_token": {
                "type": "string",
                "description": "媒体资源 token（从文档内容中获取）",
            },
            "extra": {
                "type": "string",
                "description": "额外信息（可选）",
            },
        },
        "required": ["action", "file_token"],
    },
    handler=_doc_media,
)
