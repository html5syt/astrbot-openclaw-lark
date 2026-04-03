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
        "text": {
            "elements": [{"text_run": {"content": text}}]
        },
    }


# ---------------------------------------------------------------------------
# Blocks → Markdown converter
# ---------------------------------------------------------------------------

# Feishu code block language enum → string
_CODE_LANG: dict[int, str] = {
    1: "", 2: "abap", 3: "ada", 4: "apache", 5: "apex", 6: "assembly",
    7: "bash", 8: "csharp", 9: "cpp", 10: "c", 11: "coffeescript",
    12: "css", 13: "cmake", 14: "dart", 15: "dockerfile", 16: "erlang",
    17: "fortran", 18: "fsharp", 19: "gherkin", 20: "groovy",
    21: "go", 22: "graphql", 23: "html", 24: "http", 25: "ini",
    26: "java", 27: "javascript", 28: "json", 29: "kotlin",
    30: "latex", 31: "lua", 32: "makefile", 33: "markdown",
    34: "matlab", 35: "mermaid", 36: "nginx", 37: "objectivec",
    38: "ocaml", 39: "php", 40: "perl", 41: "powershell",
    42: "prolog", 43: "protobuf", 44: "python", 45: "r",
    46: "ruby", 47: "rust", 48: "scala", 49: "shell",
    50: "sql", 51: "swift", 52: "toml", 53: "typescript",
    54: "vb", 55: "vbscript", 56: "visualbasic", 57: "xml",
    58: "yaml", 59: "zig",
}

# block_type → heading level (1–9)
_HEADING_TYPES: dict[int, int] = {3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 8: 6, 9: 7, 10: 8, 11: 9}


def _render_inline_elem(elem: dict) -> str:
    etype = elem.get("type", 0)
    if etype == 0:  # text_run
        run = elem.get("text_run", {})
        text = run.get("content", "")
        style = run.get("text_element_style", {})
        if style.get("inline_code"):
            return f"`{text}`"
        if style.get("bold"):
            text = f"**{text}**"
        if style.get("italic"):
            text = f"*{text}*"
        if style.get("strikethrough"):
            text = f"~~{text}~~"
        return text
    if etype == 1:  # mention_user
        name = elem.get("mention_user", {}).get("name", "user")
        return f"@{name}"
    if etype == 2:  # mention_doc
        d = elem.get("mention_doc", {})
        title = d.get("title", "doc")
        url = d.get("url", "")
        return f"[{title}]({url})" if url else title
    if etype == 6:  # inline equation
        eq = elem.get("equation", {}).get("content", "")
        return f"${eq}$"
    return ""


def _render_inline(elements: list) -> str:
    return "".join(_render_inline_elem(e) for e in elements)


def _blocks_to_markdown(blocks: list) -> str:
    """Convert a flat list of Feishu docx blocks to Markdown."""
    by_id: dict[str, dict] = {b["block_id"]: b for b in blocks}

    # Find the page (root) block
    root = next((b for b in blocks if b.get("block_type") == 1), None)
    if root is None and blocks:
        root = blocks[0]
    if root is None:
        return ""

    lines: list[str] = []

    def render(block: dict, depth: int = 0) -> None:
        btype = block.get("block_type", 0)
        children_ids: list[str] = block.get("children", [])
        indent = "  " * depth

        if btype == 1:  # Page — render children only
            for cid in children_ids:
                if cid in by_id:
                    render(by_id[cid], depth)
            return

        if btype == 2:  # Text / Paragraph (key is "text", not "paragraph")
            elems = block.get("text", {}).get("elements", [])
            lines.append(indent + _render_inline(elems))

        elif btype in _HEADING_TYPES:  # Headings (heading1–heading9)
            level = _HEADING_TYPES[btype]
            field = f"heading{level}"
            elems = block.get(field, {}).get("elements", [])
            lines.append(f"{'#' * level} {_render_inline(elems)}")

        elif btype == 12:  # Bullet list
            elems = block.get("bullet", {}).get("elements", [])
            lines.append(indent + f"- {_render_inline(elems)}")
            for cid in children_ids:
                if cid in by_id:
                    render(by_id[cid], depth + 1)
            return

        elif btype == 13:  # Ordered list
            elems = block.get("ordered", {}).get("elements", [])
            lines.append(indent + f"1. {_render_inline(elems)}")
            for cid in children_ids:
                if cid in by_id:
                    render(by_id[cid], depth + 1)
            return

        elif btype == 14:  # Code block
            code_data = block.get("code", {})
            lang_id = code_data.get("style", {}).get("language", 1)
            lang = _CODE_LANG.get(lang_id, "") if isinstance(lang_id, int) else str(lang_id)
            elems = code_data.get("elements", [])
            code_text = "".join(e.get("text_run", {}).get("content", "") for e in elems)
            lines.append(f"```{lang}")
            lines.append(code_text)
            lines.append("```")

        elif btype == 15:  # Quote
            elems = block.get("quote", {}).get("elements", [])
            for line in _render_inline(elems).splitlines() or [""]:
                lines.append(f"> {line}")

        elif btype == 17:  # Todo
            todo = block.get("todo", {})
            done = todo.get("style", {}).get("done", False)
            elems = todo.get("elements", [])
            checkbox = "x" if done else " "
            lines.append(indent + f"- [{checkbox}] {_render_inline(elems)}")

        elif btype == 19:  # Callout (high-light block)
            callout = block.get("callout", {})
            emoji = callout.get("emoji_id", "")
            prefix = f"{emoji} " if emoji else ""
            lines.append(f"> **{prefix}Callout**")
            for cid in children_ids:
                if cid in by_id:
                    child_lines_before = len(lines)
                    render(by_id[cid], depth)
                    # Prefix newly added lines with ">"
                    for i in range(child_lines_before, len(lines)):
                        lines[i] = f"> {lines[i]}"
            return

        elif btype == 22:  # Divider
            lines.append("---")

        elif btype == 23:  # File
            file_data = block.get("file", {})
            name = file_data.get("name", "file")
            token = file_data.get("token", "")
            lines.append(f"<view type=\"1\"><file token=\"{token}\" name=\"{name}\"/></view>")

        elif btype == 27:  # Image
            image = block.get("image", {})
            token = image.get("token", "")
            width = image.get("width", "")
            height = image.get("height", "")
            align = image.get("align", 1)
            align_str = {1: "left", 2: "center", 3: "right"}.get(align, "center")
            lines.append(
                f'<image token="{token}" width="{width}" height="{height}" align="{align_str}"/>'
            )

        elif btype == 32:  # Table — emit placeholder
            lines.append("[表格]")

        elif btype == 999:  # Child page reference
            elems = block.get("page", {}).get("elements", [])
            text = _render_inline(elems) if elems else "子页面"
            lines.append(f"[📄 {text}]")

        # Render nested children (not already handled by early-return blocks)
        for cid in children_ids:
            if cid in by_id:
                render(by_id[cid], depth)

    render(root)
    return "\n".join(lines)


async def _fetch_all_blocks(client: Any, doc_id: str) -> list:
    """Fetch all blocks for a document, handling pagination."""
    blocks: list = []
    params: dict = {"page_size": 500}
    while True:
        res = await client.get(
            f"/open-apis/docx/v1/documents/{doc_id}/blocks",
            params=params,
        )
        client.check(res, "fetch_doc.blocks")
        data = res.get("data", {})
        blocks.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        params["page_token"] = data["page_token"]
    return blocks


# ---------------------------------------------------------------------------
# feishu_fetch_doc
# ---------------------------------------------------------------------------


async def _fetch_doc(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    doc_id = extract_doc_id(kw.get("doc_id", ""))
    if not doc_id:
        return ok({"error": "doc_id is required"})

    try:
        # Get document metadata (title)
        meta_res = await client.get(f"/open-apis/docx/v1/documents/{doc_id}")
        title = ""
        if meta_res.get("code") == 0:
            title = meta_res.get("data", {}).get("document", {}).get("title", "")

        # Fetch all blocks and convert to Markdown
        blocks = await _fetch_all_blocks(client, doc_id)
        content = _blocks_to_markdown(blocks)

        # Apply offset/limit if specified
        offset = kw.get("offset", 0) or 0
        limit = kw.get("limit")
        if offset > 0:
            content = content[offset:]
        if limit:
            content = content[:limit]

        return ok({
            "doc_id": doc_id,
            "title": title,
            "content": content,
            "format": "markdown",
        })

    except Exception as e:
        return ok({"error": str(e)})


FetchDocTool: FunctionTool = make_tool(
    name="feishu_fetch_doc",
    description=(
        "获取飞书云文档内容，返回文档标题和 Markdown 格式内容。"
        "支持通过 doc_id（文档 ID 或 URL）指定文档。"
        "返回 Markdown 格式内容（保留标题、列表、代码块、引用等格式）。"
        "支持 offset/limit 按字符数分页获取。"
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
                    data={"start_index": 0, "end_index": child_count},
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
