import os
import uvicorn

port = int(os.environ.get("PORT", 8080))

from financial_analyst_mcp import mcp

# Get the ASGI app from FastMCP and run with explicit host binding
try:
    app = mcp.http_app(path="/mcp")
except AttributeError:
    app = mcp.get_asgi_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port)
