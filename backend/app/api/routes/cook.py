from fastapi import APIRouter, Response
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DbSession, LLMClientFactory, LLMClock, LLMSettings, SessionFactory
from app.api.problems import ProblemError
from app.cook import search as search_service
from app.cook.home import cook_home
from app.cook.ideas import LLMAccess
from app.cook.single_meal import cook_meal
from app.cook.stream import meal_now_events, more_events
from app.schemas.cook import CookAnswers, CookHomeOut, CookMealIn, CookMealOut, CookSearchOut, CookStreamEvent

router = APIRouter(prefix="/api/v1/cook", tags=["cook"])

NDJSON = "application/x-ndjson"
STREAM_HEADERS = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}


@router.get("/home", response_model=CookHomeOut)
def home(session: DbSession, user: CurrentUser) -> CookHomeOut:
    """The Cook home: "Same as last time" per mode, the Today card from your current plan, Saved previews."""
    return cook_home(session, user, search_service.local_now(user))


@router.post(
    "/meal-now",
    response_class=StreamingResponse,
    responses={200: {"model": CookStreamEvent, "content": {NDJSON: {}}, "description": "NDJSON event lines"}},
)
def meal_now(
    *,
    body: CookAnswers,
    user: CurrentUser,
    session_factory: SessionFactory,
    client_factory: LLMClientFactory,
    clock: LLMClock,
    llm_settings: LLMSettings,
) -> StreamingResponse:
    """A meal now: ranked recipe cards for one meal, inside this request. The response is a stream of JSON
    lines (`CookStreamEvent`): `started` (search and run ids), `progress`, `results` (the full ranked list),
    `heartbeat` lines while it works, and one `result`. With fewer than 6 good matches, one ideas call writes
    new ideas, streamed into the list as a second `results` (a rate-limit wait is a `waiting` line with a
    countdown, never an error). An identical repeat returns the stored result."""
    if body.mode != "now":
        raise ProblemError(422, "Not a meal-now search", 'Send mode "now"; meal prep has its own endpoint.')
    events = meal_now_events(
        session_factory, user.id, body, client_factory=client_factory, clock=clock, settings=llm_settings
    )
    return StreamingResponse(events, media_type=NDJSON, headers=STREAM_HEADERS)


@router.get("/searches/{search_id}", response_model=CookSearchOut)
def get_search(search_id: int, session: DbSession, user: CurrentUser) -> CookSearchOut:
    """A stored search, to reopen its results."""
    return search_service.search_out(session, user.id, search_id)


@router.post(
    "/searches/{search_id}/more",
    response_class=StreamingResponse,
    responses={200: {"model": CookStreamEvent, "content": {NDJSON: {}}, "description": "NDJSON event lines"}},
)
def more_ideas(
    search_id: int,
    *,
    session: DbSession,
    user: CurrentUser,
    session_factory: SessionFactory,
    client_factory: LLMClientFactory,
    clock: LLMClock,
    llm_settings: LLMSettings,
) -> StreamingResponse:
    """More ideas (E18). The first tap in a search makes one ideas call; a later tap shows the batch held from
    the last tap at once (`results`), or makes one ideas call when none is held. Every tap then writes the
    next batch in the background and sends it as `prefetched`: keep it until the next tap, never show it
    before. A rate-limit wait is a `waiting` line, or a `partial` result with `retry_after_s`."""
    search = search_service.get_search(session, user.id, search_id)
    if search.mode != search_service.MODE_NOW or search.status != "done":
        raise ProblemError(
            422, "Not a finished meal-now search", "More ideas works on a finished meal-now search."
        )
    events = more_events(
        session_factory, user.id, search_id, client_factory=client_factory, clock=clock, settings=llm_settings
    )
    return StreamingResponse(events, media_type=NDJSON, headers=STREAM_HEADERS)


@router.post("/meals", response_model=CookMealOut, status_code=201)
def cook_this(
    body: CookMealIn,
    *,
    response: Response,
    session: DbSession,
    user: CurrentUser,
    client_factory: LLMClientFactory,
    clock: LLMClock,
    llm_settings: LLMSettings,
) -> CookMealOut:
    """Cook this: saves the recipe at N portions as a one-meal plan for today (never your current plan),
    with its grocery list for anything to buy first. Tapping it again for the same search returns that plan
    (200). A new idea gets its steps first (409 with `retry_after_s` when they can't be written right now)."""
    out = cook_meal(
        session,
        user,
        body,
        now=search_service.local_now(user),
        access=LLMAccess(client_factory, llm_settings, clock),
    )
    session.commit()
    if not out.created:
        response.status_code = 200
    return out
