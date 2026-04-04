# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu task tools.

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from astrbot.api import FunctionTool

from ..lark_client import get_lark_client
from ._common import ok, make_tool


def _parse_time_to_ms(ts: str) -> Optional[str]:
    """Convert ISO 8601 timestamp to millisecond timestamp string."""
    if not ts:
        return None
    # Already a numeric timestamp
    if re.match(r"^\d+$", ts):
        return ts
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return str(int(dt.timestamp() * 1000))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# feishu_task_task
# ---------------------------------------------------------------------------


async def _task_task(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")
    uid_type = kw.get("user_id_type", "open_id")

    try:
        if action == "create":
            if not kw.get("summary"):
                return ok({"error": "summary is required for 'create' action"})

            task_data: dict = {"summary": kw["summary"]}
            if kw.get("description"):
                task_data["description"] = kw["description"]

            for field in ("due", "start"):
                val = kw.get(field)
                if val and val.get("timestamp"):
                    ts = _parse_time_to_ms(val["timestamp"])
                    if not ts:
                        return ok({"error": f"{field}.timestamp format error. Use ISO 8601, e.g. '2026-01-01T00:00:00+08:00'"})
                    task_data[field] = {"timestamp": ts, "is_all_day": val.get("is_all_day", False)}

            if kw.get("members"):
                task_data["members"] = kw["members"]
            if kw.get("tasklists"):
                task_data["tasklists"] = kw["tasklists"]

            res = await client.post(
                "/open-apis/task/v2/tasks",
                {"task": task_data},
            )
            client.check(res, "task_task.create")
            return ok(res.get("data", {}))

        elif action == "get":
            task_guid = kw.get("task_guid", "")
            if not task_guid:
                return ok({"error": "task_guid is required for 'get' action"})
            res = await client.get(
                f"/open-apis/task/v2/tasks/{task_guid}",
                params={"user_id_type": uid_type},
            )
            client.check(res, "task_task.get")
            return ok(res.get("data", {}))

        elif action == "list":
            params: dict = {"user_id_type": uid_type}
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            if kw.get("completed") is not None:
                params["completed"] = kw["completed"]
            res = await client.get("/open-apis/task/v2/tasks", params=params)
            client.check(res, "task_task.list")
            return ok(res.get("data", {}))

        elif action == "patch":
            task_guid = kw.get("task_guid", "")
            if not task_guid:
                return ok({"error": "task_guid is required for 'patch' action"})

            update_data: dict = {}
            if kw.get("summary"):
                update_data["summary"] = kw["summary"]
            if kw.get("description") is not None:
                update_data["description"] = kw["description"]

            for field in ("due", "start"):
                val = kw.get(field)
                if val and val.get("timestamp"):
                    ts = _parse_time_to_ms(val["timestamp"])
                    if not ts:
                        return ok({"error": f"{field}.timestamp format error"})
                    update_data[field] = {"timestamp": ts, "is_all_day": val.get("is_all_day", False)}

            completed_at = kw.get("completed_at")
            if completed_at is not None:
                if completed_at == "0":
                    update_data["completed_at"] = "0"
                elif re.match(r"^\d+$", completed_at):
                    update_data["completed_at"] = completed_at
                else:
                    ts = _parse_time_to_ms(completed_at)
                    if not ts:
                        return ok({"error": "completed_at format error"})
                    update_data["completed_at"] = ts

            if kw.get("members"):
                update_data["members"] = kw["members"]

            update_fields = list(update_data.keys())
            data = {"task": update_data, "update_fields": update_fields}

            res = await client.patch(
                f"/open-apis/task/v2/tasks/{task_guid}",
                data,
            )
            client.check(res, "task_task.patch")
            return ok(res.get("data", {}))

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


TaskTaskTool: FunctionTool = make_tool(
    name="feishu_task_task",
    description=(
        "飞书任务管理工具（以机器人身份）。"
        "Actions: create（创建任务）, get（获取任务详情）, "
        "list（查询我的任务列表）, patch（更新任务）。"
        "时间格式：ISO 8601/RFC 3339，例如 '2026-01-01T00:00:00+08:00'。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "get", "list", "patch"],
                "description": "操作类型",
            },
            "task_guid": {
                "type": "string",
                "description": "任务 GUID（action=get/patch 时必填）",
            },
            "summary": {
                "type": "string",
                "description": "任务标题（action=create 时必填；action=patch 时可选）",
            },
            "description": {
                "type": "string",
                "description": "任务描述（可选）",
            },
            "due": {
                "type": "object",
                "description": "截止时间（可选）",
                "properties": {
                    "timestamp": {
                        "type": "string",
                        "description": "截止时间，ISO 8601/RFC 3339 格式，例如 '2026-01-01T00:00:00+08:00'",
                    },
                    "is_all_day": {"type": "boolean", "description": "是否全天任务"},
                },
            },
            "start": {
                "type": "object",
                "description": "开始时间（可选）",
                "properties": {
                    "timestamp": {
                        "type": "string",
                        "description": "开始时间，ISO 8601/RFC 3339 格式",
                    },
                    "is_all_day": {"type": "boolean", "description": "是否全天"},
                },
            },
            "completed_at": {
                "type": "string",
                "description": (
                    "完成时间（action=patch 时可选）。"
                    "格式：ISO 8601/RFC 3339（设为已完成），'0'（反完成），或毫秒时间戳字符串。"
                ),
            },
            "members": {
                "type": "array",
                "description": "任务成员列表（assignee=负责人，follower=关注人）",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "成员 open_id"},
                        "role": {"type": "string", "enum": ["assignee", "follower"]},
                    },
                },
            },
            "tasklists": {
                "type": "array",
                "description": "任务所属清单列表（action=create 时可选）",
                "items": {
                    "type": "object",
                    "properties": {
                        "tasklist_guid": {"type": "string"},
                        "section_guid": {"type": "string"},
                    },
                },
            },
            "completed": {
                "type": "boolean",
                "description": "是否筛选已完成任务（action=list 时可选）",
            },
            "page_size": {"type": "number", "description": "每页数量（默认 50，最大 100）"},
            "page_token": {"type": "string", "description": "分页标记"},
            "user_id_type": {
                "type": "string",
                "enum": ["open_id", "union_id", "user_id"],
                "description": "用户 ID 类型（默认 open_id）",
            },
        },
        "required": ["action"],
    },
    handler=_task_task,
)


# ---------------------------------------------------------------------------
# feishu_task_tasklist
# ---------------------------------------------------------------------------


async def _task_tasklist(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")
    tasklist_guid = kw.get("tasklist_guid", "")

    try:
        if action == "create":
            if not kw.get("name"):
                return ok({"error": "name is required for 'create' action"})
            res = await client.post(
                "/open-apis/task/v2/tasklists",
                {"tasklist": {"name": kw["name"]}},
            )
            client.check(res, "task_tasklist.create")
            return ok(res.get("data", {}))

        elif action == "get":
            if not tasklist_guid:
                return ok({"error": "tasklist_guid is required for 'get' action"})
            res = await client.get(f"/open-apis/task/v2/tasklists/{tasklist_guid}")
            client.check(res, "task_tasklist.get")
            return ok(res.get("data", {}))

        elif action == "list":
            params: dict = {}
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            res = await client.get("/open-apis/task/v2/tasklists", params=params)
            client.check(res, "task_tasklist.list")
            return ok(res.get("data", {}))

        elif action == "patch":
            if not tasklist_guid:
                return ok({"error": "tasklist_guid is required for 'patch' action"})
            update: dict = {}
            if kw.get("name"):
                update["name"] = kw["name"]
            res = await client.patch(
                f"/open-apis/task/v2/tasklists/{tasklist_guid}",
                {"tasklist": update, "update_fields": list(update.keys())},
            )
            client.check(res, "task_tasklist.patch")
            return ok(res.get("data", {}))

        elif action == "delete":
            if not tasklist_guid:
                return ok({"error": "tasklist_guid is required for 'delete' action"})
            res = await client.delete(f"/open-apis/task/v2/tasklists/{tasklist_guid}")
            client.check(res, "task_tasklist.delete")
            return ok({"success": True})

        elif action == "tasks":
            if not tasklist_guid:
                return ok({"error": "tasklist_guid is required for 'tasks' action"})
            params = {}
            for k in ("page_size", "page_token", "completed"):
                if kw.get(k) is not None:
                    params[k] = kw[k]
            res = await client.get(
                f"/open-apis/task/v2/tasklists/{tasklist_guid}/tasks", params=params
            )
            client.check(res, "task_tasklist.tasks")
            return ok(res.get("data", {}))

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


TaskTasklistTool: FunctionTool = make_tool(
    name="feishu_task_tasklist",
    description=(
        "飞书任务清单管理工具（以机器人身份）。"
        "Actions: create（创建清单）, get（获取清单详情）, list（列出清单）, "
        "patch（更新清单）, delete（删除清单）, tasks（查询清单内任务）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "get", "list", "patch", "delete", "tasks"],
                "description": "操作类型",
            },
            "tasklist_guid": {
                "type": "string",
                "description": "清单 GUID（action=get/patch/delete/tasks 时必填）",
            },
            "name": {"type": "string", "description": "清单名称（action=create 时必填；patch 时可选）"},
            "page_size": {"type": "number", "description": "每页数量"},
            "page_token": {"type": "string", "description": "分页标记"},
            "completed": {
                "type": "boolean",
                "description": "是否筛选已完成任务（action=tasks 时可选）",
            },
            "user_id_type": {
                "type": "string",
                "enum": ["open_id", "union_id", "user_id"],
                "description": "用户 ID 类型（默认 open_id）",
            },
        },
        "required": ["action"],
    },
    handler=_task_tasklist,
)


# ---------------------------------------------------------------------------
# feishu_task_comment
# ---------------------------------------------------------------------------


async def _task_comment(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")
    task_guid = kw.get("task_guid", "")
    comment_id = kw.get("comment_id", "")

    try:
        base = f"/open-apis/task/v2/tasks/{task_guid}/comments"

        if action == "create":
            if not kw.get("content"):
                return ok({"error": "content is required for 'create' action"})
            res = await client.post(base, {"content": kw["content"]})
            client.check(res, "task_comment.create")
            return ok(res.get("data", {}))

        elif action == "get":
            if not comment_id:
                return ok({"error": "comment_id is required for 'get' action"})
            res = await client.get(f"{base}/{comment_id}")
            client.check(res, "task_comment.get")
            return ok(res.get("data", {}))

        elif action == "list":
            params: dict = {}
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            res = await client.get(base, params=params)
            client.check(res, "task_comment.list")
            return ok(res.get("data", {}))

        elif action == "update":
            if not comment_id:
                return ok({"error": "comment_id is required for 'update' action"})
            if not kw.get("content"):
                return ok({"error": "content is required for 'update' action"})
            res = await client.put(f"{base}/{comment_id}", {"content": kw["content"]})
            client.check(res, "task_comment.update")
            return ok(res.get("data", {}))

        elif action == "delete":
            if not comment_id:
                return ok({"error": "comment_id is required for 'delete' action"})
            res = await client.delete(f"{base}/{comment_id}")
            client.check(res, "task_comment.delete")
            return ok({"success": True})

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


TaskCommentTool: FunctionTool = make_tool(
    name="feishu_task_comment",
    description=(
        "飞书任务评论管理工具（以机器人身份）。"
        "Actions: create（添加评论）, get（获取评论）, list（列出评论）, "
        "update（更新评论）, delete（删除评论）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "get", "list", "update", "delete"],
                "description": "操作类型",
            },
            "task_guid": {
                "type": "string",
                "description": "任务 GUID（必填）",
            },
            "comment_id": {
                "type": "string",
                "description": "评论 ID（action=get/update/delete 时必填）",
            },
            "content": {
                "type": "string",
                "description": "评论内容（action=create/update 时必填）",
            },
            "page_size": {"type": "number", "description": "每页数量"},
            "page_token": {"type": "string", "description": "分页标记"},
        },
        "required": ["action", "task_guid"],
    },
    handler=_task_comment,
)


# ---------------------------------------------------------------------------
# feishu_task_subtask
# ---------------------------------------------------------------------------


async def _task_subtask(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")
    task_guid = kw.get("task_guid", "")

    try:
        base = f"/open-apis/task/v2/tasks/{task_guid}/subtasks"

        if action == "create":
            if not kw.get("summary"):
                return ok({"error": "summary is required for 'create' action"})
            res = await client.post(base, {"task": {"summary": kw["summary"]}})
            client.check(res, "task_subtask.create")
            return ok(res.get("data", {}))

        elif action == "list":
            params: dict = {}
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            res = await client.get(base, params=params)
            client.check(res, "task_subtask.list")
            return ok(res.get("data", {}))

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


TaskSubtaskTool: FunctionTool = make_tool(
    name="feishu_task_subtask",
    description=(
        "飞书子任务管理工具（以机器人身份）。"
        "Actions: create（创建子任务）, list（查询子任务列表）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list"],
                "description": "操作类型",
            },
            "task_guid": {
                "type": "string",
                "description": "父任务 GUID（必填）",
            },
            "summary": {
                "type": "string",
                "description": "子任务标题（action=create 时必填）",
            },
            "page_size": {"type": "number", "description": "每页数量"},
            "page_token": {"type": "string", "description": "分页标记"},
        },
        "required": ["action", "task_guid"],
    },
    handler=_task_subtask,
)


# ---------------------------------------------------------------------------
# feishu_task_section
# ---------------------------------------------------------------------------


async def _task_section(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")
    uid_type = kw.get("user_id_type", "open_id")

    try:
        if action == "create":
            if not kw.get("name"):
                return ok({"error": "name is required for 'create' action"})
            if not kw.get("resource_type"):
                return ok({"error": "resource_type is required for 'create' action"})

            section_data: dict = {
                "name": kw["name"],
                "resource_type": kw["resource_type"],
            }
            if kw.get("resource_id"):
                section_data["resource_id"] = kw["resource_id"]
            if kw.get("insert_before"):
                section_data["insert_before"] = kw["insert_before"]
            if kw.get("insert_after"):
                section_data["insert_after"] = kw["insert_after"]

            res = await client.post(
                "/open-apis/task/v2/sections",
                section_data,
                params={"user_id_type": uid_type},
            )
            client.check(res, "task_section.create")
            return ok(res.get("data", {}))

        elif action == "get":
            section_guid = kw.get("section_guid", "")
            if not section_guid:
                return ok({"error": "section_guid is required for 'get' action"})
            res = await client.get(
                f"/open-apis/task/v2/sections/{section_guid}",
                params={"user_id_type": uid_type},
            )
            client.check(res, "task_section.get")
            return ok(res.get("data", {}))

        elif action == "patch":
            section_guid = kw.get("section_guid", "")
            if not section_guid:
                return ok({"error": "section_guid is required for 'patch' action"})

            update_data: dict = {}
            update_fields: list[str] = []
            for field in ("name", "insert_before", "insert_after"):
                if kw.get(field) is not None:
                    update_data[field] = kw[field]
                    update_fields.append(field)

            if not update_fields:
                return ok({"error": "No fields to update"})

            res = await client.patch(
                f"/open-apis/task/v2/sections/{section_guid}",
                {"section": update_data, "update_fields": update_fields},
                params={"user_id_type": uid_type},
            )
            client.check(res, "task_section.patch")
            return ok(res.get("data", {}))

        elif action == "list":
            if not kw.get("resource_type"):
                return ok({"error": "resource_type is required for 'list' action"})
            params: dict = {
                "resource_type": kw["resource_type"],
                "user_id_type": uid_type,
            }
            if kw.get("resource_id"):
                params["resource_id"] = kw["resource_id"]
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            res = await client.get("/open-apis/task/v2/sections", params=params)
            client.check(res, "task_section.list")
            return ok(res.get("data", {}))

        elif action == "tasks":
            section_guid = kw.get("section_guid", "")
            if not section_guid:
                return ok({"error": "section_guid is required for 'tasks' action"})
            params = {"user_id_type": uid_type}
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            if kw.get("completed") is not None:
                params["completed"] = kw["completed"]
            if kw.get("created_from"):
                ts = _parse_time_to_ms(kw["created_from"])
                params["created_from"] = ts if ts else kw["created_from"]
            if kw.get("created_to"):
                ts = _parse_time_to_ms(kw["created_to"])
                params["created_to"] = ts if ts else kw["created_to"]
            res = await client.get(
                f"/open-apis/task/v2/sections/{section_guid}/tasks", params=params
            )
            client.check(res, "task_section.tasks")
            return ok(res.get("data", {}))

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


TaskSectionTool: FunctionTool = make_tool(
    name="feishu_task_section",
    description=(
        "飞书任务自定义分组（Section）管理工具。"
        "Actions: create（创建分组）, get（获取分组详情）, patch（更新分组）, "
        "list（列出分组）, tasks（查询分组内任务）。"
        "resource_type 可选值：'tasklist'（任务清单）或 'my_tasks'（我的任务）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "get", "patch", "list", "tasks"],
                "description": "操作类型",
            },
            "section_guid": {
                "type": "string",
                "description": "分组 GUID（action=get/patch/tasks 时必填）",
            },
            "name": {
                "type": "string",
                "description": "分组名称（action=create 时必填；patch 时可选）。最大 100 个 UTF-8 字符。",
            },
            "resource_type": {
                "type": "string",
                "enum": ["tasklist", "my_tasks"],
                "description": "分组归属资源类型（action=create/list 时必填）",
            },
            "resource_id": {
                "type": "string",
                "description": (
                    "资源 ID（action=create/list 时可选）。"
                    "当 resource_type 为 'tasklist' 时填写清单 GUID；"
                    "'my_tasks' 时无需填写。"
                ),
            },
            "insert_before": {
                "type": "string",
                "description": "将分组插入到该 section_guid 前面（可选）",
            },
            "insert_after": {
                "type": "string",
                "description": "将分组插入到该 section_guid 后面（可选）",
            },
            "completed": {
                "type": "boolean",
                "description": "按任务完成状态过滤（action=tasks 时可选，不填则不过滤）",
            },
            "created_from": {
                "type": "string",
                "description": "按创建时间筛选的起始时间（action=tasks，ISO 8601 或毫秒时间戳）",
            },
            "created_to": {
                "type": "string",
                "description": "按创建时间筛选的结束时间（action=tasks，ISO 8601 或毫秒时间戳）",
            },
            "page_size": {"type": "number", "description": "每页数量"},
            "page_token": {"type": "string", "description": "分页标记"},
            "user_id_type": {
                "type": "string",
                "enum": ["open_id", "union_id", "user_id"],
                "description": "用户 ID 类型（默认 open_id）",
            },
        },
        "required": ["action"],
    },
    handler=_task_section,
)
