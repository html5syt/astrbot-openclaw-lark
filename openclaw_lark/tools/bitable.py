# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu Bitable (多维表格) tools.

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
# feishu_bitable_app
# ---------------------------------------------------------------------------


@dataclass
class BitableAppTool(FunctionTool[AstrAgentContext]):
    """飞书多维表格应用管理工具：创建、查询、更新、复制多维表格。"""

    name: str = "feishu_bitable_app"
    description: str = (
        "飞书多维表格应用管理工具（以机器人身份）。"
        "Actions: create（创建多维表格）, get（获取元数据）, list（列出多维表格）, "
        "patch（更新元数据）, copy（复制多维表格）。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
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
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        action = kwargs.get("action")

        try:
            if action == "create":
                if not kwargs.get("name"):
                    return _ok({"error": "name is required for 'create' action"})
                data: dict = {"name": kwargs["name"]}
                if kwargs.get("folder_token"):
                    data["folder_token"] = kwargs["folder_token"]
                res = await client.post("/open-apis/bitable/v1/apps", data)
                client.check(res, "bitable_app.create")
                return _ok(res.get("data", {}))

            elif action == "get":
                app_token = kwargs.get("app_token", "")
                if not app_token:
                    return _ok({"error": "app_token is required for 'get' action"})
                res = await client.get(f"/open-apis/bitable/v1/apps/{app_token}")
                client.check(res, "bitable_app.get")
                return _ok(res.get("data", {}))

            elif action == "list":
                params: dict = {}
                if kwargs.get("folder_token"):
                    params["folder_token"] = kwargs["folder_token"]
                if kwargs.get("page_size"):
                    params["page_size"] = kwargs["page_size"]
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                res = await client.get("/open-apis/drive/v1/files", params=params)
                client.check(res, "bitable_app.list")
                data = res.get("data", {})
                # Filter bitable type files
                files = data.get("files", [])
                apps = [f for f in files if f.get("type") == "bitable"]
                return _ok({
                    "apps": apps,
                    "has_more": data.get("has_more", False),
                    "page_token": data.get("page_token"),
                })

            elif action == "patch":
                app_token = kwargs.get("app_token", "")
                if not app_token:
                    return _ok({"error": "app_token is required for 'patch' action"})
                update: dict = {}
                if kwargs.get("name") is not None:
                    update["name"] = kwargs["name"]
                if kwargs.get("is_advanced") is not None:
                    update["is_advanced"] = kwargs["is_advanced"]
                res = await client.put(f"/open-apis/bitable/v1/apps/{app_token}", update)
                client.check(res, "bitable_app.patch")
                return _ok(res.get("data", {}))

            elif action == "copy":
                app_token = kwargs.get("app_token", "")
                if not app_token:
                    return _ok({"error": "app_token is required for 'copy' action"})
                if not kwargs.get("name"):
                    return _ok({"error": "name is required for 'copy' action"})
                data = {"name": kwargs["name"]}
                if kwargs.get("folder_token"):
                    data["folder_token"] = kwargs["folder_token"]
                res = await client.post(f"/open-apis/bitable/v1/apps/{app_token}/copy", data)
                client.check(res, "bitable_app.copy")
                return _ok(res.get("data", {}))

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})


# ---------------------------------------------------------------------------
# feishu_bitable_app_table
# ---------------------------------------------------------------------------


@dataclass
class BitableTableTool(FunctionTool[AstrAgentContext]):
    """飞书多维表格数据表管理工具：创建、查询、删除数据表。"""

    name: str = "feishu_bitable_app_table"
    description: str = (
        "飞书多维表格数据表管理工具（以机器人身份）。"
        "Actions: create（创建数据表）, list（列出数据表）, "
        "delete（删除数据表）, batch_create（批量创建数据表）。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
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
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        action = kwargs.get("action")
        app_token = kwargs.get("app_token", "")

        try:
            base = f"/open-apis/bitable/v1/apps/{app_token}/tables"

            if action == "create":
                data: dict = {}
                if kwargs.get("table"):
                    data["table"] = kwargs["table"]
                res = await client.post(base, data)
                client.check(res, "bitable_table.create")
                return _ok(res.get("data", {}))

            elif action == "list":
                params: dict = {}
                if kwargs.get("page_size"):
                    params["page_size"] = kwargs["page_size"]
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                res = await client.get(base, params=params)
                client.check(res, "bitable_table.list")
                return _ok(res.get("data", {}))

            elif action == "delete":
                table_id = kwargs.get("table_id", "")
                if not table_id:
                    return _ok({"error": "table_id is required for 'delete' action"})
                res = await client.delete(f"{base}/{table_id}")
                client.check(res, "bitable_table.delete")
                return _ok({"success": True})

            elif action == "batch_create":
                tables = kwargs.get("tables", [])
                res = await client.post(f"{base}/batch_create", {"tables": tables})
                client.check(res, "bitable_table.batch_create")
                return _ok(res.get("data", {}))

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})


# ---------------------------------------------------------------------------
# feishu_bitable_app_table_record
# ---------------------------------------------------------------------------


@dataclass
class BitableRecordTool(FunctionTool[AstrAgentContext]):
    """飞书多维表格记录管理工具：增删改查多维表格中的记录（行数据）。"""

    name: str = "feishu_bitable_app_table_record"
    description: str = (
        "飞书多维表格记录管理工具（以机器人身份）。"
        "Actions: get（获取记录）, list（查询记录列表）, create（创建记录）, "
        "update（更新记录）, delete（删除记录）, "
        "batch_create（批量创建记录）, batch_update（批量更新记录）, "
        "batch_delete（批量删除记录）。"
        "⚠️ 批量操作：单次 ≤ 500 条，超过需分批。同一数据表不支持并发写，需串行调用。"
        "⚠️ 日期字段值为毫秒时间戳（如 1674206443000）；人员字段值为 [{id:'ou_xxx'}] 数组。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
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
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        action = kwargs.get("action")
        app_token = kwargs.get("app_token", "")
        table_id = kwargs.get("table_id", "")

        try:
            base = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"

            if action == "get":
                record_id = kwargs.get("record_id", "")
                if not record_id:
                    return _ok({"error": "record_id is required for 'get' action"})
                res = await client.get(f"{base}/{record_id}")
                client.check(res, "bitable_record.get")
                return _ok(res.get("data", {}))

            elif action == "list":
                params: dict = {}
                if kwargs.get("filter"):
                    params["filter"] = kwargs["filter"]
                if kwargs.get("sort"):
                    params["sort"] = json.dumps(kwargs["sort"])
                if kwargs.get("field_names"):
                    params["field_names"] = json.dumps(kwargs["field_names"])
                if kwargs.get("page_size"):
                    params["page_size"] = kwargs["page_size"]
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                res = await client.get(base, params=params)
                client.check(res, "bitable_record.list")
                return _ok(res.get("data", {}))

            elif action == "create":
                if not kwargs.get("fields"):
                    return _ok({"error": "fields is required for 'create' action"})
                res = await client.post(base, {"fields": kwargs["fields"]})
                client.check(res, "bitable_record.create")
                return _ok(res.get("data", {}))

            elif action == "update":
                record_id = kwargs.get("record_id", "")
                if not record_id:
                    return _ok({"error": "record_id is required for 'update' action"})
                if not kwargs.get("fields"):
                    return _ok({"error": "fields is required for 'update' action"})
                res = await client.put(f"{base}/{record_id}", {"fields": kwargs["fields"]})
                client.check(res, "bitable_record.update")
                return _ok(res.get("data", {}))

            elif action == "delete":
                record_id = kwargs.get("record_id", "")
                if not record_id:
                    return _ok({"error": "record_id is required for 'delete' action"})
                res = await client.delete(f"{base}/{record_id}")
                client.check(res, "bitable_record.delete")
                return _ok({"success": True})

            elif action == "batch_create":
                records = kwargs.get("records", [])
                if not records:
                    return _ok({"error": "records is required for 'batch_create' action"})
                res = await client.post(f"{base}/batch_create", {"records": records})
                client.check(res, "bitable_record.batch_create")
                return _ok(res.get("data", {}))

            elif action == "batch_update":
                records = kwargs.get("records", [])
                if not records:
                    return _ok({"error": "records is required for 'batch_update' action"})
                res = await client.post(f"{base}/batch_update", {"records": records})
                client.check(res, "bitable_record.batch_update")
                return _ok(res.get("data", {}))

            elif action == "batch_delete":
                record_ids = kwargs.get("record_ids", [])
                if not record_ids:
                    return _ok({"error": "record_ids is required for 'batch_delete' action"})
                res = await client.post(f"{base}/batch_delete", {"records": record_ids})
                client.check(res, "bitable_record.batch_delete")
                return _ok({"success": True})

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})


# ---------------------------------------------------------------------------
# feishu_bitable_app_table_field
# ---------------------------------------------------------------------------


@dataclass
class BitableFieldTool(FunctionTool[AstrAgentContext]):
    """飞书多维表格字段管理工具：查询、创建、更新、删除字段（列）。"""

    name: str = "feishu_bitable_app_table_field"
    description: str = (
        "飞书多维表格字段（列）管理工具（以机器人身份）。"
        "Actions: list（列出字段）, create（创建字段）, update（更新字段）, delete（删除字段）。"
        "⚠️ 在写入记录前，强烈建议先 list 字段以了解 type/ui_type。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
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
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        action = kwargs.get("action")
        app_token = kwargs.get("app_token", "")
        table_id = kwargs.get("table_id", "")

        try:
            base = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"

            if action == "list":
                params: dict = {}
                if kwargs.get("page_size"):
                    params["page_size"] = kwargs["page_size"]
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                if kwargs.get("view_id"):
                    params["view_id"] = kwargs["view_id"]
                res = await client.get(base, params=params)
                client.check(res, "bitable_field.list")
                return _ok(res.get("data", {}))

            elif action == "create":
                if not kwargs.get("field_name"):
                    return _ok({"error": "field_name is required for 'create' action"})
                if kwargs.get("type") is None:
                    return _ok({"error": "type is required for 'create' action"})
                data: dict = {
                    "field_name": kwargs["field_name"],
                    "type": kwargs["type"],
                }
                if kwargs.get("property"):
                    data["property"] = kwargs["property"]
                res = await client.post(base, data)
                client.check(res, "bitable_field.create")
                return _ok(res.get("data", {}))

            elif action == "update":
                field_id = kwargs.get("field_id", "")
                if not field_id:
                    return _ok({"error": "field_id is required for 'update' action"})
                data = {}
                if kwargs.get("field_name"):
                    data["field_name"] = kwargs["field_name"]
                if kwargs.get("type") is not None:
                    data["type"] = kwargs["type"]
                if kwargs.get("property"):
                    data["property"] = kwargs["property"]
                res = await client.put(f"{base}/{field_id}", data)
                client.check(res, "bitable_field.update")
                return _ok(res.get("data", {}))

            elif action == "delete":
                field_id = kwargs.get("field_id", "")
                if not field_id:
                    return _ok({"error": "field_id is required for 'delete' action"})
                res = await client.delete(f"{base}/{field_id}")
                client.check(res, "bitable_field.delete")
                return _ok({"success": True, "deleted": field_id})

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})


# ---------------------------------------------------------------------------
# feishu_bitable_app_table_view
# ---------------------------------------------------------------------------


@dataclass
class BitableViewTool(FunctionTool[AstrAgentContext]):
    """飞书多维表格视图管理工具：列出、创建、删除视图。"""

    name: str = "feishu_bitable_app_table_view"
    description: str = (
        "飞书多维表格视图管理工具（以机器人身份）。"
        "Actions: list（列出视图）, create（创建视图）, delete（删除视图）。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
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
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        action = kwargs.get("action")
        app_token = kwargs.get("app_token", "")
        table_id = kwargs.get("table_id", "")

        try:
            base = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/views"

            if action == "list":
                params: dict = {}
                if kwargs.get("page_size"):
                    params["page_size"] = kwargs["page_size"]
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                res = await client.get(base, params=params)
                client.check(res, "bitable_view.list")
                return _ok(res.get("data", {}))

            elif action == "create":
                if not kwargs.get("view_name"):
                    return _ok({"error": "view_name is required for 'create' action"})
                data: dict = {"view_name": kwargs["view_name"]}
                if kwargs.get("view_type"):
                    data["view_type"] = kwargs["view_type"]
                res = await client.post(base, data)
                client.check(res, "bitable_view.create")
                return _ok(res.get("data", {}))

            elif action == "delete":
                view_id = kwargs.get("view_id", "")
                if not view_id:
                    return _ok({"error": "view_id is required for 'delete' action"})
                res = await client.delete(f"{base}/{view_id}")
                client.check(res, "bitable_view.delete")
                return _ok({"success": True})

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})
