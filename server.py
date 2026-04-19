from fastmcp import FastMCP

mcp = FastMCP("test-server")

@mcp.tool()
def echo(text: str) -> str:
    return text

@mcp.tool()
def add(a: int, b: int) -> int:
    return a + b

@mcp.tool()
def factorial(n: int) -> int:
    """Return the factorial of a non‑negative integer n.

    Uses an iterative approach to avoid recursion limits.
    """
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result

@mcp.tool()
def gcd(a: int, b: int) -> int:
    """Compute the greatest common divisor of a and b using Euclid's algorithm."""
    while b:
        a, b = b, a % b
    return abs(a)

if __name__ == "__main__":
    mcp.run(transport="http", port=8000)