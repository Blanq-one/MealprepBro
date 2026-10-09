import pytest

from app.llm.fake import FakeLLMClient
from app.llm.structured import LLMRunContext
from app.testing.llm import FakeClock, make_settings


@pytest.fixture(params=["strict", "best_effort"])
def mode(request) -> str:
    """The full structured-output suite runs in both modes (AC 1.6)."""
    return str(request.param)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def make_ctx(db, clock):
    def build(client: FakeLLMClient, mode: str = "strict", **overrides) -> LLMRunContext:
        return LLMRunContext(
            client=client, session=db, settings=make_settings(mode, **overrides), clock=clock
        )

    return build
