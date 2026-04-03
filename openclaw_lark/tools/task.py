# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu task tools.

from __future__ import annotations

import json
import re
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


@dataclass
class TaskTaskTool(FunctionTool[AstrAgentContext]):
    """飞书任务管理工具：创建、查询、更新任务。"""

    name: str = "feishu_task_task"
    description: str = (
        "飞书任务管理工具（以机器人身份）。"
        "Actions: create（创建任务）, get（获取任务详情）, "
        "list（查询我的任务列表）, patch（更新任务）。"
        "时间格式：ISO 8601/RFC 3339，例如 '2026-01-01T00:00:00+08:00'。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
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
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        action = kwargs.get("action")
        uid_type = kwargs.get("user_id_type", "open_id")

        try:
            if action == "create":
                if not kwargs.get("summary"):
                    return _ok({"error": "summary is required for 'create' action"})

                task_data: dict = {"summary": kwargs["summary"]}
                if kwargs.get("description"):
                    task_data["description"] = kwargs["description"]

                for field in ("due", "start"):
                    val = kwargs.get(field)
                    if val and val.get("timestamp"):
                        ts = _parse_time_to_ms(val["timestamp"])
                        if not ts:
                            return _ok({"error": f"{field}.timestamp format error. Use ISO 8601, e.g. '2026-01-01T00:00:00+08:00'"})
                        task_data[field] = {"timestamp": ts, "is_all_day": val.get("is_all_day", False)}

                if kwargs.get("members"):
                    task_data["members"] = kwargs["members"]
                if kwargs.get("tasklists"):
                    task_data["tasklists"] = kwargs["tasklists"]

                res = await client.post(
                    "/open-apis/task/v2/tasks",
                    {"task": task_data},
                )
                client.check(res, "task_task.create")
                return _ok(res.get("data", {}))

            elif action == "get":
                task_guid = kwargs.get("task_guid", "")
                if not task_guid:
                    return _ok({"error": "task_guid is required for 'get' action"})
                res = await client.get(
                    f"/open-apis/task/v2/tasks/{task_guid}",
                    params={"user_id_type": uid_type},
                )
                client.check(res, "task_task.get")
                return _ok(res.get("data", {}))

            elif action == "list":
                params: dict = {"user_id_type": uid_type}
                if kwargs.get("page_size"):
                    params["page_size"] = kwargs["page_size"]
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                if kwargs.get("completed") is not None:
                    params["completed"] = kwargs["completed"]
                res = await client.get("/open-apis/task/v2/tasks", params=params)
                client.check(res, "task_task.list")
                return _ok(res.get("data", {}))

            elif action == "patch":
                task_guid = kwargs.get("task_guid", "")
                if not task_guid:
                    return _ok({"error": "task_guid is required for 'patch' action"})

                update_data: dict = {}
                if kwargs.get("summary"):
                    update_data["summary"] = kwargs["summary"]
                if kwargs.get("description") is not None:
                    update_data["description"] = kwargs["description"]

                for field in ("due", "start"):
                    val = kwargs.get(field)
                    if val and val.get("timestamp"):
                        ts = _parse_time_to_ms(val["timestamp"])
                        if not ts:
                            return _ok({"error": f"{field}.timestamp format error"})
                        update_data[field] = {"timestamp": ts, "is_all_day": val.get("is_all_day", False)}

                completed_at = kwargs.get("completed_at")
                if completed_at is not None:
                    if completed_at == "0":
                        update_data["completed_at"] = "0"
                    elif re.match(r"^\d+$", completed_at):
                        update_data["completed_at"] = completed_at
                    else:
                        ts = _parse_time_to_ms(completed_at)
                        if not ts:
                            return _ok({"error": "completed_at format error"})
                        update_data["completed_at"] = ts

                if kwargs.get("members"):
                    update_data["members"] = kwargs["members"]

                update_fields = list(update_data.keys())
                data = {"task": update_data, "update_fields": update_fields}

                res = await client.patch(
                    f"/open-apis/task/v2/tasks/{task_guid}",
                    data,
                )
                client.check(res, "task_task.patch")
                return _ok(res.get("data", {}))

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})


# ---------------------------------------------------------------------------
# feishu_task_tasklist
# ---------------------------------------------------------------------------


@dataclass
class TaskTasklistTool(FunctionTool[AstrAgentContext]):
    """飞书任务清单管理工具：创建、查询、更新、删除清单，以及查询清单内的任务。"""

    name: str = "feishu_task_tasklist"
    description: str = (
        "飞书任务清单管理工具（以机器人身份）。"
        "Actions: create（创建清单）, get（获取清单详情）, list（列出清单）, "
        "patch（更新清单）, delete（删除清单）, tasks（查询清单内任务）。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
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
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        action = kwargs.get("action")
        tasklist_guid = kwargs.get("tasklist_guid", "")

        try:
            if action == "create":
                if not kwargs.get("name"):
                    return _ok({"error": "name is required for 'create' action"})
                res = await client.post(
                    "/open-apis/task/v2/tasklists",
                    {"tasklist": {"name": kwargs["name"]}},
                )
                client.check(res, "task_tasklist.create")
                return _ok(res.get("data", {}))

            elif action == "get":
                if not tasklist_guid:
                    return _ok({"error": "tasklist_guid is required for 'get' action"})
                res = await client.get(f"/open-apis/task/v2/tasklists/{tasklist_guid}")
                client.check(res, "task_tasklist.get")
                return _ok(res.get("data", {}))

            elif action == "list":
                params: dict = {}
                if kwargs.get("page_size"):
                    params["page_size"] = kwargs["page_size"]
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                res = await client.get("/open-apis/task/v2/tasklists", params=params)
                client.check(res, "task_tasklist.list")
                return _ok(res.get("data", {}))

            elif action == "patch":
                if not tasklist_guid:
                    return _ok({"error": "tasklist_guid is required for 'patch' action"})
                update: dict = {}
                if kwargs.get("name"):
                    update["name"] = kwargs["name"]
                res = await client.patch(
                    f"/open-apis/task/v2/tasklists/{tasklist_guid}",
                    {"tasklist": update, "update_fields": list(update.keys())},
                )
                client.check(res, "task_tasklist.patch")
                return _ok(res.get("data", {}))

            elif action == "delete":
                if not tasklist_guid:
                    return _ok({"error": "tasklist_guid is required for 'delete' action"})
                res = await client.delete(f"/open-apis/task/v2/tasklists/{tasklist_guid}")
                client.check(res, "task_tasklist.delete")
                return _ok({"success": True})

            elif action == "tasks":
                if not tasklist_guid:
                    return _ok({"error": "tasklist_guid is required for 'tasks' action"})
                params = {}
                for k in ("page_size", "page_token", "completed"):
                    if kwargs.get(k) is not None:
                        params[k] = kwargs[k]
                res = await client.get(
                    f"/open-apis/task/v2/tasklists/{tasklist_guid}/tasks", params=params
                )
                client.check(res, "task_tasklist.tasks")
                return _ok(res.get("data", {}))

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})


# ---------------------------------------------------------------------------
# feishu_task_comment
# ---------------------------------------------------------------------------


@dataclass
class TaskCommentTool(FunctionTool[AstrAgentContext]):
    """飞书任务评论管理工具：创建、查询、更新、删除任务评论。"""

    name: str = "feishu_task_comment"
    description: str = (
        "飞书任务评论管理工具（以机器人身份）。"
        "Actions: create（添加评论）, get（获取评论）, list（列出评论）, "
        "update（更新评论）, delete（删除评论）。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
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
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        action = kwargs.get("action")
        task_guid = kwargs.get("task_guid", "")
        comment_id = kwargs.get("comment_id", "")

        try:
            base = f"/open-apis/task/v2/tasks/{task_guid}/comments"

            if action == "create":
                if not kwargs.get("content"):
                    return _ok({"error": "content is required for 'create' action"})
                res = await client.post(base, {"content": kwargs["content"]})
                client.check(res, "task_comment.create")
                return _ok(res.get("data", {}))

            elif action == "get":
                if not comment_id:
                    return _ok({"error": "comment_id is required for 'get' action"})
                res = await client.get(f"{base}/{comment_id}")
                client.check(res, "task_comment.get")
                return _ok(res.get("data", {}))

            elif action == "list":
                params: dict = {}
                if kwargs.get("page_size"):
                    params["page_size"] = kwargs["page_size"]
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                res = await client.get(base, params=params)
                client.check(res, "task_comment.list")
                return _ok(res.get("data", {}))

            elif action == "update":
                if not comment_id:
                    return _ok({"error": "comment_id is required for 'update' action"})
                if not kwargs.get("content"):
                    return _ok({"error": "content is required for 'update' action"})
                res = await client.put(f"{base}/{comment_id}", {"content": kwargs["content"]})
                client.check(res, "task_comment.update")
                return _ok(res.get("data", {}))

            elif action == "delete":
                if not comment_id:
                    return _ok({"error": "comment_id is required for 'delete' action"})
                res = await client.delete(f"{base}/{comment_id}")
                client.check(res, "task_comment.delete")
                return _ok({"success": True})

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})


# ---------------------------------------------------------------------------
# feishu_task_subtask
# ---------------------------------------------------------------------------


@dataclass
class TaskSubtaskTool(FunctionTool[AstrAgentContext]):
    """飞书子任务管理工具：创建、查询子任务。"""

    name: str = "feishu_task_subtask"
    description: str = (
        "飞书子任务管理工具（以机器人身份）。"
        "Actions: create（创建子任务）, list（查询子任务列表）。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
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
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        action = kwargs.get("action")
        task_guid = kwargs.get("task_guid", "")

        try:
            base = f"/open-apis/task/v2/tasks/{task_guid}/subtasks"

            if action == "create":
                if not kwargs.get("summary"):
                    return _ok({"error": "summary is required for 'create' action"})
                res = await client.post(base, {"task": {"summary": kwargs["summary"]}})
                client.check(res, "task_subtask.create")
                return _ok(res.get("data", {}))

            elif action == "list":
                params: dict = {}
                if kwargs.get("page_size"):
                    params["page_size"] = kwargs["page_size"]
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                res = await client.get(base, params=params)
                client.check(res, "task_subtask.list")
                return _ok(res.get("data", {}))

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})
