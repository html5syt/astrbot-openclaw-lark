# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu document tools (fetch, create, update).
# Uses direct Feishu REST API.

from __future__ import annotations

from typing import Any

from astrbot.api import FunctionTool

from ..lark_client import get_lark_client
from ._common import ok, make_tool, extract_doc_id


def _make_text_block(text: str) -> dict:
    """Build a paragraph block structure for the Feishu docx blocks API."""
    return {
        "block_type": 2,
        "paragraph": {
            "elements": [{"type": 0, "text_run": {"content": text}}]
        },
    }


# ---------------------------------------------------------------------------
# feishu_fetch_doc
# ---------------------------------------------------------------------------


async def _fetch_doc(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    doc_id = extract_doc_id(kw.get("doc_id", ""))
    if not doc_id:
        return ok({"error": "doc_id is required"})

    try:
        res = await client.get(
            f"/open-apis/docx/v1/documents/{doc_id}/raw_content"
        )
        client.check(res, "fetch_doc")
        data = res.get("data", {})
        content = data.get("content", "")

        # Apply offset/limit if specified
        offset = kw.get("offset", 0) or 0
        limit = kw.get("limit")
        if offset > 0:
            content = content[offset:]
        if limit:
            content = content[:limit]

        # Get document metadata for title
        meta_res = await client.get(f"/open-apis/docx/v1/documents/{doc_id}")
        title = ""
        if meta_res.get("code") == 0:
            title = meta_res.get("data", {}).get("document", {}).get("title", "")

        return ok({
            "doc_id": doc_id,
            "title": title,
            "content": content,
        })

    except Exception as e:
        return ok({"error": str(e)})


FetchDocTool: FunctionTool = make_tool(
    name="feishu_fetch_doc",
    description=(
        "获取飞书云文档内容，返回文档标题和文本内容。"
        "支持通过 doc_id（文档 ID 或 URL）指定文档。"
        "返回 plain text 格式内容。支持 offset/limit 分页。"
    ),
    parameters={
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
    },
    handler=_fetch_doc,
)


# ---------------------------------------------------------------------------
# feishu_create_doc
# ---------------------------------------------------------------------------


async def _create_doc(event: Any, **kw: Any) -> str:
    client = get_lark_client()

    try:
        data: dict = {}
        if kw.get("title"):
            data["title"] = kw["title"]
        if kw.get("folder_token"):
            data["folder_token"] = kw["folder_token"]

        res = await client.post("/open-apis/docx/v1/documents", data)
        client.check(res, "create_doc")
        doc_info = res.get("data", {}).get("document", {})
        doc_id = doc_info.get("document_id", "")

        # Optionally add initial content as text blocks
        if kw.get("markdown") and doc_id:
            content = kw["markdown"]
            # Split content into paragraphs and create blocks
            paragraphs = [p for p in content.split("\n") if p.strip()]
            if paragraphs:
                children = [_make_text_block(p) for p in paragraphs]
                await client.post(
                    f"/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
                    {"children": children, "index": -1},
                )

        return ok({
            "doc_id": doc_id,
            "document": doc_info,
        })

    except Exception as e:
        return ok({"error": str(e)})


CreateDocTool: FunctionTool = make_tool(
    name="feishu_create_doc",
    description=(
        "创建新的飞书云文档，返回文档 ID 和元数据。"
        "可指定标题、文件夹位置。如提供 markdown 内容，将作为初始文本块写入文档。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "文档标题",
            },
            "markdown": {
                "type": "string",
                "description": "初始文档内容（可选）。将按段落拆分后以文本块写入文档。",
            },
            "folder_token": {
                "type": "string",
                "description": "目标文件夹 token（可选，不填则在根目录创建）",
            },
        },
        "required": [],
    },
    handler=_create_doc,
)


# ---------------------------------------------------------------------------
# feishu_update_doc
# ---------------------------------------------------------------------------


async def _update_doc(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    doc_id = extract_doc_id(kw.get("doc_id", ""))
    mode = kw.get("mode", "append")

    if not doc_id:
        return ok({"error": "doc_id is required"})

    content = kw.get("content", "")

    try:
        if mode == "append":
            if not content:
                return ok({"error": "content is required for 'append' mode"})
            # Append text block to end of document using doc_id as root block id
            block_data = {
                "children": [_make_text_block(content)],
                "index": -1,
            }
            res = await client.post(
                f"/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
                block_data,
            )
            client.check(res, "update_doc.append")
            return ok({"success": True, "doc_id": doc_id})

        elif mode in ("replace_all", "overwrite"):
            if not content:
                return ok({"error": "content is required for 'replace_all'/'overwrite' mode"})

            # Step 1: Get current blocks to find children count
            blocks_res = await client.get(
                f"/open-apis/docx/v1/documents/{doc_id}/blocks",
                params={"page_size": 500},
            )
            client.check(blocks_res, "update_doc.get_blocks")
            blocks = blocks_res.get("data", {}).get("items", [])

            # Children of root block (block_id == doc_id)
            children = [b for b in blocks if b.get("parent_id") == doc_id]
            child_count = len(children)

            # Step 2: Delete all children if any exist
            if child_count > 0:
                await client.delete(
                    f"/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
                    params={"start_index": 0, "end_index": child_count},
                )

            # Step 3: Insert new content blocks
            paragraphs = [p for p in content.split("\n") if p.strip()]
            if not paragraphs:
                paragraphs = [content]
            new_blocks = [_make_text_block(p) for p in paragraphs]
            res = await client.post(
                f"/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
                {"children": new_blocks, "index": 0},
            )
            client.check(res, "update_doc.replace_all")
            return ok({"success": True, "doc_id": doc_id})

        else:
            return ok({
                "error": (
                    f"Mode '{mode}' is not supported via direct API. "
                    "Supported modes: append, replace_all, overwrite."
                )
            })

    except Exception as e:
        return ok({"error": str(e)})


UpdateDocTool: FunctionTool = make_tool(
    name="feishu_update_doc",
    description=(
        "更新飞书云文档内容。"
        "支持 append（追加内容到文档末尾）、replace_all/overwrite（清空并替换全文）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "doc_id": {
                "type": "string",
                "description": "文档 ID 或飞书文档 URL",
            },
            "mode": {
                "type": "string",
                "enum": ["append", "replace_all", "overwrite"],
                "description": (
                    "更新模式。"
                    "append: 追加内容到文档末尾；"
                    "replace_all/overwrite: 清空文档全文后写入新内容（慎用）。"
                ),
            },
            "content": {
                "type": "string",
                "description": "要写入的文本内容",
            },
        },
        "required": ["doc_id", "mode"],
    },
    handler=_update_doc,
)
