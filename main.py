#!/usr/bin/env python
# -*- coding:utf-8 -*-

__author__ = 'Taisue'
__copyright__ = 'Copyright © 2025/05/23, Banyu Tech Ltd.'

from fastmcp import FastMCP
from app.detect_pii import DetectPII
from app.detect_toxic import DetectToxic
from typing import Any, Dict, List, Literal, Optional, Union

mcp = FastMCP("Firewall2")

@mcp.tool()
def detect_pii(query: str, pii_entities: List = None) -> str:
    pii_entities = DetectPII.PII_ENTITIES_MAP["pii"] if pii_entities is None else pii_entities
    pii_service = DetectPII(pii_entities=pii_entities)
    results = pii_service.validate(query, {"pii_entities": pii_entities})
    return results.to_dict()

@mcp.tool()
def detect_toxic(query: str) -> str:
    detector = DetectToxic(model="guard", base_url="http://localhost:11434")
    results = detector.validate(query=query)
    return results.to_dict()

if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8080)