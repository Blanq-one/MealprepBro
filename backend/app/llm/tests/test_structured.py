"""The structured retry loop, run under both LLM_STRUCTURED_MODE values (AC 1.6, 1.7)."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.db.models import LlmCall, Recipe
from app.llm.errors import (
    LLMConfigError,
    LLMOutputError,
    LLMProviderOutputError,
    LLMStrictUnsupportedError,
    LLMTruncatedError,
)
from app.llm.fake import FakeLLMClient, fixture_response, fixture_text, response
from app.llm.schema import transport_schema
from app.llm.structured import StructuredSpec
from app.schemas.llm_recipe import GeneratedRecipeBatch
from app.testing.llm import make_settings

SNAPSHOT = Path(__file__).parent / "snapshots" / "generated_recipe_batch.schema.json"


def spec(**kwargs) -> StructuredSpec[GeneratedRecipeBatch]:
    return StructuredSpec(
        purpose="candidate_generation",
        prompt_version="test/1",
        messages=({"role": "system", "content": "rules"}, {"role": "user", "content": "write drinks"}),
        response_model=GeneratedRecipeBatch,
        **kwargs,
    )


def calls(db) -> list[LlmCall]:
    return list(db.scalars(select(LlmCall).order_by(LlmCall.id)))


def test_valid_first_try_is_one_call(make_ctx, mode, db):
    client = FakeLLMClient([fixture_response("drinks_batch.json")])
    result = make_ctx(client, mode).generate(spec())
    assert [r.title for r in result.value.recipes] == ["Golden turmeric milk", "Cinnamon cocoa milk"]
    assert client.calls == 1 and result.attempts == 1
    (row,) = calls(db)
    assert row.outcome == "ok" and row.structured_mode == mode and row.attempt == 1
    assert row.model == "fake-model" and row.prompt_version == "test/1"
    assert row.prompt_tokens == 900 and row.completion_tokens == 600


def test_prose_wrapped_json_is_retried_with_the_error(make_ctx, mode, db):
    client = FakeLLMClient([fixture_response("prose_wrapped.txt"), fixture_response("drinks_batch.json")])
    result = make_ctx(client, mode).generate(spec())
    assert result.attempts == 2
    first, second = calls(db)
    assert first.outcome == "parse_error" and second.outcome == "ok"
    assert second.parent_call_id == first.id and second.attempt == 2
    retry = client.requests[1].messages
    # a long failed reply isn't re-sent (it would push the retry past Groq's 8K tokens/minute)
    assert [m["role"] for m in retry] == ["system", "user", "user"]
    assert "not valid JSON" in retry[-1]["content"] and "isn't repeated here" in retry[-1]["content"]


def test_a_short_failed_reply_is_sent_back_with_the_errors(make_ctx, mode):
    client = FakeLLMClient([response('{"recipes": []}'), fixture_response("drinks_batch.json")])
    make_ctx(client, mode).generate(spec())
    retry = client.requests[1].messages
    assert retry[-2] == {"role": "assistant", "content": '{"recipes": []}'}
    assert "recipes: List should have at least 1 item" in retry[-1]["content"]


def test_retries_do_not_grow_past_the_first_request(make_ctx, mode):
    client = FakeLLMClient(default=fixture_response("prose_wrapped.txt"))
    with pytest.raises(LLMOutputError):
        make_ctx(client, mode).generate(spec())
    sizes = [sum(len(m["content"]) for m in r.messages) for r in client.requests]
    assert max(sizes) - sizes[0] < 2000


def test_truncated_json_raises_so_the_batch_can_be_halved(make_ctx, mode, db):
    client = FakeLLMClient([fixture_response("truncated.txt", finish_reason="length")])
    with pytest.raises(LLMTruncatedError):
        make_ctx(client, mode).generate(spec(raise_on_truncation=True))
    (row,) = calls(db)
    assert row.outcome == "parse_error" and row.error_detail["truncated"] is True


def test_truncation_without_halving_is_retried(make_ctx, mode):
    client = FakeLLMClient(
        [fixture_response("truncated.txt", finish_reason="length"), fixture_response("drinks_batch.json")]
    )
    assert make_ctx(client, mode).generate(spec()).attempts == 2
    assert "cut off" in client.requests[1].messages[-1]["content"]


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("wrong_types.json", "base_servings"),
        ("extra_calories_field.json", "calories"),
        ("total_less_than_active.json", "total_minutes must be >= active_minutes"),
    ],
)
def test_invalid_output_is_retried_with_concise_errors(make_ctx, mode, db, fixture, expected):
    client = FakeLLMClient([fixture_response(fixture), fixture_response("drinks_batch.json")])
    result = make_ctx(client, mode).generate(spec())
    assert result.attempts == 2
    first, _ = calls(db)
    assert first.outcome == "validation_error"
    assert any(expected in e for e in first.error_detail["errors"])
    assert expected in client.requests[1].messages[-1]["content"]


def test_extra_calories_field_is_rejected_by_the_model():
    with pytest.raises(ValidationError, match="calories"):
        GeneratedRecipeBatch.model_validate_json(fixture_text("extra_calories_field.json"))


def test_three_failures_raise_and_persist_nothing(make_ctx, mode, db):
    recipes_before = db.scalar(select(func.count()).select_from(Recipe))
    client = FakeLLMClient(default=fixture_response("wrong_types.json"))
    with pytest.raises(LLMOutputError) as info:
        make_ctx(client, mode).generate(spec())
    assert client.calls == 3
    rows = calls(db)
    assert [r.outcome for r in rows] == ["validation_error"] * 3
    assert [r.attempt for r in rows] == [1, 2, 3]
    assert rows[2].parent_call_id == rows[1].id and rows[1].parent_call_id == rows[0].id
    assert info.value.detail["call_ids"] == [r.id for r in rows]
    assert db.scalar(select(func.count()).select_from(Recipe)) == recipes_before


def test_domain_hook_errors_are_retried(make_ctx, mode, db):
    seen = []

    def check(batch: GeneratedRecipeBatch) -> list[str]:
        seen.append(batch)
        return ["Golden turmeric milk: 'saffron' is not in the ingredient list"] if len(seen) == 1 else []

    client = FakeLLMClient([fixture_response("drinks_batch.json"), fixture_response("drinks_batch.json")])
    result = make_ctx(client, mode).generate(spec(domain_check=check))
    assert result.attempts == 2
    assert calls(db)[0].outcome == "domain_error"
    assert "saffron" in client.requests[1].messages[-1]["content"]


def test_provider_rejected_json_is_a_parse_error_and_retried(make_ctx, mode, db):
    client = FakeLLMClient(
        [
            LLMProviderOutputError("json_validate_failed", failed_output="{oops"),
            fixture_response("drinks_batch.json"),
        ]
    )
    assert make_ctx(client, mode).generate(spec()).attempts == 2
    assert calls(db)[0].outcome == "parse_error"


def test_request_strict_flag_follows_the_mode(make_ctx, mode):
    client = FakeLLMClient([fixture_response("drinks_batch.json")])
    make_ctx(client, mode).generate(spec())
    request = client.requests[0]
    assert request.strict is (mode == "strict")
    assert request.json_schema == transport_schema(GeneratedRecipeBatch)
    system = request.messages[0]["content"]
    if mode == "best_effort":
        assert "Reply with one JSON object with exactly these fields" in system
        assert "recipes: list of objects" in system
    else:
        assert system == "rules"


def test_strict_transport_schema_snapshot():
    schema = transport_schema(GeneratedRecipeBatch)
    assert schema == json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_transport_schema_follows_groq_strict_rules():
    schema = transport_schema(GeneratedRecipeBatch)
    text = json.dumps(schema)
    assert "$ref" not in text and "$defs" not in text

    def walk(node):  # node is a schema (dict), never a properties mapping
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                assert node["additionalProperties"] is False
                assert node["required"] == list(node["properties"])
            for key in ("minLength", "maxLength", "minimum", "maximum", "default", "title"):
                assert key not in node
            for key, value in node.items():
                if key == "properties":
                    for prop in value.values():
                        walk(prop)
                elif key in ("items", "anyOf"):
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    recipe = schema["properties"]["recipes"]["items"]
    assert "calories" not in recipe["properties"]
    assert recipe["properties"]["cuisine"]["anyOf"] == [{"type": "string"}, {"type": "null"}] or any(
        option.get("type") == "null" for option in recipe["properties"]["cuisine"]["anyOf"]
    )


def test_unknown_structured_mode_is_a_config_error_at_startup():
    with pytest.raises(ValidationError, match="llm_structured_mode"):
        make_settings("bogus")


def test_strict_not_supported_suggests_best_effort(make_ctx, db):
    client = FakeLLMClient([LLMStrictUnsupportedError("json_schema strict is not supported for this model")])
    with pytest.raises(LLMConfigError, match="LLM_STRUCTURED_MODE=best_effort"):
        make_ctx(client, "strict").generate(spec())
    assert calls(db)[0].outcome == "transport_error"


def test_retry_message_is_compact(make_ctx):
    client = FakeLLMClient([response("{}"), fixture_response("drinks_batch.json")])
    make_ctx(client).generate(spec())
    feedback = client.requests[1].messages[-1]["content"]
    assert feedback.startswith("Your previous reply had these problems:")
    assert "recipes: Field required" in feedback
