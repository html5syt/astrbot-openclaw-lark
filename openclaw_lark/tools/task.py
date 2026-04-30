# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu task tools.

from __future__ import annotations

import base64
import re
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
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
    user_id = kw.get("_user_id")

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

            members = list(kw["members"]) if kw.get("members") else []
            current_user_id = kw.get("current_user_id")
            if current_user_id:
                member_ids = {m.get("id") for m in members}
                if current_user_id not in member_ids:
                    members.append({"id": current_user_id, "type": "user", "role": "follower"})
            if members:
                task_data["members"] = members

            if kw.get("repeat_rule"):
                task_data["repeat_rule"] = kw["repeat_rule"]
            if kw.get("tasklists"):
                task_data["tasklists"] = kw["tasklists"]

            res = await client.post(
                "/open-apis/task/v2/tasks",
                {"task": task_data},
                params={"user_id_type": uid_type},
                user_id=user_id,
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
                user_id=user_id,
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
            if kw.get("agent_task_status") is not None:
                params["agent_task_status"] = kw["agent_task_status"]
            res = await client.get("/open-apis/task/v2/tasks", params=params, user_id=user_id)
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
            if kw.get("repeat_rule"):
                update_data["repeat_rule"] = kw["repeat_rule"]

            update_fields = list(update_data.keys())
            data = {"task": update_data, "update_fields": update_fields}

            res = await client.patch(
                f"/open-apis/task/v2/tasks/{task_guid}",
                data,
                params={"user_id_type": uid_type},
                user_id=user_id,
            )
            client.check(res, "task_task.patch")
            return ok(res.get("data", {}))

        elif action == "add_members":
            task_guid = kw.get("task_guid", "")
            if not task_guid:
                return ok({"error": "task_guid is required for 'add_members' action"})
            members = kw.get("members")
            if not members:
                return ok({"error": "members is required and cannot be empty for 'add_members' action"})

            member_data = [
                {"id": m["id"], "type": m.get("type", "user"), "role": m.get("role", "assignee")}
                for m in members
            ]
            body: dict = {"members": member_data}
            if kw.get("client_token"):
                body["client_token"] = kw["client_token"]

            res = await client.post(
                f"/open-apis/task/v2/tasks/{task_guid}/add_members",
                body,
                params={"user_id_type": uid_type},
                user_id=user_id,
            )
            client.check(res, "task_task.add_members")
            return ok(res.get("data", {}))

        elif action == "append_steps":
            task_guid = kw.get("task_guid", "")
            if not task_guid:
                return ok({"error": "task_guid is required for 'append_steps' action"})
            idempotent_key = kw.get("idempotent_key", "")
            if not idempotent_key:
                return ok({"error": "idempotent_key is required for 'append_steps' action"})
            task_steps = kw.get("task_steps")
            if not task_steps:
                return ok({"error": "task_steps is required and cannot be empty for 'append_steps' action"})

            # append_steps always uses tenant (app) access token
            res = await client.post(
                "/open-apis/task/v2/agent_task_step_info/append_task_steps",
                {
                    "task_guid": task_guid,
                    "idempotent_key": idempotent_key,
                    "task_steps": task_steps,
                },
                user_id=None,  # force tenant token regardless of global auth_mode
            )
            client.check(res, "task_task.append_steps")
            return ok(res.get("data", {}))

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


TaskTaskTool: FunctionTool = make_tool(
    name="feishu_task_task",
    description=(
        "【以用户或应用身份】飞书任务管理工具。"
        "用于创建、查询、更新任务，以及添加任务成员、追加任务步骤记录。"
        "Actions: create（创建任务）, get（获取任务详情）, "
        "list（查询任务列表，仅返回我负责的任务）, patch（更新任务）, "
        "add_members（添加任务成员）, append_steps（追加任务步骤记录，固定使用应用身份）。"
        "时间格式：ISO 8601/RFC 3339（含时区），例如 '2026-01-01T00:00:00+08:00'。"
        "支持通过 auth_type 参数切换用户（user）或应用（tenant）身份，append_steps 固定使用应用身份。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "get", "list", "patch", "add_members", "append_steps"],
                "description": "操作类型",
            },
            "auth_type": {
                "type": "string",
                "enum": ["tenant", "user"],
                "description": "授权类型，默认 user（用户身份）；tenant 为应用身份。",
            },
            "task_guid": {
                "type": "string",
                "description": "任务 GUID（action=get/patch/add_members/append_steps 时必填）",
            },
            "summary": {
                "type": "string",
                "description": "任务标题（action=create 时必填；action=patch 时可选）",
            },
            "current_user_id": {
                "type": "string",
                "description": (
                    "当前用户的 open_id（action=create 时建议填写，从消息上下文的 SenderId 获取）。"
                    "若 members 中不包含此用户，工具会自动添加为 follower，确保创建者可编辑任务。"
                ),
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
                        "description": "截止时间，ISO 8601/RFC 3339 格式（含时区），例如 '2026-01-01T00:00:00+08:00'",
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
                        "description": "开始时间，ISO 8601/RFC 3339 格式（含时区）",
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
                "description": "任务成员列表（assignee=负责人，follower=关注人）。成员类型（type）支持 user 和 app，默认 user。",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "成员 open_id"},
                        "type": {"type": "string", "enum": ["user", "app"], "description": "成员类型，默认 user"},
                        "role": {"type": "string", "enum": ["assignee", "follower"]},
                    },
                },
            },
            "repeat_rule": {
                "type": "string",
                "description": "重复规则（RRULE 格式，action=create/patch 时可选）",
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
            "client_token": {
                "type": "string",
                "description": "幂等 token，提供后实现幂等行为（action=add_members 时可选）",
            },
            "completed": {
                "type": "boolean",
                "description": "是否筛选已完成任务（action=list 时可选）",
            },
            "agent_task_status": {
                "type": "integer",
                "description": "Agent 任务状态过滤（action=list 时可选）",
            },
            "idempotent_key": {
                "type": "string",
                "description": "幂等键（action=append_steps 时必填）",
            },
            "task_steps": {
                "type": "array",
                "description": "要追加的任务步骤列表（action=append_steps 时必填，至少一项）",
                "items": {
                    "type": "object",
                    "properties": {
                        "quote": {"type": "string", "description": "步骤引用信息"},
                        "content": {"type": "string", "description": "步骤内容"},
                        "timestamp": {"type": "integer", "description": "步骤时间戳"},
                    },
                    "required": ["quote", "content", "timestamp"],
                },
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
    uid_type = kw.get("user_id_type", "open_id")
    user_id = kw.get("_user_id")

    try:
        if action == "create":
            if not kw.get("name"):
                return ok({"error": "name is required for 'create' action"})
            body: dict = {"name": kw["name"]}
            if kw.get("members"):
                body["members"] = [
                    {"id": m["id"], "type": m.get("type", "user"), "role": m.get("role", "editor")}
                    for m in kw["members"]
                ]
            res = await client.post(
                "/open-apis/task/v2/tasklists",
                {"tasklist": body},
                params={"user_id_type": uid_type},
                user_id=user_id,
            )
            client.check(res, "task_tasklist.create")
            return ok(res.get("data", {}))

        elif action == "get":
            if not tasklist_guid:
                return ok({"error": "tasklist_guid is required for 'get' action"})
            res = await client.get(
                f"/open-apis/task/v2/tasklists/{tasklist_guid}",
                params={"user_id_type": uid_type},
                user_id=user_id,
            )
            client.check(res, "task_tasklist.get")
            return ok(res.get("data", {}))

        elif action == "list":
            params: dict = {"user_id_type": uid_type}
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            res = await client.get("/open-apis/task/v2/tasklists", params=params, user_id=user_id)
            client.check(res, "task_tasklist.list")
            return ok(res.get("data", {}))

        elif action == "patch":
            if not tasklist_guid:
                return ok({"error": "tasklist_guid is required for 'patch' action"})
            update: dict = {}
            if kw.get("name"):
                update["name"] = kw["name"]
            if not update:
                return ok({"error": "No fields to update"})
            res = await client.patch(
                f"/open-apis/task/v2/tasklists/{tasklist_guid}",
                {"tasklist": update, "update_fields": list(update.keys())},
                params={"user_id_type": uid_type},
                user_id=user_id,
            )
            client.check(res, "task_tasklist.patch")
            return ok(res.get("data", {}))

        elif action == "add_members":
            if not tasklist_guid:
                return ok({"error": "tasklist_guid is required for 'add_members' action"})
            members = kw.get("members")
            if not members:
                return ok({"error": "members is required and cannot be empty for 'add_members' action"})
            member_data = [
                {"id": m["id"], "type": m.get("type", "user"), "role": m.get("role", "editor")}
                for m in members
            ]
            res = await client.post(
                f"/open-apis/task/v2/tasklists/{tasklist_guid}/add_members",
                {"members": member_data},
                params={"user_id_type": uid_type},
                user_id=user_id,
            )
            client.check(res, "task_tasklist.add_members")
            return ok(res.get("data", {}))

        elif action == "tasks":
            if not tasklist_guid:
                return ok({"error": "tasklist_guid is required for 'tasks' action"})
            params = {"user_id_type": uid_type}
            for k in ("page_size", "page_token", "completed"):
                if kw.get(k) is not None:
                    params[k] = kw[k]
            res = await client.get(
                f"/open-apis/task/v2/tasklists/{tasklist_guid}/tasks",
                params=params,
                user_id=user_id,
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
        "【以用户或应用身份】飞书任务清单管理工具。"
        "当用户要求创建/查询/管理清单、查看清单内的任务时使用。"
        "Actions: create（创建清单）, get（获取清单详情）, list（列出所有可读取的清单）, "
        "tasks（列出清单内的任务）, patch（更新清单）, add_members（添加成员）。"
        "支持通过 auth_type 参数切换用户（user）或应用（tenant）身份，默认 user。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "get", "list", "patch", "add_members", "tasks"],
                "description": "操作类型",
            },
            "auth_type": {
                "type": "string",
                "enum": ["tenant", "user"],
                "description": "授权类型，默认 user（用户身份）；tenant 为应用身份。",
            },
            "tasklist_guid": {
                "type": "string",
                "description": "清单 GUID（action=get/patch/add_members/tasks 时必填）",
            },
            "name": {"type": "string", "description": "清单名称（action=create 时必填；patch 时可选）"},
            "members": {
                "type": "array",
                "description": (
                    "成员列表（action=create/add_members 时使用）。"
                    "editor=可编辑，viewer=可查看；类型支持 user 和 app，默认 user。"
                    "注意：创建人自动成为 owner，如在 members 中也指定创建人，该用户最终成为 owner（同一用户只能有一个角色）。"
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "成员 ID（通常为 open_id）"},
                        "type": {"type": "string", "enum": ["user", "app"], "description": "成员类型，默认 user"},
                        "role": {"type": "string", "enum": ["editor", "viewer"], "description": "成员角色"},
                    },
                    "required": ["id"],
                },
            },
            "page_size": {"type": "number", "description": "每页数量（默认 50，最大 100）"},
            "page_token": {"type": "string", "description": "分页标记"},
            "completed": {
                "type": "boolean",
                "description": "是否只返回已完成的任务（action=tasks 时可选，默认返回所有）",
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
    uid_type = kw.get("user_id_type", "open_id")
    user_id = kw.get("_user_id")

    try:
        if action == "create":
            if not task_guid:
                return ok({"error": "task_guid is required for 'create' action"})
            if not kw.get("content"):
                return ok({"error": "content is required for 'create' action"})
            body: dict = {
                "content": kw["content"],
                "resource_type": "task",
                "resource_id": task_guid,
            }
            if kw.get("reply_to_comment_id"):
                body["reply_to_comment_id"] = kw["reply_to_comment_id"]
            res = await client.post(
                f"/open-apis/task/v2/tasks/{task_guid}/comments",
                body,
                params={"user_id_type": uid_type},
                user_id=user_id,
            )
            client.check(res, "task_comment.create")
            return ok(res.get("data", {}))

        elif action == "get":
            if not comment_id:
                return ok({"error": "comment_id is required for 'get' action"})
            res = await client.get(
                f"/open-apis/task/v2/comments/{comment_id}",
                params={"user_id_type": uid_type},
                user_id=user_id,
            )
            client.check(res, "task_comment.get")
            return ok(res.get("data", {}))

        elif action == "list":
            resource_id = kw.get("resource_id") or task_guid
            if not resource_id:
                return ok({"error": "resource_id (or task_guid) is required for 'list' action"})
            params: dict = {
                "resource_type": "task",
                "resource_id": resource_id,
                "user_id_type": uid_type,
            }
            if kw.get("direction"):
                params["direction"] = kw["direction"]
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            res = await client.get("/open-apis/task/v2/comments", params=params, user_id=user_id)
            client.check(res, "task_comment.list")
            return ok(res.get("data", {}))

        elif action == "update":
            if not comment_id:
                return ok({"error": "comment_id is required for 'update' action"})
            if not kw.get("content"):
                return ok({"error": "content is required for 'update' action"})
            res = await client.put(
                f"/open-apis/task/v2/comments/{comment_id}",
                {"content": kw["content"]},
                user_id=user_id,
            )
            client.check(res, "task_comment.update")
            return ok(res.get("data", {}))

        elif action == "delete":
            if not comment_id:
                return ok({"error": "comment_id is required for 'delete' action"})
            res = await client.delete(
                f"/open-apis/task/v2/comments/{comment_id}",
                user_id=user_id,
            )
            client.check(res, "task_comment.delete")
            return ok({"success": True})

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


TaskCommentTool: FunctionTool = make_tool(
    name="feishu_task_comment",
    description=(
        "【以用户或应用身份】飞书任务评论管理工具。"
        "当用户要求添加/查询任务评论、回复评论时使用。"
        "Actions: create（添加评论）, list（列出任务的所有评论）, get（获取单个评论详情）, "
        "update（更新评论）, delete（删除评论）。"
        "支持通过 auth_type 参数切换用户（user）或应用（tenant）身份。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "get", "list", "update", "delete"],
                "description": "操作类型",
            },
            "auth_type": {
                "type": "string",
                "enum": ["tenant", "user"],
                "description": "授权类型，默认 user（用户身份）；tenant 为应用身份。",
            },
            "task_guid": {
                "type": "string",
                "description": "任务 GUID（action=create 时必填；list 时作为 resource_id 的备用）",
            },
            "resource_id": {
                "type": "string",
                "description": "要获取评论的资源 ID（任务 GUID，action=list 时必填，优先于 task_guid）",
            },
            "comment_id": {
                "type": "string",
                "description": "评论 ID（action=get/update/delete 时必填）",
            },
            "content": {
                "type": "string",
                "description": "评论内容，纯文本，最长 3000 字符（action=create/update 时必填）",
            },
            "reply_to_comment_id": {
                "type": "string",
                "description": "要回复的评论 ID（action=create 时可选，用于回复某条评论）",
            },
            "direction": {
                "type": "string",
                "enum": ["asc", "desc"],
                "description": "排序方式（asc=从旧到新，desc=从新到旧，默认 asc，action=list 时可选）",
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
    handler=_task_comment,
)


# ---------------------------------------------------------------------------
# feishu_task_subtask
# ---------------------------------------------------------------------------


async def _task_subtask(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")
    task_guid = kw.get("task_guid", "")
    uid_type = kw.get("user_id_type", "open_id")
    user_id = kw.get("_user_id")

    try:
        base = f"/open-apis/task/v2/tasks/{task_guid}/subtasks"

        if action == "create":
            if not task_guid:
                return ok({"error": "task_guid is required for 'create' action"})
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
                task_data["members"] = [
                    {"id": m["id"], "type": m.get("type", "user"), "role": m.get("role", "assignee")}
                    for m in kw["members"]
                ]

            res = await client.post(
                base,
                {"task": task_data},
                params={"user_id_type": uid_type},
                user_id=user_id,
            )
            client.check(res, "task_subtask.create")
            return ok(res.get("data", {}))

        elif action == "list":
            if not task_guid:
                return ok({"error": "task_guid is required for 'list' action"})
            params: dict = {"user_id_type": uid_type}
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            res = await client.get(base, params=params, user_id=user_id)
            client.check(res, "task_subtask.list")
            return ok(res.get("data", {}))

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


TaskSubtaskTool: FunctionTool = make_tool(
    name="feishu_task_subtask",
    description=(
        "【以用户或应用身份】飞书任务的子任务管理工具。"
        "当用户要求创建子任务、查询任务的子任务列表时使用。"
        "Actions: create（创建子任务）, list（列出任务的所有子任务）。"
        "支持通过 auth_type 参数切换用户（user）或应用（tenant）身份。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list"],
                "description": "操作类型",
            },
            "auth_type": {
                "type": "string",
                "enum": ["tenant", "user"],
                "description": "授权类型，默认 user（用户身份）；tenant 为应用身份。",
            },
            "task_guid": {
                "type": "string",
                "description": "父任务 GUID（必填）",
            },
            "summary": {
                "type": "string",
                "description": "子任务标题（action=create 时必填）",
            },
            "description": {
                "type": "string",
                "description": "子任务描述（action=create 时可选）",
            },
            "due": {
                "type": "object",
                "description": "截止时间（action=create 时可选）",
                "properties": {
                    "timestamp": {
                        "type": "string",
                        "description": "截止时间，ISO 8601/RFC 3339 格式（含时区），例如 '2026-01-01T00:00:00+08:00'",
                    },
                    "is_all_day": {"type": "boolean", "description": "是否全天任务"},
                },
            },
            "start": {
                "type": "object",
                "description": "开始时间（action=create 时可选）",
                "properties": {
                    "timestamp": {
                        "type": "string",
                        "description": "开始时间，ISO 8601/RFC 3339 格式（含时区）",
                    },
                    "is_all_day": {"type": "boolean", "description": "是否全天"},
                },
            },
            "members": {
                "type": "array",
                "description": "子任务成员列表（assignee=负责人，follower=关注人）。成员类型支持 user 和 app，默认 user。",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "成员 ID（通常为 open_id）"},
                        "type": {"type": "string", "enum": ["user", "app"], "description": "成员类型，默认 user"},
                        "role": {"type": "string", "enum": ["assignee", "follower"]},
                    },
                    "required": ["id"],
                },
            },
            "page_size": {"type": "number", "description": "每页数量（默认 50，最大 100）"},
            "page_token": {"type": "string", "description": "分页标记"},
            "user_id_type": {
                "type": "string",
                "enum": ["open_id", "union_id", "user_id"],
                "description": "用户 ID 类型（默认 open_id）",
            },
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
    user_id = kw.get("_user_id")

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
                user_id=user_id,
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
                user_id=user_id,
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
                user_id=user_id,
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
            res = await client.get("/open-apis/task/v2/sections", params=params, user_id=user_id)
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
                f"/open-apis/task/v2/sections/{section_guid}/tasks",
                params=params,
                user_id=user_id,
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
        "【以用户或应用身份】飞书任务自定义分组（Section）管理工具。"
        "用于创建、查询、更新自定义分组，以及列出分组内的任务。"
        "Actions: create（创建分组）, get（获取分组详情）, patch（更新分组）, "
        "list（获取分组列表）, tasks（获取分组任务列表）。"
        "resource_type 可选值：'tasklist'（任务清单）或 'my_tasks'（我的任务）。"
        "支持通过 auth_type 参数切换用户（user）或应用（tenant）身份。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "get", "patch", "list", "tasks"],
                "description": "操作类型",
            },
            "auth_type": {
                "type": "string",
                "enum": ["tenant", "user"],
                "description": "授权类型，默认 user（用户身份）；tenant 为应用身份。",
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


# ---------------------------------------------------------------------------
# feishu_task_agent
# ---------------------------------------------------------------------------


async def _task_task_agent(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")

    try:
        if action == "register":
            # Always tenant (app) identity
            res = await client.post(
                "/open-apis/task/v2/agent/register_agent",
                None,
                user_id=None,
            )
            client.check(res, "task_agent.register")
            return ok(res.get("data", {}))

        elif action == "update_profile":
            profile_content = kw.get("profile_content", "")
            if not profile_content:
                return ok({"error": "profile_content is required for 'update_profile' action"})
            res = await client.post(
                "/open-apis/task/v2/agent/update_agent_profile",
                {"profile_content": profile_content},
                user_id=None,
            )
            client.check(res, "task_agent.update_profile")
            return ok(res.get("data", {}))

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


TaskTaskAgentTool: FunctionTool = make_tool(
    name="feishu_task_agent",
    description=(
        "飞书任务 Agent 注册管理工具（固定使用应用身份）。"
        "用于注册任务 Agent 或更新任务 Agent 的 Profile 内容。"
        "Actions: register（注册任务 Agent）, update_profile（更新 Agent Profile）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["register", "update_profile"],
                "description": "操作类型",
            },
            "profile_content": {
                "type": "string",
                "description": "Agent Profile 内容（action=update_profile 时必填）",
            },
        },
        "required": ["action"],
    },
    handler=_task_task_agent,
)


# ---------------------------------------------------------------------------
# feishu_task_attachment
# ---------------------------------------------------------------------------


async def _task_attachment(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")

    try:
        if action == "upload":
            resource_type = kw.get("resource_type", "task")
            resource_id = kw.get("resource_id", "")
            if not resource_id:
                return ok({"error": "resource_id is required for 'upload' action"})
            file_b64 = kw.get("file", "")
            if not file_b64:
                return ok({"error": "file is required for 'upload' action"})

            try:
                file_bytes = base64.b64decode(file_b64)
            except Exception:
                return ok({"error": "file must be a valid base64-encoded string"})

            file_name = kw.get("name") or "attachment"

            # Always use tenant access token for attachment upload
            token = await client.get_tenant_token()
            url = f"{client.base_url}/open-apis/task/v2/attachments/upload"

            async with httpx.AsyncClient(timeout=60.0) as hc:
                resp = await hc.post(
                    url,
                    files={"file": (file_name, file_bytes, "application/octet-stream")},
                    data={"resource_type": resource_type, "resource_id": resource_id},
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                res = resp.json()

            client.check(res, "task_attachment.upload")
            return ok(res.get("data", {}))

        else:
            return ok({"error": f"Unknown action: {action}"})

    except Exception as e:
        return ok({"error": str(e)})


TaskAttachmentTool: FunctionTool = make_tool(
    name="feishu_task_attachment",
    description=(
        "飞书任务附件工具（固定使用应用身份）。"
        "用于上传任务附件（base64 编码文件）。"
        "Actions: upload（上传附件）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["upload"],
                "description": "操作类型",
            },
            "resource_type": {
                "type": "string",
                "enum": ["task", "task_delivery"],
                "description": "资源类型，可选值：task、task_delivery。默认 task。",
            },
            "resource_id": {
                "type": "string",
                "description": "资源 ID（任务 GUID），action=upload 时必填。",
            },
            "file": {
                "type": "string",
                "description": "文件内容的 base64 编码字符串（action=upload 时必填）",
            },
            "name": {
                "type": "string",
                "description": "文件名（可选，默认 'attachment'）",
            },
        },
        "required": ["action", "resource_id", "file"],
    },
    handler=_task_attachment,
)
