"""The cook-day schedule (FLOW_SPEC §20.5, step 2b.9)."""

import random
import time
from datetime import date

import pytest

from app.domain.cook_schedule import (
    DishBatch,
    DishTiming,
    FinishTask,
    StepTiming,
    Task,
    clock,
    dish_alone,
    finish_schedules,
    grown_hands,
    minutes_text,
    round_up_5,
    rounds_for,
    schedule_day,
    smallest_over,
    task_preds,
    timeline,
    timing_from_steps,
)

OVEN_DISH = DishTiming((Task("chicken", None, 10, 0), Task("chicken", "oven", 1, 30, 400, "oven")))
AIR_DISH = DishTiming((Task("fish", None, 4, 0), Task("fish", "air_fryer", 1, 15, 400, "air_fryer")))
RICE_DISH = DishTiming((Task("rice", "rice_cooker", 1, 25, section="rice"),))


def batch(key: str, timing: DishTiming, portions: int = 4, base: int = 4) -> DishBatch:
    return DishBatch(key, key.title(), timing, base, portions)


def intervals(s, *, hands: bool = False, equipment: str | None = None):
    out = []
    for p in s.placed:
        if hands and p.hands_on:
            out.append((p.start, p.start + p.hands_on))
        if equipment is not None and p.equipment == equipment:
            out.append((p.start, p.end))
    return sorted(out)


def max_overlap(spans) -> int:
    events = sorted([(a, 1) for a, _ in spans] + [(b, -1) for _, b in spans], key=lambda e: (e[0], e[1]))
    now = most = 0
    for _, step in events:
        now += step
        most = max(most, now)
    return most


# ---------------- in parallel ----------------
def test_three_dishes_on_three_appliances_finish_faster_together() -> None:
    alone = [dish_alone(d, 4, 4).elapsed for d in (OVEN_DISH, AIR_DISH, RICE_DISH)]
    assert alone == [41, 20, 26]  # the oven waits for its 10-minute preheat, which overlaps the prep
    s = schedule_day([batch("oven", OVEN_DISH), batch("air", AIR_DISH), batch("rice", RICE_DISH)])
    # the kitchen order (AA7): all the chopping first (14 min), then the oven (the longest cook), the rice
    # and the fish while it runs: 45, against 87 one after another (41 if the oven went in before the fish
    # was chopped)
    assert s.elapsed == 45 < sum(alone)
    assert s.hands_on == 17


def test_hands_on_work_that_cant_overlap_adds_to_the_longest_chain() -> None:
    prep_heavy = [
        batch("a", DishTiming((Task("x", None, 10, 0), Task("x", "oven", 1, 30, 400, "oven")))),
        batch("b", DishTiming((Task("y", None, 10, 0), Task("y", "air_fryer", 1, 15, 400, "air_fryer")))),
        batch("c", DishTiming((Task("z", None, 5, 0), Task("z", "rice_cooker", 1, 25)))),
    ]
    s = schedule_day(prep_heavy)
    # every dish's prep first (25 min), then the oven dish (the longest chain), the fish and the rice while it
    # runs: 56, not 41 + 27 + 31
    assert s.elapsed == 56
    assert s.elapsed < sum(dish_alone(b.timing, 4, 4).elapsed for b in prep_heavy)


def test_two_oven_dishes_share_the_oven_only_when_they_fit_together() -> None:
    def roast(temp: int) -> DishTiming:
        return DishTiming((Task("tray", "oven", 1, 30, temp, "oven"),))

    together = schedule_day([batch("a", roast(425)), batch("b", roast(425))])
    assert together.elapsed == 42  # both in at once after preheating: 10-41 and 11-42
    close = schedule_day([batch("a", roast(400)), batch("b", roast(425))])
    assert close.elapsed == 42  # within 25°F (V14)
    apart = schedule_day([batch("a", roast(350)), batch("b", roast(425))])
    assert apart.elapsed == 72  # the second goes in when the first comes out
    too_many = schedule_day([batch("a", roast(425), portions=6), batch("b", roast(425))])
    assert too_many.elapsed == 73  # 6 + 4 portions don't fit 8: one after the other
    for s in (apart, too_many):
        assert max_overlap(intervals(s, equipment="oven")) == 1


def test_hands_never_overlap_and_appliances_run_one_task_at_a_time() -> None:
    simmer = DishTiming((Task("pot", "stovetop", 2, 20, section="stovetop"),))
    s = schedule_day([batch(f"d{i}", simmer) for i in range(6)])
    assert max_overlap(intervals(s, hands=True)) == 1
    assert max_overlap(intervals(s, equipment="stovetop")) == 4  # 4 burners
    assert s.elapsed == 46  # the fifth pot waits for the first burner
    air = schedule_day([batch("a", AIR_DISH), batch("b", AIR_DISH), batch("c", OVEN_DISH)])
    assert max_overlap(intervals(air, equipment="air_fryer")) == 1
    assert max_overlap(intervals(air, hands=True)) == 1


# ---------------- batch size ----------------
def test_hands_on_grows_with_portions_and_never_drops_below_the_base() -> None:
    assert grown_hands(10, 4, 4) == 10
    assert grown_hands(10, 2, 4) == 10  # never below the base
    assert grown_hands(10, 8, 4) == 16  # doubling adds about half
    assert grown_hands(10, 16, 4) == 23  # quadrupling about 130%
    assert grown_hands(0, 16, 4) == 0
    small = dish_alone(DishTiming((Task(None, None, 20, 0),)), 4, 4)
    big = dish_alone(DishTiming((Task(None, None, 20, 0),)), 4, 12)
    assert (small.hands_on, big.hands_on) == (20, 39)


def test_a_batch_above_capacity_takes_extra_rounds() -> None:
    chicken = DishTiming((Task("chicken", "air_fryer", 1, 18, 400, "air_fryer"),))
    s = dish_alone(chicken, 4, 8)
    rounds = [p for p in s.placed if p.equipment == "air_fryer"]
    assert [(p.round, p.rounds, p.hands_off) for p in rounds] == [(0, 2, 18), (1, 2, 18)]
    assert s.elapsed == 38  # 2 rounds of 18 minutes, plus loading each
    assert dish_alone(chicken, 4, 4).elapsed == 19
    # a pot holds 12 portions, a skillet sears 4 per round
    assert rounds_for(Task("curry", "stovetop", 2, 20), 12, 4) == (1, 20)
    assert rounds_for(Task("sear", "stovetop", 12, 0), 8, 4) == (2, 0)
    # the tagged minutes already cover the rounds the recipe's own servings need (4 mugs, 2 at a time)
    assert rounds_for(Task("mugs", "microwave", 1, 5), 4, 4) == (1, 5)
    assert rounds_for(Task("mugs", "microwave", 1, 4), 8, 4) == (4, 2)


# ---------------- order and determinism ----------------
def test_the_same_day_gives_the_same_timeline_whatever_order_the_dishes_arrive_in() -> None:
    dishes = [
        batch("oven", OVEN_DISH),
        batch("air", AIR_DISH),
        batch("rice", RICE_DISH),
        batch("air2", AIR_DISH, portions=8),
        batch("pot", DishTiming((Task(None, None, 6, 0), Task("dal", "stovetop", 2, 25)))),
    ]
    first = schedule_day(dishes)
    rng = random.Random(7)
    for _ in range(10):
        shuffled = list(dishes)
        rng.shuffle(shuffled)
        again = schedule_day(shuffled)
        assert again == first
        assert timeline(again) == timeline(first)


def test_shared_prep_and_portioning_order_a_dish() -> None:
    tasks = (
        Task(None, None, 5, 0),  # 0: shared prep
        Task("chicken", "oven", 1, 20, 425, "oven"),  # 1
        Task("rice", "stovetop", 2, 20),  # 2
        Task("chicken", None, 2, 0, section="assembly"),  # 3: after the chicken
        Task(None, None, 4, 0, section="portioning"),  # 4: after everything
    )
    assert task_preds(tasks) == ((), (0,), (0,), (1,), (2, 3))
    s = dish_alone(DishTiming(tasks), 4, 4)
    start = {p.task: p.start for p in s.placed}
    assert start[1] >= 5 and start[2] >= 5
    assert start[4] >= max(p.end for p in s.placed if p.task in (2, 3))


# ---------------- the fridge and the timeline ----------------
def test_a_last_wait_in_the_fridge_doesnt_count_toward_the_day() -> None:
    oats = DishTiming(
        (Task(None, None, 5, 0, section="no_cook"), Task(None, None, 2, 480, section="portioning"))
    )
    s = schedule_day([batch("oats", oats)])
    assert (s.elapsed, s.fridge_minutes) == (7, 480)
    lines = timeline(s)
    assert [(line.at_display, line.text) for line in lines] == [
        ("0:00", "Mix Oats (5 min)"),
        ("0:05", "Oats into the fridge to set (8 h)"),
        ("0:07", "Done"),
    ]
    marinade = DishTiming(
        (Task("chicken", None, 3, 30, section="marinate"), Task("chicken", "oven", 1, 20, 425))
    )
    assert dish_alone(marinade, 4, 4).elapsed == 54  # a marinade in the middle keeps you waiting


def test_timeline_lines_are_templated_with_times_from_the_schedule() -> None:
    s = schedule_day([batch("sheet", OVEN_DISH), batch("rice", RICE_DISH)])
    lines = timeline(s)
    assert [(line.at_display, line.text, line.kind) for line in lines] == [
        ("0:00", "Preheat the oven to 400°F", "preheat"),
        ("0:00", "Prep the chicken (10 min)", "hands_on"),
        ("0:10", "Chicken into the oven at 400°F (31 min)", "runs"),
        ("0:11", "Rice in the rice cooker (26 min)", "runs"),
        ("0:41", "Done", "done"),
    ]
    assert all(not line.estimated for line in lines)
    assert lines[2].equipment == "oven" and lines[2].minutes == 31
    assert s.dishes[lines[2].dish or 0].title == "Sheet"


# ---------------- finish tasks (smart prep) ----------------
def test_finish_tasks_are_scheduled_on_their_eating_day_only() -> None:
    wed, thu = date(2026, 10, 14), date(2026, 10, 15)
    roast = Task("tandoori chicken", "oven", 5, 25, 425, "oven")
    reheat = Task("rice", "microwave", 1, 3, section="reheating")
    days = finish_schedules(
        [
            FinishTask(wed, "tandoori", "Tandoori chicken", roast),
            FinishTask(wed, "rice", "Rice", reheat),
            FinishTask(thu, "rice", "Rice", reheat),
        ]
    )
    assert sorted(days) == [wed, thu]
    assert len(days[wed].placed) == 2 and len(days[thu].placed) == 1
    assert days[thu].elapsed == 4
    assert days[wed].elapsed == 40  # the oven preheats while nothing else waits for it


# ---------------- from steps ----------------
def test_tagged_steps_become_tasks_without_storage_or_reheating() -> None:
    steps = [
        StepTiming("prep", component="chicken", hands_on_minutes=8, hands_off_minutes=0),
        StepTiming("marinate", component="Chicken ", hands_on_minutes=2, hands_off_minutes=15),
        StepTiming(
            "stovetop", component="chicken", equipment="stovetop", hands_on_minutes=12, hands_off_minutes=0
        ),
        StepTiming(
            "stovetop", component="chicken", equipment="stovetop", hands_on_minutes=1, hands_off_minutes=4
        ),
        StepTiming(
            "stovetop", component="chicken", equipment="stovetop", hands_on_minutes=2, hands_off_minutes=0
        ),
        StepTiming("portioning", hands_on_minutes=4, hands_off_minutes=0),
        StepTiming("storage", hands_on_minutes=0, hands_off_minutes=0),
        StepTiming("reheating", hands_on_minutes=0, hands_off_minutes=0),
    ]
    timing = timing_from_steps(steps, active_minutes=30, total_minutes=45)
    assert not timing.estimated
    assert [(t.component, t.equipment, t.hands_on, t.hands_off) for t in timing.tasks] == [
        ("chicken", None, 10, 15),  # prep + marinate: the hands-on part first
        ("chicken", "stovetop", 13, 4),  # sear + simmer
        ("chicken", "stovetop", 2, 0),  # after a hands-off part: a task of its own
        (None, None, 4, 0),
    ]
    assert timing.hands_on == 29


def test_untagged_steps_are_estimated_from_their_sections() -> None:
    steps = [
        StepTiming("prep"),
        StepTiming("prep"),
        StepTiming("oven", 25, 425),
        StepTiming("rice", 25),
        StepTiming("assembly"),
        StepTiming("portioning"),
        StepTiming("storage"),
        StepTiming("reheating"),
    ]
    timing = timing_from_steps(steps, active_minutes=20, total_minutes=45, equipment=["oven", "stovetop"])
    assert timing.estimated
    assert [(t.component, t.equipment, t.hands_on, t.hands_off) for t in timing.tasks] == [
        (None, None, 8, 0),  # the two prep steps share what's left of the 20 hands-on minutes
        (
            "oven",
            "oven",
            2,
            23,
        ),
        ("rice", "stovetop", 2, 23),
        (None, None, 8, 0),
    ]
    assert dish_alone(timing, 4, 4).elapsed == 43
    with_cooker = timing_from_steps(steps, active_minutes=20, total_minutes=45, equipment=["rice_cooker"])
    assert with_cooker.tasks[2].equipment == "rice_cooker"
    marinated = timing_from_steps(
        [
            StepTiming("prep"),
            StepTiming("marinate", 30),
            StepTiming("rice", 25),
            StepTiming("stovetop", 12),
            StepTiming("portioning"),
        ],
        active_minutes=25,
        total_minutes=60,
    )
    assert [(t.component, t.hands_off) for t in marinated.tasks][:2] == [(None, 0), ("stovetop", 30)]
    assert timing_from_steps([], active_minutes=10, total_minutes=30, equipment=["oven"]).tasks == (
        Task(None, None, 10, 20, section="cook"),
    )
    # with no appliance at all, the wait is chilling: it sets in the fridge, after you leave the kitchen
    chilled = timing_from_steps([], active_minutes=10, total_minutes=30)
    assert chilled.tasks == (Task(None, None, 10, 20, section="no_cook"),)
    assert dish_alone(chilled, 4, 4).elapsed == 10


# ---------------- the kitchen order (AA7) ----------------
def kitchen_order_problems(s) -> list[str]:
    """What breaks the systematic kitchen order in a schedule: hands-on cooking or portioning started while
    some prep (chopping, marinating) was ready and waiting, or portioning while some cooking was (and its
    appliance was free)."""
    out = []
    hands = [p for p in s.placed if p.hands_on]

    def free(equipment: str | None, at: int) -> bool:
        """Whether a task on this appliance could have started then (the oven only when it's empty)."""
        if equipment is None:
            return True
        if equipment == "oven" and s.preheat_at is not None and at < s.preheat_at + 10:
            return False
        busy = sum(1 for o in s.placed if o.equipment == equipment and o.start <= at < o.end)
        return busy < (4 if equipment == "stovetop" else 1)

    for p in hands:
        for q in hands:
            if q.phase < p.phase and q.ready <= p.start < q.start and free(q.equipment, p.start):
                out.append(f"{p.section} at {p.start} before the {q.section} ready at {q.ready}")
    return out


def test_a_cook_day_runs_prep_first_then_the_longest_cook_then_the_rest_and_portions_last() -> None:
    """AA7: chop and marinate everything first, start the longest-cooking item next, the rest while it cooks,
    and finish by portioning."""
    roast = DishTiming(
        (
            Task("chicken", None, 8, 0),  # chop
            Task("chicken", "oven", 2, 40, 425, "oven"),
            Task(None, None, 4, 0, section="portioning"),
        )
    )
    kebab = DishTiming(
        (
            Task("lamb", None, 5, 0),  # chop
            Task("lamb", None, 0, 30, section="marinate"),
            Task("lamb", "air_fryer", 2, 15, 400, "air_fryer"),
            Task(None, None, 3, 0, section="portioning"),
        )
    )
    stew = DishTiming(
        (
            Task("beans", None, 6, 0),  # chop
            Task("beans", "stovetop", 10, 20, section="stovetop"),
            Task(None, None, 3, 0, section="portioning"),
        )
    )
    s = schedule_day([batch("roast", roast), batch("kebab", kebab), batch("stew", stew)])
    assert kitchen_order_problems(s) == []
    lines = [line.text for line in timeline(s) if line.kind != "preheat"]
    chops = [n for n, text in enumerate(lines) if text.startswith("Prep the")]
    cooks = [n for n, text in enumerate(lines) if "oven" in text or "air fryer" in text or "stove" in text]
    assert len(chops) == 3 and max(chops) < min(cooks)  # all the chopping first
    assert lines.index("Marinate the lamb (30 min)") < min(cooks)  # the marinade starts with the prep
    assert lines[min(cooks)].startswith("Chicken into the oven")  # the longest cook goes in first
    portions = [n for n, text in enumerate(lines) if text.startswith("Portion out")]
    assert lines[-1] == "Done" and portions[-1] == len(lines) - 2  # it ends by portioning
    assert all(n > min(cooks) for n in portions)


def test_every_cook_day_keeps_the_kitchen_order() -> None:
    """The same order on 300 random cook days of 1-5 dishes (prep chains, marinades, appliances, shared
    steps, big batches)."""
    rng = random.Random(42)
    appliances = ["oven", "air_fryer", "stovetop", "rice_cooker", None]
    for _ in range(300):
        dishes = []
        for d in range(rng.randint(1, 5)):
            tasks = []
            if rng.random() < 0.5:
                tasks.append(Task(None, None, rng.randint(2, 12), 0))  # shared prep
            for part in range(rng.randint(1, 3)):
                name = f"part{part}"
                tasks.append(Task(name, None, rng.randint(1, 10), 0))
                if rng.random() < 0.3:
                    tasks.append(Task(name, None, 0, rng.randint(10, 60), section="marinate"))
                equipment = rng.choice(appliances)
                if equipment is not None:
                    temp = 425 if equipment in ("oven", "air_fryer") else None
                    tasks.append(
                        Task(name, equipment, rng.randint(1, 8), rng.randint(5, 45), temp, equipment)
                    )
            tasks.append(Task(None, None, rng.randint(2, 6), 0, section="portioning"))
            dishes.append(batch(f"d{d}", DishTiming(tuple(tasks)), portions=rng.choice([2, 4, 8])))
        s = schedule_day(dishes)
        assert kitchen_order_problems(s) == [], [d.timing for d in dishes]


# ---------------- the solver's cut ----------------
def test_smallest_over_keeps_only_the_batches_that_run_over_together() -> None:
    hands = DishTiming((Task(None, None, 25, 0),))
    three = [batch("a", hands), batch("b", hands), batch("c", hands)]
    assert schedule_day(three).elapsed == 75
    assert [d.key for d in smallest_over(three, 60)] == ["a", "b", "c"]
    long = DishTiming((Task(None, None, 70, 0),))
    assert [d.key for d in smallest_over([*three, batch("z", long)], 60)] == ["z"]


def test_minutes_and_clock_text() -> None:
    assert [minutes_text(m) for m in (45, 60, 95, 480)] == ["45 min", "1 h", "1 h 35 min", "8 h"]
    assert [clock(m) for m in (0, 12, 65)] == ["0:00", "0:12", "1:05"]
    assert [round_up_5(m) for m in (90, 91, 94, 95)] == [90, 95, 95, 95]


@pytest.mark.perf
def test_a_six_dish_day_schedules_in_under_50_ms() -> None:
    dishes = [
        batch(
            "sheet",
            DishTiming(
                (
                    Task("chicken", None, 12, 0),
                    Task("chicken", "oven", 1, 25, 425, "oven"),
                    Task("rice", "stovetop", 2, 23),
                    Task("sauce", None, 3, 0, section="assembly"),
                    Task(None, None, 4, 0, section="portioning"),
                )
            ),
            portions=8,
        ),
        batch(
            "curry",
            DishTiming(
                (
                    Task(None, None, 10, 0),
                    Task("gravy", "stovetop", 21, 0),
                    Task("gravy", "stovetop", 2, 16),
                    Task(None, None, 3, 0, section="portioning"),
                )
            ),
        ),
        batch("air", AIR_DISH, portions=8),
        batch(
            "dal",
            DishTiming(
                (
                    Task(None, None, 6, 0),
                    Task("dal", "stovetop", 2, 25),
                    Task("rice", "stovetop", 2, 23),
                    Task("tadka", "stovetop", 8, 0),
                    Task(None, None, 3, 0, section="portioning"),
                )
            ),
        ),
        batch(
            "drums",
            DishTiming(
                (
                    Task("chicken", None, 8, 0),
                    Task("chicken", None, 3, 60, section="marinate"),
                    Task("chicken", "oven", 2, 38, 425, "oven"),
                    Task(None, None, 4, 0, section="portioning"),
                )
            ),
        ),
        batch(
            "oats",
            DishTiming(
                (Task(None, None, 8, 0, section="no_cook"), Task(None, None, 3, 480, section="portioning"))
            ),
        ),
    ]
    schedule_day(dishes)  # warm up
    start = time.perf_counter()
    s = schedule_day(dishes)
    assert time.perf_counter() - start < 0.05
    assert s.elapsed > 0
