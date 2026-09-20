"""Safe arithmetic, HTTPS fetch, and local-time tools."""

import ast
from datetime import datetime
import operator
from typing import Any
from urllib.parse import urlparse

import httpx

from src.config import HTTP_ALLOWED_HOSTS

_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _arithmetic(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _arithmetic(node.left)
        right = _arithmetic(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("Exponent magnitude exceeds 100.")
        return _BINARY_OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_arithmetic(node.operand))
    raise ValueError("Only numbers and + - * / ** parentheses are allowed.")


def calc(expression: str) -> dict[str, Any]:
    """Evaluate bounded arithmetic without eval or names."""
    try:
        if not isinstance(expression, str) or not expression.strip():
            return {"error": "Expression must be a non-empty string."}
        if len(expression) > 256:
            return {"error": "Expression exceeds 256 characters."}
        parsed = ast.parse(expression, mode="eval")
        result = _arithmetic(parsed.body)
        return {"expression": expression, "result": result}
    except (ArithmeticError, SyntaxError, TypeError, ValueError) as exc:
        return {"error": str(exc)}


def http_get(url: str) -> dict[str, Any]:
    """Fetch up to 4,000 response characters from an allowlisted HTTPS host."""
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() != "https":
            return {"error": "Only https URLs are allowed."}
        if parsed.username or parsed.password:
            return {"error": "URL credentials are not allowed."}
        host = (parsed.hostname or "").lower().rstrip(".")
        if host not in HTTP_ALLOWED_HOSTS:
            return {"error": f"Host is not allowlisted: {host}"}
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            response = client.get(url, headers={"User-Agent": "AgentWorkbench/1.0"})
        return {"status": response.status_code, "text": response.text[:4000]}
    except (TypeError, ValueError) as exc:
        return {"error": f"Invalid URL: {exc}"}
    except httpx.RequestError as exc:
        return {"error": f"HTTP request failed: {exc}"}


def now() -> str:
    """Return local time as an ISO 8601 string."""
    return datetime.now().astimezone().isoformat()
