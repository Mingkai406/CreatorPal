"""Generate and execute sandboxed Python analytics code using PAL."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd
from RestrictedPython import compile_restricted
from RestrictedPython.Guards import guarded_unpack_sequence, safe_builtins, safer_getattr
from openai import OpenAI

_SYSTEM_PROMPT = (
    "You are a Python code generator. Given a task description and context data, "
    "generate ONLY executable Python code. Do not include markdown fences, explanations, "
    "or comments. The code must assign its final answer to a variable called 'result'. "
    "You may use pandas (as 'pd'), numpy (as 'np'), and standard builtins. "
    "If a DataFrame is provided it will be available as 'df'."
)

_FENCE_RE = re.compile(r"^```(?:python)?\s*\n?(.*?)```\s*$", re.DOTALL)


class PALExecutor:
    """Generate Python programs with LLMs and run them in a restricted sandbox."""

    def __init__(self, client: OpenAI, model_name: str) -> None:
        """Initialize PAL with an LLM endpoint and model name.

        Args:
            client: OpenAI-compatible API client (e.g. vLLM endpoint).
            model_name: Model identifier to use for code generation.
        """
        self._client = client
        self._model_name = model_name

    def generate_program(self, task_prompt: str, context: Mapping[str, Any]) -> str:
        """Generate Python code for channel and subreddit analytics tasks.

        Args:
            task_prompt: Natural-language description of the computation to perform.
            context: Supporting data to include in the user message.

        Returns:
            Generated Python source code as a string.
        """
        user_message = f"Task: {task_prompt}\n\nContext:\n{context}"
        response = self._client.chat.completions.create(
            model=self._model_name,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.0,
        )
        code = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        match = _FENCE_RE.match(code)
        if match:
            code = match.group(1).strip()
        return code

    def build_execution_globals(self) -> dict[str, Any]:
        """Build the restricted execution environment for PAL code.

        Returns:
            Dict of allowed names for sandboxed execution.
        """
        allowed = dict(safe_builtins)
        allowed.update({
            "pd": pd,
            "np": np,
            "len": len,
            "range": range,
            "sum": sum,
            "min": min,
            "max": max,
            "sorted": sorted,
            "round": round,
            "abs": abs,
            "float": float,
            "int": int,
            "str": str,
            "list": list,
            "dict": dict,
            "print": print,
        })
        globs: dict[str, Any] = {"__builtins__": allowed}
        # RestrictedPython guards required for subscript, attribute, and iteration access
        globs["_getitem_"] = lambda obj, key: obj[key]
        globs["_getattr_"] = safer_getattr
        globs["_getiter_"] = iter
        globs["_unpack_sequence_"] = guarded_unpack_sequence
        globs["_write_"] = lambda obj: obj
        globs["_inplacevar_"] = lambda op, x, y: op(x, y)
        return globs

    def execute_program(self, program: str, dataframe: pd.DataFrame | None = None) -> dict[str, Any]:
        """Execute generated code inside a RestrictedPython sandbox.

        Args:
            program: Python source code to execute. Must assign to 'result'.
            dataframe: Optional DataFrame exposed as 'df' in the sandbox.

        Returns:
            Dict with key 'result' on success, or 'error' on failure.
        """
        try:
            compiled = compile_restricted(program, filename="<pal>", mode="exec")
            exec_globals = self.build_execution_globals()
            if dataframe is not None:
                exec_globals["df"] = dataframe
            exec(compiled, exec_globals)
            if "result" not in exec_globals:
                return {"error": "Program did not assign to 'result'."}
            return {"result": exec_globals["result"]}
        except Exception as exc:
            return {"error": str(exc)}
