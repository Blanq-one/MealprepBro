"""A cook day's prep order (FLOW_SPEC C1b; 2b.5 deliverable 11, AC 14): what starts first, then what to cook
while it runs; nothing when there's one batch or only hands-on work."""

from app.domain.prep_order import PrepBatch, prep_order

SHEET_PAN = PrepBatch(
    "Sheet-pan chicken", 20, 45, frozenset({"oven", "stovetop"}), ("prep", "oven", "rice", "portioning")
)
STIR_FRY = PrepBatch("Chicken stir-fry", 20, 20, frozenset({"stovetop"}), ("prep", "stovetop", "portioning"))
CURRY = PrepBatch("Chicken curry", 30, 55, frozenset({"stovetop"}), ("prep", "stovetop", "portioning"))
OATS = PrepBatch("Overnight oats", 5, 485, frozenset(), ("prep", "no_cook", "portioning"))


def test_the_oven_batch_starts_first_and_the_stovetop_one_cooks_while_it_runs():
    assert prep_order([STIR_FRY, SHEET_PAN]) == [
        "1. Start Sheet-pan chicken first: it goes in the oven",
        "2. Cook Chicken stir-fry while the oven runs",
    ]


def test_a_simmering_batch_starts_after_the_oven_and_chilling_comes_first_of_all():
    assert prep_order([CURRY, SHEET_PAN, STIR_FRY, OATS]) == [
        "1. Start Overnight oats first: it chills in the fridge",
        "2. While it chills, start Sheet-pan chicken: it goes in the oven",
        "3. While it chills, start Chicken curry: it simmers on the stove",
        "4. Cook Chicken stir-fry while it chills",
    ]


def test_one_batch_or_only_hands_on_work_has_no_order():
    assert prep_order([SHEET_PAN]) == []
    assert prep_order([STIR_FRY, PrepBatch("Egg wraps", 25, 25, frozenset({"stovetop"}), ("prep",))]) == []
