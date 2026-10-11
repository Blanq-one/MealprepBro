"""The Saved lists (C7, E9): your ♥ favorites or 🔖 saved-for-later recipes as cards, most recently saved
first, at their default version, scaled to your household at your portion size (the numbers the recipe page
shows for that portion count), with pantry coverage against your current pantry (step 2b.3a)."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cook import answers as answers_mod
from app.cook.cards import badges, coverage_lines, numbers, portions_display
from app.cook.pool import load_pool
from app.db.models import AppUser, Recipe, RecipeFavorite, RecipeSaved, RecipeVersion
from app.schemas.cook import CookAnswers
from app.schemas.recipes import SavedRecipeOut
from app.services import favorites
from app.services.dishes import dish_categories
from app.services.settings import load_settings

TABLES: dict[favorites.SavedList, type[RecipeFavorite] | type[RecipeSaved]] = {
    favorites.SavedList.FAVORITES: RecipeFavorite,
    favorites.SavedList.LATER: RecipeSaved,
}


def saved_rows(
    session: Session, user_id: int, which: favorites.SavedList
) -> list[tuple[datetime, Recipe, RecipeVersion]]:
    table = TABLES[which]
    return [
        (saved_at, recipe, version)
        for saved_at, recipe, version in session.execute(
            select(table.created_at, Recipe, RecipeVersion)
            .join(Recipe, Recipe.id == table.recipe_id)
            .join(RecipeVersion, RecipeVersion.id == Recipe.default_version_id)
            .where(table.user_id == user_id, Recipe.archived_at.is_(None))
            .order_by(table.created_at.desc(), Recipe.id.desc())
        ).tuples()
    ]


def saved_cards(
    session: Session, user: AppUser, which: favorites.SavedList, now: datetime
) -> list[SavedRecipeOut]:
    rows = saved_rows(session, user.id, which)
    if not rows:
        return []
    settings = load_settings(session, user.id)
    query = answers_mod.resolve(CookAnswers(mode="now"), settings, now)  # your whole pantry, no extras
    pool = load_pool(
        session, user.id, settings, query, pairs=[(recipe, version) for _, recipe, version in rows]
    )
    marks = favorites.marks(session, user.id, [recipe.id for _, recipe, _ in rows])
    categories = dish_categories(session, [version.id for _, _, version in rows])
    cards = []
    for saved_at, _, version in rows:
        item = pool.item(version.id)
        if item is None:  # a recipe without ingredient lines can't be a card
            continue
        uses, could_buy, missing, swaps = coverage_lines(item.rank_input.coverage)
        cards.append(
            SavedRecipeOut(
                recipe_id=item.recipe.id,
                version_id=version.id,
                title=version.title,
                dish_category=categories[version.id].value,
                badges=badges(item, marks.saved, marks.favorites),
                steps_ready=version.steps_status is None,
                portions=query.people,
                portion_size=query.portion_size.value,
                portions_display=portions_display(query.people),
                numbers=numbers(item, (), query.store_order),
                uses=uses,
                could_buy=could_buy,
                missing=missing,
                swaps=swaps,
                saved_at=saved_at,
            )
        )
    return cards
