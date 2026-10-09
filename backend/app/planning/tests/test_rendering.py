"""Recipe rendering: injected safety lines, code storage/reheating text, per-container weight, labels and
the draft badge."""

from decimal import Decimal

from app.domain.food_safety import SafetyCategory
from app.planning.rendering import LineInput, RenderInput, StepInput, render


def lines(chicken_category=SafetyCategory.POULTRY, egg_role="protein"):
    return [
        LineInput(1, "chicken thigh", Decimal(680), "g", Decimal(680), "protein", chicken_category),
        LineInput(2, "rice (dry)", Decimal(300), "g", Decimal(300), "carb"),
        LineInput(3, "egg", Decimal(2), "count", Decimal(100), egg_role, SafetyCategory.EGG),
        LineInput(4, "cilantro", Decimal(10), "g", Decimal(10), "garnish", optional=True),
    ]


def data(steps, freezer=True, draft=True, line_items=None):
    return RenderInput(
        version_id=1,
        title="Chicken rice",
        description="d",
        is_draft=draft,
        freezer_friendly=freezer,
        portions=4,
        lines=line_items or lines(),
        steps=steps,
        leftover_fridge_days=3,
        per_portion={"energy_kcal": Decimal("612.4"), "protein_g": Decimal(45), "iron_mg": Decimal("2.4")},
        daily_values={"protein_g": Decimal(50), "iron_mg": Decimal(18)},
        heme_iron_mg=Decimal("0.9"),
    )


STEPS = [
    StepInput("prep", "Cut the chicken."),
    StepInput("stovetop", "Sear the chicken until cooked through.", 12, None, 1),
    StepInput("portioning", "Divide among 4 containers."),
    StepInput("reheating", "Microwave covered, stirring halfway."),
]


def test_doneness_step_gets_the_safe_temperature():
    r = render(data(STEPS))
    sear = next(s for s in r.steps if s.text.startswith("Sear"))
    assert sear.safety_note == "Check that the chicken thigh reaches 165°F in the thickest part."


def test_missing_doneness_step_is_appended_with_the_strictest_temperature():
    steps = [
        StepInput("prep", "Cut the chicken."),
        StepInput("stovetop", "Sear the chicken."),
        StepInput("portioning", "Divide."),
    ]
    r = render(data(steps))
    added = [s for s in r.steps if s.added_by_app and s.safety_note]
    assert len(added) == 1 and "165°F" in added[0].safety_note and added[0].section == "stovetop"


def test_eggs_only_count_as_an_egg_dish_when_they_are_the_protein():
    items = lines(chicken_category=None, egg_role="other")
    r = render(
        data(
            [StepInput("prep", "Mix."), StepInput("oven", "Bake."), StepInput("portioning", "Cut.")],
            line_items=items,
        )
    )
    assert r.safety_notes == ()


def test_storage_and_reheating_end_with_the_code_text():
    r = render(data(STEPS))
    storage = [s.text for s in r.steps if s.section == "storage"]
    assert storage and storage[-1].startswith("Refrigerate in airtight containers and eat within 3 days")
    assert "Freezer:" in storage[-1] and "FoodSafety.gov" in storage[-1]
    reheat = [s.text for s in r.steps if s.section == "reheating"]
    assert reheat[-1] == "Reheat leftovers until they reach 165°F throughout."
    assert [s.section for s in r.steps][-1] == "reheating"


def test_no_freezer_text_when_not_freezer_friendly():
    r = render(data(STEPS, freezer=False))
    assert "Freezer" not in " ".join(s.text for s in r.steps)


def test_per_container_weight_labels_heme_and_badge():
    r = render(data(STEPS))
    assert r.per_container == "≈ 270 g per container"  # (680 + 300 + 100) / 4, optional cilantro left out
    assert "High in protein" in r.labels and "Good source of iron" in r.labels
    assert r.heme_note == "Iron: about 0.9 mg heme and 1.5 mg non-heme per portion (estimated)"
    assert r.badge == "draft" and r.kcal_per_portion == 612
    assert render(data(STEPS, draft=False)).badge is None
