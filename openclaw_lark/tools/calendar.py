# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Feishu calendar tools.

from __future__ import annotations

from typing import Any

from astrbot.api import FunctionTool

from ..lark_client import get_lark_client
from ._common import ok, make_tool


# ---------------------------------------------------------------------------
# feishu_calendar_calendar
# ---------------------------------------------------------------------------


async def _calendar_calendar(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")
    try:
        if action == "list":
            params: dict = {}
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            res = await client.get("/open-apis/calendar/v4/calendars", params=params)
            client.check(res, "calendar_calendar.list")
            return ok(res.get("data", {}))
        if action == "get":
            cid = kw.get("calendar_id", "")
            if not cid:
                return ok({"error": "calendar_id is required for 'get'"})
            res = await client.get(f"/open-apis/calendar/v4/calendars/{cid}")
            client.check(res, "calendar_calendar.get")
            return ok(res.get("data", {}))
        if action == "primary":
            res = await client.post("/open-apis/calendar/v4/calendars/primary")
            client.check(res, "calendar_calendar.primary")
            return ok(res.get("data", {}))
        return ok({"error": f"Unknown action: {action}"})
    except Exception as e:
        return ok({"error": str(e)})


CalendarCalendarTool: FunctionTool = make_tool(
    name="feishu_calendar_calendar",
    description=(
        "飞书日历管理工具（以机器人身份）。"
        "action: list（查询日历列表）, get（获取指定日历信息）, primary（查询主日历信息）。"
    ),
    parameters={
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
    },
    handler=_calendar_calendar,
)


# ---------------------------------------------------------------------------
# feishu_calendar_event
# ---------------------------------------------------------------------------


async def _calendar_event(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")
    cal_id = kw.get("calendar_id", "primary")
    ev_id = kw.get("event_id", "")
    try:
        base = f"/open-apis/calendar/v4/calendars/{cal_id}/events"

        if action == "create":
            if not kw.get("summary"):
                return ok({"error": "summary is required"})
            if not kw.get("start_time") or not kw.get("end_time"):
                return ok({"error": "start_time and end_time are required"})
            data: dict = {
                "summary": kw["summary"],
                "start_time": {"date_time": kw["start_time"]},
                "end_time": {"date_time": kw["end_time"]},
            }
            if kw.get("description"):
                data["description"] = kw["description"]
            if kw.get("location"):
                data["location"] = {"name": kw["location"]}
            if kw.get("attendees"):
                data["attendees"] = kw["attendees"]
            res = await client.post(base, data)
            client.check(res, "calendar_event.create")
            return ok(res.get("data", {}))

        if action == "list":
            params: dict = {}
            for k in ("start_time", "end_time", "page_token", "page_size"):
                if kw.get(k):
                    params[k] = kw[k]
            res = await client.get(base, params=params)
            client.check(res, "calendar_event.list")
            return ok(res.get("data", {}))

        if action == "get":
            if not ev_id:
                return ok({"error": "event_id is required"})
            res = await client.get(f"{base}/{ev_id}")
            client.check(res, "calendar_event.get")
            return ok(res.get("data", {}))

        if action == "patch":
            if not ev_id:
                return ok({"error": "event_id is required"})
            data = {}
            for f in ("summary", "description"):
                if kw.get(f) is not None:
                    data[f] = kw[f]
            if kw.get("start_time"):
                data["start_time"] = {"date_time": kw["start_time"]}
            if kw.get("end_time"):
                data["end_time"] = {"date_time": kw["end_time"]}
            if kw.get("location"):
                data["location"] = {"name": kw["location"]}
            res = await client.patch(f"{base}/{ev_id}", data)
            client.check(res, "calendar_event.patch")
            return ok(res.get("data", {}))

        if action == "delete":
            if not ev_id:
                return ok({"error": "event_id is required"})
            res = await client.delete(f"{base}/{ev_id}")
            client.check(res, "calendar_event.delete")
            return ok({"success": True})

        if action == "search":
            query = kw.get("query", "")
            params = {}
            for k in ("page_token", "page_size"):
                if kw.get(k):
                    params[k] = kw[k]
            res = await client.post(f"{base}/search", {"query": query}, params=params)
            client.check(res, "calendar_event.search")
            return ok(res.get("data", {}))

        if action == "reply":
            if not ev_id or not kw.get("rsvp_status"):
                return ok({"error": "event_id and rsvp_status are required"})
            res = await client.post(
                f"{base}/{ev_id}/reply", {"rsvp_status": kw["rsvp_status"]}
            )
            client.check(res, "calendar_event.reply")
            return ok({"success": True})

        if action == "instances":
            if not ev_id:
                return ok({"error": "event_id is required"})
            params = {}
            for k in ("start_time", "end_time", "page_token", "page_size"):
                if kw.get(k):
                    params[k] = kw[k]
            res = await client.get(f"{base}/{ev_id}/instances", params=params)
            client.check(res, "calendar_event.instances")
            return ok(res.get("data", {}))

        return ok({"error": f"Unknown action: {action}"})
    except Exception as e:
        return ok({"error": str(e)})


CalendarEventTool: FunctionTool = make_tool(
    name="feishu_calendar_event",
    description=(
        "飞书日程管理工具（以机器人身份）。"
        "action: create（创建日程）, list（查询日程列表）, get（获取日程详情）, "
        "patch（更新日程）, delete（删除日程）, search（搜索日程）, "
        "reply（回复日程邀请）, instances（查询重复日程实例）。"
        "时间格式：ISO 8601，例如 '2026-01-01T14:00:00+08:00'。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "get", "patch", "delete", "search", "reply", "instances"],
                "description": "操作类型",
            },
            "calendar_id": {"type": "string", "description": "日历 ID（默认 primary）"},
            "event_id": {"type": "string", "description": "日程 ID"},
            "summary": {"type": "string", "description": "日程标题（create 必填）"},
            "description": {"type": "string", "description": "日程描述"},
            "start_time": {"type": "string", "description": "开始时间 ISO 8601"},
            "end_time": {"type": "string", "description": "结束时间 ISO 8601"},
            "location": {"type": "string", "description": "地点"},
            "attendees": {
                "type": "array",
                "description": "参会人列表，每项为 {type, user_id?, chat_id?, room_id?}",
                "items": {"type": "object"},
            },
            "query": {"type": "string", "description": "搜索关键词（action=search）"},
            "rsvp_status": {
                "type": "string",
                "enum": ["accept", "decline", "tentative"],
                "description": "回复状态（action=reply）",
            },
            "page_token": {"type": "string", "description": "分页标记"},
            "page_size": {"type": "number", "description": "每页数量"},
        },
        "required": ["action"],
    },
    handler=_calendar_event,
)


# ---------------------------------------------------------------------------
# feishu_calendar_event_attendee
# ---------------------------------------------------------------------------


async def _calendar_event_attendee(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    action = kw.get("action")
    cal_id = kw.get("calendar_id", "primary")
    ev_id = kw.get("event_id", "")
    base = f"/open-apis/calendar/v4/calendars/{cal_id}/events/{ev_id}/attendees"
    try:
        if action == "create":
            res = await client.post(base, {"attendees": kw.get("attendees", [])})
            client.check(res, "attendee.create")
            return ok(res.get("data", {}))
        if action == "list":
            params: dict = {}
            if kw.get("page_token"):
                params["page_token"] = kw["page_token"]
            if kw.get("page_size"):
                params["page_size"] = kw["page_size"]
            res = await client.get(base, params=params)
            client.check(res, "attendee.list")
            return ok(res.get("data", {}))
        if action == "delete":
            aid = kw.get("attendee_id", "")
            if not aid:
                return ok({"error": "attendee_id required"})
            res = await client.delete(f"{base}/{aid}")
            client.check(res, "attendee.delete")
            return ok({"success": True})
        if action == "batch_delete":
            ids = [a.get("attendee_id", "") for a in (kw.get("attendees") or []) if a.get("attendee_id")]
            if not ids:
                return ok({"error": "attendees with attendee_id required"})
            res = await client.post(f"{base}/batch_delete", {"attendee_ids": ids})
            client.check(res, "attendee.batch_delete")
            return ok({"success": True})
        return ok({"error": f"Unknown action: {action}"})
    except Exception as e:
        return ok({"error": str(e)})


CalendarEventAttendeeTool: FunctionTool = make_tool(
    name="feishu_calendar_event_attendee",
    description=(
        "飞书日程参会人管理工具（以机器人身份）。"
        "action: create（添加参会人）, list（查询参会人列表）, "
        "delete（删除参会人）, batch_delete（批量删除参会人）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "delete", "batch_delete"],
                "description": "操作类型",
            },
            "calendar_id": {"type": "string", "description": "日历 ID（默认 primary）"},
            "event_id": {"type": "string", "description": "日程 ID（必填）"},
            "attendees": {
                "type": "array",
                "description": "参会人列表（create/batch_delete 使用）",
                "items": {"type": "object"},
            },
            "attendee_id": {"type": "string", "description": "参会人 ID（delete 使用）"},
            "page_token": {"type": "string", "description": "分页标记"},
            "page_size": {"type": "number", "description": "每页数量"},
        },
        "required": ["action", "event_id"],
    },
    handler=_calendar_event_attendee,
)


# ---------------------------------------------------------------------------
# feishu_calendar_freebusy
# ---------------------------------------------------------------------------


async def _calendar_freebusy(event: Any, **kw: Any) -> str:
    client = get_lark_client()
    try:
        time_min = kw.get("time_min", "")
        time_max = kw.get("time_max", "")
        user_ids = kw.get("user_ids", [])
        if not time_min or not time_max:
            return ok({"error": "time_min and time_max are required"})
        if not user_ids:
            return ok({"error": "user_ids is required"})
        data = {"time_min": time_min, "time_max": time_max, "user_ids": user_ids}
        res = await client.post("/open-apis/calendar/v4/freebusy/batch_get", data)
        client.check(res, "calendar_freebusy.list")
        return ok(res.get("data", {}))
    except Exception as e:
        return ok({"error": str(e)})


CalendarFreebusyTool: FunctionTool = make_tool(
    name="feishu_calendar_freebusy",
    description=(
        "飞书忙闲查询工具（以机器人身份）。"
        "查询指定用户在时间段内的忙闲状态。"
        "时间格式：ISO 8601，例如 '2026-01-01T14:00:00+08:00'。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "time_min": {"type": "string", "description": "查询开始时间 ISO 8601（必填）"},
            "time_max": {"type": "string", "description": "查询结束时间 ISO 8601（必填）"},
            "user_ids": {
                "type": "array",
                "description": "用户 open_id 列表（必填）",
                "items": {"type": "string"},
            },
        },
        "required": ["time_min", "time_max", "user_ids"],
    },
    handler=_calendar_freebusy,
)
