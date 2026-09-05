"""Child-process entry point for a deliberately restricted Python analytics language.

No imports, attributes, arbitrary calls, host environment, or filesystem APIs are exposed.
This is a language restriction plus resource controls, not a general Python security sandbox.
"""

import ast
import json
import sys

FUNCTIONS = {
    "sum": sum,
    "len": len,
    "min": min,
    "max": max,
    "sorted": sorted,
    "round": round,
    "abs": abs,
    "float": float,
    "int": int,
    "range": range,
}
ALLOWED = (
    ast.Module,
    ast.Assign,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Constant,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.Subscript,
    ast.Slice,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    ast.Call,
    ast.keyword,
    ast.ListComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.comprehension,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Gt,
    ast.GtE,
    ast.Lt,
    ast.LtE,
    ast.In,
    ast.NotIn,
    ast.IfExp,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.Not,
)


def execute(program, rows):
    tree = ast.parse(program)
    nodes = list(ast.walk(tree))
    if len(nodes) > 400:
        raise ValueError("Program exceeds syntax budget")
    for node in nodes:
        if not isinstance(node, ALLOWED):
            raise ValueError(f"Unsupported syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and (node.id.startswith("_") or node.id == "__builtins__"):
            raise ValueError("Private names are unavailable")
        if isinstance(node, ast.Call) and (
            not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS
        ):
            raise ValueError("Only approved numeric builtins may be called")
        if isinstance(node, ast.Assign) and any(not isinstance(t, ast.Name) for t in node.targets):
            raise ValueError("Only local-name assignment is permitted")
    scope = {"__builtins__": {}, **FUNCTIONS, "rows": rows}
    exec(compile(tree, "<analytics>", "exec"), scope)
    if "result" not in scope:
        raise ValueError("Program must assign result")
    return scope["result"]


def main():
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        if sys.platform.startswith("linux"):
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except ImportError:
        # Windows users must select Docker; the parent rejects this backend on Windows.
        pass
    try:
        payload = json.loads(sys.stdin.read(100_001))
        result = execute(payload["program"], payload["rows"])
        encoded = json.dumps({"status": "ok", "result": result}, allow_nan=False)
        if len(encoded) > 32_000:
            raise ValueError("Result exceeds output budget")
        print(encoded)
    except Exception as exc:
        print(json.dumps({"status": "error", "error_type": type(exc).__name__}))


if __name__ == "__main__":
    main()
