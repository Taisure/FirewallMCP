from fastmcp import FastMCP
from app.detect_pii import DetectPII
mcp = FastMCP("Firewall2")

@mcp.tool()
def detect_pii(text, pii_entities = None) -> str:
    pii_entities = DetectPII.PII_ENTITIES_MAP["pii"] if pii_entities is None else pii_entities
    pii_service = DetectPII(pii_entities=pii_entities)
    results = pii_service.validate(text, {"pii_entities": pii_entities})
    return results.to_dict()


if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8080)