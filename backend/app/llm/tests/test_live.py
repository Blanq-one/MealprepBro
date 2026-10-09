"""One real Groq batch through the full validation path. Opt-in only, so normal runs never spend rate limits:

RUN_LIVE_LLM_TESTS=1 uv run pytest -m live_llm -s
"""

import os
from datetime import date

import pytest

from app.config import get_settings
from app.db.models import GenerationRun
from app.domain.enums import MealSlot
from app.llm.client import make_client
from app.llm.structured import LLMRunContext
from app.planning.candidates import CandidateGenerator, gap_analysis
from app.planning.inputs import constraints_for
from app.planning.loader import build_problem
from app.schemas.plans import PlanRequest
from app.services.settings import current_user

pytestmark = [
    pytest.mark.live_llm,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_LLM_TESTS") != "1", reason="set RUN_LIVE_LLM_TESTS=1 to call Groq"
    ),
]


def test_one_real_batch_passes_every_validator(seeded_db):
    settings = get_settings()
    user = current_user(seeded_db)
    c = constraints_for(
        seeded_db,
        user.id,
        PlanRequest(week_start=date(2026, 10, 12), slot_kcal={MealSlot.DINNER: 550, MealSlot.DRINK: 100}),
    )
    problem = build_problem(seeded_db, user.id, c)
    gaps = gap_analysis(problem)
    assert [g.slot for g in gaps] == [MealSlot.DRINK]
    run = GenerationRun(user_id=user.id, purpose="weekly_plan", status="running")
    seeded_db.add(run)
    seeded_db.flush()
    ctx = LLMRunContext(make_client(settings), seeded_db, settings, run.id)
    generator = CandidateGenerator(seeded_db, user.id, ctx)
    created = generator.generate(problem, gaps)
    print(
        f"\nmode={settings.llm_structured_mode} model={settings.llm_model} calls={run.llm_call_count} "
        f"tokens={run.total_tokens} created={len(created)} dropped={generator.dropped}"
    )
    assert created, generator.dropped
