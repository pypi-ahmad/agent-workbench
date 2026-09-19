"""Safe mathematical calculator and current time utility tools."""

import ast
from datetime import datetime, timezone
import math
import operator
from typing import Any, Dict

SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

SAFE_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "pow": pow,
    "sqrt": math.sqrt,
    "ceil": math.ceil,
    "floor": math.floor,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
    "pi": math.pi,
    "e": math.e,
}


def _evaluate_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value)}")

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _evaluate_node(node.left)
        right = _evaluate_node(node.right)
        if op_type == ast.Pow and (isinstance(right, (int, float)) and right > 1000):
            raise ValueError("Exponent too large to evaluate safely.")
        return SAFE_OPERATORS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        operand = _evaluate_node(node.operand)
        return SAFE_OPERATORS[op_type](operand)

    if isinstance(node, ast.Name):
        if node.id in SAFE_FUNCTIONS:
            return SAFE_FUNCTIONS[node.id]
        raise ValueError(f"Unknown variable or function: '{node.id}'")

    if isinstance(node, ast.Call):
        func = _evaluate_node(node.func)
        if not callable(func):
            raise ValueError(f"'{ast.unparse(node.func)}' is not a callable function")
        args = [_evaluate_node(arg) for arg in node.args]
        return func(*args)

    raise ValueError(f"Unsupported syntax in expression: {type(node).__name__}")


def calc(expression: str) -> Dict[str, Any]:
    """Safely evaluate mathematical expressions using an AST parser.
    
    Args:
        expression: Math expression string (e.g. '2 * (3 + 4)', 'sqrt(144) + log10(100)').
    """
    try:
        cleaned = expression.strip()
        if not cleaned:
            return {"error": "Empty expression provided."}
        
        parsed = ast.parse(cleaned, mode="eval")
        result = _evaluate_node(parsed.body)
        return {
            "expression": expression,
            "result": result,
            "type": type(result).__name__,
        }
    except Exception as e:
        return {"error": f"Calculation failed: {str(e)}"}


def now() -> Dict[str, Any]:
    """Retrieve current timestamp information in UTC and local time."""
    utc_dt = datetime.now(timezone.utc)
    local_dt = datetime.now().astimezone()

    return {
        "utc_iso": utc_dt.isoformat(),
        "local_iso": local_dt.isoformat(),
        "local_tz": str(local_dt.tzinfo),
        "unix_timestamp": int(utc_dt.timestamp()),
        "day_of_week": local_dt.strftime("%A"),
        "readable": local_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }
