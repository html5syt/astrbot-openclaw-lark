# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu document tools (fetch, create, update).
# Supports both MCP server and direct Feishu REST API.

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext

from ..lark_client import get_lark_client


def _ok(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _extract_doc_id(doc_id_or_url: str) -> str:
    """Extract document ID from a URL or return the ID directly."""
    if not doc_id_or_url:
        return ""
    # Try to extract from URL patterns like:
    # https://xxx.feishu.cn/docx/TOKEN
    # https://xxx.feishu.cn/document/doxcnXXX
    match = re.search(
        r"/(?:docx|docs?|document|wiki)/([A-Za-z0-9_-]+)", doc_id_or_url
    )
    if match:
        return match.group(1)
    # Return as-is if it looks like a token
    return doc_id_or_url


# ---------------------------------------------------------------------------
# feishu_fetch_doc
# ---------------------------------------------------------------------------


@dataclass
class FetchDocTool(FunctionTool[AstrAgentContext]):
    """获取飞书云文档内容，返回 Markdown 格式文本。"""

    name: str = "feishu_fetch_doc"
    description: str = (
        "获取飞书云文档内容，返回文档标题和文本内容。"
        "支持通过 doc_id（文档 ID 或 URL）指定文档。"
        "如配置了 MCP 服务，将返回 Lark-flavored Markdown 格式内容（更完整）；"
        "否则返回 plain text 格式内容。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "doc_id": {
                    "type": "string",
                    "description": "文档 ID 或飞书文档 URL（支持自动解析）",
                },
                "offset": {
                    "type": "number",
                    "description": "字符偏移量（可选，默认 0）。用于大文档分页获取。",
                },
                "limit": {
                    "type": "number",
                    "description": "返回最大字符数（可选）。仅在用户明确要求分页时使用。",
                },
            },
            "required": ["doc_id"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        doc_id = _extract_doc_id(kwargs.get("doc_id", ""))
        if not doc_id:
            return _ok({"error": "doc_id is required"})

        try:
            # If MCP is configured, use it for richer Markdown output
            if client.has_mcp():
                args: dict = {"doc_id": kwargs["doc_id"]}
                if kwargs.get("offset"):
                    args["offset"] = kwargs["offset"]
                if kwargs.get("limit"):
                    args["limit"] = kwargs["limit"]
                result = await client.mcp_call("fetch-doc", args)
                return str(result)

            # Fallback: use Feishu Docx REST API for raw content
            res = await client.get(
                f"/open-apis/docx/v1/documents/{doc_id}/raw_content"
            )
            client.check(res, "fetch_doc")
            data = res.get("data", {})
            content = data.get("content", "")

            # Apply offset/limit if specified
            offset = kwargs.get("offset", 0) or 0
            limit = kwargs.get("limit")
            if offset > 0:
                content = content[offset:]
            if limit:
                content = content[:limit]

            # Also get document metadata
            meta_res = await client.get(f"/open-apis/docx/v1/documents/{doc_id}")
            title = ""
            if meta_res.get("code") == 0:
                title = meta_res.get("data", {}).get("document", {}).get("title", "")

            return _ok({
                "doc_id": doc_id,
                "title": title,
                "content": content,
            })

        except Exception as e:
            return _ok({"error": str(e)})


# ---------------------------------------------------------------------------
# feishu_create_doc
# ---------------------------------------------------------------------------


@dataclass
class CreateDocTool(FunctionTool[AstrAgentContext]):
    """创建新的飞书云文档。"""

    name: str = "feishu_create_doc"
    description: str = (
        "创建新的飞书云文档，返回文档 ID 和访问链接。"
        "如配置了 MCP 服务，支持从 Lark-flavored Markdown 内容创建文档（更完整的格式支持）；"
        "否则创建空白文档（可指定标题和文件夹位置）。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "文档标题",
                },
                "markdown": {
                    "type": "string",
                    "description": (
                        "文档的 Markdown 内容（Lark-flavored Markdown 格式）。"
                        "仅在 MCP 服务配置时生效，将用于创建有内容的文档。"
                    ),
                },
                "folder_token": {
                    "type": "string",
                    "description": "目标文件夹 token（可选，不填则在根目录创建）",
                },
                "space_id": {
                    "type": "string",
                    "description": "知识库空间 ID（可选，在知识库中创建时使用）",
                },
                "parent_node_token": {
                    "type": "string",
                    "description": "父节点 token（可选，在知识库中创建时使用）",
                },
            },
            "required": [],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()

        try:
            # If MCP is configured, use it for rich content creation
            if client.has_mcp():
                args: dict = {}
                if kwargs.get("markdown"):
                    args["markdown"] = kwargs["markdown"]
                if kwargs.get("title"):
                    args["title"] = kwargs["title"]
                if kwargs.get("folder_token"):
                    args["folder_token"] = kwargs["folder_token"]
                if kwargs.get("space_id"):
                    args["space_id"] = kwargs["space_id"]
                if kwargs.get("parent_node_token"):
                    args["parent_node_token"] = kwargs["parent_node_token"]
                result = await client.mcp_call("create-doc", args)
                return str(result)

            # Fallback: create document using Docx API
            data: dict = {}
            if kwargs.get("title"):
                data["title"] = kwargs["title"]
            if kwargs.get("folder_token"):
                data["folder_token"] = kwargs["folder_token"]

            res = await client.post("/open-apis/docx/v1/documents", data)
            client.check(res, "create_doc")
            doc_info = res.get("data", {}).get("document", {})
            doc_id = doc_info.get("document_id", "")
            doc_url = doc_info.get("revision_id", "")

            return _ok({
                "doc_id": doc_id,
                "document": doc_info,
            })

        except Exception as e:
            return _ok({"error": str(e)})


# ---------------------------------------------------------------------------
# feishu_update_doc
# ---------------------------------------------------------------------------


@dataclass
class UpdateDocTool(FunctionTool[AstrAgentContext]):
    """更新飞书云文档内容。"""

    name: str = "feishu_update_doc"
    description: str = (
        "更新飞书云文档内容。"
        "如配置了 MCP 服务，支持 7 种更新模式（append/overwrite/replace_range/replace_all/"
        "insert_before/insert_after/delete_range）；"
        "否则支持 append（追加内容）操作。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "doc_id": {
                    "type": "string",
                    "description": "文档 ID 或飞书文档 URL",
                },
                "mode": {
                    "type": "string",
                    "enum": ["append", "overwrite", "replace_range", "replace_all", "insert_before", "insert_after", "delete_range"],
                    "description": (
                        "更新模式（MCP 模式下支持全部；非 MCP 仅支持 append）。"
                        "append: 追加内容到文档末尾；"
                        "overwrite: 覆盖全文（慎用，可能丢失图片、评论）；"
                        "replace_range: 定位替换；replace_all: 全文替换；"
                        "insert_before/insert_after: 前后插入；delete_range: 删除范围。"
                    ),
                },
                "content": {
                    "type": "string",
                    "description": "要写入的 Markdown 内容",
                },
                "selection_with_ellipsis": {
                    "type": "string",
                    "description": (
                        "内容定位（mode=replace_range/replace_all/insert_before/insert_after/delete_range 时使用）。"
                        "格式：'开头内容...结尾内容'（范围匹配）或完整文本（精确匹配）。"
                    ),
                },
            },
            "required": ["doc_id", "mode"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        doc_id = _extract_doc_id(kwargs.get("doc_id", ""))
        mode = kwargs.get("mode", "append")

        if not doc_id:
            return _ok({"error": "doc_id is required"})

        try:
            # If MCP is configured, delegate to MCP server
            if client.has_mcp():
                args: dict = {"doc_id": kwargs["doc_id"], "mode": mode}
                if kwargs.get("content"):
                    args["content"] = kwargs["content"]
                if kwargs.get("selection_with_ellipsis"):
                    args["selection_with_ellipsis"] = kwargs["selection_with_ellipsis"]
                result = await client.mcp_call("update-doc", args)
                return str(result)

            # Fallback: only "append" is supported via REST API
            if mode != "append":
                return _ok({
                    "error": (
                        f"Mode '{mode}' requires MCP service. "
                        "Please configure mcp_base_url in plugin settings, "
                        "or use 'append' mode."
                    )
                })

            content = kwargs.get("content", "")
            if not content:
                return _ok({"error": "content is required for 'append' mode"})

            # Append plain text using block API
            # First get the document to find the last block
            doc_res = await client.get(f"/open-apis/docx/v1/documents/{doc_id}")
            client.check(doc_res, "update_doc.get_doc")
            revision_id = doc_res.get("data", {}).get("document", {}).get("revision_id", -1)

            # Append text as a paragraph block to the end
            block_data = {
                "children": [
                    {
                        "block_type": 2,  # paragraph
                        "paragraph": {
                            "elements": [
                                {
                                    "type": 0,  # text run
                                    "text_run": {"content": content},
                                }
                            ]
                        },
                    }
                ],
                "index": -1,  # append to end
            }

            res = await client.post(
                f"/open-apis/docx/v1/documents/{doc_id}/blocks/children",
                block_data,
            )
            client.check(res, "update_doc.append")
            return _ok({"success": True, "doc_id": doc_id})

        except Exception as e:
            return _ok({"error": str(e)})
