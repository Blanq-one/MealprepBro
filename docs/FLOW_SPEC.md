# Mealbro Flow Spec: the cook-first redesign (Phase 2b)

**Status:** **approved 2026-10-10** with four changes, now applied: a shorter onboarding (9 screens, with "Skip, use
my current settings"), a capped protein reward, the Cook home order, and friendly rate-limit waits. All flagged changes
(§16) are approved, and the questions (§18) are answered with the defaults. No code has been written yet; building
starts with step 2b.1.
**Sources:** your redesign brief (2026-10-10), `CLAUDE.md` (wins on conflict), `docs/PRD.md` (new "Primary user flow"
section), `docs/BUILD_PLAN.md` (Phase 2b build steps, §9).

This spec describes every screen of the redesigned app: what is on it, what each tap does, and its loading, empty and
error states. It then maps each screen to the backend that exists today, lists exactly what is new, explains how
single-meal suggestions work without the weekly solver, estimates LLM usage, and flags every earlier decision this
changes.

| § | Contents |
|---|---|
| 1 | The flow at a glance |
| 2 | Rules every screen keeps |
| 3 | Navigation and routes |
| 4 | Look, feel and personality |
| 5 | Shared building blocks (question screens, controls, cards, states) |
| 6 | First-run onboarding |
| 7 | Cook tab |
| 8 | Grocery tab |
| 9 | Pantry tab |
| 10 | Settings tab |
| 11 | Pending UI fixes: where each one lands |
| 12 | Screen → backend map |
| 13 | New backend work (endpoints, models, scoring, data model, prompts, stages, logging) |
| 14 | Single-meal suggestions without the weekly solver |
| 15 | LLM budget: calls, tokens and caching |
| 16 | Changes to earlier decisions (approved) |
| 17 | What moves between phases |
| 18 | Questions (answered) |

---

## 1. The flow at a glance

```
             ┌────────── Cook (opens here) ──────────┐  Grocery          Pantry          Settings
             │                                       │
 Step 1      │  [A meal now]   [Meal prep]           │  What should      inventory       everything from
             │  Same as last time ▸ (skips to 4)     │  I buy? ▸         (unchanged)     onboarding, any
             │  Today from your plan ▸               │  checklist by     + amount        time
             │  Saved: ♥ favorites · 🔖 later        │  store, stock-up, picker
             │                                       │  Done shopping
 Step 1b     │            How much? When?  (prep)    │
 Step 2      │  Goals: protein · carb · cheap ·      │
             │  quick · iron · low cal + mood        │
 Step 3      │  What do you have? (pantry toggles,   │
             │  + have it / could buy)               │
 Step 3b     │            Shopping for this? (prep)  │
             │                │                      │
 Building    │  real stages: pantry → recipes →      │
             │  calories → groceries → checking      │
             │        │                     │        │
 Step 4      │  meal now: ranked cards   meal prep: Today, then days;
             │  (saved first, new ideas  swap any meal; Recipes | Shopping
             │  stream in)                             │
 Step 5      │  Recipe page: Cook this · ♥ · 🔖 · Mark cooked
             └───────────────────────────────────────┘
First launch: onboarding wizard (9 short screens, or "Skip, use my current settings") fills Settings once.
```

Two engines sit behind the Cook tab:

- **A meal now** uses a **ranking** over saved, seed and freshly generated recipes. One meal has nothing to coordinate
  with, so it needs no MILP (§14).
- **Meal prep**, **swap** and **What should I buy?** use the **existing weekly solver**, because those choices are
  coupled: shared packages, fridge windows, cook-day time, calorie limits per day and week, and the budget.

---

## 2. Rules every screen keeps

These are unchanged from `CLAUDE.md` and the build plan. The redesign moves screens around; it changes none of these.

- **Code does all the math.** Every kcal, gram, dollar, portion count, amount option and total on screen comes from
  the API as a number plus a display string. The frontend formats cents and lays things out; it never adds, scales,
  converts or prices (Phase 2 AC 7). Where a screen needs a live total (for example calories per meal adding up to the
  day), it asks the API (`POST /settings/preview`, §13.1).
- **The LLM writes only creative text** (recipe ideas, steps, names). It never produces a number that is shown or
  used. Generated recipes go through the existing recipe validator, prose filter (§7.3 of the build plan), food-safety
  injection and code-computed nutrition before anyone sees them.
- **Diet rules hold in every flow:** beef and beef-derived items are excluded; possibly-beef items stay held until
  you allow them; pork components are capped (default 1 meal a week) and never favored by nutrition, price or pantry
  scoring; trace pork is unlimited.
- **Cost words:** "cheap", "cheapest" and "deal" appear only in labels code produces from stored price data. The
  "Cheap" goal tile is your input, not a claim. Prices that are estimates carry "est.".
- **Nutrition wording:** nutrient content only ("high in iron"), never effects. Iron shows heme and non-heme
  separately, with heme marked "estimated".

---

## 3. Navigation and routes

A bottom bar with four tabs, always visible except inside a question flow (which shows a back arrow and progress dots
instead) and in cooking mode.

| Tab | Icon | Route | Opens on |
|---|---|---|---|
| **Cook** (default) | 🍳 | `/cook/` | Cook home (Step 1) |
| **Grocery** | 🛒 | `/grocery/` | Current list, with "What should I buy?" on top |
| **Pantry** | 🥫 | `/pantry/` | Inventory by location |
| **Settings** | ⚙️ | `/settings/` | Grouped settings list |

The static export keeps one page per screen with query parameters (Phase 2 D36). Each question step is part of the URL,
so the back arrow and the browser's back gesture both work:

| Route | Screen |
|---|---|
| `/welcome/?step=household` … `?step=done` | Onboarding W0–W8 (§6) |
| `/cook/` | C0 Cook home |
| `/cook/ask/?mode=now&step=goals` · `step=have` | Meal-now questions |
| `/cook/ask/?mode=prep&step=amount` · `when` · `goals` · `have` · `shop` | Meal-prep questions |
| `/cook/results/?search=<id>` | C5 ranked results (meal now) |
| `/cook/plan/?id=<plan id>` | C6 meal-prep results (also the "current plan" view) |
| `/cook/saved/?list=favorites` · `list=later` | C7 Saved lists |
| `/recipe/?version=<id>&search=<id>` · `?batch=<id>` · `?version=<id>` | C8 Recipe page (search, plan batch, or saved context) |
| `/grocery/advice/?step=goals` · `step=budget` · `?plan=<id>` | G1–G3 What should I buy? |
| `/pantry/` | P0 Pantry |
| `/settings/` · `/settings/edit/?field=<name>` | S0 list · S1 editor |
| `/login/` | Login (unchanged) |

The old `/plan/`, `/day/` and `/inventory/` routes redirect to `/cook/plan/` and `/pantry/` so bookmarks and the
offline shell keep working.

Answers in progress live in a client draft (session storage) until the search is sent; the server keeps the sent
answers as your **last answers** (§13.4, `cook_search`), which pre-fill the next run.

---

## 4. Look, feel and personality

### 4.1 Personality: Pottle

The app keeps the name **Mealbro**. Its character is **Pottle**, a small round clay pot: a terracotta body, a cream
lid with a round knob, two dot eyes and a small smile. Pottle is drawn as a simple inline SVG (a few shapes, no image
generation, no photos). The steam above the lid shows what Pottle is doing:

| State | Steam | Used on |
|---|---|---|
| Idle | one lazy curl | Next to the Cook home greeting (32 px), onboarding welcome |
| Working | three curls rising (static when "reduce motion" is on) | Building screen |
| Happy | the curl forms a small heart | Right after you favorite something; "All set" |
| Sleepy | lid tilted, a "z" curl | Offline banner |
| Oops | lid askew, one surprised curl | Error screens |

Pottle appears on a handful of screens only (welcome, building, empty and error states, the Cook home greeting), never
on every card. It is original: no existing app's mascot, colors or wording.

**Voice:** a calm friend who is good in the kitchen and keeps it simple. Short sentences, plain words, second person,
a little warmth, sometimes light humor. Never guilt, never health claims, never a cost word that code didn't earn,
never a number that didn't come from the API.

| Moment | Pottle says | Never |
|---|---|---|
| Why a question is asked | "I'll scale every recipe to match." | "This helps us optimize your experience." |
| Building | "Balancing calories across the days…" | "Crunching the perfect healthy plan!" |
| Per-minute rate limit | "The recipe service needs a short breather. Writing your ideas in 0:23…" | "Error 429: rate limited." |
| Empty saved list | "Nothing saved yet. Tap ♥ on a recipe you'd make again." | — |
| LLM unavailable (not a rate-limit wait) | "I couldn't write new ideas just now. Here are your saved ones." | "Something went wrong." |
| Nothing fits | "Nothing fits 20 minutes with what you have. Allow 30 minutes, or let me write something new?" | "No results." |
| Over a target | "This one is about 120 kcal over your usual dinner." | "Careful, that's a lot!" |
| Offline | "You're offline. Your plan and saved recipes still open." | — |

All of this copy is code templates. LLM text appears only in recipe titles, descriptions and steps (prose-filtered).

### 4.2 Color

Light is the default; dark is a choice in Settings → Appearance (Light / Dark / Match my phone), stored per device.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#FFF8F1` cream | `#1C1714` | page |
| `--surface` | `#FFFFFF` | `#26201C` | cards |
| `--surface-2` | `#FBEFE3` | `#312923` | tiles, inputs, sections |
| `--text` | `#2A211C` | `#F6EDE4` | body text |
| `--muted` | `#6B5E55` | `#BBA99A` | why lines, secondary |
| `--border` | `#EBDDD0` | `#3D332C` | hairlines |
| `--accent` | `#B5482F` terracotta | `#F08A68` | primary buttons, selected tiles |
| `--accent-text` | `#FFFFFF` | `#2A140C` | text on accent |
| `--accent-soft` | `#FBE3D9` | `#4A2A1F` | selected backgrounds, chips |
| `--herb` | `#3F7D58` | `#7CC79A` | "you have it", success |
| `--honey` | `#E9A93B` | `#F2C063` | highlights only (never text on light) |
| `--danger`, `--safety`, `--warn` | kept from Phase 2 | kept | errors, food-safety lines, warnings |

White text on `--accent` is about 5.3:1 in light mode, so it meets WCAG AA for normal text.

### 4.3 Type, spacing and shape

- **Font:** `ui-rounded, "SF Pro Rounded", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`. iPhone gets
  the system rounded face; no web font to download or cache offline, and no new dependency.
- **Sizes:** body 18 px / 1.5, small 15 px, labels 16 px semibold, h1 30 px bold, h2 23 px, stepper value 40 px with
  tabular numbers. Sizes are in rem, so iOS text-size settings scale them.
- **Spacing:** 8-point grid, 16 px side gutters, 24 px between sections.
- **Shape:** cards 20 px radius, tiles 18 px, buttons 16 px, chips fully rounded. Soft shadow on cards in light mode,
  a border in dark mode.
- **Tap targets:** at least 48 px; the primary bottom button is 56 px tall and full width above the safe area.
- **Motion:** 150–250 ms fades and slides; nothing essential is animated; "reduce motion" turns it all off.

### 4.4 Dish-category icons

No food photos. Each recipe gets one category, chosen by a deterministic code classifier
(`domain/dish_category.py`, §13.3) from its meal slots, title words, ingredient roles and equipment. First match wins.

| Category | Icon | Rule (first match) |
|---|---|---|
| drink | 🥤 | drink slot, or smoothie / shake / latte |
| dessert | 🍮 | protein-dessert slot, or pudding / mousse / cake / brownie / cookie |
| oats | 🥣 | oats / oatmeal / porridge / granola, or oats are the main carb |
| eggs | 🍳 | omelet / frittata / scramble, or egg is the protein in a breakfast |
| wrap | 🌯 | wrap / burrito / taco / quesadilla, or a tortilla line |
| sandwich | 🥪 | sandwich / toast, or bread is the main carb |
| soup | 🍲 | soup / stew / chili |
| curry | 🍛 | curry / masala / gravy / dal / korma |
| pasta | 🍝 | pasta / noodle / spaghetti / ramen |
| salad | 🥗 | salad, or no-cook with mostly vegetables |
| bowl | 🍚 | bowl, or rice is the main carb |
| roast | 🍗 | sheet pan / roast / baked / air-fried protein |
| snack | 🥜 | snack slot |
| other | 🍽️ | fallback |

Goal tiles, meal tiles and mode cards use emoji too (§7). Equipment tiles use small in-house line icons, because emoji
don't cover ovens or air fryers well. Every icon has a text label; emoji carry `aria-label`s.

---

## 5. Shared building blocks

### 5.1 The question screen

Every question in onboarding, the Cook flow, Settings editors and "What should I buy?" uses one layout:

```
┌──────────────────────────────────┐
│ ←          ● ● ○ ○ ○        Skip │  back arrow (44 px) · progress dots · Skip only if optional
│                                  │
│ How many people are you          │  the question (h1)
│ cooking for?                     │
│ I'll scale every recipe to match.│  the why line (muted, one sentence)
│                                  │
│        (−)     1     (+)         │  one large control
│               person             │
│                                  │
│ ┌──────────────────────────────┐ │
│ │           Continue           │ │  fixed bottom button, 56 px, above the safe area
│ └──────────────────────────────┘ │
└──────────────────────────────────┘
```

- **Continue** is disabled until the answer is valid; the reason shows under the control. In Settings the button
  says **Save**; on the last Cook question it names the action ("Find recipes", "Build my plan").
- **Back** keeps the answers already given. **Skip** appears only on optional questions and keeps the pre-filled
  value.
- Every control starts **pre-filled**: from your last answers in the Cook flow, otherwise from Settings.
- **Onboarding is the one exception:** to keep the wizard to 9 screens, some of its screens pair two closely
  related questions, each with its own large control (for example calories and protein). Settings editors still show
  one field at a time.

### 5.2 Controls

| Control | Looks like | Behavior |
|---|---|---|
| **Stepper** | 64 px round − and + around a 40 px value and its unit | Tap steps by the field's increment; press and hold repeats; tap the value to type it (numeric keypad). Bounds come from the API's validation (e.g. calories 800–6,000 in steps of 50). |
| **Slider** | 32 px thumb, value above it, "No limit" at the right end | Budget only: $0–$200 in $5 steps; sliding to the end means no budget. |
| **Tile grid** | 2 columns of 96 px tiles: icon + label | Multi- or single-select per question. Selected = accent fill, check badge, `aria-pressed="true"`. A limit (e.g. two nutrition goals) is explained when you hit it. |
| **Segmented control** | 2–5 equal buttons in a pill | **Fixed selected state** (pending fix): the chosen segment is accent-filled with a check, bold, and announced as selected. |
| **Chips** | 40 px rounded labels, ✕ to remove | Pantry extras, suggestions, filters. |
| **Toggle row** | label, badges, switch on the right | Pantry items in "What do you have?". |
| **Bottom sheet** | slides up, grabber, one task | Amount picker, people/slot picker, confirmations. |

### 5.3 The recipe card

Used by meal-now results, Saved lists, meal-prep "Recipes" view and grocery-advice meals. Every number and every
line is a display string from the API.

```
┌───────────────────────────────────────────┐
│ 🍛  Everyday chicken curry       ♥   🔖   │  icon · title · favorite · save for later
│     Favorite · Draft                      │  badges: Favorite, Saved, New, Draft
│ 540 kcal · 41 g protein · 35 min · $2.10  │  per portion (time = total; hands-on on the page)
│ Uses: chicken thigh, spinach, onion       │  your items (pantry or "have it")
│ Could buy: chickpeas $1.29 (Stop & Shop)  │  your "could buy" items, whole-package cost
│ Missing: lemon → lime juice (you have it) │  missing items with a code-suggested substitute
│ Uses 3 of your items · ready in 35 min    │  "why" chips from the score components
└───────────────────────────────────────────┘
```

- The numbers row follows your goals: with **Iron rich** on it adds "4.1 mg iron (1.6 mg heme, est.)"; with **High
  carb** it adds carbs.
- A missing item with no substitute shows its price ("Missing: lemon · buy $0.79"), or "no price yet".
- Numbers are for the recipe as written. A substitute line says so on the recipe page.
- ♥ and 🔖 toggle in place (optimistic, queued offline, §13.1 E7–E8).

### 5.4 Building steps

A vertical list of real stages from the stream (§13.6), each with a state:

```
✓ Checking your pantry
✓ Finding recipes
◌ Balancing calories across the days…      ← current, with Pottle working
○ Pricing your groceries
○ Double-checking every number
  The recipe service needs a short breather. Back in 0:23   ← only during a rate-limit wait (live countdown)
                                             0:41 elapsed
```

The list only advances when the server reports a stage. A rate-limit wait is a normal step, not an error: the
countdown comes from the server's `wait_s` (§13.2), and work resumes by itself when it reaches zero. A re-solve after rounding moves the marker back to "Balancing
calories" with "Adjusting after rounding". **Stop watching** returns to the previous screen; the run still finishes on
the server, and its result appears under "Same as last time".

### 5.5 Loading, empty, error, offline

| State | Pattern |
|---|---|
| **Loading** | Skeleton cards in the final layout; never a bare spinner. Longer work uses Building steps (5.4). |
| **Empty** | Pottle (idle), one sentence, one action button. |
| **Error** | Pottle (oops), the problem's title in plain words, one sentence of detail, **Try again**, and a "Details" expander with the server's problem text and run id. |
| **Offline** | A slim banner ("You're offline · showing what was saved at 3:42 pm"). Cached screens open read-only. Check-offs, price entries, ♥ and 🔖 are queued and replayed once (existing queue, `client_ref`). Anything that needs the server (searching, planning, swapping, saving settings) is disabled with "Needs a connection". |
| **Session expired** | Goes to Login, then back to the same step with the answers kept. |
| **Rate-limit wait** | Never an error. When an LLM call would go over Groq's per-minute limit (a 429 reply, or the pacer predicting one from the rate-limit headers, e.g. More ideas tapped twice quickly), Pottle shows the working state with "The recipe service needs a short breather" and a countdown from `wait_s`. **Short wait** (fits within `LLM_MAX_RATE_WAIT_SECONDS`, 60 s, and the request's time budget): the request waits and carries on by itself. **Longer wait:** the request ends gracefully with what it has and a `retry_after_s`. The button that asked for it shows "Ready in 0:45", counting down, and turns back into a normal button at zero; one tap continues. Only the daily token guard shows a different message: "That's today's new-idea allowance; back tomorrow." Your saved results stay on screen throughout. |

---

## 6. First-run onboarding

**When:** on launch, if `GET /settings` returns `onboarding_completed: false`. Settings v3 starts with it false for
you too, so the wizard runs once and pre-fills everything from your saved settings (§13.4).

**How it saves:** answers stay in a device draft while you go; **All set** sends one `PUT /settings` (plus
`POST /stores` for a store you added). The wizard never calculates a calorie or protein recommendation; it shows
your saved values.

**Nine screens.** Related questions share a screen, each with its own large control (§5.1). Progress dots count
W1–W7.

| # | Screen | Why line | Controls | Pre-fill | Validation / notes |
|---|---|---|---|---|---|
| W0 | Welcome | "Let's set up your kitchen. It takes about a minute, and you can change anything later in Settings." | **Let's go** · **Skip, use my current settings** (keeps your settings exactly as they are, marks onboarding done, opens Cook home) | — | Pottle idle. Skip is offered because your settings already exist |
| W1 | Who you're cooking for, and your budget | "I'll scale every recipe to match, and start each shopping plan with your budget." | **People:** stepper 1–8. **Weekly grocery budget (optional):** slider, "No limit" at the end | 1 person; your budget or none | Your calorie and protein targets apply to your portion; everyone gets the same size (§16 F5). The budget is a pre-fill only; each plan sets its own limit (§16 F4) |
| W2 | Your daily targets | "Every plan fits your calories and reaches at least your protein. Use the numbers that work for you." | **Calories a day:** stepper, 50 kcal steps, 800–6,000. **Protein:** stepper, 5 g steps, 0–400 (0 shows "No target") | 1,800 kcal · 100 g | — |
| W3 | Meals to plan, and their calories | "I'll only plan these. Each one aims for its calories; anything left over stays free for whatever you like." | **Meal tiles:** breakfast 🥣, lunch 🥪, dinner 🍽️, protein dessert 🍮, snack 🥜, drink 🥤. Under them, **one stepper per chosen meal** (25 kcal steps) and a line from the API: "1,800 of 1,800 kcal a day planned" | Your saved meals and allocations; a newly added meal starts empty and needs a value | At least one meal. Live check via `POST /settings/preview`; can't exceed the daily target |
| W4 | When you cook | "On other days you'll eat what you cooked earlier. Simmering and chilling don't count against your time." | **Weekday tiles** Mon–Sun. **Hands-on minutes:** one stepper (15 min steps, 0–240) for all cook days; "Different each day" opens per-day steppers | Mon, Wed, Thu, Sat, Sun · your saved minutes | At least one cook day |
| W5 | What's in your kitchen? | "I'll only suggest recipes you can make with these." | Equipment tiles: stovetop, oven, air fryer, microwave, rice cooker, pressure cooker, slow cooker, blender, food processor, grill | Saved equipment | At least one |
| W6 | Where do you shop? | "Prices are kept per store, so I can show where something costs less." | Tiles for known stores (names only, no logos) + **Add a store** (typed name); the order you tap = your preference order, shown as 1, 2… | Stop & Shop 1, Price Rite 2 | At least one store. "Other" (powder etc.) stays a background source, never a tile |
| W7 | Your food rules | "These apply everywhere: recipes, plans and grocery lists." | Three cards: **Beef: never** (locked, with "includes broth, tallow, gelatin from beef"); **Pork: up to [stepper 0–7] meals a week** (trace pork such as lard in tortillas is always fine); **Held items** (possibly beef: gelatin, cheese, bouillon cubes, collagen, marshmallows, generic pepperoni and salami), each with an **Allow** toggle | Beef locked; pork 1; all held | An allow writes `ingredient_preference = allow`; beef can't be allowed (422) |
| W8 | All set | "Here's what I'll work with." | Summary rows (each taps back to its screen) + **Start cooking** | — | Saves; Pottle happy; opens Cook home |

**States.** Loading: skeleton on W1 while settings load. Save error on W8: stays on W8, shows the server's message
next to the row it concerns, and keeps the draft. Offline: you can step through, but **Start cooking** says "Needs a
connection to save" until you're back online; Skip needs a connection too, since it records that onboarding is done.
Closing the app mid-way keeps the draft for next launch.

---

## 7. Cook tab

### C0 Cook home (Step 1)

**On screen, top to bottom.** The two choice buttons are the dominant element, at the top. Everything else sits
below them.

1. **The screen title** is a one-line greeting by time of day in the top bar, with a 32 px idle Pottle: "Evening!
   What are we making?" It takes no space of its own above the buttons.
2. **The two dominant buttons:** **A meal now** 🍳 ("One meal, ready to cook") and **Meal prep** 🍱 ("Portions for the
   days ahead"). Each is a large accent card, at least 120 px tall, full width, stacked. Both are fully visible
   without scrolling on a 375 × 667 screen, whatever sits below them.
3. **Same as last time** (up to two compact cards, one per mode, most recent first), for example:
   *Meal prep · 5 lunches from today · High protein, Cheap · Simple · cooking today · shopping, $45 limit*
   *A meal now · Dinner for 1 · Quick (30 min) · + chickpeas (could buy)*
4. **Today** card, if you have a current plan covering today: each of today's meals with its icon, and what to cook
   today ("Cook: Chicken over rice, 5 portions · 35 min hands-on") or "Nothing to cook, eating prepped meals". A plan
   that starts later says "Your plan starts Monday"; one that ended says "Your plan ended Sunday".
5. **Saved:** two short horizontal rows, **♥ Favorites** and **🔖 Saved for later**, with **See all**.

| Tap | Does |
|---|---|
| A meal now | Starts the meal-now questions at C2 Goals, pre-filled from your last meal-now answers |
| Meal prep | Starts at C1 How much, pre-filled from your last meal-prep answers |
| Same as last time | Sends those exact answers again with today's pantry and goes straight to results (instantly if nothing changed, §15.3) |
| Today card | Opens C6 for the current plan, scrolled to today |
| A saved card | Opens C8 for that recipe, scaled to your household |
| See all | C7 Saved lists |

**States.** First ever: just the two choice buttons and a hint under Saved ("Tap ♥ on a recipe to keep it here").
Loading: skeleton. Offline: choice cards and Same as last time are disabled ("Needs a connection"); Today and Saved
open from cache. Error loading home: the choice cards still work; the other sections show "Couldn't load" + retry.

### C1 How much are you prepping? (meal prep)

- **Preset tiles:** "5 lunches", "Lunch + dinner, 5 days", "My usual week" (your planned meals for 7 days),
  "Something else".
- **Something else** shows a segmented choice:
  - **By portions:** a stepper (1–20) and a meal tile (one), for example 6 dinners.
  - **By days:** day chips for the next 14 days and meal tiles (several).
- **Starting:** chips "Today", "Tomorrow", or a date.
- **Extra portions to freeze:** stepper 0–20 (PRD §8, "make 10 and freeze half").
- **Why line:** "I'll scale the recipes to exactly this and plan what goes in the fridge or freezer."
- **Validation:** at least one meal. A meal with no calories set in Settings shows "Dessert has no calories set" and
  a link to that setting.

"By portions" is a shortcut: N portions of one meal means that meal on N consecutive days from the start day. Both
shapes become the same plan request (§13.3).

### C1b When are you cooking? (meal prep)

- **Tiles:** **Today, all at once** (one cook session today) or **On my cook days** (your schedule, e.g. Mon, Wed,
  Thu, Sat, Sun).
- **Today, all at once** shows a minutes stepper, pre-filled from today's schedule, or from your longest cook day if
  today isn't one.
- **Why line:** "Cooked food keeps 3 days in the fridge, so anything past that goes in the freezer."
- Meals beyond the fridge window come from the freezer, so only freezer-friendly recipes can fill them (existing
  planner rule). If none can, the plan says so (C6 states).

### C2 What are you in the mood for? (both modes)

- **Goal tiles (multi-select):** High protein 🍗 · High carb 🍚 · Cheap 🪙 · Quick ⏱️ · Iron rich 🥬 · Low calorie 🪶.
  - At most **two nutrition goals** (high protein, high carb, iron rich). The first you tap is primary, the second
    secondary. A third tap shows "Pick up to two nutrition goals" and swaps out the oldest.
  - **Quick** reveals an inline stepper, "Ready in 30 min" (meal now: total time; meal prep: hands-on per cook day).
- **Mood (segmented, one):** Simple · Medium · Fancy.
- **For (meal now only):** a line "Dinner for 1 ▸". The meal is guessed from the clock (breakfast until 10:30, lunch
  until 15:00, dinner until 21:00, then snack) and the count from your household size. Tapping it opens a sheet with
  meal tiles and a people stepper.
- **Why line:** "Time and mood rule recipes out; the goals change the order."
- No goal selected is fine: your Settings priority applies. Goal mapping: §13.3.

### C3 What do you have? (both modes)

- **Your pantry,** grouped Fridge / Freezer / Pantry. Each item is a toggle row, **on** by default, with its amount and
  badges ("open", "use by Thu"). Turning one off means "not for this search" (saved with your answers, so next time it
  starts off too). Your **Always have** staples sit in one collapsed line ("Always have: rice, oil, salt and 9
  more") and can't be toggled here.
- **Add something:** a search field (typed entry, autocomplete from the ingredient list) and quick-add chips (your
  usual items). Each added item gets a segmented **Have it / Could buy**:
  - **Have it** means it's in your kitchen. For meal now no amount is needed (code assumes enough for one recipe);
    for meal prep the amount picker opens (default: one usual package). A **Save to pantry** switch (off by default)
    also adds it to your inventory.
  - **Could buy** means you'd happily pick it up (standing in the store looking at chickpeas). Its price comes from
    your stores.
- **From last time:** your previous extras appear as chips under the list ("chickpeas · could buy"); one tap adds
  them back. They are not pre-selected, because last week's "have it" may be gone.
- **Why line:** "I'll use these first. 'Could buy' items are things you're happy to pick up."
- **Continue** says **Find recipes** (meal now) or **Next** (meal prep, to C3b).

**States.** Empty pantry: "Your pantry is empty. Add what you have, or skip and I'll show what to buy." Continue
still works. Ingredient search with no match: "No match for 'zaatar'. Try another name." Excluded item typed (e.g.
ground beef): "Beef is off your list, so I won't use it." Held item: "Gelatin is held (it may come from beef). Allow it in Settings if it's fine." Offline:
the list shows from cache; Continue is disabled.

### C3b Shopping for this? (meal prep)

- **Tiles:** **Use what I have** (plus your could-buy items) or **Make me a shopping list**.
- **Make me a shopping list** shows the budget slider, pre-filled from your Settings budget (or "No limit"), and the
  note "Long-life items like rice and protein powder are listed separately and don't count toward this."
- **Why line:** "So I know whether to plan around a shop."
- **Continue** says **Build my plan**.

### C4 Building

The Building steps from 5.4.

- **Meal now:** "Checking your pantry" → "Finding recipes". As soon as the first ranked list arrives (normally under
  a second), the app moves to C5 and keeps a compact strip on top while new ideas are written.
- **Meal prep:** the full list (pantry → recipes → calories → groceries → checking), then C6.

### C5 Results: a meal now (Step 4)

- **Header:** "Dinner for 1 · High protein, Quick · Simple" with **Edit** (back to C2, answers kept).
- **Strip while new ideas are written:** "Writing 2 new ideas…". During a rate-limit wait it becomes the friendly
  wait state with a live countdown: "The recipe service needs a short breather. Writing your ideas in 0:23…" (5.5).
  When they land:
  they slide into their ranked places with a **New** badge, and a toast says "2 new ideas added". If generation fails:
  "I couldn't write new ideas just now. These are your saved ones." Nothing else changes.
- **Cards:** the top 12 recipe cards in rank order (5.3); **Show more** loads the rest.
- **More ideas** at the bottom asks for one more generation call.
  - While a call is running it reads "Writing…" and ignores further taps.
  - Tapped again before Groq's per-minute allowance has room, it never errors: a short wait runs inside the request
    with the countdown strip; a longer one shows "Ready in 0:45" on the button, counting down to a normal button.
  - When the daily guard is used up it says "That's today's new-idea allowance; back tomorrow."

| Tap | Does |
|---|---|
| A card | C8 recipe page in this search's context (same portions, same pantry coverage) |
| ♥ / 🔖 on a card | Toggles favorite / save for later in place (E7, E8) |
| Edit | Back to C2 with the answers kept |
| More ideas | Same answers, `more_ideas: true`: one LLM call, results merged in |

**States.**
- **Loading:** skeleton cards.
- **Empty** (nothing passes time, mood and equipment): Pottle: "Nothing fits 20 minutes and Fancy with your
  equipment." Buttons come from the filter that removed the most recipes: "Allow 30 min", "Try Medium", "Write new
  recipes".
- **Stream error** after some results: keep them, show "Lost the connection; these may be incomplete" with **Try
  again**.
- **Error before any results:** error pattern (5.5).

### C6 Results: meal prep (Step 4), also the current-plan view

- **Header:** "5 lunches · Wed 14 – Sun 18 · High protein · Simple", then a totals line from the API:
  "Groceries $24.10 + $62.50 stock-up" (pending fix: always shown separately) and "35 min hands-on today".
- **Segmented toggle:** **Recipes | Shopping list**.
- **Recipes view** (default):
  - **Cook sessions** at the top: "Today: Chicken over rice, 5 portions (3 fridge, 2 freezer) · 35 min hands-on ·
    about 50 min start to finish" with a recipe card.
  - **Days, Today first,** then the following days. Days before today fold into "Earlier in this plan".
  - **Day header:** "Today · Wed 14" + "1,780 kcal · 112 g protein · $8.40" (the cost of the food eaten that day).
  - **Day note:** "Cook: Chicken over rice (5 portions)" on a cook day, or "Nothing to cook, eating prepped meals"
    (pending fix; replaces "Cook day · 0 min hands-on").
  - **Meal row:** icon · meal label · name · "520 kcal · 38 g protein" · badges ("from the freezer: thaw Fri night",
    "Draft") · **⇄ Swap** (44 px).
- **Shopping list view:** the plan's grocery list exactly as on the Grocery tab (store groups, stock-up section,
  "check you have", unpriced), read-only here, with **Open in Grocery** to check things off.
- **Bottom bar:** **Use this plan** on a draft, "This is your current plan ✓" on the active one.

| Tap | Does |
|---|---|
| A meal row | C8 for that meal's batch |
| ⇄ Swap | Replaces only this meal (E5). The row shows "Finding another lunch…", then the new meal, highlighted. A toast says "Swapped. Also changed: Monday's batch 5 → 4 portions. **Undo**". Each further swap of the same meal skips the ones you already swapped away. |
| Undo | Restores the plan as it was before the swap (re-accepts the previous version) |
| Use this plan | Accepts the plan (E6). If it overlaps your current plan, a sheet asks "Replace your current plan (Mon 12 – Sun 18, 21 meals)?" first |
| Recipes / Shopping list | Switches the view; the choice is remembered per device |

**Swap outcomes.**
- **No other recipe fits** that meal's calories, time and the rest of the plan: a sheet says "No other lunch fits
  Wednesday's calories and cook time" and offers **Write a new one** (one LLM call) or **Keep this one**. If that
  call has to wait for the per-minute limit, the sheet shows the countdown wait state (5.5) instead of an error.
- **After "Done shopping":** the swap plans from your pantry only. If it would need buying something, it says what
  and offers **Allow buying**, which adds those items to your list.
- **A meal from a batch you already cooked:** the freed portion stays yours: "Extra portion of Curry: eat it another
  day or freeze it." Leftovers aren't tracked as inventory until Phase 3 (prepared portions, §18 Q3).

**States.**
- **Loading:** skeleton days.
- **Infeasible:** Pottle oops plus one to three plain-language reasons from the solver diagnostics, each with a fix
  button: calories → "Change calories", time → "Allow 45 min", budget → "Raise to $55 (the cheapest plan that fits
  costs $52.60)", no recipes for a meal → "Write new recipes", held items → "Review held items".
- **Failed** (LLM or validation): error pattern with retry; recipes written before the failure stay saved.
- **Offline:** the cached plan opens read-only; Swap and Use this plan are disabled.

### C7 Saved lists

- **Segmented:** **♥ Favorites** | **🔖 Saved for later**.
- **Cards:** recipe cards (5.3), with pantry coverage computed against your current pantry, sorted by most recently
  saved.
- **Favorites** mean "suggest this more often": they get a ranking boost in meal-now results and the solver's
  favorite bonus in plans, whenever they fit your constraints. **Saved for later** is a plain bookmark with no effect
  on ranking.
- Tapping ♥ or 🔖 on a card removes it from this list with **Undo**; a card can be in both lists.
- **Empty:** "Nothing saved yet. Tap ♥ on a recipe you'd make again" / "Tap 🔖 on anything you want to try later."

### C8 Recipe page (Step 5)

The existing recipe view, with these additions:

- **Header:** dish icon, title, badges, the numbers row (5.3), then the portions line from the API: "1 portion" /
  "for 2 people" / "5 portions: 3 fridge, 2 freezer".
- **Before you start** box:
  - meal now: could-buy and missing items, with prices and substitutes;
  - plan batch: the existing package notes and freeze notes.
- **Ingredients** in practical quantities. A missing line shows "Don't have lemon? Bottled lime juice works (you have
  it): 2 tbsp" (code-computed amount) and "Numbers are for the recipe as written."
- **Steps** by section, with injected safety lines; then storage and reheating text, per-portion nutrition, heme iron
  "estimated", and cost per portion (all existing).
- **Sticky action bar:** **Cook this** (primary) · ♥ · 🔖. For a plan batch, **Mark cooked** replaces Cook this once
  you're in cooking mode or the batch's day has come.

| Tap | Does |
|---|---|
| Cook this (meal now or saved) | Saves this meal as a one-meal plan for today (E3), so inventory deduction, open packages and history work as for planned batches; then opens **cooking mode**. If you have could-buy or missing items, a **Buy first** checklist comes first (check-off and Done use the existing grocery endpoints). |
| Cook this (plan batch) | Opens cooking mode for that batch |
| Cooking mode | Large one-step-at-a-time view, back/next buttons, safety lines highlighted, the screen kept awake (browser Wake Lock), **Mark cooked** at the end |
| Mark cooked | Existing endpoint: deducts inventory FIFO (open packages first), records open-package remainders, and shows what was taken and any shortfall |
| ♥ / 🔖 | Toggle (E7, E8) |

**States.** Loading: skeleton. Not found: "This recipe isn't available anymore." Offline: cached recipe opens; Cook
this and Mark cooked are disabled. Mark cooked twice: "Already marked cooked on Wed 14" (the existing 409).

---

## 8. Grocery tab

### G0 Grocery home

- **What should I buy?** card at the top (Pottle small): "Tell me your goals and I'll do the math."
- **Current list** (from your current plan), the Phase 2 checklist unchanged:
  - **Header:** "This trip: $52.91 groceries + $90.43 stock-up" (pending fix), the store-split note ("Price Rite
    saves you $5.40 this week") and checked counts.
  - **Body:** group by store / by category (segmented, fixed selected state), the stock-up section, **Check you
    have**, unpriced items, and **Done shopping**.
  - **Check you have** never lists water, never shows "0 g" (a tiny amount shows the name only), and leaves out your
    Always-have staples. Each row has **I always have this**, which adds it to that list.
- **Other open lists:** items for a one-meal plan from Cook this ("For tonight's dinner: chickpeas $1.29"), each with
  check-off and Done.
- **Empty:** "No list yet." + **What should I buy?** + **Plan meal prep**.

### G1–G2 What should I buy? (questions)

- **G1 Filters:** tiles Protein rich · Low calorie · Cheap · Iron rich · High carb · Quick (same mapping as C2, §13.3),
  plus a line "For the next 7 days ▸" (a sheet with a days stepper, 1–14) and mood from Settings.
- **G2 Budget:** slider, pre-filled from Settings, optional ("No limit"); the same stock-up note as C3b.
- **Why lines:** "I'll pick groceries that make real meals with what you already have." / "I'll keep regular
  groceries under this."
- Then the Building steps (pantry → recipes → calories → groceries → checking).

### G3 Suggestions

- **Items** grouped by store, each with amount and packages ("2 lb family pack"), cost, and **one reason line**,
  chosen by code from computed facts in this order:
  1. **A comparison** when the stored prices support it, e.g. "Chicken thighs: cheapest protein per dollar at your
     stores (Price Rite, est. price)". It is produced only when the item is strictly lowest among the protein (or
     carb, or iron-source) options your recipes use and your stores price; otherwise this line is skipped.
  2. **A store split:** "At Price Rite: saves $5.40 this week vs Stop & Shop."
  3. **What it's for:** "For 4 meals: Chicken over rice ×2, Everyday curry ×2."
  4. **Stock-up:** "Stock-up: this plan uses about 8 of the tub's 73 scoops."
- **Totals:** "Groceries $38.70 + $62.50 stock-up", and how many meals and portions this makes.
- **Meals this makes:** an expandable list of the days and meals behind the list.

| Tap | Does |
|---|---|
| Use this list | Accepts the plan behind it (with the overlap question if needed); the list becomes G0's current list |
| See the meals | Opens C6 for that draft plan (swap works there too) |
| Change filters | Back to G1 |

**States.** Budget too low: "The cheapest plan that fits costs $52.60. Raise the budget to $55?" (existing
money-first diagnostics, Phase 1 D22). No prices for an item: listed under "No price yet" and counted as incomplete.
Offline: disabled with "Needs a connection".

There are no "deal" or "seasonal" labels yet. Those need price history and seasonality data (Phase 5).

---

## 9. Pantry tab

### P0 Pantry

The Phase 2 inventory screen, unchanged: items by location, expiring and open-package badges, quick-pick chips,
natural-language quick add with confirm, and edit/discard. Two changes: the quick-pick tap opens P1, and a quick-add
parse that hits the per-minute limit shows the countdown wait state (5.5) instead of an error.

### P1 Amount picker (bottom sheet)

```
Chicken thighs: how much?
[ Full ] [ ¾ ] [ ½ ] [ ¼ ] [ Custom ]
  Full = family pack, 2 lb (907 g)
Custom:  (−)  1.25  (+)  [ lb ▾ ]
Where:   [ Fridge ] [ Freezer ] [ Pantry ]
[              Add               ]
```

- **Default: Full.** The options and their display strings come from the API (`amount_options` on each quick pick):
  "¾ · 1.5 lb (680 g)", "½ · 6 eggs", "¼ head".
- **Custom** uses the item's natural unit (lb, oz, count, head, cup) with sensible steps (0.25 lb, 1 egg, ½ head),
  and the unit chip offers the units the API allows for that item. The server converts the amount.
- **Where** is pre-filled from the item's usual location.
- **States:** adding (spinner on Add), error (message under the control; the sheet stays open), offline (disabled:
  inventory changes aren't in the offline queue).

---

## 10. Settings tab

### S0 Settings list

Grouped rows; each shows its current value and opens an editor (S1). Everything from onboarding is editable here any
time.

| Group | Rows |
|---|---|
| You | People · Calories per day · Protein target · Weekly budget (pre-fill) |
| Meals | Meals to plan · Calories per meal · Calorie mode (strict daily / weekly) and, **in weekly mode only**, "each day within ±150 kcal" (pending fix: hidden in strict mode) · Portion size |
| Cooking | Cook days · Time per cook day · Mood per cook day · Kitchen equipment · Fridge days for leftovers |
| Shopping | Stores and their order · Separate-store trip only if it saves at least $5 |
| Diet | Beef (locked) · Held items · Frequency caps (pork ≤ 1 a week, any other caps) · Excluded and disliked ingredients |
| Kitchen staples | **Always have** (S2) |
| Appearance | Light · Dark · Match my phone |
| Account | Sign out |

### S1 Editor

The same question screen the wizard used for that field, with **Save**. A save error keeps the edit and shows the
server's message under the control.

### S2 Always have

- A searchable list of ingredients with switches, common staples first (salt, pepper, oil, rice, garlic, onion,
  spices…).
- **Why line:** "These always count as in stock: never on a shopping list or 'check you have'."
- Effect: planning treats each as unlimited stock you already own (§13.3).

---

## 11. Pending UI fixes: where each one lands

| Fix | Where | Work |
|---|---|---|
| Obvious selected state on segmented controls | Every segmented control (5.2) | CSS + `aria-pressed`; Vitest checks the attribute |
| Hide "each day within ±" in strict daily mode | S0 Meals row and its editor | Frontend condition on `calorie_mode` |
| Grocery header and plan cash line show groceries and stock-up separately | G0 header, C6 header, G3 totals | API adds `cash_split_display` ("$52.91 groceries + $90.43 stock-up") to costs and grocery list; the frontend shows it |
| "Check you have" never shows water or "0 g" | G0, C6 Shopping list | `grocery_list.py`: water is never listed; a staple amount that would display as 0 shows the name only |
| "Always have" staples list | S2; applied in planning, grocery list and C3 | Settings v3 `always_have`; planning treats it as unlimited stock |
| Quick-add amount picker | P1 | API `amount_options` + custom amount in the natural unit |
| "Nothing to cook, eating prepped meals" instead of "Cook day · 0 min hands-on" | C6 day notes, C0 Today card | API `DayOut.cook_note` |

---

## 12. Screen → backend map

| Screen | Existing pieces it uses | New pieces |
|---|---|---|
| W0–W8 Onboarding, S0–S2 Settings | `GET/PUT /settings`, `UserSettings` v2, `diet_review`, `PUT/DELETE /settings/ingredient-preferences/{id}`, frequency caps, cook schedule | Settings v3 fields (§13.4), `POST /settings/preview`, `GET/POST /stores` |
| C0 Cook home | `GET /plans` (current plan), `GET /plans/{id}` (today's meals) | `GET /cook/home` (last answers + summaries, Today card, saved previews); `cook_search`; `recipe_favorite` and `recipe_saved` |
| C1, C1b How much, When | `PlanRequest` (`days`, `slot_kcal`, `day_overrides` for cook days and minutes, `portion_requests` with `extra_portions_to_freeze`) | `CookAnswers` → `PlanRequest` mapping (`app/cook/answers.py`) |
| C2 Goals | `NutritionPriority`, `GroceryMode`, `RecipeMood`, cook minutes, mood limits (`domain/cook_time.py`) | Goal mapping (§13.3): protein reward when its tile is on, low-calorie slot targets, Quick as a time limit |
| C3 What do you have | Inventory lots (open packages, expiry), quick picks, `GET /ingredients?q=` search, resolver, diet status | Per-search pantry toggles, "have it" lots for this search, could-buy list, Always-have lots |
| C3b Shopping | Planning modes (inventory / shop), `budget_cents`, `topup_cents`, stock-up rule (C10) | Could-buy items as the only allowed purchases in "use what I have" mode |
| C4 Building (meal now) | Loader (`build_problem` pieces), recipe pool, NDJSON streaming pattern, `generation_run` | `POST /cook/meal-now`, single-meal ranking (§14), `meal_now_generation` prompt |
| C4 Building (meal prep) | `POST /plans` stream, orchestrator stages, solver, rounding, absorption, validator, grocery list | `POST /cook/meal-prep`; friendly stage names and a real `pricing` stage; household multiplier; calendar-week caps |
| C5 Results (meal now) | Recipe validator, prose filter, safety injection, resolver, version view (scaled nutrition and cost), `plan_candidate` exposure log | Ranking + coverage + deterministic substitutes; streamed merge; search cache |
| C6 Results (meal prep) | `PlanSummaryOut` (days, meals, batches, costs, freeze notes), grocery list view, `accept` | Per-meal and per-day cost, `dish_category`, `cook_note`, `cash_split_display`, overlap-aware accept |
| C6 Swap | Solver, post-solve, validator, `save_plan`, `meal_plan.supersedes_plan_id`, accept | `POST /plans/{id}/meals/{meal_id}/swap`: pinned re-solve (`planning/pins.py`), check-off carry-over, `meal_swapped` event |
| C7 Saved lists | Version view | `GET /recipes/saved`, `PUT/DELETE /recipes/{id}/favorite` and `/saved`, `feedback_event` |
| C8 Recipe page | `GET /recipe-versions/{id}?portions=`, `GET /cook-batches/{id}`, `POST /cook-batches/{id}/cooked`, grocery item PATCH and `complete` | `POST /cook/meals` (one-meal plan), favorite/saved flags and `dish_category` in the version response, substitute lines |
| G0 Grocery home | `GET /plans/{id}/grocery-list?group_by=`, `PATCH /grocery-items/{id}`, `POST /grocery-lists/{id}/complete`, offline queue | `cash_split_display`, water/0 g/Always-have fixes, open one-meal lists, "I always have this" |
| G1–G3 What should I buy? | Orchestrator in shop mode, budget and stock-up rules, R4 store split, money-first diagnostics | `POST /grocery/advice`, reason templates (`app/cook/grocery_advice.py`) |
| P0–P1 Pantry | Inventory CRUD, `POST /inventory/parse`, `POST /inventory/bulk`, `GET /inventory/quick-picks` | `amount_options` on quick picks; bulk add with an option key or a custom amount in the natural unit |

---

## 13. New backend work

### 13.1 Endpoints

All under `/api/v1`, signed-in only, problem+json errors. "NDJSON" endpoints follow the Phase 2 pattern: they finish
inside the request, stream `started`, `progress` and a `heartbeat` every 5 s, and end with one `result`. This is
streaming of **our HTTP response** only. LLM calls stay non-streaming structured calls (CLAUDE.md rule 6).

| # | Endpoint | Purpose | Kind | Step |
|---|---|---|---|---|
| E1 | `GET /cook/home` | Cook home data: last answers per mode with summary lines, the Today card, saved previews | JSON | 2b.3 |
| E2 | `POST /cook/meal-now` | Ranked suggestions: saved and seed first, generated ideas merged in as they pass validation | NDJSON | 2b.3 |
| E3 | `POST /cook/meals` | Cook this: saves one recipe at N portions as a one-meal plan for today (with its could-buy grocery list); returns the batch id | JSON | 2b.3 |
| E4 | `POST /cook/meal-prep` | A meal-prep plan from Cook answers (wraps the orchestrator) | NDJSON | 2b.5 |
| E5 | `POST /plans/{plan_id}/meals/{meal_id}/swap` | Replace one meal; the rest of the plan stays fixed | NDJSON | 2b.6 |
| E6 | `POST /plans/{plan_id}/accept` (changed) | Overlap-aware: 409 with the overlapping plan unless `replace_overlapping=true` | JSON | 2b.5 |
| E7 | `PUT` / `DELETE /recipes/{recipe_id}/favorite` | ♥ on or off (idempotent; offline-queueable) | 204 | 2b.1 |
| E8 | `PUT` / `DELETE /recipes/{recipe_id}/saved` | 🔖 on or off | 204 | 2b.1 |
| E9 | `GET /recipes/saved?list=favorites\|later` | Saved lists as cards (pantry coverage added in 2b.3) | JSON | 2b.1 |
| E10 | `POST /grocery/advice` | What should I buy? | NDJSON | 2b.8 |
| E11 | `POST /settings/preview` | Validate settings without saving; computed summary lines and field errors | JSON | 2b.1 |
| E12 | `GET` / `POST /stores` | List your stores; add a grocery store by name | JSON | 2b.1 |
| E13 | `GET /inventory/quick-picks` (changed) | Adds `amount_options` and `custom_units` | JSON | 2b.1 |
| E14 | `POST /inventory/bulk` (changed) | Accepts `amount_option` or `custom_amount` + `custom_unit` | JSON | 2b.1 |
| E15 | `GET /plans/{id}` (changed) | Adds `kind`, per-meal and per-day cost, `dish_category`, `cook_note`, `cash_split_display` | JSON | 2b.1 |
| E16 | `GET /plans/{id}/grocery-list` (changed) | Water, 0 g and Always-have fixes; `cash_split_display` | JSON | 2b.1 |
| E17 | `GET /recipe-versions/{id}` (changed) | Adds `dish_category`, `is_favorite`, `is_saved`; with `search=<id>`, the coverage and substitute lines from that search | JSON | 2b.1 / 2b.3 |

`POST /plans` stays as it is for the CLI and for compatibility.

### 13.2 Request and response models (sketch)

```python
class GoalTile(StrEnum):
    HIGH_PROTEIN = "high_protein"; HIGH_CARB = "high_carb"; IRON_RICH = "iron_rich"
    LOW_CALORIE = "low_calorie"; CHEAP = "cheap"; QUICK = "quick"

class PantryToggle(_Strict):          # only items you turned off need sending
    ingredient_id: int
    include: bool

class ExtraItem(_Strict):             # added in "What do you have?"
    ingredient_id: int
    status: Literal["have", "could_buy"]
    quantity: Decimal | None = None   # "have it" in meal prep; None = enough for one recipe (meal now)
    unit: str | None = None
    save_to_pantry: bool = False

class PrepAmount(_Strict):
    shape: Literal["portions", "days"]
    slot: MealSlot | None = None      # portions: which meal
    portions: int | None = Field(default=None, ge=1, le=20)
    start: Literal["today", "tomorrow"] | date = "today"   # relative, so "same as last time" moves with the calendar
    day_count: int | None = Field(default=None, ge=1, le=14)
    slots: list[MealSlot] = []
    extra_to_freeze: int = Field(default=0, ge=0, le=20)
    cooking: Literal["today", "cook_days"] = "today"
    cook_minutes_today: int | None = Field(default=None, ge=0, le=600)

class CookAnswers(_Strict):
    schema_version: Literal[1] = 1
    mode: Literal["now", "prep"]
    slot: MealSlot | None = None      # meal now; None = from the clock
    people: int | None = None         # None = settings.household_size
    goals: list[GoalTile] = []        # in tap order; at most two nutrition goals
    mood: RecipeMood | None = None    # None = settings / today's schedule
    time_limit_minutes: int | None = Field(default=None, ge=5, le=240)   # with Quick
    pantry: list[PantryToggle] = []
    extras: list[ExtraItem] = []
    prep: PrepAmount | None = None
    shopping: Literal["use_what_i_have", "make_a_list"] | None = None    # prep
    budget_cents: int | None = Field(default=None, ge=0)
    allow_llm: bool = True
    more_ideas: bool = False

class SuggestionOut(BaseModel):       # one recipe card; every number is code-computed
    version_id: int; recipe_id: int; title: str; dish_category: str
    badges: list[Literal["favorite", "saved", "new", "draft"]]
    portions: int; portions_display: str
    numbers: list[str]                # "540 kcal", "41 g protein", "35 min", "$2.10 a portion" (+ goal extras)
    uses: list[str]                   # your items
    could_buy: list[CostLineOut]      # name, cost_display, store, is_estimate
    missing: list[MissingLineOut]     # name, substitute (name, amount display, you_have), buy (cost_display, store) | None
    why: list[str]                    # templated from the score components
    score: Decimal                    # kept for the exposure log and debugging

class CookStreamEvent(BaseModel):
    event: Literal["started", "progress", "heartbeat", "results", "result"]
    search_id: int; run_id: int; elapsed_s: float
    stage: str | None = None; message: str | None = None
    suggestions: list[SuggestionOut] | None = None   # "results": the full re-ranked list, replacing the last one
    new_version_ids: list[int] = []
    status: Literal["succeeded", "partial", "failed"] | None = None   # "result" only
    wait_s: int | None = None          # "progress" with stage "waiting": seconds until the call can go (countdown)
    retry_after_s: int | None = None   # "result" with status "partial" after a wait too long for this request
    notes: list[str] = []; problem: ProblemOut | None = None
    llm_call_count: int | None = None; total_tokens: int | None = None

class SwapIn(_Strict):
    exclude_version_ids: list[int] = []   # recipes already swapped away for this meal
    allow_llm: bool = False               # True only after you tap "Write a new one"

class GroceryAdviceIn(_Strict):
    goals: list[GoalTile] = []
    day_count: int = Field(default=7, ge=1, le=14)
    start: Literal["today", "tomorrow"] | date = "today"
    budget_cents: int | None = Field(default=None, ge=0)
    allow_llm: bool = False

class AmountOption(BaseModel):
    key: Literal["full", "three_quarters", "half", "quarter"]
    quantity: Decimal; unit: str; display: str   # "¾ · 1.5 lb (680 g)"
```

The meal-prep stream reuses `PlanStreamEvent` with the new stage names and the same `wait_s` field. The swap result
carries the new plan summary, the replaced and new meal, an `also_changed` list of display lines, and `undo_plan_id`.
`POST /inventory/parse` returns `retry_after_s` (with HTTP 200 and status `waiting`, not an error) when its call can't
go within the wait limit.

**Rate-limit waits (all LLM paths).**
- **Before each call,** the pacer (`llm/pacing.py`) compares the call's estimated tokens with the per-minute
  allowance left, read from Groq's `x-ratelimit-*` headers.
- **If it doesn't fit** (or Groq replies 429), the call waits, and the stream sends `progress` with stage `waiting` and
  `wait_s`.
- **A wait longer than `LLM_MAX_RATE_WAIT_SECONDS` or the request's time budget** ends the request gracefully: status
  `partial`, with everything already found and `retry_after_s`.
- **Problem errors** are reserved for real failures (bad configuration, repeated invalid output, transport failures
  after retries). A rate limit is never one.

### 13.3 Scoring and planning changes

**Goal mapping**

| Input | Meal now (ranking, §14) | Meal prep, swap, grocery advice (solver) |
|---|---|---|
| High protein | + protein per portion, counted only up to the meal's share of 1.5 × your daily target | **Protein reward above the floor, capped, this request only** (§16 F3): each day's protein (per person) earns a reward only up to **1.5 × the daily target**; protein above that earns nothing. The floor stays |
| High carb | + carbs per portion | `nutrition_priority` (or secondary) = carb |
| Iron rich | + iron per portion, heme counted twice (as today) | priority = iron |
| Two nutrition goals | both terms, 1.0 and 0.6 | primary + secondary in tap order |
| Low calorie | fit target = 85% of the meal's calories; + lower kcal | `slot_kcal` = 85% of each meal's allocation for this request (§18 Q1) |
| Cheap | − cash to buy now, − cost per portion | `grocery_mode = cheapest` weights |
| Quick | filter: total time ≤ N (default 30); + shorter | hands-on minutes per cook day ≤ N |
| Mood | filter: recipe mood ≤ chosen; + exact match | `DaySpec.mood` for the cook days |
| No goals | your Settings priority | your Settings priority and grocery mode |

**The capped protein reward** (approved 2026-10-10):
- **In the MILP,** per day d, a reward variable `y_d` gets `y_d ≤ protein_d` (your portion) and
  `y_d ≤ 1.5 × daily_protein_target_g`. The objective adds `w_protein × y_d` only while the High protein tile is on.
  Maximizing a capped linear term keeps it exact, with no new integer variables.
- **The floor is unchanged:** strict mode per day, weekly mode per week.
- **Why the cap:** without it, the tile could push plans back into expensive all-chicken weeks; above 1.5 × the
  target, extra protein has to win on cost and fit like everything else.
- **With no protein target** (0), the tile rewards protein up to 1.5 × the 100 g default, so it still has a bound.
- **The meal-now ranking** uses the same cap, per meal: protein per portion counts up to that meal's share of 1.5 ×
  the daily target (meal kcal ÷ day kcal × 1.5 × target).

**Other changes**

- **Favorites are real.** `favorite_recipe_ids` is filled from `recipe_favorite` (today it is always empty). The
  solver's existing favorite bonus (preference weight 0.3 per portion) and the exposure log's `source = favorite`
  start working. **Saved for later has no effect on scores.**
- **Pantry toggles:** a toggled-off ingredient's lots are left out of this request's problem.
- **"Have it" extras** become lots for this request only: meal now assumes enough for one recipe; meal prep uses the
  amount you picked. With **Save to pantry** they are written as real lots (with an `inventory_event`) first.
- **Could buy:**
  - meal now: priced purchases with a small preference bonus;
  - meal prep, "use what I have": the **only** purchases the solver may make (new constraint: purchasable
    ingredients = the could-buy set);
  - meal prep, shopping list: a small preference bonus.
- **Always have:** each item is an unlimited lot you own. It is never bought or listed. Food eaten is still costed
  at its unit price when one is known, so cash + from inventory = eaten + frozen + leftover still balances to the
  cent. Water is always treated this way.
- **Household size h:** in the solver, post-solve, validator and grocery list, a meal is h portions from one batch.
  Purchases and portions scale; calorie and protein limits apply to your portion. Meal-now cards are for h portions;
  nutrition is shown per portion.
- **Calendar-week caps:** frequency caps (pork ≤ 1 meal a week) count per Monday–Sunday week in your timezone,
  across active plans, this plan and one-meal plans. A plan that spans two weeks gets one cap constraint per week.
  The ranking filters capped recipes when the week's allowance is used up.
- **Pinned re-solve for swap** (`planning/pins.py`):
  - Every other meal keeps its recipe, day, portion size and batch.
  - Every other batch keeps its recipe, cook day and multiplier.
  - Only the swapped meal's slot is free, and only the batches that fed it, or a new batch on a cook day within that
    meal's fridge window, may change portion counts.
  - Every limit still holds: day and week calories, protein floor, the plan's purchase limit, caps and cook time.
  - The swapped-away recipes are excluded. Cooked batches are fixed exactly.
  - After "Done shopping" the swap runs in inventory mode with no purchases unless you tap Allow buying.
- **Overlapping plans:** plans may start on any day; accepting one supersedes any active non-one-meal plan whose days
  overlap it (after your confirmation), not only one with the same `week_start`.
- **One-meal plans** (`meal_plan.kind = 'single'`) never become the current plan, and the validator runs on them in a
  "single" scope that skips the day and week calorie and protein floors (one meal isn't a day). Every other check
  runs: exclusions, caps, equipment, time, safety, prose, numbers recomputed.
- **Solver time limit:** `SOLVER_TIME_LIMIT_SECONDS` default 12 → **30** (your carried decision; D43). Tests are
  unaffected (`conftest.py` sets its own limit).
- **Per-meal and per-day cost:** each batch's consumed cost (rounded once per batch, §7.1) is split across its
  portions by largest remainder, so meal costs add up to the batch exactly and day costs add up to "food eaten" to
  the cent.
- **Dish category:** `domain/dish_category.py`, pure and deterministic (§4.4). It is computed when read, so it needs
  no column and no LLM field.

### 13.4 Data model changes

**Migration `0005_cook_flow`** (additive, like every migration so far):

```
recipe_favorite                                 -- as designed for Phase 3 (§4.5), pulled forward
  user_id FK→app_user, recipe_id FK→recipe, created_at          PK (user_id, recipe_id)

recipe_saved                                    -- new: "save for later", no ranking effect
  user_id FK→app_user, recipe_id FK→recipe, created_at          PK (user_id, recipe_id)

feedback_event                                  -- as designed for Phase 3 (§4.5), pulled forward, append-only
  (columns unchanged). 2b writes: favorite_added, favorite_removed, saved_added (new type),
  saved_removed (new type), meal_swapped. Ratings, cook logs and the rest stay Phase 3.

cook_search                                     -- new: last-answers memory, result cache, meal-now exposures
  id bigint PK, user_id FK→app_user NN
  mode text NN                -- now | prep | grocery
  answers jsonb NN            -- CookAnswers (schema_version), exactly as sent
  answers_hash text NN
  cache_key text NN           -- answers + resolved dates + pantry snapshot + settings + recipe pool + prices
  generation_run_id bigint NULL FK→generation_run
  meal_plan_id bigint NULL FK→meal_plan        -- prep/grocery: its plan; now: the one-meal plan once you cook
  results jsonb NULL          -- meal now: the ranked snapshot (version ids, scores, components, card lines)
  status text NN              -- running | done | failed
  created_at timestamptz NN
  IX (user_id, mode, created_at DESC) · IX (user_id, cache_key)

ALTER meal_plan ADD kind text NULL              -- meal_prep | single | grocery_advice; NULL = Phase 1–2 week plans
```

- **`plan_candidate`:** no column change. Meal-now searches write rows with `selected = false`; Cook this sets
  `selected = true` and `portions_selected`, and links `meal_plan_id` to the one-meal plan (§16 F9).
- **Settings v3** (data migration, like 0002):

  | Field | Type | Default | Notes |
  |---|---|---|---|
  | `household_size` | int, 1–8 | 1 | Scales recipes (F5) |
  | `always_have` | list of ingredient slugs | `[]` | Unlimited stock; never bought or listed |
  | `default_budget_cents` | int or null | null | Pre-fill only (F4) |
  | `onboarding_completed` | bool | **false** | So the wizard runs once for you, pre-filled |

- **Seed data:** sweet potatoes get a multi-week pantry shelf life like russet potatoes (28 days, cited the same way
  as D38). No migration.
- **No other schema changes.** The deterministic substitute suggestions read `ingredient_substitution` (accepted
  pairs) and store nothing. Dish categories are computed.

### 13.5 Prompts

- **`meal_now_generation/1`** (new). The same system rules and `GeneratedRecipe` schema as today. The user part asks
  for 2 recipes for one meal, mood, time limit, equipment and `base_servings` 2 (code scales to your household). It
  has:
  - **must use:** up to 6 of your items, open packages and soonest-expiring first, then proteins;
  - **may buy:** your could-buy items;
  - **goal hints** as ingredient directions ("favor protein-rich ingredients such as eggs, chicken, Greek yogurt,
    chickpeas"); never as claims, and the prose filter still blocks claims in the output;
  - **avoid** the titles already on screen;
  - a **narrowed vocabulary:** your items, could-buys, Always-have and assume-in-stock staples, plus up to 30 common
    allowed ingredients your stores price (by how often your recipes use them). The never-use list is unchanged.
    This cuts the prompt by roughly the length of the full ingredient list (§15).
- **`recipe_revision/1`** is reused unchanged. In meal now it runs only when a batch yields **no** valid recipe, to
  keep the wait short.
- Meal prep, swap ("Write a new one") and grocery advice use the existing `candidate_generation/1`.

### 13.6 Progress stages

| Friendly step | Server stages (real) | Notes |
|---|---|---|
| Checking your pantry | `constraints` (settings, diet, inventory, toggles, extras) | — |
| Finding recipes | `candidates`, `generating`, `waiting` | Meal now: `results` events arrive here. `waiting` carries `wait_s` and shows the countdown wait state, never an error |
| Balancing calories across the days | `solving`, `re-solving` | Meal prep, swap, grocery advice |
| Pricing your groceries | **`pricing`** (new): practical rounding, package absorption, packages, store choice, costs | Emitted after the solve, before `build_rounded_plan` |
| Double-checking every number | `validating` | Moves after `pricing` (today it is emitted before rounding) |

### 13.7 Logging for the future ranker

- **Exposures:** meal-now searches log every offered and filtered recipe in `plan_candidate` under a `generation_run`
  with purpose `meal_now`. Swaps log under `swap` and grocery advice under `grocery_advice`. Failed runs log nothing
  (D42 unchanged).
- **Events:** ♥ and 🔖 toggles and swaps go to `feedback_event` from day one. They can't be backfilled, which is the
  same reason exposure logging moved to Phase 2.

---

## 14. Single-meal suggestions without the weekly solver

**Approach.** "A meal now" ranks candidates with a deterministic scoring function (`app/cook/ranking.py`):

1. **Pool:** seed drafts, saved and generated versions (your latest version of each recipe), and favorites, eligible
   for the chosen meal.
2. **Hard filters,** each recorded as a `filtered_reason`: excluded or held ingredients; the pork cap used up this
   week; equipment; recipe mood above the chosen mood; total time over the Quick limit; incomplete nutrition.
3. **Scale and round** each candidate to h portions at your portion size, with the same practical rounding the
   planner uses. Nutrition and cost come from the rounded lines: the same numbers the recipe page shows for that
   portion count.
4. **Coverage** per non-staple line:
   - **have**: toggled-on pantry lots (open packages first, then soonest expiry) or "have it" extras;
   - **could buy**: whole-package cash at your preferred store that prices it;
   - **missing**: shown with a deterministic substitute (an accepted pair, else a pantry item with the same role and
     category, allowed and not disliked; amounts keep protein grams for proteins, mass for vegetables, kcal for
     carbs), else its price.
5. **Score** = a weighted sum of components normalized across the eligible pool (initial weights, tuned with golden
   tests in step 2b.3):

   | Component | Weight |
   |---|---|
   | Selected goal terms (§13.3) | 1.0 each (secondary nutrition goal 0.6) |
   | Pantry fit: share of non-staple lines you have | 1.0 |
   | Uses an open package or a lot expiring within 3 days | +0.5 each, at most 1.0 |
   | Missing line with no substitute | −0.6 each |
   | Missing line with a pantry substitute | −0.2 each |
   | Could-buy line | −0.1 each (cash counts too only with Cheap) |
   | Favorite | +0.3 (the solver's weight) |
   | Contains a disliked ingredient | −0.3 |
   | Exact mood match | +0.1 |
   | kcal per portion beyond ±15% of the meal's target | −0.004 per kcal (as in D2) |

   **Never favored** (pork components): goal, pantry, use-up and cost terms are zero, plus the −0.05 tie-break, so
   they rank only on neutral grounds (§7.4).
6. **Sort** by score, then fewer missing items, then version id. Cards carry the components as "why" chips.

**Gap rule for new ideas:**
- A **good match** passes the filters and, if your pantry isn't empty, uses at least one of your items as its protein
  or carb with at most 2 missing items that have no substitute.
- With fewer than 3 good matches (or when you tap **More ideas**), one generation call writes 2 recipes.
- They pass the recipe validator, are saved, scored by the same function, and streamed into the list.

**Why not the solver.**
- **Nothing is coupled.** One meal shares no packages, fridge windows, cook days or weekly totals with other choices,
  so the best answer is simply the best-scoring candidate. A MILP would add nothing but solve time.
- **Speed.** Ranking 50 candidates is milliseconds of math on top of the loader. The saved list appears in under a
  second, while the weekly solver takes 5–30 s.
- **Explainable and stable.** Each card's position comes from named components ("uses 3 of your items", "your
  favorite"), and identical input gives an identical order.
- **Same numbers and rules.** It reuses the planner's rounding, nutrition, cost, exclusion, cap and validator code. A
  card's kcal and cost equal the recipe page's at the same portions, and the one-meal plan made by Cook this is
  validated like any plan.

**Where the solver stays:** meal prep, swap and grocery advice, where package sharing, fridge windows, cook-day time,
day and week calories, the protein floor and the budget interact.

---

## 15. LLM budget: calls, tokens and caching

### 15.1 Limits we work inside (build plan §7.6)

Groq free tier for the strict-output models: **8K tokens a minute**, 200K tokens a day (the app's own guard,
`LLM_DAILY_TOKEN_BUDGET`, stops at 150K), 30 requests a minute, 1K a day. The Phase 1 live run measured a 2-recipe
candidate batch at **≈ 5.9K prompt + ≈ 1.8K completion ≈ 7.7K tokens**, so about **one generation call a minute**.

### 15.2 Estimates

| Flow | Typical calls | Typical tokens | Worst case (capped) |
|---|---|---|---|
| **A meal now** | **0–1.** 0 when at least 3 saved or seed recipes are good matches; 1 otherwise, or when you tap More ideas | ≈ 6–7K per call (≈ 4.5–5K prompt with the narrowed vocabulary + ≈ 1.8K completion; to be measured in 2b.3's live test) | 2 calls (one batch + one revision, only if the batch had no valid recipe) ≈ 14K |
| **Meal prep** (5 lunches, or lunch + dinner Mon–Fri) | **0** with today's library: 6 lunch/dinner seeds cover a slot for up to 5 days each (variety rule) | 0 | One batch per uncovered meal slot (≈ 7.7K) plus targeted rounds after an infeasible solve. The 180 s request budget and 8K/min allow about **3 calls**, ≈ 23K |
| **Swap one meal** | **0** (other saved recipes fit) | 0 | 1 targeted batch, only after you tap **Write a new one**, plus at most 1 revision: ≈ 8–15K |
| **What should I buy?** | **0** (generation is off by default) | 0 | As meal prep, if you turn on "include new recipes" |
| **Same as last time, reopening results** | **0** | 0 | 0 when nothing changed; otherwise as the flow |
| NL quick add (unchanged) | 1 per parse | ≈ 1–2K | 3 attempts |

**A heavy day:** 5 meal-now searches that each generate, 1 meal prep with one gap, and 2 swaps ≈ 5 × 6.5K + 7.7K ≈
40K tokens, about a quarter of the daily guard. **A second call within the same minute** (e.g. More ideas tapped
twice quickly) gets the friendly countdown wait (5.5), never an error. Requests per minute and per day never bind
first.

### 15.3 What is cached or reused

1. **Every validated recipe is saved** and joins the pool for all flows (rule 7). Ideas written for one search become
   saved candidates for the next, so repeated pantries rarely need new calls.
2. **Search results** (`cook_search`) are keyed by answers + resolved dates + pantry snapshot + settings + recipe-pool
   version + price version. A repeat with nothing changed (Same as last time, reopening results, coming back to the
   tab) returns the stored result with 0 calls and no re-solve.
3. **The gap rule:** meal now generates only when the saved pool is thin; meal prep only for uncovered meal slots
   (existing `gap_analysis`).
4. **Substitutes** are deterministic in 2b (accepted pairs + pantry items with the same role), so 0 calls. Phase 3's
   LLM substitution engine keeps its per-ingredient cache.
5. **Swaps** remember the recipes already swapped away for that meal, so repeated taps cycle through saved options
   instead of asking the LLM.
6. **Grocery advice** has LLM off by default and plans from the saved pool.
7. **The daily token guard:** when it can't afford another call, flows fall back to saved recipes with a note, never
   an error.

---

## 16. Changes to earlier decisions (all approved 2026-10-10)

You approved all 18 changes on 2026-10-10, with the protein reward in F3 capped at 1.5 × the daily target.

| # | Earlier decision | Change | Why |
|---|---|---|---|
| F1 | Phase 2 screens: Week, Day, Inventory, Grocery, Settings; the app opens on the week | Four tabs; the app opens on **Cook**; the plan view becomes the meal-prep results screen (Today first); Inventory is renamed Pantry | Your redesign |
| F2 | Favorites, `recipe_favorite` and `feedback_event` in Phase 3 (migration 0003) | Pulled into **2b** (migration `0005_cook_flow`), plus a new `recipe_saved` table | Favorites and Saved are on the Cook tab; toggle history can't be backfilled |
| F3 | C7: protein is a floor and earns **no reward** | With the **High protein** tile on, that request adds a protein reward above the floor, **capped: protein above 1.5 × the daily target earns nothing** (§13.3). The floor stays; without the tile, C7 holds | The tile asks for more protein; the cap stops it pushing plans back into expensive all-chicken weeks |
| F4 | C4: the budget is a per-request parameter, **not a setting** | Settings stores `default_budget_cents` **to pre-fill** the request; the request still owns the limit | Onboarding asks for a weekly budget |
| F5 | Phase 1 plans for one eater | `household_size`: a meal = h equal portions; your targets apply to your portion | "How many people" scales recipes |
| F6 | One active plan per `week_start`; plans are weeks | Plans start on any day; one current plan; accepting one that overlaps replaces the current one after confirmation; one-meal plans never count as current | Meal prep starts "today" |
| F7 | Frequency caps count per plan ("this week" = the plan's days) | Per Monday–Sunday week across all plans and one-meal plans | Rolling plans and single meals would otherwise each get their own pork allowance |
| F8 | Every plan is a solver output for a week | **One-meal plans** (`kind = single`) from Cook this, validated in a "single" scope | Reuses Mark cooked, deductions, grocery check-off and history unchanged |
| F9 | `plan_candidate` rows are written once, with `selected`, when a plan is saved | Meal-now rows are written at search time with `selected = false`, then updated when you cook one | Meal-now selection happens after the search |
| F10 | Partial re-solve with the rest fixed belongs to Phase 4 (daily overrides) | The single-meal swap (a pinned re-solve) moves to **2b**; a swap writes a new plan version that supersedes the old one, and Undo re-accepts the old one | Swap is on every meal row |
| F11 | The substitution engine is Phase 3 | **Deterministic** suggestions for missing items (accepted pairs, pantry same-role, code amounts) move to 2b; the LLM engine, applying a substitution and rewriting steps stay in Phase 3 | Cards show a substitute for anything missing |
| F12 | Grocery recommendations are Phase 5 (§12, §14 of the PRD) | A basic **What should I buy?** (a shop-mode plan + templated reasons from current prices) moves to 2b; deals, seasonality, usual items and the cart optimizer stay in Phase 5 | Grocery tab |
| F13 | Staples (`assume_in_stock`) are listed under "check you have" | **Always have**: unlimited stock you own, never listed; eaten cost still counted where priced | Your pending fix |
| F14 | Stage `validating` is emitted before rounding | New `pricing` stage, `validating` moves after it; friendly labels | Your building screen |
| F15 | `SOLVER_TIME_LIMIT_SECONDS` = 12 (D6) | **30** | Your carried decision (D43) |
| F16 | Later migrations named 0003–0006 | Renumbered: 2b `0005`, Phase 3 `0006`, Phase 4 `0007`, Phase 5 `0008`, Phase 6 `0009` | 0004 is already used |
| F17 | Settings v2 | Settings **v3** (data migration): household size, Always have, default budget, onboarding flag | Above |
| F18 | `CLAUDE.md` phase outline lists favorites in Phase 3 and has no Phase 2b | **Updated 2026-10-10** with your OK, using the wording in BUILD_PLAN §11 item 7 | CLAUDE.md is yours and wins on conflict |

Unchanged on purpose: the variety rule (Q14: at most 5 portions of one recipe a week for meals, never twice a day).
A user-editable variety cap stays deferred (your carried decision).

---

## 17. What moves between phases

| From | Pulled into 2b | Stays where it was |
|---|---|---|
| **Phase 3** | Favorites (♥, persistence, ranking and solver boost), the `recipe_favorite` and `feedback_event` tables; new Save for later; deterministic substitute suggestions | Ratings (👍/😐/👎, stars, tags, comments), the cook log (actual time and cost), prepared portions and cross-week leftovers, recipe editing and **versioning**, the LLM substitution engine and applying substitutions, the **preference profile** and "What I've learned", the weighted preference score in `plan_candidate`, Cook Again |
| **Phase 4** | The pinned re-solve, used for the single-meal swap | The Today screen's consumption tracking (it now builds on the Cook home Today card), day-level time/mood overrides (these reuse the pinned re-solve), off-plan logging, dynamic calorie rebalancing (which can later feed meal now's calorie target, "750 kcal left today"), the strict/weekly toggle per plan |
| **Phase 5** | Basic "What should I buy?" with templated reasons from current prices | Price history, within-store deal detection ("good deal"), seasonality, grocery-mode UI, usual items, Grocery Store Mode and Optimize My Cart (these live in the Grocery tab) |
| **Phase 6** | — | Unchanged; the dataset now also includes meal-now exposures (selected later) and swaps (a negative signal) |

---

## 18. Questions (answered 2026-10-10)

You accepted the defaults for all ten.

| # | Question | Answer |
|---|---|---|
| Q1 | **Low calorie** in meal prep and grocery advice: 85% of each meal's usual calories for that request, or only re-rank? | **85%**, shown on the results ("aiming for about 1,530 kcal a day") |
| Q2 | Items marked **Have it** during a search: per search, or always saved to the pantry? | **Per search**, with a "Save to pantry" switch, off by default |
| Q3 | Already-cooked portions when a plan is replaced: prepared portions in Phase 3, or pull them into 2b? | **Keep in Phase 3**; the replace sheet names the cooked portions you still have |
| Q4 | **Household size:** same portion size for everyone, only your targets checked? | **Yes** |
| Q5 | **What should I buy?** builds a meal plan behind the list, and **Use this list** also sets that plan? | **Yes** |
| Q6 | The **pork cap week** is Monday–Sunday in your timezone, across all plans and single meals? | **Yes** |
| Q7 | The **mascot**? | **Pottle**, the small clay pot |
| Q8 | **Meal now** writes new ideas automatically only when fewer than 3 saved recipes fit well (plus More ideas)? | **Yes** |
| Q9 | **Phase 2 approval?** | **Approved 2026-10-10** |
| Q10 | **CLAUDE.md** phase outline update? | **Yes**; applied with the BUILD_PLAN §11 item 7 wording |
