"""The narrow prose filter (BUILD_PLAN §7.3, AC 1.5)."""

import pytest

from app.domain.text_rules import ProseCategory, check_text, passes
from app.seed.files import load_seed_files

MUST_PASS = [
    "Air fry at 400F for 18 minutes, flip at 9.",
    "Preheat the oven to 425°F; roast 25–30 minutes, turning once.",
    "Rinse 1 cup rice; add 1½ cups water; simmer covered 15 minutes, rest 10.",
    "Marinate 2–12 hours in the fridge.",
    "Refrigerate overnight to marinate.",
    "Chill the pudding 30 minutes before serving.",
    "Freeze 20 minutes to firm up before slicing.",
    "Bake at 375°F until the chicken is cooked through.",
    "Divide into 4 containers, about 350 g each.",
    "Toss with oil to prevent sticking.",
    "Whisk the protein powder into the milk.",
    "Warm each tortilla on a dry pan 30 seconds per side.",
    "Pressure cook on high 8 minutes, natural release 10.",
    # extra real-world instructions that must not trip the filter
    "Whisk 30 g protein powder into the milk.",
    "Add the low-sodium chicken broth and simmer 15 minutes.",
    "Fold in the full-fat Greek yogurt off the heat.",
    "Heat until the oil reaches 350°F, then fry in batches.",
    "Season with a healthy pinch of salt.",
    "Stir so the sauce helps the rice thicken; it saves time on busy nights.",
    "Makes 4 servings; sear the protein in a hot pan.",
    "Cook over low heat, then raise to high heat for 2 minutes.",
    "Protein pudding: divide into 2 cups.",
]

MUST_BLOCK = [
    ("Cook until the internal temperature reaches 165°F.", ProseCategory.SAFE_TEMPERATURE),
    ("A thermometer should read 165 F in the thickest part.", ProseCategory.SAFE_TEMPERATURE),
    ("Keeps 5 days in the fridge.", ProseCategory.STORAGE_DURATION),
    ("Freezes well for up to 3 months.", ProseCategory.STORAGE_DURATION),
    ("About 450 calories per bowl.", ProseCategory.CALORIES),
    ("A light, low-calorie lunch.", ProseCategory.CALORIES),
    ("40 g protein per serving.", ProseCategory.MACROS),
    ("High-protein and low-carb.", ProseCategory.MACROS),
    ("Costs about $2.50 per serving.", ProseCategory.COST),
    ("A cheap weeknight dinner.", ProseCategory.COST),
    ("Helps prevent anemia.", ProseCategory.HEALTH_CLAIM),
    ("Boosts your immunity.", ProseCategory.HEALTH_CLAIM),
    # the R7 cost words
    ("The cheapest option this week.", ProseCategory.COST),
    ("A budget-friendly bowl.", ProseCategory.COST),
    ("Chicken thighs are a good deal right now.", ProseCategory.COST),
    ("Spinach is on sale.", ProseCategory.COST),
    # nutrient-content claims are code-only labels
    ("Spinach makes this rich in iron.", ProseCategory.MACROS),
    ("A good source of fiber.", ProseCategory.MACROS),
    ("Refrigerate for up to 3 days.", ProseCategory.STORAGE_DURATION),
    ("Good for your heart.", ProseCategory.HEALTH_CLAIM),
]


@pytest.mark.parametrize("text", MUST_PASS)
def test_must_pass(text):
    assert check_text(text) == [], text


@pytest.mark.parametrize(("text", "category"), MUST_BLOCK)
def test_must_block_names_the_phrase(text, category):
    violations = check_text(text)
    assert violations, text
    hit = [v for v in violations if v.category is category]
    assert hit, (text, violations)
    for v in hit:
        assert v.phrase and v.phrase.lower() in text.lower()
        assert v.phrase in v.message


def test_mixed_oven_and_internal_temperature_keeps_the_oven_temperature():
    violations = check_text("Bake at 375°F until the internal temperature reaches 165°F")
    assert len(violations) == 1
    v = violations[0]
    assert v.category is ProseCategory.SAFE_TEMPERATURE
    assert v.phrase == "until the internal temperature reaches 165°F"
    assert "keep the oven temperature" in v.message
    assert "375°F" in v.message


def test_empty_text_passes():
    assert passes("")
    assert passes("   ")


def test_every_seed_recipe_text_passes_the_filter():
    """Seed text goes through the same filter as LLM text (§13)."""
    for file_name, recipe in load_seed_files().recipes:
        texts = [recipe.title, recipe.description]
        texts += [line.preparation for line in recipe.ingredients if line.preparation]
        texts += [step.text for step in recipe.steps]
        for text in texts:
            assert check_text(text) == [], (file_name, text)
