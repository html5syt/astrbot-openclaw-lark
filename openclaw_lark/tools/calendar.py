# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu calendar tools.

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


def _parse_time(ts: str) -> Optional[str]:
    """Parse ISO 8601 timestamp to RFC 3339 string (no conversion needed, just validate)."""
    if not ts:
        return None
    # Accept as-is if already ISO 8601
    try:
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return ts
    except ValueError:
        return None


def _ok(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# feishu_calendar_calendar
# ---------------------------------------------------------------------------


@dataclass
class CalendarCalendarTool(FunctionTool[AstrAgentContext]):
    """飞书日历管理工具：查询日历列表、获取日历信息、查询主日历。"""

    name: str = "feishu_calendar_calendar"
    description: str = (
        "飞书日历管理工具（以机器人身份）。"
        "Actions: list（查询日历列表）, get（获取指定日历信息）, primary（查询主日历信息）。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "get", "primary"],
                    "description": "操作类型",
                },
                "calendar_id": {
                    "type": "string",
                    "description": "日历 ID（action=get 时必填）",
                },
                "page_size": {
                    "type": "number",
                    "description": "每页数量（action=list，默认 50，最大 1000）",
                },
                "page_token": {
                    "type": "string",
                    "description": "分页标记（action=list）",
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
            if action == "list":
                params: dict = {}
                if kwargs.get("page_size"):
                    params["page_size"] = kwargs["page_size"]
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                res = await client.get("/open-apis/calendar/v4/calendars", params=params)
                client.check(res, "calendar_calendar.list")
                return _ok(res.get("data", {}))

            elif action == "get":
                calendar_id = kwargs.get("calendar_id", "")
                if not calendar_id:
                    return _ok({"error": "calendar_id is required for 'get' action"})
                res = await client.get(f"/open-apis/calendar/v4/calendars/{calendar_id}")
                client.check(res, "calendar_calendar.get")
                return _ok(res.get("data", {}))

            elif action == "primary":
                res = await client.post("/open-apis/calendar/v4/calendars/primary")
                client.check(res, "calendar_calendar.primary")
                return _ok(res.get("data", {}))

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})


# ---------------------------------------------------------------------------
# feishu_calendar_event
# ---------------------------------------------------------------------------


@dataclass
class CalendarEventTool(FunctionTool[AstrAgentContext]):
    """飞书日程管理工具：创建、查询、更新、删除、搜索日程，以及管理重复日程实例。"""

    name: str = "feishu_calendar_event"
    description: str = (
        "飞书日程管理工具（以机器人身份）。"
        "Actions: create（创建日程）, list（查询日程列表）, get（获取日程详情）, "
        "patch（更新日程）, delete（删除日程）, search（搜索日程）, "
        "reply（回复日程邀请）, instances（查询重复日程实例）。"
        "时间格式：ISO 8601/RFC 3339，例如 '2026-01-01T14:00:00+08:00'。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "list", "get", "patch", "delete", "search", "reply", "instances"],
                    "description": "操作类型",
                },
                "calendar_id": {
                    "type": "string",
                    "description": "日历 ID（默认使用 primary）",
                },
                "event_id": {
                    "type": "string",
                    "description": "日程 ID（get/patch/delete/reply/instances 时必填）",
                },
                "summary": {
                    "type": "string",
                    "description": "日程标题（create 时必填）",
                },
                "description": {
                    "type": "string",
                    "description": "日程描述",
                },
                "start_time": {
                    "type": "string",
                    "description": "开始时间，ISO 8601/RFC 3339 格式，例如 '2026-01-01T14:00:00+08:00'",
                },
                "end_time": {
                    "type": "string",
                    "description": "结束时间，ISO 8601/RFC 3339 格式",
                },
                "location": {
                    "type": "string",
                    "description": "地点（可选）",
                },
                "attendees": {
                    "type": "array",
                    "description": "参会人列表，每项为 {type: 'user'/'chat'/'resource', user_id?: string, chat_id?: string, room_id?: string}",
                    "items": {"type": "object"},
                },
                "query": {
                    "type": "string",
                    "description": "搜索关键词（action=search 时必填）",
                },
                "rsvp_status": {
                    "type": "string",
                    "enum": ["accept", "decline", "tentative"],
                    "description": "回复状态（action=reply 时必填）",
                },
                "page_token": {
                    "type": "string",
                    "description": "分页标记",
                },
                "page_size": {
                    "type": "number",
                    "description": "每页数量",
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
        calendar_id = kwargs.get("calendar_id", "primary")
        event_id = kwargs.get("event_id", "")

        try:
            if action == "create":
                if not kwargs.get("summary"):
                    return _ok({"error": "summary is required for 'create' action"})
                if not kwargs.get("start_time") or not kwargs.get("end_time"):
                    return _ok({"error": "start_time and end_time are required for 'create' action"})

                data: dict = {
                    "summary": kwargs["summary"],
                    "start_time": {"date_time": kwargs["start_time"]},
                    "end_time": {"date_time": kwargs["end_time"]},
                }
                if kwargs.get("description"):
                    data["description"] = kwargs["description"]
                if kwargs.get("location"):
                    data["location"] = {"name": kwargs["location"]}
                if kwargs.get("attendees"):
                    data["attendees"] = kwargs["attendees"]

                res = await client.post(
                    f"/open-apis/calendar/v4/calendars/{calendar_id}/events", data
                )
                client.check(res, "calendar_event.create")
                return _ok(res.get("data", {}))

            elif action == "list":
                params: dict = {}
                for k in ("start_time", "end_time", "page_token", "page_size"):
                    if kwargs.get(k):
                        params[k] = kwargs[k]
                res = await client.get(
                    f"/open-apis/calendar/v4/calendars/{calendar_id}/events", params=params
                )
                client.check(res, "calendar_event.list")
                return _ok(res.get("data", {}))

            elif action == "get":
                if not event_id:
                    return _ok({"error": "event_id is required for 'get' action"})
                res = await client.get(
                    f"/open-apis/calendar/v4/calendars/{calendar_id}/events/{event_id}"
                )
                client.check(res, "calendar_event.get")
                return _ok(res.get("data", {}))

            elif action == "patch":
                if not event_id:
                    return _ok({"error": "event_id is required for 'patch' action"})
                data = {}
                if kwargs.get("summary"):
                    data["summary"] = kwargs["summary"]
                if kwargs.get("description") is not None:
                    data["description"] = kwargs["description"]
                if kwargs.get("start_time"):
                    data["start_time"] = {"date_time": kwargs["start_time"]}
                if kwargs.get("end_time"):
                    data["end_time"] = {"date_time": kwargs["end_time"]}
                if kwargs.get("location"):
                    data["location"] = {"name": kwargs["location"]}

                res = await client.patch(
                    f"/open-apis/calendar/v4/calendars/{calendar_id}/events/{event_id}",
                    data,
                )
                client.check(res, "calendar_event.patch")
                return _ok(res.get("data", {}))

            elif action == "delete":
                if not event_id:
                    return _ok({"error": "event_id is required for 'delete' action"})
                res = await client.delete(
                    f"/open-apis/calendar/v4/calendars/{calendar_id}/events/{event_id}"
                )
                client.check(res, "calendar_event.delete")
                return _ok({"success": True})

            elif action == "search":
                query = kwargs.get("query", "")
                data = {"query": query}
                params = {}
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                if kwargs.get("page_size"):
                    params["page_size"] = kwargs["page_size"]
                res = await client.post(
                    f"/open-apis/calendar/v4/calendars/{calendar_id}/events/search",
                    data,
                )
                client.check(res, "calendar_event.search")
                return _ok(res.get("data", {}))

            elif action == "reply":
                if not event_id:
                    return _ok({"error": "event_id is required for 'reply' action"})
                rsvp_status = kwargs.get("rsvp_status")
                if not rsvp_status:
                    return _ok({"error": "rsvp_status is required for 'reply' action"})
                data = {"rsvp_status": rsvp_status}
                res = await client.post(
                    f"/open-apis/calendar/v4/calendars/{calendar_id}/events/{event_id}/reply",
                    data,
                )
                client.check(res, "calendar_event.reply")
                return _ok({"success": True})

            elif action == "instances":
                if not event_id:
                    return _ok({"error": "event_id is required for 'instances' action"})
                params = {}
                for k in ("start_time", "end_time", "page_token", "page_size"):
                    if kwargs.get(k):
                        params[k] = kwargs[k]
                res = await client.get(
                    f"/open-apis/calendar/v4/calendars/{calendar_id}/events/{event_id}/instances",
                    params=params,
                )
                client.check(res, "calendar_event.instances")
                return _ok(res.get("data", {}))

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})


# ---------------------------------------------------------------------------
# feishu_calendar_event_attendee
# ---------------------------------------------------------------------------


@dataclass
class CalendarEventAttendeeTool(FunctionTool[AstrAgentContext]):
    """飞书日程参会人管理工具：添加、查询、删除参会人。"""

    name: str = "feishu_calendar_event_attendee"
    description: str = (
        "飞书日程参会人管理工具（以机器人身份）。"
        "Actions: create（添加参会人）, list（查询参会人列表）, "
        "delete（删除参会人）, batch_delete（批量删除参会人）。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "list", "delete", "batch_delete"],
                    "description": "操作类型",
                },
                "calendar_id": {
                    "type": "string",
                    "description": "日历 ID（默认 primary）",
                },
                "event_id": {
                    "type": "string",
                    "description": "日程 ID（必填）",
                },
                "attendees": {
                    "type": "array",
                    "description": (
                        "参会人列表（action=create/batch_delete 时使用）。"
                        "每项为 {type: 'user'/'chat'/'resource', user_id?: string, "
                        "chat_id?: string, room_id?: string}"
                    ),
                    "items": {"type": "object"},
                },
                "attendee_id": {
                    "type": "string",
                    "description": "参会人 ID（action=delete 时使用）",
                },
                "page_token": {"type": "string", "description": "分页标记"},
                "page_size": {"type": "number", "description": "每页数量"},
            },
            "required": ["action", "event_id"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        action = kwargs.get("action")
        calendar_id = kwargs.get("calendar_id", "primary")
        event_id = kwargs.get("event_id", "")

        try:
            base = f"/open-apis/calendar/v4/calendars/{calendar_id}/events/{event_id}/attendees"

            if action == "create":
                attendees = kwargs.get("attendees", [])
                data = {"attendees": attendees}
                res = await client.post(base, data)
                client.check(res, "calendar_event_attendee.create")
                return _ok(res.get("data", {}))

            elif action == "list":
                params: dict = {}
                if kwargs.get("page_token"):
                    params["page_token"] = kwargs["page_token"]
                if kwargs.get("page_size"):
                    params["page_size"] = kwargs["page_size"]
                res = await client.get(base, params=params)
                client.check(res, "calendar_event_attendee.list")
                return _ok(res.get("data", {}))

            elif action == "delete":
                attendee_id = kwargs.get("attendee_id", "")
                if not attendee_id:
                    return _ok({"error": "attendee_id is required for 'delete' action"})
                res = await client.delete(f"{base}/{attendee_id}")
                client.check(res, "calendar_event_attendee.delete")
                return _ok({"success": True})

            elif action == "batch_delete":
                attendee_ids = [a.get("attendee_id", "") for a in (kwargs.get("attendees") or []) if a.get("attendee_id")]
                if not attendee_ids:
                    return _ok({"error": "attendees with attendee_id list required for 'batch_delete' action"})
                data = {"attendee_ids": attendee_ids}
                res = await client.post(f"{base}/batch_delete", data)
                client.check(res, "calendar_event_attendee.batch_delete")
                return _ok({"success": True})

            else:
                return _ok({"error": f"Unknown action: {action}"})

        except Exception as e:
            return _ok({"error": str(e)})


# ---------------------------------------------------------------------------
# feishu_calendar_freebusy
# ---------------------------------------------------------------------------


@dataclass
class CalendarFreebusyTool(FunctionTool[AstrAgentContext]):
    """飞书忙闲查询工具：查询指定用户在时间段内的忙闲状态。"""

    name: str = "feishu_calendar_freebusy"
    description: str = (
        "飞书忙闲查询工具（以机器人身份）。"
        "Actions: list（查询用户忙闲状态）。"
        "时间格式：ISO 8601/RFC 3339，例如 '2026-01-01T14:00:00+08:00'。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list"],
                    "description": "操作类型（固定为 list）",
                },
                "time_min": {
                    "type": "string",
                    "description": "查询开始时间，ISO 8601/RFC 3339 格式（必填）",
                },
                "time_max": {
                    "type": "string",
                    "description": "查询结束时间，ISO 8601/RFC 3339 格式（必填）",
                },
                "user_ids": {
                    "type": "array",
                    "description": "用户 open_id 列表（必填）",
                    "items": {"type": "string"},
                },
            },
            "required": ["action", "time_min", "time_max", "user_ids"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs: Any
    ) -> ToolExecResult:
        client = get_lark_client()
        try:
            time_min = kwargs.get("time_min", "")
            time_max = kwargs.get("time_max", "")
            user_ids = kwargs.get("user_ids", [])

            if not time_min or not time_max:
                return _ok({"error": "time_min and time_max are required"})
            if not user_ids:
                return _ok({"error": "user_ids is required"})

            data = {
                "time_min": time_min,
                "time_max": time_max,
                "user_ids": user_ids,
            }
            res = await client.post("/open-apis/calendar/v4/freebusy/batch_get", data)
            client.check(res, "calendar_freebusy.list")
            return _ok(res.get("data", {}))

        except Exception as e:
            return _ok({"error": str(e)})
