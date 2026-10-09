"""LLM architecture rules (§7.5): provider isolation, no model-name literals, no streaming or tools."""

import ast
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2]
MODEL_LITERAL = re.compile(
    r"(gpt-|gpt_oss|llama|qwen|gemma|mixtral|mistral|deepseek|kimi|openai/|meta-llama/)", re.I
)


def _source_files() -> list[Path]:
    return [p for p in APP.rglob("*.py") if "tests" not in p.parts]


def test_no_model_name_literals_in_app_code():
    offenders = []
    for path in _source_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and MODEL_LITERAL.search(node.value)
            ):
                offenders.append((str(path.relative_to(APP)), node.value[:60]))
    assert offenders == []


def test_only_the_llm_client_imports_groq():
    for path in APP.rglob("*.py"):
        if path == APP / "llm" / "client.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(import groq|from groq\b)", text, re.M), path


def test_no_stream_or_tools_in_provider_calls():
    tree = ast.parse((APP / "llm" / "client.py").read_text(encoding="utf-8"))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            keys.update(k.arg for k in node.keywords if k.arg)
        if isinstance(node, ast.Dict):
            keys.update(
                k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)
            )
    assert not keys & {"stream", "tools", "tool_choice", "functions"}
