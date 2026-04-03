# Copyright (c) 2026 html5syt
# SPDX-License-Identifier: MIT
#
# Shared helpers for tool modules.

from __future__ import annotations

import json
import re
from typing import Any, Optional

from astrbot.api import FunctionTool


def ok(data: Any) -> str:
    """Serialize data to JSON string for LLM consumption."""
    return json.dumps(data, ensure_ascii=False, default=str)


def extract_doc_id(doc_id_or_url: str) -> str:
    """Extract document ID from a URL or return the ID as-is."""
    if not doc_id_or_url:
        return ""
    m = re.search(
        r"/(?:docx|docs?|document|wiki)/([A-Za-z0-9_-]+)", doc_id_or_url
    )
    return m.group(1) if m else doc_id_or_url


def make_tool(name: str, description: str, parameters: dict, handler: Any) -> FunctionTool:
    """Create a FunctionTool with a handler function.

    The handler signature must be: async def handler(event, **kwargs) -> str
    where `event` is the AstrMessageEvent (may be unused).
    """
    return FunctionTool(
        name=name,
        description=description,
        parameters=parameters,
        handler=handler,
    )
