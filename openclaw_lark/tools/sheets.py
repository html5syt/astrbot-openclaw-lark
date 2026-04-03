# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu Sheets tool.

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext

from ..lark_client import get_lark_client


def _ok(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


MAX_READ_ROWS = 200
MAX_WRITE_ROWS = 5000


def _parse_sheet_url(url: str) -> dict | None:
    """Parse spreadsheet token and optional sheet_id from a Feishu URL."""
    try:
        u = urlparse(url)
        import re
        match = re.search(r"/(?:sheets|wiki)/([^/?#]+)", u.path)
        if not match:
            return None
        params = {}
        from urllib.parse import parse_qs
        qs = parse_qs(u.query)
        sheet_id = qs.get("sheet", [None])[0]
        return {"token": match.group(1), "sheet_id": sheet_id}
    except Exception:
        return None


def _resolve_token(spreadsheet_token: str) -> tuple[str, str | None]:
    """Return (token, sheet_id) from a token or URL."""
    if spreadsheet_token.startswith("http"):
        parsed = _parse_sheet_url(spreadsheet_token)
        if parsed:
            return parsed["token"], parsed.get("sheet_id")
    return spreadsheet_token, None


# ---------------------------------------------------------------------------
# feishu_sheet
# ---------------------------------------------------------------------------


@dataclass
class SheetTool(FunctionTool[AstrAgentContext]):
    """飞书电子表格工具：读写、追加数据，获取表格信息，创建电子表格。"""

    name: str = "feishu_sheet"
    description: str = (
        "飞书电子表格工具（以机器人身份）。"
        "Actions: info（获取表格信息和工作表列表）, read（读取单元格数据）, "
        "write（写入数据）, append（追加数据）, create（创建电子表格）。"
        "spreadsheet_token 支持直接传入 token 或飞书链接（自动解析）。"
        f"单次读取最多 {MAX_READ_ROWS} 行，写入最多 {MAX_WRITE_ROWS} 行。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["info", "read", "write", "append", "create"],
                    "description": "操作类型",
                },
                "spreadsheet_token": {
                    "type": "string",
                    "description": (
                        "电子表格 token 或飞书链接（action=info/read/write/append 时必填）。"
                        "示例：https://example.feishu.cn/sheets/TOKEN?sheet=SHEET_ID"
                    ),
                },
                "range": {
                    "type": "string",
                    "description": (
                        "单元格范围（action=read/write 时必填；action=append 时可选）。"
                        "格式：'工作表ID!A1:B5' 或 'A1:B5'（使用第一个工作表）。"
                        "不指定时读取第一个工作表全部数据。"
                    ),
                },
                "values": {
                    "type": "array",
                    "description": "写入数据（action=write/append 时必填）。二维数组，每行为一个数组。",
                    "items": {
                        "type": "array",
                        "items": {},
                    },
                },
                "title": {
                    "type": "string",
                    "description": "电子表格标题（action=create 时可选）",
                },
                "folder_token": {
                    "type": "string",
                    "description": "文件夹 token（action=create 时可选，默认我的空间）",
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
            if action == "info":
                spreadsheet_token = kwargs.get("spreadsheet_token", "")
                if not spreadsheet_token:
                    return _ok({"error": "spreadsheet_token is required for 'info' action"})
                token, _ = _resolve_token(spreadsheet_token)

                # Get spreadsheet metadata
                meta_res = await client.get(
                    f"/open-apis/sheets/v3/spreadsheets/{token}"
                )
                client.check(meta_res, "sheet.info.meta")

                # Get sheets list
                sheets_res = await client.get(
                    f"/open-apis/sheets/v3/spreadsheets/{token}/sheets/query"
                )
                client.check(sheets_res, "sheet.info.sheets")

                return _ok({
                    "spreadsheet": meta_res.get("data", {}).get("spreadsheet", {}),
                    "sheets": sheets_res.get("data", {}).get("sheets", []),
                })

            elif action == "read":
                spreadsheet_token = kwargs.get("spreadsheet_token", "")
                if not spreadsheet_token:
                    return _ok({"error": "spreadsheet_token is required for 'read' action"})
                token, sheet_id = _resolve_token(spreadsheet_token)

                range_str = kwargs.get("range", "")
                if not range_str:
                    if sheet_id:
                        range_str = f"{sheet_id}!A1:ZZ{MAX_READ_ROWS}"
                    else:
                        range_str = f"A1:ZZ{MAX_READ_ROWS}"

                res = await client.get(
                    f"/open-apis/sheets/v2/spreadsheets/{token}/values/{range_str}",
                    params={"valueRenderOption": "ToString"},
                )
                client.check(res, "sheet.read")
                return _ok(res.get("data", {}))

            elif action == "write":
                spreadsheet_token = kwargs.get("spreadsheet_token", "")
                if not spreadsheet_token:
                    return _ok({"error": "spreadsheet_token is required for 'write' action"})
                range_str = kwargs.get("range", "")
                if not range_str:
                    return _ok({"error": "range is required for 'write' action"})
                values = kwargs.get("values")
                if not values:
                    return _ok({"error": "values is required for 'write' action"})

                token, _ = _resolve_token(spreadsheet_token)
                data = {
                    "valueRange": {
                        "range": range_str,
                        "values": values[:MAX_WRITE_ROWS],
                    }
                }
                res = await client.put(
                    f"/open-apis/sheets/v2/spreadsheets/{token}/values", data
                )
                client.check(res, "sheet.write")
                return _ok(res.get("data", {}))

            elif action == "append":
                spreadsheet_token = kwargs.get("spreadsheet_token", "")
                if not spreadsheet_token:
                    return _ok({"error": "spreadsheet_token is required for 'append' action"})
                values = kwargs.get("values")
                if not values:
                    return _ok({"error": "values is required for 'append' action"})

                token, sheet_id = _resolve_token(spreadsheet_token)
                range_str = kwargs.get("range", "")
                if not range_str:
                    range_str = f"{sheet_id}!A1" if sheet_id else "A1"

                data = {
                    "valueRange": {
                        "range": range_str,
                        "values": values[:MAX_WRITE_ROWS],
                    }
                }
                res = await client.post(
                    f"/open-apis/sheets/v2/spreadsheets/{token}/values_append",
                    data,
                )
                client.check(res, "sheet.append")
                return _ok(res.get("data", {}))

            elif action == "create":
                data: dict = {}
                if kwargs.get("title"):
                    data["title"] = kwargs["title"]
                if kwargs.get("folder_token"):
                    data["folder_token"] = kwargs["folder_token"]
                res = await client.post(
                    "/open-apis/sheets/v3/spreadsheets", data
                )
                client.check(res, "sheet.create")
                return _ok(res.get("data", {}))

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})
