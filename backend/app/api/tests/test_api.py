from sqlalchemy import select, text

from app.db.models import Ingredient

PROBLEM = "application/problem+json"


def _id(session, slug):
    return session.scalars(select(Ingredient.id).where(Ingredient.slug == slug)).one()


def _nutrient(nutrition, code):
    return next(n for n in nutrition["nutrients"] if n["code"] == code)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_ingredient_search(client):
    hits = client.get("/api/v1/ingredients", params={"q": "boneless thighs"}).json()
    assert hits[0]["slug"] == "chicken-thigh-boneless-skinless"
    assert hits[0]["status"] == "allowed"
    beef = client.get("/api/v1/ingredients", params={"q": "beef broth"}).json()[0]
    assert (beef["slug"], beef["status"]) == ("beef-broth", "excluded")


def test_ingredient_detail_and_404(client, seeded_db):
    tortilla = client.get(f"/api/v1/ingredients/{_id(seeded_db, 'flour-tortilla-small')}").json()
    assert tortilla["count_unit_weight_g"] == "37.000"
    assert tortilla["nutrition_source"] == "package_label"
    assert "package label" in tortilla["notes"]
    energy = next(n for n in tortilla["nutrients"] if n["code"] == "energy_kcal")
    assert (energy["amount_per_100g"], energy["source"]) == ("297.2970", "package_label")
    assert {(p["store_name"], p["price_cents"], p["is_estimate"]) for p in tortilla["prices"]} == {
        ("Price Rite", 199, False),
        ("Stop & Shop", 279, True),
    }
    missing = client.get("/api/v1/ingredients/999999999")
    assert missing.status_code == 404
    assert missing.headers["content-type"] == PROBLEM
    assert missing.json()["status"] == 404


def test_calculation_round_trip(client, seeded_db):
    body = {
        "servings": 4,
        "lines": [
            {
                "ingredient_id": _id(seeded_db, "chicken-thigh-boneless-skinless"),
                "quantity": "680",
                "unit": "g",
            },
            {"ingredient_id": _id(seeded_db, "rice-long-grain-white"), "quantity": "300", "unit": "g"},
            {"ingredient_id": _id(seeded_db, "olive-oil"), "quantity": "2", "unit": "tbsp"},
            {"ingredient_id": _id(seeded_db, "salt"), "quantity": "1 1/4", "unit": "tsp"},
        ],
    }
    response = client.post("/api/v1/calculations/recipe", json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["portions"] == 4
    assert data["nutrition_complete"] is True
    assert data["per_portion"]["kcal"] == round(data["total"]["kcal"] / 4)
    assert _nutrient(data["per_portion"], "protein_g")["label"] == "high_in"
    assert data["per_portion"]["heme_iron"]["label"] == "estimated"
    ss = next(c for c in data["costs"] if c["store_name"] == "Stop & Shop")
    assert ss["complete"] is True and ss["staples_not_costed"] == ["salt"]
    assert isinstance(ss["total_cents"], int)
    assert data["lines"][3]["display"] == "1¼ tsp salt"  # shown as written
    assert (data["lines"][3]["quantity"], data["lines"][3]["unit"]) == ("6.161", "ml")  # stored base amount


def test_calculation_scaled_to_practical_amounts(client, seeded_db):
    body = {
        "servings": 4,
        "scale_to_portions": 5,
        "lines": [
            {"ingredient_id": _id(seeded_db, "egg-large"), "quantity": "3", "unit": "count"},
            {"ingredient_id": _id(seeded_db, "salt"), "quantity": "1", "unit": "tsp"},
        ],
    }
    data = client.post("/api/v1/calculations/recipe", json=body).json()
    assert data["scale_factor"] == "1.2500"
    assert [line["display"] for line in data["lines"]] == ["4 egg, large", "1¼ tsp salt"]
    assert data["lines"][0]["quantity"] == "4"  # the practical amount drives the numbers: 4 eggs, not 3.75
    assert data["total"]["kcal"] == 286  # 4 × 50 g × 143 kcal / 100 g


def test_calculation_validation_errors_are_problem_json(client, seeded_db):
    salt = _id(seeded_db, "salt")
    bad_quantity = client.post(
        "/api/v1/calculations/recipe",
        json={"servings": 1, "lines": [{"ingredient_id": salt, "quantity": "abc", "unit": "g"}]},
    )
    assert bad_quantity.status_code == 422
    assert bad_quantity.headers["content-type"] == PROBLEM
    assert bad_quantity.json()["errors"]

    ambiguous = client.post(
        "/api/v1/calculations/recipe",
        json={"servings": 1, "lines": [{"ingredient_id": salt, "quantity": "1", "unit": "T"}]},
    )
    assert ambiguous.status_code == 422
    assert "tbsp' or 'tsp" in ambiguous.json()["detail"]

    no_density = client.post(
        "/api/v1/calculations/recipe",
        json={
            "servings": 1,
            "lines": [{"ingredient_id": _id(seeded_db, "chia-seeds"), "quantity": "1", "unit": "tbsp"}],
        },
    )
    assert no_density.status_code == 422
    assert "no density" in no_density.json()["detail"]

    unknown = client.post(
        "/api/v1/calculations/recipe",
        json={"servings": 1, "lines": [{"ingredient_id": 999999999, "quantity": "1", "unit": "g"}]},
    )
    assert unknown.status_code == 422


def test_seed_recipes_endpoint(client):
    recipes = client.get("/api/v1/recipes/seed").json()
    assert len(recipes) == 10  # 9 Phase 0 drafts + the chia pudding added in Phase 1
    assert all(r["is_draft"] for r in recipes)
    by_title = {r["title"]: r for r in recipes}
    assert all(r["status"] == "complete" and r["incomplete_reasons"] == [] for r in recipes)
    for title in (
        "Double chocolate protein pudding",
        "Chocolate protein overnight oats",
        "Chocolate protein chia pudding",
    ):
        # nutrition complete, cost pending: no protein powder price yet
        assert all(c["unpriced"] == ["protein powder, double chocolate"] for c in by_title[title]["costs"])
        assert not any(c["complete"] for c in by_title[title]["costs"])
    pudding = by_title["Double chocolate protein pudding"]["per_serving"]
    assert _nutrient(pudding, "protein_g")["amount"] == "42.9"  # 24 g per scoop now, not 25
    for recipe in recipes:
        assert recipe["per_serving"]["kcal"] > 0
    wraps = by_title["Egg, spinach and pepper breakfast wraps"]
    pr = next(c for c in wraps["costs"] if c["store_name"] == "Price Rite")
    ss = next(c for c in wraps["costs"] if c["store_name"] == "Stop & Shop")
    assert pr["total_cents"] < ss["total_cents"]  # $1.99 / 20 tortillas at Price Rite


def test_unknown_route_is_problem_json(client):
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM


def test_not_seeded_is_503(client, seeded_db):
    seeded_db.execute(text("DELETE FROM user_settings"))
    response = client.get("/api/v1/ingredients", params={"q": "rice"})
    assert response.status_code == 503
    assert response.headers["content-type"] == PROBLEM
    assert "seed" in response.json()["detail"]
