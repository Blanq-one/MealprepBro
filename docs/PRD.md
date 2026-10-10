# Personal Meal-Prep AI - Expanded Product Requirements

## Primary user flow (added 2026-10-10)

The app is organized around how I actually think about cooking: "what can I make now?" or "what should I prep for
the next few days?", then "what do I have?", then "show me options". Every screen asks one question with one large
control, explains in one short line why it asks, and starts pre-filled from my last answers or my settings. The full
screen-by-screen spec is `docs/FLOW_SPEC.md`; the sections below remain the detailed requirements behind it.

**Four tabs: Cook (the app opens here), Grocery, Pantry, Settings.**

### Cook

1. **A meal now, or meal prep:** the two dominant buttons at the top of the screen. Meal prep also asks how much (a
   number of portions, or which days and meals, e.g. 5 lunches, or lunch + dinner Mon–Fri) and when I'll cook (today,
   or on my cook days). Below the two buttons the screen also shows:
   - a **Same as last time** card that skips straight to results;
   - today's meals from my current plan;
   - a **Saved** section with my favorites and recipes saved for later.
2. **Goals:** multi-select tiles (high protein, high carb, cheap, quick, iron rich, low calorie) plus a mood (simple,
   medium, fancy). They map onto the existing nutrition priorities (§3), time limits (§6), moods (§5) and cost
   weighting (§13).
3. **What do I have?** Pre-filled from my pantry inventory; I can switch any item off for this search. I can add more
   items, each marked **have it** or **could buy** (e.g. standing in the store looking at chickpeas), with quick add
   or typed entry. Meal prep then asks whether I'm shopping for it, with an optional budget.
4. **Results.**
   - **A meal now:** a ranked list of recipe cards. Each card shows a dish-category icon, kcal, protein, time, cost,
     which of my ingredients it uses, the "could buy" items with their cost, and anything missing with a suggested
     substitute. Saved and seed recipes appear immediately; newly generated recipes stream in after, once they pass
     the same validator and code-computed nutrition rules as everything else.
   - **Meal prep:** a plan that starts with today, then the following days. Each day shows kcal, protein and cost;
     each meal row shows its icon, name, kcal and protein, and has a **swap** button that replaces only that meal
     and keeps the plan valid. A Recipes / Shopping list toggle switches views.
5. **Recipe page:** full ingredients and real cooking instructions (§11), with **cook this**, **favorite**, **save
   for later** and **mark cooked**. For meal prep it is scaled to the requested portions, with the batch, fridge and
   freezer logic of the weekly planner.

While anything is built, the app shows its real progress stages as friendly steps (checking pantry, finding
recipes, balancing calories, pricing groceries), not a spinner. When the recipe service's per-minute limit needs a
pause (e.g. tapping "More ideas" twice quickly), the app shows a friendly wait with a short countdown, never an
error.

**High protein** asks for more protein than my target, but only up to 1.5 × my daily target. Beyond that, extra
protein earns nothing, so the tile can't push plans back into expensive all-chicken weeks.

### Grocery

**What should I buy?** I pick filters (protein rich, low calorie, cheap, …) and an optional budget. The app does the
math and suggests what to buy, with a one-line reason per item computed from stored data (e.g. "chicken thighs:
cheapest protein per dollar at Price Rite"). The checklist grouped by store, the stock-up section and Done shopping
stay here.

### Pantry and Settings

- **Pantry** is the inventory screen. Quick add asks how much: full, ¾, ½, ¼, or a custom amount in the item's
  natural unit (default full).
- **Settings** holds everything (people, calories, protein target, budget, cook days, stores, diet rules, held items,
  frequency caps, meals to plan, equipment, "always have" staples), editable any time.
- **A first-run onboarding wizard** (9 short screens, related questions combined) fills Settings once, pre-filled
  from my saved settings: how many people I cook for, calories, protein, weekly budget (optional), stores, dietary
  rules, which meals to plan, cook days and kitchen equipment. The first screen offers **Skip, use my current
  settings**. It never calculates a calorie recommendation.

### Favorites and save for later

- **Favorite (♥)** means "suggest this more often": it persists and boosts the recipe in rankings and plans whenever
  it fits my constraints (§17).
- **Save for later (🔖)** is a plain bookmark with no ranking effect, for recipes I want to try another time.
- Both appear in the Saved section of the Cook tab, and both buttons are on recipe cards and recipe pages.

### Look and feel

Friendly and warm: a light theme by default with a dark mode, large type, generous spacing, rounded cards, and
dish-category icons or emoji instead of food photos. The app has its own original personality (a small clay pot
called Pottle) and a calm, plain-spoken voice.

### What doesn't change

Code does all math; the LLM only writes recipes and text; nutrition comes from the database; the solver fits
multi-meal plans; every LLM output is validated; diet, food-safety and claims rules apply on every screen. Ratings,
recipe editing and versioning, the preference profile and Cook Again (§18–§24) come later.

## 1. Core Concept

This is a personal AI-powered meal-prep and grocery optimization app.

The app should answer:

> "Given my calorie/nutrition goals, budget, available ingredients, grocery prices, equipment, available cooking time, portion requirements, and personal preferences, what should I cook this week?"

It is not primarily a recipe app.

It is a personal optimization system that combines:

- Pantry/fridge/freezer inventory
- Grocery prices
- Budget
- Calories
- Protein/carbohydrate/fat priorities
- Micronutrient priorities
- Portion size
- Cooking time
- Cooking complexity
- Food preferences
- Food waste
- Seasonal ingredients
- Personal meal history
- Likes/dislikes/favorites

---

## 2. Calorie Planning

Calories should be a weekly planning constraint, not merely a per-recipe statistic.

Default personal target: **1,800 kcal/day**

The app should allow the user to configure:

- Calories per day
- Number of days
- Total calories for the week
- Calories per meal
- Calories reserved for snacks/desserts

Example: 1,800 kcal/day x 7 days = 12,600 kcal/week

The app should be able to plan around a weekly calorie budget (12,600 kcal), then allocate those calories across:

- Breakfast
- Lunch
- Dinner
- Snacks
- Protein desserts
- Drinks if included

Example:

| Slot | Allocation |
|---|---|
| Weekly target | 12,600 kcal |
| Breakfast | ~350 kcal/day |
| Lunch | ~550 kcal/day |
| Dinner | ~650 kcal/day |
| Snack/dessert | ~250 kcal/day |

These are examples only. The user should be able to change the allocation.

The system should show:

`Planned: 12,430 / 12,600 kcal`

rather than merely giving individual recipe calories.

---

## 3. Nutrition Priority Modes

The user should be able to configure what nutritional characteristic matters most for the current week.

### Protein Rich

Prioritize:

- Chicken
- Eggs
- Greek yogurt
- Protein powder
- Chickpeas
- Other high-protein foods

Optimize for high protein while remaining within the calorie budget.

### Carb Rich

Useful for weeks where the user wants more carbohydrate-heavy meals.

Prioritize:

- Rice
- Potatoes
- Oats
- Other carbohydrate sources

Still respect the calorie target.

### Iron Rich

Prioritize foods containing meaningful amounts of iron.

Potential ingredients:

- Spinach
- Chickpeas
- Lentils
- Seeds
- Meat
- Other iron-containing foods

The system should distinguish between heme iron and non-heme iron, and should not make medical claims.

### Other possible modes

Architecture should allow future modes:

- Fiber rich
- Lower fat
- Higher satiety
- Higher vegetable intake
- Budget maximum
- Balanced nutrition

---

## 4. Weekly Nutrition Configuration

At the beginning of each week, the user should be able to select:

| Setting | Example |
|---|---|
| Calories | 1,800 kcal/day |
| Nutrition priority | Protein Rich |
| Secondary priority | Iron Rich |
| Days | 7 |
| Meals | 3/day |
| Dessert | Yes |
| Budget | $40 |

The AI then generates the week's plan around these constraints.

The configuration should be editable at any time.

---

## 5. Recipe Mood / Complexity

The user should be able to specify the cooking mood for the day.

### SIMPLE

For days when I don't want to cook.

Examples:

- One-pan meals
- Air-fryer chicken
- Simple rice bowls
- Minimal chopping
- 3-6 ingredients where practical

Target: ~10-30 minutes active/total cooking time depending on recipe.

### MEDIUM

Normal cooking.

Examples:

- Marinated chicken
- Rice + protein + vegetables
- Multi-component bowls
- Basic sauces

Target: ~30-60 minutes.

### FANCY

For when I actually want to cook.

Examples:

- More complex sauces
- Multiple components
- More elaborate seasoning
- More presentation
- Restaurant-style meal-prep concepts

Time can be 60-120+ minutes.

The app should never assume the user wants complicated food every day.

---

## 6. Cooking Time Configuration

The user should be able to choose: "How much time do you have?"

Options:

- 10 minutes
- 20 minutes
- 30 minutes
- 45 minutes
- 60 minutes
- 90 minutes
- 2 hours
- Custom

The user may say "I have 30 minutes today." or "I have 2 hours today; give me something worth the effort."

The AI should optimize accordingly.

---

## 7. Portion Size

Portion size must be configurable.

- **Small:** Smaller meal portions.
- **Normal:** Standard portion.
- **Large:** More food per meal.
- **Extra Large:** For particularly hungry/high-activity days.

Or allow: "I need 5 large portions."

The app should recalculate automatically:

- Ingredients
- Calories
- Protein
- Cost
- Cooking quantity

---

## 8. Meal-Prep Quantity

The user should be able to say:

- "Make 7 portions."
- "I need lunch for Monday-Friday."
- "Make 10 servings and freeze half."

The app should automatically scale recipes.

It should account for practical package sizes.

Example: Recipe requires 1.7 lb chicken. If the grocery package contains 2 lb:

> "You have 2 lb. Use the entire package and adjust the recipe."

---

## 9. Recipe Editing

Every generated recipe must be editable.

The user should be able to change:

- Ingredient
- Quantity
- Seasoning
- Protein
- Vegetable
- Carb
- Sauce
- Cooking method
- Portion size

Example: "Replace broccoli."

The app should respond with alternatives based on:

- What is already available
- Price
- Nutrition
- Cooking compatibility

Example:

Replace broccoli with:

1. **Cauliflower** - Similar preparation, slightly cheaper
2. **Cabbage** - Much cheaper, lower cooking complexity
3. **Frozen mixed vegetables** - Already in freezer, lowest additional cost

---

## 10. Ingredient Substitution Engine

The app should understand substitutions intelligently.

Instead of simply searching a static substitution table, it should consider:

- **Nutritional equivalence:** If replacing a protein, preserve protein where possible.
- **Cooking compatibility:** An ingredient going into an air fryer should have an appropriate replacement.
- **Available inventory:** Prefer ingredients already owned.
- **Price:** Prefer cheaper alternatives when budget mode is enabled.
- **User preference:** Avoid ingredients the user dislikes.

Example: "I don't have Greek yogurt."

The app might suggest:

- Regular yogurt
- Cottage cheese
- Milk + another thickener
- Other suitable ingredient depending on the recipe

and explain how the quantities/cooking process change.

---

## 11. Cooking Instructions

Every recipe must include actual cooking instructions.

Not merely "Cook chicken."

Instead:

**Preparation**

1. Cut chicken into appropriate pieces.
2. Add yogurt and spices.
3. Mix thoroughly.
4. Marinate for X hours if desired.

**Oven**

- Temperature
- Rack position if relevant
- Approximate cooking time
- When to check
- Safe internal temperature where relevant

**Air Fryer**

- Temperature
- Approximate time
- When to shake/flip
- Batch considerations

**Rice**

- Water ratio
- Cooking method
- Resting time

**Portioning**

- Approximate amount per container

**Storage**

- Refrigerator/freezer recommendation

**Reheating**

- Microwave instructions

The app should prioritize practical instructions over recipe-blog-style writing.

---

## 12. Grocery Recommendations

The app should generate the next grocery list, not merely a shopping list for the current recipes.

It should look at:

- Current inventory
- Upcoming meal plan
- Expiring ingredients
- Historical consumption
- User preferences
- Budget
- Nutrition priorities
- Seasonal availability
- Previous grocery prices

Then recommend what to buy.

---

## 13. Grocery List Modes

The user should be able to select:

### CHEAPEST

Optimize for minimum grocery cost.

Use:

- Sale items
- Cheap vegetables
- Pantry staples
- Bulk ingredients where economical
- Existing inventory

### HEALTHIER

Prioritize:

- Vegetables
- Fiber
- Protein
- Nutrient density
- Balanced meals

while remaining within the user's calorie target.

### SEASONAL

Prioritize ingredients that are:

- In season
- Typically more available
- Potentially cheaper
- Appropriate for the current season/location

The system should clearly distinguish actual current pricing from general seasonal assumptions.

### BALANCED

Balance:

- Price
- Nutrition
- Variety
- Convenience

---

## 14. Grocery Recommendation Engine

The app should be able to say:

- "You have enough chicken for this week, so don't buy more."
- "Cabbage is unusually cheap compared with your previous purchases. Consider buying one."
- "You already have three vegetables. Buying another vegetable would add variety but isn't necessary."

Eventually:

- "Chicken thighs are currently cheaper per gram of protein than chicken breast, and you already have the equipment needed to cook them."

This is where the app becomes a genuine grocery optimizer.

---

## 15. Price Tracking

The app should optionally remember grocery prices.

Example:

| Item | Chicken thighs |
|---|---|
| Current | $1.99/lb |
| Your historical average | $2.69/lb |
| Status | GOOD DEAL |

The user can manually enter prices initially.

Future versions can potentially support:

- Grocery APIs
- Store APIs
- Receipt scanning
- OCR
- Online grocery data

These should be optional integrations rather than MVP requirements.

---

## 16. Seasonal Recommendations

The app should know the user's general location/region when the user chooses to provide it.

For example: Boston / New England

Then seasonal recommendations can be incorporated.

However, the system should distinguish seasonal availability from actual store price.

A seasonal ingredient is not automatically cheaper.

The app should say "Seasonal in your region" rather than falsely claiming "Cheapest" unless actual price data supports that conclusion.

---

## 17. Favorites

Every recipe should have a ❤️ Favorite button.

Favoriting a recipe means: "I want this to be considered more often in future plans."

Favorites should be stored persistently.

Example favorites:

- Spicy Yogurt Chicken Bowl ❤️
- Chicken Tomato Rice ❤️
- Air Fryer Chicken + Potatoes ❤️
- Protein Chocolate Pudding ❤️

The AI should preferentially reuse favorites when they fit the current constraints.

---

## 18. Likes / Ratings

After eating a meal, the user should be able to rate it.

Examples: ⭐ 1-5 stars, or simply:

- 👍 Like
- 😐 Neutral
- 👎 Dislike

Optional feedback:

- "Too spicy."
- "Too dry."
- "Loved the sauce."
- "Good but too much cabbage."

This feedback should influence future recipe generation.

---

## 19. Personal Preference Learning

The system should gradually learn:

- Favorite proteins
- Favorite vegetables
- Favorite spices
- Favorite cuisines
- Preferred portion sizes
- Preferred cooking methods
- Typical cooking time
- Foods disliked
- Recipes frequently repeated
- Recipes never finished
- Recipes rated highly
- Budget patterns

Example: After several weeks the AI may infer "You consistently rate yogurt-marinated chicken highly." and "You tend to dislike recipes where cabbage is the dominant ingredient."

The system should use these patterns when generating future plans.

---

## 20. Retraining / Learning Pipeline

The app should have a structured feedback pipeline.

Important distinction: **Do NOT blindly retrain the AI model after every meal.**

Instead, initially use a personal preference/profile layer.

Every interaction generates structured feedback:

```json
{
  "recipe_id": "chicken_yogurt_001",
  "rating": 5,
  "liked": true,
  "difficulty": "easy",
  "actual_cooking_time": 34,
  "portion_size": "large",
  "comments": "Loved it, maybe less spicy next time"
}
```

The system can update the user's preference profile.

Example:

| Preference | Value |
|---|---|
| Protein preference | Chicken +++ |
| Spice | Medium-high |
| Cooking complexity | Low-medium |
| Favorite vegetables | Broccoli, Potatoes, Spinach |
| Disliked | Very plain meals |

---

## 21. Future ML/Retraining Pipeline

Once enough personal data exists, build a separate learning pipeline.

Potential inputs:

- Recipe
- Ingredients
- Price
- Nutrition
- Cooking time
- Complexity
- User rating
- Whether recipe was repeated
- Whether ingredients were wasted
- Actual cost
- Actual preparation time

Potential output: Probability user will like this recipe.

The model could eventually rank candidate recipes based on:

```
Preference Score
+ Nutrition Score
+ Budget Score
+ Inventory Utilization
+ Time Score
+ Food-Waste Score
```

The LLM can generate candidate recipes while a separate ranking system learns which candidates are most likely to work for the user.

This is preferable to continually fine-tuning an LLM.

---

## 22. Personal Learning Loop

The overall system becomes:

```
Generate meal plan
        ↓
Cook
        ↓
Rate meal
        ↓
Record actual cost/time
        ↓
Record substitutions
        ↓
Record leftovers/waste
        ↓
Update personal preference profile
        ↓
Improve future ranking
        ↓
Generate better next meal plan
```

This creates a genuine feedback loop.

---

## 23. Recipe Versioning

If the user edits a recipe, save the modification.

Example: Original is "Spicy Yogurt Chicken". User changes:

- 1 tbsp chili → ½ tbsp chili
- Broccoli → cabbage
- 300 g rice → 250 g rice

The app should remember the user's version of this recipe.

Next time it should suggest the personalized version rather than the original.

---

## 24. "Cook Again" Feature

After completing a recipe, **Cook Again** should regenerate the recipe using:

- Current inventory
- Current prices
- Current calorie target
- Current nutrition priority
- User's previous modifications

This is different from simply opening the old recipe.

---

## 25. Weekly Planning

The main weekly planning screen should look something like:

```
WEEK OF OCT 12
Calories:              12,600 kcal
Planned:               12,420 kcal
Nutrition focus:       HIGH PROTEIN
Budget:                $42
Estimated grocery cost: $38.70
Cooking time:          ~3.5 hours total
Meals:                 21
Protein:               ~X g/day
```

Then:

```
MON
  Breakfast
  Lunch ❤️
  Dinner
TUE
  Breakfast
  Lunch
  Dinner
...
```

---

## 26. Daily Adjustment

The user should be able to override the weekly plan.

Example: "Today I only have 20 minutes."

The app should regenerate today's dinner without destroying the rest of the weekly plan.

Or: "Today I want a fancy meal."

The app adjusts only today's meal.

---

## 27. Dynamic Calorie Rebalancing

If I eat something outside the plan, e.g. "I had a 400 calorie dessert.", the app should be able to recalculate the remaining day/week.

Example:

| | |
|---|---|
| Daily target | 1,800 kcal |
| Already consumed | 1,050 kcal |
| Remaining | 750 kcal |

Then: "You have approximately 750 kcal left today."

It can suggest dinner within that amount.

Similarly, if I eat fewer calories one day, the weekly planning system can account for it without unnecessarily forcing exact daily equality.

---

## 28. Flexible Weekly Calories

The app should support both:

- **Strict daily target:** 1,800 kcal every day.
- **Weekly target:** 12,600 kcal/week.

This matters because real life isn't perfectly consistent.

For example: Monday 1,700, Tuesday 1,850, Wednesday 1,750, ...

The user can choose whether the app should enforce a hard daily ceiling or optimize primarily against the weekly budget.

---

## 29. Protein Dessert Integration

Protein desserts should be first-class meals/snacks.

Examples:

- Protein pudding
- Chocolate protein pudding
- Mocha protein dessert
- Yogurt protein mousse
- Frozen protein dessert

The weekly planner can reserve calories for them.

Example:

| Slot | kcal |
|---|---|
| Daily calories | 1,800 |
| Breakfast | 350 |
| Lunch | 500 |
| Dinner | 650 |
| Protein dessert | 200 |
| Snack | 100 |

The user should not have to manually squeeze dessert into the plan.

---

## 30. Meal Categories

The app should understand:

- Breakfast
- Lunch
- Dinner
- Snack
- Protein dessert
- Drink

This allows different calorie allocations.

---

## 31. AI Prompting Architecture

Do not put all logic inside one giant prompt.

Separate:

**Deterministic logic** - use code for:

- Unit conversions
- Recipe scaling
- Calorie totals
- Protein totals
- Cost calculations
- Inventory subtraction
- Portion calculations
- Weekly totals
- Budget calculations

**AI reasoning** - use the LLM for:

- Recipe generation
- Ingredient substitution
- Cooking instructions
- Flavor combinations
- Meal-plan reasoning
- Natural-language inventory parsing
- Explaining recommendations
- Generating alternatives

This keeps the application reliable.

---

## 32. Constraint Engine

Before asking the LLM to generate the final plan, construct a structured constraint object.

Example:

```json
{
  "daily_calorie_limit": 1800,
  "weekly_calorie_limit": 12600,
  "nutrition_priority": "protein",
  "secondary_priority": "iron",
  "budget_priority": "high",
  "days": 7,
  "meals_per_day": 3,
  "portion_size": "large",
  "cooking_time": "30-60_minutes",
  "recipe_mood": "medium",
  "equipment": [
    "oven",
    "air_fryer",
    "microwave"
  ]
}
```

The LLM then generates a plan within these constraints.

The application code validates the result afterward.

---

## 33. Validation Layer

AI-generated recipes should be validated programmatically.

Check:

- Daily calories ≤ configured limit
- Weekly calories ≤ configured limit when applicable
- Ingredient quantities are valid
- Ingredients exist or appear on shopping list
- Portions match requested quantity
- Equipment is available
- Cooking time fits selected constraint
- Cost is within budget when possible

If the generated plan violates constraints, automatically ask the AI to revise it.

This is important.

Do not simply trust the LLM's arithmetic.

---

## 34. Mobile-First PWA

The application should be designed primarily for mobile.

It should work well on:

- iPhone
- iPad
- Windows laptop
- Desktop browser

The iPhone experience is particularly important because grocery shopping happens on the phone.

The user should be able to install it to the iPhone Home Screen as a PWA.

Important mobile features:

- Large buttons
- Fast ingredient entry
- Minimal typing
- Quick-add grocery items
- Swipe between meals
- Easy recipe editing
- Grocery-list checklist
- Offline access to saved recipes/inventory where possible

---

## 35. Grocery Store Mode

When shopping:

```
+ Add Grocery
Chicken thighs   [ $1.99 / lb ]
Cabbage          [ $0.79 / head ]
Potatoes         [ $2.99 / 5 lb ]
Broccoli         [ $1.49 / lb ]
```

Then: **Optimize My Cart**

The app can estimate:

- Cheapest combination
- Nutritional value
- Meals generated
- Number of servings
- Cost per serving

---

## 36. Final Product Vision

The system should eventually behave like a personal food operating system:

```
               GROCERY PRICES
                     ↓
              CURRENT INVENTORY
                     ↓
             CALORIE TARGETS
                     ↓
          NUTRITION PRIORITIES
                     ↓
          BUDGET / SEASON / DEALS
                     ↓
            COOKING EQUIPMENT
                     ↓
              TIME AVAILABLE
                     ↓
              PORTION SIZE
                     ↓
          PERSONAL PREFERENCES
                     ↓
            PREVIOUS FEEDBACK
                     ↓
              AI GENERATION
                     ↓
            CONSTRAINT CHECK
                     ↓
              WEEKLY PLAN
                     ↓
          COOK → RATE → LEARN
                     ↓
           BETTER NEXT PLAN
```

The central objective remains:

> Turn whatever food I can afford and already have into the cheapest, healthiest, highest-protein, lowest-waste and most enjoyable meal plan that fits my available time and equipment.
