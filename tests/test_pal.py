"""Tests for the PAL executor module."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.pal.executor import PALExecutor


@pytest.fixture()
def mock_client() -> MagicMock:
    """Return a mock OpenAI-compatible client."""
    return MagicMock()


@pytest.fixture()
def executor(mock_client: MagicMock) -> PALExecutor:
    """Return a PALExecutor wired to the mock client."""
    return PALExecutor(client=mock_client, model_name="test-model")


@pytest.fixture()
def sample_df() -> pd.DataFrame:
    """Return a small DataFrame for sandbox tests."""
    return pd.DataFrame({
        "subreddit": ["r/python", "r/python", "r/golang"],
        "score": [0.8, 0.6, -0.3],
    })


class TestBuildExecutionGlobals:
    """Tests for build_execution_globals."""

    def test_contains_pandas(self, executor: PALExecutor) -> None:
        g = executor.build_execution_globals()
        assert g["__builtins__"]["pd"] is pd

    def test_contains_numpy(self, executor: PALExecutor) -> None:
        g = executor.build_execution_globals()
        assert g["__builtins__"]["np"] is np

    def test_contains_standard_builtins(self, executor: PALExecutor) -> None:
        g = executor.build_execution_globals()
        for name in ("len", "range", "sum", "min", "max", "sorted", "round",
                     "abs", "float", "int", "str", "list", "dict", "print"):
            assert name in g["__builtins__"], f"Missing builtin: {name}"


class TestExecuteProgram:
    """Tests for execute_program."""

    def test_simple_mean(self, executor: PALExecutor, sample_df: pd.DataFrame) -> None:
        program = "result = df['score'].mean()"
        out = executor.execute_program(program, dataframe=sample_df)
        assert "result" in out
        assert out["result"] == pytest.approx((0.8 + 0.6 - 0.3) / 3)

    def test_numpy_usage(self, executor: PALExecutor, sample_df: pd.DataFrame) -> None:
        program = "result = float(np.sum(df['score'].values))"
        out = executor.execute_program(program, dataframe=sample_df)
        assert "result" in out
        assert out["result"] == pytest.approx(0.8 + 0.6 - 0.3)

    def test_no_result_variable(self, executor: PALExecutor) -> None:
        program = "x = 42"
        out = executor.execute_program(program)
        assert "error" in out
        assert "result" in out["error"]

    def test_syntax_error(self, executor: PALExecutor) -> None:
        program = "result = ]["
        out = executor.execute_program(program)
        assert "error" in out

    def test_runtime_error(self, executor: PALExecutor) -> None:
        program = "result = 1 / 0"
        out = executor.execute_program(program)
        assert "error" in out

    def test_no_dataframe(self, executor: PALExecutor) -> None:
        program = "result = sum([1, 2, 3])"
        out = executor.execute_program(program)
        assert out["result"] == 6


class TestGenerateProgram:
    """Tests for generate_program (LLM mocked)."""

    def test_returns_generated_code(self, executor: PALExecutor, mock_client: MagicMock) -> None:
        mock_message = MagicMock()
        mock_message.content = "result = len(df)"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        code = executor.generate_program("Count rows", {"rows": 100})
        assert code == "result = len(df)"
        mock_client.chat.completions.create.assert_called_once()

    def test_strips_markdown_fences(self, executor: PALExecutor, mock_client: MagicMock) -> None:
        mock_message = MagicMock()
        mock_message.content = "```python\nresult = 42\n```"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        code = executor.generate_program("Return 42", {})
        assert code == "result = 42"

    def test_strips_plain_fences(self, executor: PALExecutor, mock_client: MagicMock) -> None:
        mock_message = MagicMock()
        mock_message.content = "```\nresult = 99\n```"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        code = executor.generate_program("Return 99", {})
        assert code == "result = 99"
