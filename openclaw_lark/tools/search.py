# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu document/wiki search tool.

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext

from ..lark_client import get_lark_client


def _ok(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _convert_time_range(time_range: Optional[dict]) -> Optional[dict]:
    """Convert ISO 8601 time range to unix timestamp seconds."""
    if not time_range:
        return None
    result = {}
    for key in ("start", "end"):
        val = time_range.get(key)
        if val:
            try:
                dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                result[key] = str(int(dt.timestamp()))
            except ValueError:
                result[key] = val
    return result or None


# ---------------------------------------------------------------------------
# feishu_search_doc_wiki
# ---------------------------------------------------------------------------


@dataclass
class SearchDocWikiTool(FunctionTool[AstrAgentContext]):
    """飞书文档与 Wiki 统一搜索工具。"""

    name: str = "feishu_search_doc_wiki"
    description: str = (
        "飞书文档与知识库（Wiki）统一搜索工具（以机器人身份）。"
        "同时搜索云空间文档和知识库 Wiki。Actions: search。"
        "支持按文档类型、创建者、创建时间、打开时间等多维度筛选。"
        "返回结果包含标题和摘要（<h>标签包裹匹配关键词）。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search"],
                    "description": "操作类型（固定为 search）",
                },
                "query": {
                    "type": "string",
                    "description": "搜索关键词（可选，空字符串表示空搜，按最近浏览时间返回结果）",
                    "maxLength": 50,
                },
                "filter": {
                    "type": "object",
                    "description": "搜索过滤条件（可选）",
                    "properties": {
                        "creator_ids": {
                            "type": "array",
                            "description": "创建者 OpenID 列表（最多 20 个）",
                            "items": {"type": "string"},
                        },
                        "doc_types": {
                            "type": "array",
                            "description": (
                                "文档类型列表：DOC, SHEET, BITABLE, MINDNOTE, FILE, "
                                "WIKI, DOCX, FOLDER, CATALOG, SLIDES, SHORTCUT"
                            ),
                            "items": {"type": "string"},
                        },
                        "only_title": {
                            "type": "boolean",
                            "description": "仅搜索标题（默认 false）",
                        },
                        "sort_type": {
                            "type": "string",
                            "enum": ["DEFAULT_TYPE", "OPEN_TIME", "EDIT_TIME", "EDIT_TIME_ASC", "CREATE_TIME"],
                            "description": "排序方式（EDIT_TIME=编辑时间降序，推荐）",
                        },
                        "create_time": {
                            "type": "object",
                            "description": "创建时间范围",
                            "properties": {
                                "start": {
                                    "type": "string",
                                    "description": "起始时间，ISO 8601/RFC 3339 格式",
                                },
                                "end": {
                                    "type": "string",
                                    "description": "截止时间，ISO 8601/RFC 3339 格式",
                                },
                            },
                        },
                        "open_time": {
                            "type": "object",
                            "description": "打开时间范围",
                            "properties": {
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                            },
                        },
                    },
                },
                "page_token": {
                    "type": "string",
                    "description": "分页标记（has_more 为 true 时可传入继续获取下一页）",
                },
                "page_size": {
                    "type": "number",
                    "description": "分页大小（默认 15，最大 20）",
                },
            },
            "required": ["action"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()

        try:
            query = kwargs.get("query", "")
            filter_data = kwargs.get("filter")

            request_data: dict = {
                "query": query,
            }
            if kwargs.get("page_size"):
                request_data["page_size"] = kwargs["page_size"]
            if kwargs.get("page_token"):
                request_data["page_token"] = kwargs["page_token"]

            # Build filter objects
            if filter_data:
                f = dict(filter_data)

                # Convert time range fields from ISO 8601 to unix timestamps
                if f.get("open_time"):
                    converted = _convert_time_range(f["open_time"])
                    if converted:
                        f["open_time"] = converted
                if f.get("create_time"):
                    converted = _convert_time_range(f["create_time"])
                    if converted:
                        f["create_time"] = converted

                # API requires both doc_filter and wiki_filter even if identical
                request_data["doc_filter"] = dict(f)
                request_data["wiki_filter"] = dict(f)
            else:
                # API requires empty filter objects when no filter is specified
                request_data["doc_filter"] = {}
                request_data["wiki_filter"] = {}

            res = await client.post(
                "/open-apis/search/v2/doc_wiki/search", request_data
            )
            if res.get("code") != 0:
                return _ok({
                    "error": f"API error: code={res.get('code')}, msg={res.get('msg')}"
                })

            data = res.get("data", {})
            return _ok({
                "total": data.get("total"),
                "has_more": data.get("has_more", False),
                "results": data.get("res_units", []),
                "page_token": data.get("page_token"),
            })

        except Exception as e:
            return _ok({"error": str(e)})
