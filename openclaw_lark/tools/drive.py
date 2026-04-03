# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu Drive / Doc media / Doc comments tools.

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
# feishu_drive_file
# ---------------------------------------------------------------------------


@dataclass
class DriveFileTool(FunctionTool[AstrAgentContext]):
    """飞书云空间文件管理工具：列出、获取元数据、复制、移动、删除、下载文件及创建文件夹。"""

    name: str = "feishu_drive_file"
    description: str = (
        "飞书云空间文件管理工具（以机器人身份）。"
        "Actions: list（列出文件/文件夹内容）, get_meta（批量获取文件元数据）, "
        "copy（复制文件）, move（移动文件）, delete（删除文件）, "
        "create_folder（创建文件夹）, download（下载文件，返回 base64 内容）。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
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
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        action = kwargs.get("action")

        try:
            if action == "list":
                params: dict = {}
                if kwargs.get("folder_token"):
                    params["folder_token"] = kwargs["folder_token"]
                if kwargs.get("page_size"):
                    params["page_size"] = kwargs["page_size"]
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                if kwargs.get("order_by"):
                    params["order_by"] = kwargs["order_by"]
                if kwargs.get("direction"):
                    params["direction"] = kwargs["direction"]
                res = await client.get("/open-apis/drive/v1/files", params=params)
                client.check(res, "drive_file.list")
                return _ok(res.get("data", {}))

            elif action == "get_meta":
                docs = kwargs.get("request_docs", [])
                if not docs:
                    return _ok({"error": "request_docs is required for 'get_meta' action"})
                res = await client.post(
                    "/open-apis/drive/v1/metas/batch_query",
                    {"request_docs": docs},
                )
                client.check(res, "drive_file.get_meta")
                return _ok(res.get("data", {}))

            elif action == "copy":
                file_token = kwargs.get("file_token", "")
                if not file_token:
                    return _ok({"error": "file_token is required for 'copy' action"})
                data: dict = {}
                if kwargs.get("name"):
                    data["name"] = kwargs["name"]
                if kwargs.get("target_parent_token"):
                    data["target_parent_token"] = kwargs["target_parent_token"]
                res = await client.post(
                    f"/open-apis/drive/v1/files/{file_token}/copy", data
                )
                client.check(res, "drive_file.copy")
                return _ok(res.get("data", {}))

            elif action == "move":
                file_token = kwargs.get("file_token", "")
                if not file_token:
                    return _ok({"error": "file_token is required for 'move' action"})
                data = {}
                if kwargs.get("target_parent_token"):
                    data["target_parent_token"] = kwargs["target_parent_token"]
                res = await client.post(
                    f"/open-apis/drive/v1/files/{file_token}/move", data
                )
                client.check(res, "drive_file.move")
                return _ok(res.get("data", {}))

            elif action == "delete":
                file_token = kwargs.get("file_token", "")
                file_type = kwargs.get("file_type", "")
                if not file_token:
                    return _ok({"error": "file_token is required for 'delete' action"})
                if not file_type:
                    return _ok({"error": "file_type is required for 'delete' action"})
                res = await client.delete(
                    f"/open-apis/drive/v1/files/{file_token}",
                    params={"type": file_type},
                )
                client.check(res, "drive_file.delete")
                return _ok({"success": True, "task_id": res.get("data", {}).get("task_id")})

            elif action == "create_folder":
                params = {}
                data = {}
                if kwargs.get("name"):
                    data["name"] = kwargs["name"]
                if kwargs.get("folder_token"):
                    data["folder_token"] = kwargs["folder_token"]
                res = await client.post("/open-apis/drive/v1/files/create_folder", data)
                client.check(res, "drive_file.create_folder")
                return _ok(res.get("data", {}))

            elif action == "download":
                file_token = kwargs.get("file_token", "")
                if not file_token:
                    return _ok({"error": "file_token is required for 'download' action"})
                raw = await client.get(
                    f"/open-apis/drive/v1/files/{file_token}/download",
                    raw_response=True,
                )
                import base64
                encoded = base64.b64encode(raw).decode("utf-8")
                return _ok({"file_token": file_token, "content_base64": encoded})

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})


# ---------------------------------------------------------------------------
# feishu_doc_comments
# ---------------------------------------------------------------------------


@dataclass
class DocCommentsTool(FunctionTool[AstrAgentContext]):
    """飞书文档评论管理工具：创建、列出、删除文档评论。"""

    name: str = "feishu_doc_comments"
    description: str = (
        "飞书文档评论管理工具（以机器人身份）。"
        "Actions: create（添加评论）, list（获取评论列表）, delete（删除评论）。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
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
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        action = kwargs.get("action")
        file_token = kwargs.get("file_token", "")
        file_type = kwargs.get("file_type", "")

        try:
            if action == "create":
                if not kwargs.get("content"):
                    return _ok({"error": "content is required for 'create' action"})
                data = {
                    "file_token": file_token,
                    "file_type": file_type,
                    "comment_list": [
                        {
                            "reply_list": {
                                "replies": [
                                    {
                                        "content": {
                                            "elements": [{"type": "text_run", "text_run": {"text": kwargs["content"]}}]
                                        }
                                    }
                                ]
                            }
                        }
                    ],
                }
                res = await client.post("/open-apis/drive/v1/files/comments", data)
                client.check(res, "doc_comments.create")
                return _ok(res.get("data", {}))

            elif action == "list":
                params: dict = {
                    "file_token": file_token,
                    "file_type": file_type,
                }
                if kwargs.get("page_size"):
                    params["page_size"] = kwargs["page_size"]
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                res = await client.get("/open-apis/drive/v1/files/comments", params=params)
                client.check(res, "doc_comments.list")
                return _ok(res.get("data", {}))

            elif action == "delete":
                comment_id = kwargs.get("comment_id", "")
                if not comment_id:
                    return _ok({"error": "comment_id is required for 'delete' action"})
                res = await client.delete(
                    f"/open-apis/drive/v1/files/{file_token}/comments/{comment_id}",
                    params={"file_type": file_type},
                )
                client.check(res, "doc_comments.delete")
                return _ok({"success": True})

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})


# ---------------------------------------------------------------------------
# feishu_doc_media
# ---------------------------------------------------------------------------


@dataclass
class DocMediaTool(FunctionTool[AstrAgentContext]):
    """飞书文档媒体资源工具：下载文档中的图片、文件等媒体资源。"""

    name: str = "feishu_doc_media"
    description: str = (
        "飞书文档媒体资源工具（以机器人身份）。"
        "Actions: download（下载文档中的图片/文件资源）。"
        "返回资源的 base64 编码内容。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
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
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        action = kwargs.get("action")
        file_token = kwargs.get("file_token", "")

        try:
            if action == "download":
                if not file_token:
                    return _ok({"error": "file_token is required for 'download' action"})

                params: dict = {}
                if kwargs.get("extra"):
                    params["extra"] = kwargs["extra"]

                raw = await client.get(
                    f"/open-apis/drive/v1/medias/{file_token}/download",
                    params=params,
                    raw_response=True,
                )
                import base64
                encoded = base64.b64encode(raw).decode("utf-8")
                return _ok({"file_token": file_token, "content_base64": encoded})

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})
