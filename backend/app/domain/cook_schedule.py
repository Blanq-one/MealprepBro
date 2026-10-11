"""A cook day's schedule (FLOW_SPEC §20, step 2b.9): what to start when, so dishes cook in parallel. Pure and
deterministic; no LLM.

  tasks      each recipe's work as tasks: consecutive steps of one component on one piece of equipment, added
             up (a step joins the task before it only while that task is still all hands-on, so a task's
             hands-on minutes always come first). Seeds' steps are tagged by hand; an idea brings its own task
             list; steps without tags are estimated from their section and duration and marked "estimated"
             (V15). Storage and reheating steps aren't cook-day work
  order      within a dish, each component's tasks run in order; a shared task (no component: prep for
             everything, assembly, portioning) waits for everything before it, and everything after it waits
             for it. Different dishes don't depend on each other
  batch      hands-on time grows with portions, more slowly than the portions: base × (portions ÷ base
             servings)^0.6, rounded up, never below the base. Hands-off time doesn't grow. A batch above its
             appliance's capacity takes extra rounds, each repeating the hands-off time and its share of the
             loading (§20.2)
  resources  your hands do one hands-on task at a time; each appliance runs one task at a time, the stovetop
             up to 4 (one per burner) and the oven several when their portions fit (8) and their temperatures
             are within 25°F. A task needs your hands for its hands-on minutes, at its start, and holds its
             appliance until its hands-off minutes end; waiting (marinating, resting, chilling) holds nothing.
             The oven preheats for 10 minutes before its first task, while you work
  schedule   list scheduling: at each moment, start the ready tasks with the longest chain of work still
             behind them (ties: more hands-off first, then dish order) whose hands and appliance are free. The
             dish orders that change a tie are tried too (up to 6 dishes, 720 orders) and the shortest day is
             kept; ties keep the first
  result     the elapsed minutes (start to finish: your time in the kitchen; a dish's last wait in the fridge,
             like overnight oats setting, runs after you leave and doesn't count), the hands-on minutes, the
             longest fridge wait and the timeline
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from itertools import pairwise, permutations
from math import ceil
from typing import Literal

Kind = Literal["hands_on", "runs", "wait"]

APPLIANCES = (
    "oven",
    "air_fryer",
    "stovetop",
    "rice_cooker",
    "pressure_cooker",
    "slow_cooker",
    "microwave",
    "grill",
)
# portions per round (§20.2, V13: estimates; a size per appliance in Settings is DF5)
CAPACITY: Mapping[str, int] = {
    "oven": 8,  # two sheet pans
    "air_fryer": 4,  # one basket
    "rice_cooker": 10,
    "pressure_cooker": 8,
    "slow_cooker": 10,
    "microwave": 2,
    "grill": 6,
}
SKILLET_PORTIONS = 4  # a mostly hands-on stovetop task (searing, stir-frying)
POT_PORTIONS = 12  # a mostly hands-off one (simmering)
BURNERS = 4
OVEN_SHARE_WITHIN_F = 25
OVEN_PREHEAT_MINUTES = 10
GROWTH_EXPONENT = 0.6
OFF_DAY_SECTIONS = frozenset({"storage", "reheating"})  # after cooking, or on the eating day
FRIDGE_SECTIONS = frozenset(
    {"no_cook", "portioning", "assembly"}
)  # a dish's last wait here sets in the fridge
MAX_HANDS_ON = 60
MAX_HANDS_OFF = 240
MAX_WAIT = 720  # chilling or soaking, with no appliance
MAX_ORDER_DISHES = 6
# estimates for steps without timing tags (V15)
ESTIMATE_LOADING_MINUTES = 2  # oven, air fryer, rice, microwave and cooker steps: the rest is hands-off
SECTION_APPLIANCE: Mapping[str, str] = {
    "oven": "oven",
    "air_fryer": "air_fryer",
    "stovetop": "stovetop",
    "microwave": "microwave",
}
RICE_APPLIANCES = (
    "rice_cooker",
    "pressure_cooker",
    "stovetop",
)  # a rice step's appliance, first one you have


@dataclass(frozen=True)
class Task:
    """One piece of work at a recipe's base servings."""

    component: str | None  # None = shared: prep for everything, assembly, portioning
    equipment: str | None  # None = hands only, or waiting
    hands_on: int
    hands_off: int
    temp_f: int | None = None  # oven and air fryer
    section: str = "prep"  # the first step's section, for the timeline's wording

    @property
    def kind(self) -> Kind:
        if self.hands_off == 0:
            return "hands_on"
        return "runs" if self.equipment is not None else "wait"


@dataclass(frozen=True)
class DishTiming:
    """A recipe's tasks, in step order. `estimated`: derived from untagged steps (or only the recipe's stated
    minutes), so the timeline marks it."""

    tasks: tuple[Task, ...]
    estimated: bool = False

    @property
    def hands_on(self) -> int:
        return sum(t.hands_on for t in self.tasks)

    def appliances(self) -> frozenset[str]:
        return frozenset(t.equipment for t in self.tasks if t.equipment is not None)


@dataclass(frozen=True)
class StepTiming:
    """What the scheduler reads from a stored step."""

    section: str
    duration_minutes: int | None = None
    appliance_temp_f: int | None = None
    component: str | None = None
    equipment: str | None = None
    hands_on_minutes: int | None = None
    hands_off_minutes: int | None = None

    @property
    def tagged(self) -> bool:
        return self.hands_on_minutes is not None and self.hands_off_minutes is not None


SECTION_STEP_APPLIANCES: Mapping[str, frozenset[str]] = {
    "oven": frozenset({"oven"}),
    "air_fryer": frozenset({"air_fryer"}),
    "microwave": frozenset({"microwave"}),
    "stovetop": frozenset({"stovetop"}),
    "rice": frozenset({"stovetop", "rice_cooker", "pressure_cooker"}),
}


def step_timing_errors(
    section: str,
    equipment: str | None,
    hands_on: int,
    hands_off: int,
    recipe_equipment: Iterable[str],
) -> list[str]:
    """What's wrong with one step's timing fields (FLOW_SPEC §20.1), as messages that say what to change. A
    step's appliance must be one the recipe lists and fit its section (oven steps on the oven); waiting with
    no appliance (marinating, chilling, soaking) may run up to 12 hours, an appliance's hands-off time up to
    4 hours."""
    errors: list[str] = []
    listed = frozenset(recipe_equipment)
    if equipment is not None:
        if equipment not in APPLIANCES:
            errors.append(
                f"equipment '{equipment}' isn't an appliance a step can occupy; use one of "
                f"{', '.join(APPLIANCES)}, or null for hands-only work and waiting"
            )
        elif equipment not in listed:
            errors.append(f"equipment '{equipment}' isn't in the recipe's equipment")
        allowed = SECTION_STEP_APPLIANCES.get(section)
        if allowed is not None and equipment not in allowed:
            kind = section.replace("_", " ")
            article = "an" if kind[0] in "aeiou" else "a"
            errors.append(
                f"{article} {kind} step can't run on the {equipment}: use {' or '.join(sorted(allowed))}"
            )
    if not 0 <= hands_on <= MAX_HANDS_ON:
        errors.append(f"hands_on_minutes must be 0 to {MAX_HANDS_ON}")
    limit = MAX_WAIT if equipment is None else MAX_HANDS_OFF
    if not 0 <= hands_off <= limit:
        errors.append(
            f"hands_off_minutes must be 0 to {limit}"
            + (" (longer waits are for chilling or soaking, with no appliance)" if equipment else "")
        )
    return errors


TASK_SECTION: Mapping[str, str] = {
    "oven": "oven",
    "air_fryer": "air_fryer",
    "stovetop": "stovetop",
    "microwave": "microwave",
    "rice_cooker": "rice",
}


def task_section(component: str | None, equipment: str | None, hands_off: int) -> str:
    """An idea's task has no step section; the timeline's wording and the fridge rule read one from its
    appliance (a last wait with no appliance sets in the fridge, like a seed's chilling step)."""
    if equipment is not None:
        return TASK_SECTION.get(equipment, "cook")
    if hands_off == 0:
        return "prep"
    return "marinate" if component and "marin" in component.lower() else "no_cook"


def normalized_component(name: str | None) -> str | None:
    if name is None:
        return None
    text = " ".join(name.strip().lower().split())
    return text or None


def merged(tasks: Iterable[Task]) -> tuple[Task, ...]:
    """Consecutive tasks of one component on one piece of equipment, added up, while the task so far is all
    hands-on (so its hands-on minutes stay at its start). Empty tasks (0 and 0) are dropped."""
    out: list[Task] = []
    for t in tasks:
        if t.hands_on == 0 and t.hands_off == 0:
            continue
        prev = out[-1] if out else None
        if (
            prev is not None
            and prev.component == t.component
            and prev.equipment == t.equipment
            and prev.hands_off == 0
        ):
            out[-1] = Task(
                prev.component,
                prev.equipment,
                prev.hands_on + t.hands_on,
                t.hands_off,
                prev.temp_f if prev.temp_f is not None else t.temp_f,
                # a step with waiting or running time says what the task is (marinate, chill in the fridge)
                t.section if t.hands_off else prev.section,
            )
        else:
            out.append(t)
    return tuple(out)


def fallback_timing(active_minutes: int, total_minutes: int, *, no_cook: bool = False) -> DishTiming:
    """No steps to read (a recipe saved without them): the stated hands-on time, then the rest as cooking
    that needs watching (it counts toward the day), or, for a recipe with no appliance, as setting in the
    fridge."""
    wait = max(total_minutes - active_minutes, 0)
    section = "no_cook" if no_cook else "cook"
    return DishTiming((Task(None, None, max(active_minutes, 1), wait, section=section),), estimated=True)


def no_appliance(equipment: Iterable[str]) -> bool:
    return not set(equipment) & set(APPLIANCES)


def timing_from_steps(
    steps: Sequence[StepTiming],
    *,
    active_minutes: int,
    total_minutes: int,
    equipment: Iterable[str] = (),
) -> DishTiming:
    """Tagged steps as tasks, or an estimate when any cook-day step lacks its tags (V15)."""
    day = [s for s in steps if s.section not in OFF_DAY_SECTIONS]
    equipment = list(equipment)
    if not day:
        return fallback_timing(active_minutes, total_minutes, no_cook=no_appliance(equipment))
    if all(s.tagged for s in day):
        tasks = merged(
            Task(
                normalized_component(s.component),
                s.equipment,
                s.hands_on_minutes or 0,
                s.hands_off_minutes or 0,
                s.appliance_temp_f,
                s.section,
            )
            for s in day
        )
        if not tasks:
            return fallback_timing(active_minutes, total_minutes, no_cook=no_appliance(equipment))
        return DishTiming(tasks)
    return estimated_timing(day, active_minutes=active_minutes, equipment=frozenset(equipment))


def _rice_appliance(equipment: frozenset[str]) -> str:
    return next((e for e in RICE_APPLIANCES if e in equipment), "stovetop")


def estimated_timing(
    steps: Sequence[StepTiming], *, active_minutes: int, equipment: frozenset[str]
) -> DishTiming:
    """Timing derived from each step's section and duration (V15): oven, air fryer, rice, microwave and cooker
    steps take 2 minutes hands-on and the rest hands-off; stovetop, prep and assembly steps are all hands-on;
    marinating and chilling are waiting. Steps with no duration share what's left of the recipe's hands-on
    minutes. Each appliance's steps form their own component, so different appliances run side by side;
    marinating belongs to the cooking step after it; prep before the first cooking step and assembly or
    portioning after are shared."""
    rows: list[tuple[str | None, str | None, int | None, int, int | None, str]] = []
    # (component, equipment, hands-on or None = a share of the rest, hands-off, temp, section)
    for s in steps:
        d = s.duration_minutes
        if s.section in ("oven", "air_fryer", "rice", "microwave"):
            appliance = _rice_appliance(equipment) if s.section == "rice" else SECTION_APPLIANCE[s.section]
            hands = min(ESTIMATE_LOADING_MINUTES, d) if d else ESTIMATE_LOADING_MINUTES
            rows.append(
                (s.section, appliance, hands, max((d or 0) - hands, 0), s.appliance_temp_f, s.section)
            )
        elif s.section == "stovetop":
            rows.append(("stovetop", "stovetop", d or None, 0, None, s.section))
        elif s.section == "marinate":
            rows.append(("marinade", None, 0, d or 0, None, s.section))
        elif d and s.section in ("no_cook", "portioning"):  # chilling
            rows.append((None, None, 0, d, None, s.section))
        else:  # prep, assembly and portioning are shared
            rows.append((None, None, d or None, 0, None, s.section))
    known = sum(r[2] or 0 for r in rows)
    shares = [i for i, r in enumerate(rows) if r[2] is None]
    rest = max(active_minutes - known, len(shares))
    hands_for = {i: rest // len(shares) + (1 if n < rest % len(shares) else 0) for n, i in enumerate(shares)}
    tasks: list[Task] = []
    for i, (part, tool, minutes, off, temp, section) in enumerate(rows):
        component = part
        if part == "marinade":  # it belongs to the next cooking step that isn't the rice
            nxt = next((r for r in rows[i + 1 :] if r[1] is not None and r[0] != "rice"), None)
            component = nxt[0] if nxt is not None else None
        tasks.append(
            Task(component, tool, minutes if minutes is not None else hands_for[i], off, temp, section)
        )
    out = merged(tasks)
    if not out or sum(t.hands_on for t in out) == 0:
        return fallback_timing(max(active_minutes, 1), max(active_minutes, 1))
    return DishTiming(out, estimated=True)


def timing_from_tasks(tasks: Iterable[Task]) -> DishTiming:
    """An idea's own task list (FLOW_SPEC §20.1), in order."""
    return DishTiming(
        merged(
            Task(
                normalized_component(t.component),
                t.equipment,
                t.hands_on,
                t.hands_off,
                t.temp_f,
                t.section,
            )
            for t in tasks
        )
    )


# ---------------- batch size ----------------
def grown_hands(base: int, portions: int, base_servings: int) -> int:
    """base × (portions ÷ base servings)^0.6, rounded up, never below the base (V12)."""
    if base <= 0 or portions <= base_servings:
        return base
    factor: float = (portions / base_servings) ** GROWTH_EXPONENT
    return max(base, ceil(round(base * factor, 6)))


def capacity(task: Task) -> int | None:
    """Portions per round on the task's appliance; None = no appliance (hands, or waiting)."""
    if task.equipment is None:
        return None
    if task.equipment == "stovetop":
        return SKILLET_PORTIONS if task.hands_on >= task.hands_off else POT_PORTIONS
    return CAPACITY.get(task.equipment)


def rounds_for(task: Task, portions: int, base_servings: int) -> tuple[int, int]:
    """(rounds, hands-off minutes per round) for a batch of `portions`. The tagged minutes already cover the
    rounds the recipe's own servings need; only a bigger batch adds rounds."""
    cap = capacity(task)
    if cap is None:
        return 1, task.hands_off
    base_rounds = ceil(base_servings / cap)
    needed = ceil(portions / cap)
    if needed <= base_rounds:
        return 1, task.hands_off
    return needed, ceil(task.hands_off / base_rounds)


# ---------------- the schedule ----------------
@dataclass(frozen=True)
class DishBatch:
    """One batch to cook on the day. `key` orders dishes the same way whatever order they arrive in."""

    key: str
    title: str
    timing: DishTiming
    base_servings: int
    portions: int


@dataclass
class _Job:
    dish: int
    task: int
    round: int
    rounds: int
    hands: int
    off: int
    equipment: str | None
    temp: int | None
    load: int
    preds: tuple[int, ...]
    component: str | None
    section: str
    fridge: bool = False
    tail: int = 0

    @property
    def kitchen(self) -> int:
        """Minutes of this job that keep you in the kitchen (a last wait in the fridge doesn't)."""
        return self.hands if self.fridge else self.hands + self.off


def task_preds(tasks: Sequence[Task]) -> tuple[tuple[int, ...], ...]:
    """For each task, the tasks it waits for: the previous task of its component, and shared tasks as
    barriers (a shared task waits for every component's last task since the previous one)."""
    preds: list[tuple[int, ...]] = []
    barrier: int | None = None
    last: dict[str, int] = {}
    for i, t in enumerate(tasks):
        if t.component is None:
            before = set(last.values())
            if not before and barrier is not None:
                before.add(barrier)
            preds.append(tuple(sorted(before)))
            barrier, last = i, {}
        else:
            if t.component in last:
                preds.append((last[t.component],))
            else:
                preds.append((barrier,) if barrier is not None else ())
            last[t.component] = i
    return tuple(preds)


def _expand(dish: int, batch: DishBatch, offset: int) -> list[_Job]:
    tasks = batch.timing.tasks
    preds = task_preds(tasks)
    has_successor = {p for ps in preds for p in ps}
    last_job: dict[int, int] = {}
    jobs: list[_Job] = []
    for i, t in enumerate(tasks):
        hands = grown_hands(t.hands_on, batch.portions, batch.base_servings)
        rounds, off = rounds_for(t, batch.portions, batch.base_servings)
        cap = capacity(t)
        sink = i not in has_successor
        for r in range(rounds):
            before = tuple(last_job[p] for p in preds[i]) if r == 0 else (offset + len(jobs) - 1,)
            share = hands // rounds + (1 if r < hands % rounds else 0)
            if cap is None:
                load = batch.portions
            elif rounds == 1:
                load = min(batch.portions, cap)
            else:
                load = cap if r < rounds - 1 else batch.portions - cap * (rounds - 1)
            last_round = r == rounds - 1
            jobs.append(
                _Job(
                    dish=dish,
                    task=i,
                    round=r,
                    rounds=rounds,
                    hands=share,
                    off=off,
                    equipment=t.equipment,
                    temp=t.temp_f,
                    load=load,
                    preds=before,
                    component=t.component,
                    section=t.section,
                    fridge=sink
                    and last_round
                    and t.equipment is None
                    and off > 0
                    and t.section in FRIDGE_SECTIONS,
                )
            )
        last_job[i] = offset + len(jobs) - 1
    # the longest chain of kitchen work from each job's start to its dish's end (the priority)
    succ: dict[int, list[int]] = {}
    for n, job in enumerate(jobs):
        for p in job.preds:
            succ.setdefault(p, []).append(offset + n)
    for n in range(len(jobs) - 1, -1, -1):
        job = jobs[n]
        after = [jobs[s - offset].tail for s in succ.get(offset + n, [])]
        job.tail = job.kitchen + max(after, default=0)
    return jobs


@dataclass(frozen=True)
class Placed:
    dish: int  # index into DaySchedule.dishes
    task: int
    round: int
    rounds: int
    start: int
    hands_on: int
    hands_off: int
    equipment: str | None
    temp_f: int | None
    component: str | None
    section: str
    fridge: bool

    @property
    def end(self) -> int:
        return self.start + self.hands_on + self.hands_off

    @property
    def kind(self) -> Kind:
        if self.hands_off == 0:
            return "hands_on"
        return "runs" if self.equipment is not None else "wait"


@dataclass(frozen=True)
class DaySchedule:
    dishes: tuple[DishBatch, ...]  # in canonical order
    placed: tuple[Placed, ...]
    elapsed: int  # start to finish, minutes in the kitchen
    hands_on: int
    fridge_minutes: int  # the longest last wait in the fridge (0 = none)
    preheat_at: int | None = None  # when the oven goes on, if it's used
    preheat_temp_f: int | None = None
    lower_bound: int = 0

    @property
    def ready(self) -> int:
        """When the food is ready: start to finish, plus any last wait in the fridge."""
        return max([self.elapsed, *(p.end for p in self.placed)])

    @property
    def estimated(self) -> bool:
        return any(d.timing.estimated for d in self.dishes)


@dataclass
class _Run:
    starts: list[int]
    elapsed: int
    tied: set[int] = field(default_factory=set)


def _fits(
    i: int,
    t: int,
    *,
    jobs: Sequence[_Job],
    running: Mapping[str, list[int]],
    finish: Sequence[int],
    oven_ready: int,
) -> bool:
    job = jobs[i]
    if job.equipment is None:
        return True
    active = [jobs[k] for k in running.get(job.equipment, []) if finish[k] > t]
    if job.equipment == "stovetop":
        return len(active) < BURNERS
    if job.equipment == "oven":
        if t < oven_ready or sum(j.load for j in active) + job.load > CAPACITY["oven"]:
            return False
        return all(
            j.temp is None or job.temp is None or abs(j.temp - job.temp) <= OVEN_SHARE_WITHIN_F
            for j in active
        )
    return not active


def _run(jobs: Sequence[_Job], rank: Sequence[int], oven_ready: int) -> _Run:
    """One pass of list scheduling with this dish order for ties."""
    n = len(jobs)
    starts = [-1] * n
    finish = [0] * n
    waiting = [len(j.preds) for j in jobs]
    succ: list[list[int]] = [[] for _ in range(n)]
    for i, job in enumerate(jobs):
        for p in job.preds:
            succ[p].append(i)
    available = {i: 0 for i in range(n) if not jobs[i].preds}
    running: dict[str, list[int]] = {}
    hands_free = 0
    t = 0
    tied: set[int] = set()
    left = n

    def key(i: int) -> tuple[int, int, int, int]:
        j = jobs[i]
        return (-j.tail, -j.off, rank[j.dish], i)

    def same_last(a: int, b: int) -> bool:
        """Two dishes' identical last tasks (portioning, say): either order gives the same day."""
        ja, jb = jobs[a], jobs[b]
        shape = (ja.hands, ja.off, ja.equipment, ja.temp, ja.load)
        return not succ[a] and not succ[b] and shape == (jb.hands, jb.off, jb.equipment, jb.temp, jb.load)

    while left:
        ready = sorted((i for i, at in available.items() if at <= t), key=key)
        for a, b in pairwise(ready):
            ja, jb = jobs[a], jobs[b]
            if ja.dish != jb.dish and ja.tail == jb.tail and ja.off == jb.off and not same_last(a, b):
                tied.update((ja.dish, jb.dish))
        for i in ready:
            job = jobs[i]
            if (job.hands and hands_free > t) or not _fits(
                i, t, jobs=jobs, running=running, finish=finish, oven_ready=oven_ready
            ):
                continue
            starts[i] = t
            finish[i] = t + job.hands + job.off
            if job.hands:
                hands_free = t + job.hands
            if job.equipment is not None:
                running.setdefault(job.equipment, []).append(i)
            del available[i]
            left -= 1
            for s in succ[i]:
                waiting[s] -= 1
                if waiting[s] == 0:
                    available[s] = max(finish[p] for p in jobs[s].preds)
        if not left:
            break
        upcoming = [at for at in available.values() if at > t]
        if hands_free > t:
            upcoming.append(hands_free)
        upcoming += [finish[k] for group in running.values() for k in group if finish[k] > t]
        if oven_ready > t:
            upcoming.append(oven_ready)
        if not upcoming:  # nothing can ever start; valid jobs never get here
            raise RuntimeError("cook schedule stalled")
        t = min(upcoming)
    elapsed = max((starts[i] + jobs[i].kitchen for i in range(n)), default=0)
    return _Run(starts, elapsed, tied)


def _lower_bound(jobs: Sequence[_Job]) -> int:
    """No schedule can be shorter: your hands-on total, the longest dish, each appliance's busy minutes (the
    stovetop's over 4 burners, the oven's portion-minutes over its capacity, after preheating)."""
    hands = sum(j.hands for j in jobs)
    chain = max((j.tail for j in jobs if not j.preds), default=0)
    busy: dict[str, float] = {}
    for j in jobs:
        if j.equipment is None:
            continue
        minutes = j.hands + j.off
        if j.equipment == "oven":
            busy["oven"] = busy.get("oven", OVEN_PREHEAT_MINUTES) + j.load * minutes / CAPACITY["oven"]
        elif j.equipment == "stovetop":
            busy["stovetop"] = busy.get("stovetop", 0) + minutes / BURNERS
        else:
            busy[j.equipment] = busy.get(j.equipment, 0) + minutes
    return max([hands, chain, *(ceil(round(v, 6)) for v in busy.values())])


def _distinct_orders(tied: Sequence[int], canon: Sequence[DishBatch]) -> Iterable[tuple[int, ...]]:
    """Every order of the tied dishes, in permutation order, skipping orders that only swap two identical
    batches (same tasks, servings and portions): those give the same day."""
    seen: set[tuple[tuple[DishTiming, int, int], ...]] = set()
    for order in permutations(tied):
        shape = tuple((canon[d].timing, canon[d].base_servings, canon[d].portions) for d in order)
        if shape in seen:
            continue
        seen.add(shape)
        yield order


def schedule_day(dishes: Iterable[DishBatch]) -> DaySchedule:
    """The day's schedule for these batches (any order in; the same schedule out)."""
    canon = tuple(sorted(dishes, key=lambda d: (d.key, d.portions, d.title)))
    jobs: list[_Job] = []
    for n, batch in enumerate(canon):
        jobs += _expand(n, batch, len(jobs))
    if not jobs:
        return DaySchedule(canon, (), 0, 0, 0)
    oven_ready = OVEN_PREHEAT_MINUTES if any(j.equipment == "oven" for j in jobs) else 0
    bound = _lower_bound(jobs)
    identity = list(range(len(canon)))
    best = _run(jobs, identity, oven_ready)
    if best.elapsed > bound and best.tied and len(canon) <= MAX_ORDER_DISHES:
        tied = sorted(best.tied)
        for order in _distinct_orders(tied, canon):
            if list(order) == tied:
                continue
            rank = list(identity)
            for position, dish in zip(tied, order, strict=True):
                rank[dish] = position
            run = _run(jobs, rank, oven_ready)
            if run.elapsed < best.elapsed:
                best = run
                if best.elapsed <= bound:
                    break
    placed = tuple(
        Placed(
            dish=j.dish,
            task=j.task,
            round=j.round,
            rounds=j.rounds,
            start=best.starts[i],
            hands_on=j.hands,
            hands_off=j.off,
            equipment=j.equipment,
            temp_f=j.temp,
            component=j.component,
            section=j.section,
            fridge=j.fridge,
        )
        for i, j in enumerate(jobs)
    )
    oven = sorted((p for p in placed if p.equipment == "oven"), key=lambda p: (p.start, p.dish, p.task))
    return DaySchedule(
        dishes=canon,
        placed=placed,
        elapsed=best.elapsed,
        hands_on=sum(j.hands for j in jobs),
        fridge_minutes=max((j.off for j in jobs if j.fridge), default=0),
        preheat_at=max(oven[0].start - OVEN_PREHEAT_MINUTES, 0) if oven else None,
        preheat_temp_f=oven[0].temp_f if oven else None,
        lower_bound=bound,
    )


@lru_cache(maxsize=8192)
def dish_alone(timing: DishTiming, base_servings: int, portions: int) -> DaySchedule:
    """One recipe's own schedule (its components side by side): a recipe's total time (§20.3)."""
    return schedule_day([DishBatch("", "", timing, base_servings, portions)])


def smallest_over(dishes: Sequence[DishBatch], minutes: int) -> tuple[DishBatch, ...]:
    """A smallest set of these batches that still runs over `minutes` (each one is needed to run over): the
    solver's cut (FLOW_SPEC §20.3). The quickest batches are dropped first, so the cut keeps the ones that
    take the time."""
    canon = sorted(dishes, key=lambda d: (d.key, d.portions, d.title))
    alone = {id(d): dish_alone(d.timing, d.base_servings, d.portions).elapsed for d in canon}
    keep = list(canon)
    for batch in sorted(canon, key=lambda d: alone[id(d)]):
        trial = [d for d in keep if d is not batch]
        if trial and schedule_day(trial).elapsed > minutes:
            keep = trial
    return tuple(keep)


# ---------------- eating days ----------------
@dataclass(frozen=True)
class FinishTask:
    """Work left for an eating day (smart prep, FLOW_SPEC §19): a last stage, a reheat, an assembly."""

    day: date
    key: str
    title: str
    task: Task
    portions: int = 1


def finish_schedules(tasks: Iterable[FinishTask]) -> dict[date, DaySchedule]:
    """Each eating day's finish tasks, scheduled on that day only (checked against its weeknight time, V7)."""
    by_day: dict[date, list[DishBatch]] = {}
    for f in tasks:
        by_day.setdefault(f.day, []).append(
            DishBatch(f.key, f.title, DishTiming((f.task,)), f.portions, f.portions)
        )
    return {day: schedule_day(batches) for day, batches in sorted(by_day.items())}


# ---------------- the timeline (§20.4) ----------------
@dataclass(frozen=True)
class TimelineLine:
    at_min: int
    text: str
    kind: Kind | Literal["preheat", "done"]
    minutes: int
    equipment: str | None
    estimated: bool
    dish: int | None  # index into DaySchedule.dishes; None = preheat and done

    @property
    def at_display(self) -> str:
        return clock(self.at_min)


APPLIANCE_PLACE = {
    "oven": "into the oven",
    "air_fryer": "into the air fryer",
    "stovetop": "on the stove",
    "rice_cooker": "in the rice cooker",
    "pressure_cooker": "in the pressure cooker",
    "slow_cooker": "in the slow cooker",
    "microwave": "in the microwave",
    "grill": "on the grill",
}
HANDS_VERB = {
    "prep": "Prep",
    "no_cook": "Mix",
    "assembly": "Make",
    "portioning": "Portion out",
    "marinate": "Marinate",
    "stovetop": "Cook",
    "cook": "Cook",
}


def clock(minutes: int) -> str:
    """'0:12', '1:05'."""
    return f"{minutes // 60}:{minutes % 60:02d}"


def minutes_text(minutes: int) -> str:
    """'45 min', '1 h', '1 h 35 min', '8 h'."""
    h, m = divmod(max(minutes, 0), 60)
    if not h:
        return f"{m} min"
    return f"{h} h" if not m else f"{h} h {m} min"


def round_up_5(minutes: int) -> int:
    return -(-minutes // 5) * 5


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def _line_text(p: Placed, dish_title: str) -> str:
    what = p.component or dish_title
    temp = f" at {p.temp_f}°F" if p.temp_f is not None and p.equipment in ("oven", "air_fryer") else ""
    rounds = f", round {p.round + 1} of {p.rounds}" if p.rounds > 1 else ""
    if p.fridge:
        return f"{_capital(what)} into the fridge to set ({minutes_text(p.hands_off)}{rounds})"
    if p.kind == "runs":
        assert p.equipment is not None
        place = APPLIANCE_PLACE.get(p.equipment, f"on the {p.equipment.replace('_', ' ')}")
        if p.equipment == "stovetop" and p.hands_on >= p.hands_off:
            return f"Cook the {what} on the stove ({minutes_text(p.hands_on + p.hands_off)}{rounds})"
        return f"{_capital(what)} {place}{temp} ({minutes_text(p.hands_on + p.hands_off)}{rounds})"
    if p.kind == "wait":
        verb = "Marinate the" if p.section == "marinate" else "Let it rest:"
        return f"{verb} {what} ({minutes_text(p.hands_on + p.hands_off)}{rounds})"
    verb = HANDS_VERB.get(p.section, "Work on")
    if p.equipment == "stovetop" and p.section not in ("stovetop", "cook"):
        verb = "Cook"
    the = "the " if p.component else ""
    return f"{verb} {the}{what} ({minutes_text(p.hands_on)}{rounds})"


def timeline(schedule: DaySchedule) -> list[TimelineLine]:
    """The day's lines, in time order (preheat first at its minute), ending with Done. Templated by code from
    each task's component, appliance and section; the LLM writes none of it."""
    lines: list[tuple[tuple[int, int, int, int], TimelineLine]] = []
    if schedule.preheat_at is not None:
        temp = f" to {schedule.preheat_temp_f}°F" if schedule.preheat_temp_f is not None else ""
        lines.append(
            (
                (schedule.preheat_at, -1, 0, 0),
                TimelineLine(
                    schedule.preheat_at,
                    f"Preheat the oven{temp}",
                    "preheat",
                    OVEN_PREHEAT_MINUTES,
                    "oven",
                    False,
                    None,
                ),
            )
        )
    for p in schedule.placed:
        dish = schedule.dishes[p.dish]
        minutes = p.hands_on if p.kind == "hands_on" else p.hands_on + p.hands_off
        lines.append(
            (
                (p.start, p.dish, p.task, p.round),
                TimelineLine(
                    p.start,
                    _line_text(p, dish.title),
                    p.kind,
                    minutes,
                    p.equipment,
                    dish.timing.estimated,
                    p.dish,
                ),
            )
        )
    lines.sort(key=lambda kv: kv[0])
    out = [line for _, line in lines]
    out.append(TimelineLine(schedule.elapsed, "Done", "done", 0, None, False, None))
    return out
