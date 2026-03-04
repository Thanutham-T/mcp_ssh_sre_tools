from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sre-ssh-server")

if __name__ == "__main__":
    # Start the server using SSE transport
    mcp.run(transport="sse")
