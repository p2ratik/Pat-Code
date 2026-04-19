from fastmcp import FastMCP

mcp = FastMCP("test-server")

@mcp.tool()
def echo(text: str) -> str:
    return text

@mcp.tool()
def add(a: int, b: int) -> int:
    return a + b

if __name__ == "__main__":
    mcp.run(transport="http", port=8000)