# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu Bitable (多维表格) tools.

from __future__ import annotations

import json
from typing import Any

from astrbot.api import FunctionTool

from ..lark_client import get_lark_client
from ._common import ok, make_tool


# ---------------------------------------------------------------------------
# feishu_bitable_app
# ---------------------------------------------------------------------------


async def _bitable_app(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")

    try:
        if action == "create":
            if not kw.get("name"):
                return ok({"error": "name is required for 'create' action"})
            data: dict = {"name": kw["name"]}
            if kw.get("folder_token"):
                data["folder_token"] = kw["folder_token"]
            res = await client.post("/open-apis/bitable/v1/apps", data)
            client.check(res, "bitable_app.create")
            return ok(res.get("data", {}))

        elif action == "get":
            app_token = kw.get("app_token", "")
            if not app_token:
                return ok({"error": "app_token is required for 'get' action"})
            res = await client.get(f"/open-apis/bitable/v1/apps/{app_token}")
            client.check(res, "bitable_app.get")
            return ok(res.get("data", {}))

        elif action == "list":
            params: dict = {}
            if kw.get("folder_token"):
                params["folder_token"] = kw["folder_token"]
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            res = await client.get("/open-apis/drive/v1/files", params=params)
            client.check(res, "bitable_app.list")
            data = res.get("data", {})
            # Filter bitable type files
            files = data.get("files", [])
            apps = [f for f in files if f.get("type") == "bitable"]
            return ok({
                "apps": apps,
                "has_more": data.get("has_more", False),
                "page_token": data.get("page_token"),
            })

        elif action == "patch":
            app_token = kw.get("app_token", "")
            if not app_token:
                return ok({"error": "app_token is required for 'patch' action"})
            update: dict = {}
            if kw.get("name") is not None:
                update["name"] = kw["name"]
            if kw.get("is_advanced") is not None:
                update["is_advanced"] = kw["is_advanced"]
            res = await client.put(f"/open-apis/bitable/v1/apps/{app_token}", update)
            client.check(res, "bitable_app.patch")
            return ok(res.get("data", {}))

        elif action == "copy":
            app_token = kw.get("app_token", "")
            if not app_token:
                return ok({"error": "app_token is required for 'copy' action"})
            if not kw.get("name"):
                return ok({"error": "name is required for 'copy' action"})
            data = {"name": kw["name"]}
            if kw.get("folder_token"):
                data["folder_token"] = kw["folder_token"]
            res = await client.post(f"/open-apis/bitable/v1/apps/{app_token}/copy", data)
            client.check(res, "bitable_app.copy")
            return ok(res.get("data", {}))

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


BitableAppTool: FunctionTool = make_tool(
    name="feishu_bitable_app",
    description=(
        "飞书多维表格应用管理工具（以机器人身份）。"
        "Actions: create（创建多维表格）, get（获取元数据）, list（列出多维表格）, "
        "patch（更新元数据）, copy（复制多维表格）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "get", "list", "patch", "copy"],
                "description": "操作类型",
            },
            "app_token": {
                "type": "string",
                "description": "多维表格 token（action=get/patch/copy 时必填）",
            },
            "name": {
                "type": "string",
                "description": "名称（action=create/copy 时必填；patch 时可选）",
            },
            "folder_token": {
                "type": "string",
                "description": "文件夹 token（action=create/copy 时可选，默认我的空间）",
            },
            "is_advanced": {
                "type": "boolean",
                "description": "是否开启高级权限（action=patch 时可选）",
            },
            "page_size": {"type": "number", "description": "每页数量（action=list，默认 50，最大 200）"},
            "page_token": {"type": "string", "description": "分页标记"},
        },
        "required": ["action"],
    },
    handler=_bitable_app,
)


# ---------------------------------------------------------------------------
# feishu_bitable_app_table
# ---------------------------------------------------------------------------


async def _bitable_table(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")
    app_token = kw.get("app_token", "")

    try:
        base = f"/open-apis/bitable/v1/apps/{app_token}/tables"

        if action == "create":
            data: dict = {}
            if kw.get("table"):
                data["table"] = kw["table"]
            res = await client.post(base, data)
            client.check(res, "bitable_table.create")
            return ok(res.get("data", {}))

        elif action == "list":
            params: dict = {}
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            res = await client.get(base, params=params)
            client.check(res, "bitable_table.list")
            return ok(res.get("data", {}))

        elif action == "delete":
            table_id = kw.get("table_id", "")
            if not table_id:
                return ok({"error": "table_id is required for 'delete' action"})
            res = await client.delete(f"{base}/{table_id}")
            client.check(res, "bitable_table.delete")
            return ok({"success": True})

        elif action == "batch_create":
            tables = kw.get("tables", [])
            res = await client.post(f"{base}/batch_create", {"tables": tables})
            client.check(res, "bitable_table.batch_create")
            return ok(res.get("data", {}))

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


BitableTableTool: FunctionTool = make_tool(
    name="feishu_bitable_app_table",
    description=(
        "飞书多维表格数据表管理工具（以机器人身份）。"
        "Actions: create（创建数据表）, list（列出数据表）, "
        "delete（删除数据表）, batch_create（批量创建数据表）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "delete", "batch_create"],
                "description": "操作类型",
            },
            "app_token": {"type": "string", "description": "多维表格 token（必填）"},
            "table_id": {
                "type": "string",
                "description": "数据表 ID（action=delete 时必填）",
            },
            "table": {
                "type": "object",
                "description": (
                    "数据表配置（action=create 时可选）。"
                    "包含 name（表名）、default_view_name（默认视图名）、"
                    "fields（字段列表，每项含 field_name、type 等）。"
                ),
                "properties": {
                    "name": {"type": "string", "description": "数据表名称"},
                    "default_view_name": {"type": "string", "description": "默认视图名称"},
                    "fields": {
                        "type": "array",
                        "description": "字段列表",
                        "items": {"type": "object"},
                    },
                },
            },
            "tables": {
                "type": "array",
                "description": "数据表配置列表（action=batch_create 时使用）",
                "items": {"type": "object"},
            },
            "page_size": {"type": "number", "description": "每页数量"},
            "page_token": {"type": "string", "description": "分页标记"},
        },
        "required": ["action", "app_token"],
    },
    handler=_bitable_table,
)


# ---------------------------------------------------------------------------
# feishu_bitable_app_table_record
# ---------------------------------------------------------------------------


async def _bitable_record(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")
    app_token = kw.get("app_token", "")
    table_id = kw.get("table_id", "")

    try:
        base = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"

        if action == "get":
            record_id = kw.get("record_id", "")
            if not record_id:
                return ok({"error": "record_id is required for 'get' action"})
            res = await client.get(f"{base}/{record_id}")
            client.check(res, "bitable_record.get")
            return ok(res.get("data", {}))

        elif action == "list":
            params: dict = {}
            if kw.get("filter"):
                params["filter"] = kw["filter"]
            if kw.get("sort"):
                params["sort"] = json.dumps(kw["sort"])
            if kw.get("field_names"):
                params["field_names"] = json.dumps(kw["field_names"])
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            res = await client.get(base, params=params)
            client.check(res, "bitable_record.list")
            return ok(res.get("data", {}))

        elif action == "create":
            if not kw.get("fields"):
                return ok({"error": "fields is required for 'create' action"})
            res = await client.post(base, {"fields": kw["fields"]})
            client.check(res, "bitable_record.create")
            return ok(res.get("data", {}))

        elif action == "update":
            record_id = kw.get("record_id", "")
            if not record_id:
                return ok({"error": "record_id is required for 'update' action"})
            if not kw.get("fields"):
                return ok({"error": "fields is required for 'update' action"})
            res = await client.put(f"{base}/{record_id}", {"fields": kw["fields"]})
            client.check(res, "bitable_record.update")
            return ok(res.get("data", {}))

        elif action == "delete":
            record_id = kw.get("record_id", "")
            if not record_id:
                return ok({"error": "record_id is required for 'delete' action"})
            res = await client.delete(f"{base}/{record_id}")
            client.check(res, "bitable_record.delete")
            return ok({"success": True})

        elif action == "batch_create":
            records = kw.get("records", [])
            if not records:
                return ok({"error": "records is required for 'batch_create' action"})
            res = await client.post(f"{base}/batch_create", {"records": records})
            client.check(res, "bitable_record.batch_create")
            return ok(res.get("data", {}))

        elif action == "batch_update":
            records = kw.get("records", [])
            if not records:
                return ok({"error": "records is required for 'batch_update' action"})
            res = await client.post(f"{base}/batch_update", {"records": records})
            client.check(res, "bitable_record.batch_update")
            return ok(res.get("data", {}))

        elif action == "batch_delete":
            record_ids = kw.get("record_ids", [])
            if not record_ids:
                return ok({"error": "record_ids is required for 'batch_delete' action"})
            res = await client.post(f"{base}/batch_delete", {"records": record_ids})
            client.check(res, "bitable_record.batch_delete")
            return ok({"success": True})

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


BitableRecordTool: FunctionTool = make_tool(
    name="feishu_bitable_app_table_record",
    description=(
        "飞书多维表格记录管理工具（以机器人身份）。"
        "Actions: get（获取记录）, list（查询记录列表）, create（创建记录）, "
        "update（更新记录）, delete（删除记录）, "
        "batch_create（批量创建记录）, batch_update（批量更新记录）, "
        "batch_delete（批量删除记录）。"
        "⚠️ 批量操作：单次 ≤ 500 条，超过需分批。同一数据表不支持并发写，需串行调用。"
        "⚠️ 日期字段值为毫秒时间戳（如 1674206443000）；人员字段值为 [{id:'ou_xxx'}] 数组。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get", "list", "create", "update", "delete", "batch_create", "batch_update", "batch_delete"],
                "description": "操作类型",
            },
            "app_token": {"type": "string", "description": "多维表格 token（必填）"},
            "table_id": {"type": "string", "description": "数据表 ID（必填）"},
            "record_id": {
                "type": "string",
                "description": "记录 ID（action=get/update/delete 时必填）",
            },
            "fields": {
                "type": "object",
                "description": "记录字段数据（action=create/update 时必填）",
            },
            "records": {
                "type": "array",
                "description": "记录列表（action=batch_create/batch_update 时必填）",
                "items": {
                    "type": "object",
                    "properties": {
                        "record_id": {"type": "string", "description": "记录 ID（batch_update 时必填）"},
                        "fields": {"type": "object", "description": "字段数据"},
                    },
                },
            },
            "record_ids": {
                "type": "array",
                "description": "记录 ID 列表（action=batch_delete 时必填）",
                "items": {"type": "string"},
            },
            "filter": {
                "type": "string",
                "description": "筛选条件（action=list 时可选，例如 'CurrentValue.[数字] > 0'）",
            },
            "sort": {
                "type": "array",
                "description": "排序条件（action=list 时可选）",
                "items": {"type": "object"},
            },
            "field_names": {
                "type": "array",
                "description": "指定要返回的字段名列表（可选）",
                "items": {"type": "string"},
            },
            "page_size": {
                "type": "number",
                "description": "每页数量（action=list，默认 20，最大 500）",
            },
            "page_token": {"type": "string", "description": "分页标记"},
        },
        "required": ["action", "app_token", "table_id"],
    },
    handler=_bitable_record,
)


# ---------------------------------------------------------------------------
# feishu_bitable_app_table_field
# ---------------------------------------------------------------------------


async def _bitable_field(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")
    app_token = kw.get("app_token", "")
    table_id = kw.get("table_id", "")

    try:
        base = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"

        if action == "list":
            params: dict = {}
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            if kw.get("view_id"):
                params["view_id"] = kw["view_id"]
            res = await client.get(base, params=params)
            client.check(res, "bitable_field.list")
            return ok(res.get("data", {}))

        elif action == "create":
            if not kw.get("field_name"):
                return ok({"error": "field_name is required for 'create' action"})
            if kw.get("type") is None:
                return ok({"error": "type is required for 'create' action"})
            data: dict = {
                "field_name": kw["field_name"],
                "type": kw["type"],
            }
            if kw.get("property"):
                data["property"] = kw["property"]
            res = await client.post(base, data)
            client.check(res, "bitable_field.create")
            return ok(res.get("data", {}))

        elif action == "update":
            field_id = kw.get("field_id", "")
            if not field_id:
                return ok({"error": "field_id is required for 'update' action"})
            data = {}
            if kw.get("field_name"):
                data["field_name"] = kw["field_name"]
            if kw.get("type") is not None:
                data["type"] = kw["type"]
            if kw.get("property"):
                data["property"] = kw["property"]
            res = await client.put(f"{base}/{field_id}", data)
            client.check(res, "bitable_field.update")
            return ok(res.get("data", {}))

        elif action == "delete":
            field_id = kw.get("field_id", "")
            if not field_id:
                return ok({"error": "field_id is required for 'delete' action"})
            res = await client.delete(f"{base}/{field_id}")
            client.check(res, "bitable_field.delete")
            return ok({"success": True, "deleted": field_id})

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


BitableFieldTool: FunctionTool = make_tool(
    name="feishu_bitable_app_table_field",
    description=(
        "飞书多维表格字段（列）管理工具（以机器人身份）。"
        "Actions: list（列出字段）, create（创建字段）, update（更新字段）, delete（删除字段）。"
        "⚠️ 在写入记录前，强烈建议先 list 字段以了解 type/ui_type。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "create", "update", "delete"],
                "description": "操作类型",
            },
            "app_token": {"type": "string", "description": "多维表格 token（必填）"},
            "table_id": {"type": "string", "description": "数据表 ID（必填）"},
            "field_id": {
                "type": "string",
                "description": "字段 ID（action=update/delete 时必填）",
            },
            "field_name": {
                "type": "string",
                "description": "字段名称（action=create/update 时必填）",
            },
            "type": {
                "type": "number",
                "description": (
                    "字段类型代码（action=create 时必填）。"
                    "1=文本, 2=数字, 3=单选, 4=多选, 5=日期, 7=复选框, "
                    "11=人员, 13=电话, 15=链接, 17=附件, 18=关联, "
                    "20=公式, 21=双向关联, 22=地理位置, 23=群组, 1001=创建时间, "
                    "1002=最后更新时间, 1003=创建人, 1004=修改人, 1005=自动编号"
                ),
            },
            "property": {
                "type": "object",
                "description": "字段属性（可选，根据 type 不同而不同）",
            },
            "page_size": {"type": "number", "description": "每页数量"},
            "page_token": {"type": "string", "description": "分页标记"},
            "view_id": {"type": "string", "description": "视图 ID（action=list 时可选）"},
        },
        "required": ["action", "app_token", "table_id"],
    },
    handler=_bitable_field,
)


# ---------------------------------------------------------------------------
# feishu_bitable_app_table_view
# ---------------------------------------------------------------------------


async def _bitable_view(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")
    app_token = kw.get("app_token", "")
    table_id = kw.get("table_id", "")

    try:
        base = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views"

        if action == "list":
            params: dict = {}
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            res = await client.get(base, params=params)
            client.check(res, "bitable_view.list")
            return ok(res.get("data", {}))

        elif action == "create":
            if not kw.get("view_name"):
                return ok({"error": "view_name is required for 'create' action"})
            data: dict = {"view_name": kw["view_name"]}
            if kw.get("view_type"):
                data["view_type"] = kw["view_type"]
            res = await client.post(base, data)
            client.check(res, "bitable_view.create")
            return ok(res.get("data", {}))

        elif action == "delete":
            view_id = kw.get("view_id", "")
            if not view_id:
                return ok({"error": "view_id is required for 'delete' action"})
            res = await client.delete(f"{base}/{view_id}")
            client.check(res, "bitable_view.delete")
            return ok({"success": True})

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


BitableViewTool: FunctionTool = make_tool(
    name="feishu_bitable_app_table_view",
    description=(
        "飞书多维表格视图管理工具（以机器人身份）。"
        "Actions: list（列出视图）, create（创建视图）, delete（删除视图）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "create", "delete"],
                "description": "操作类型",
            },
            "app_token": {"type": "string", "description": "多维表格 token（必填）"},
            "table_id": {"type": "string", "description": "数据表 ID（必填）"},
            "view_id": {
                "type": "string",
                "description": "视图 ID（action=delete 时必填）",
            },
            "view_name": {
                "type": "string",
                "description": "视图名称（action=create 时必填）",
            },
            "view_type": {
                "type": "string",
                "description": "视图类型（action=create 时可选）：grid（表格视图）, kanban（看板视图）, gallery（画册视图）, gantt（甘特图）, form（表单视图）",
            },
            "page_size": {"type": "number", "description": "每页数量"},
            "page_token": {"type": "string", "description": "分页标记"},
        },
        "required": ["action", "app_token", "table_id"],
    },
    handler=_bitable_view,
)
