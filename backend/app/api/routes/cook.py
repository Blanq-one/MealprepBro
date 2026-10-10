from fastapi import APIRouter, Response
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DbSession, SessionFactory
from app.api.problems import ProblemError
from app.cook import search as search_service
from app.cook.home import cook_home
from app.cook.single_meal import cook_meal
from app.cook.stream import meal_now_events
from app.schemas.cook import CookAnswers, CookHomeOut, CookMealIn, CookMealOut, CookSearchOut, CookStreamEvent

router = APIRouter(prefix="/api/v1/cook", tags=["cook"])

NDJSON = "application/x-ndjson"


@router.get("/home", response_model=CookHomeOut)
def home(session: DbSession, user: CurrentUser) -> CookHomeOut:
    """The Cook home: "Same as last time" per mode, the Today card from your current plan, Saved previews."""
    return cook_home(session, user, search_service.local_now(user))


@router.post(
    "/meal-now",
    response_class=StreamingResponse,
    responses={200: {"model": CookStreamEvent, "content": {NDJSON: {}}, "description": "NDJSON event lines"}},
)
def meal_now(*, body: CookAnswers, user: CurrentUser, session_factory: SessionFactory) -> StreamingResponse:
    """A meal now: ranked recipe cards for one meal, inside this request. The response is a stream of JSON
    lines (`CookStreamEvent`): `started` (search and run ids), `progress`, `results` (the full ranked list),
    `heartbeat` lines while it works, and one `result`. An identical repeat returns the stored result."""
    if body.mode != "now":
        raise ProblemError(422, "Not a meal-now search", 'Send mode "now"; meal prep has its own endpoint.')
    events = meal_now_events(session_factory, user.id, body)
    return StreamingResponse(
        events, media_type=NDJSON, headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
    )


@router.get("/searches/{search_id}", response_model=CookSearchOut)
def get_search(search_id: int, session: DbSession, user: CurrentUser) -> CookSearchOut:
    """A stored search, to reopen its results."""
    return search_service.search_out(session, user.id, search_id)


@router.post("/meals", response_model=CookMealOut, status_code=201)
def cook_this(body: CookMealIn, response: Response, session: DbSession, user: CurrentUser) -> CookMealOut:
    """Cook this: saves the recipe at N portions as a one-meal plan for today (never your current plan),
    with its grocery list for anything to buy first. Tapping it again for the same search returns that plan
    (200)."""
    out = cook_meal(session, user, body, now=search_service.local_now(user))
    session.commit()
    if not out.created:
        response.status_code = 200
    return out
