# Mealbro Flow Spec: the cook-first redesign (Phase 2b)

**Status:** **approved 2026-10-10** with four changes, now applied: a shorter onboarding (9 screens, with "Skip, use
my current settings"), a capped protein reward, the Cook home order, and friendly rate-limit waits. All flagged changes
(§16) are approved, and the questions (§18) are answered with the defaults. No code has been written yet; building
starts with step 2b.1.
**Addition (2026-10-10):** recipes are generated in two stages to fit Groq's 8K tokens a minute: an ideas pass for
the cards, then steps the first time you open a recipe. After your first More ideas tap in a search, a background
batch makes later taps usually instant (§13.5, §14, §15; changes F19–F21, approved, with F21 tightened to start
only after that first tap). The target-0 fallback for the protein cap (§13.3) is approved. Built in steps 2b.3a
(ranking and cards) and 2b.3b (ideas, steps, background batch).
**Notes from the 2b.2 approval (2026-10-10, BUILD_PLAN H3–H5), to build in 2b.5 and 2b.7:** the meal-prep "How do
you want to cook?" step with four options (C1b), the per-day fridge and freezer rules and the "freezes well" flag
(C1b, C6), and the new plan view with its one Prep notes row (C6); change F22 (§16). The build order is now 2b.3a →
2b.4 → 2b.3b, so until 2b.3b More ideas shows disabled with "coming soon" (C5).
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
  used. Generated recipes arrive in two passes (§13.5), and each is checked before anyone sees it:
  - an **idea** (name, ingredients and amounts, method, equipment, rough time) is resolved and checked, gets
    code-computed nutrition and cost, and passes the prose filter (§7.3 of the build plan) before it becomes a card;
  - its **steps**, written the first time you open it, pass the step checks, the prose filter and food-safety
    injection before they are shown.
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
| Steps for a new idea | "Writing the steps for this one…" | "Generating instructions…" |
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
| dessert | 🍮 | protein-dessert slot, or pudding / mousse / cake / brownie / cookie / parfait / yogurt bowl |
| oats | 🥣 | oats / oatmeal / porridge / granola, or oats are the main carb |
| eggs | 🍳 | omelet / frittata / scramble, or egg is the protein in a breakfast |
| wrap | 🌯 | wrap / burrito / taco / quesadilla, or a tortilla line |
| sandwich | 🥪 | sandwich / toast, or bread is the main carb |
| soup | 🍲 | soup / stew / chili |
| curry | 🍛 | curry / masala / gravy / dal / korma / keema / butter chicken |
| pasta | 🍝 | pasta / noodle / spaghetti / ramen |
| salad | 🥗 | salad, or no-cook with mostly vegetables |
| bowl | 🍚 | bowl, or rice is the main carb |
| roast | 🍗 | sheet pan / roast / baked / air-fried protein |
| snack | 🥜 | snack slot, or dip / bites / chaat / roasted chickpeas (these words are checked right after dessert's) |
| other | 🍽️ | fallback |

A "burrito bowl" is a bowl: that phrase is checked before the table. (The snack words, the extra dessert and curry
words and the burrito-bowl phrase were added at the step 2b.4 approval fixes, for the 37 new seed recipes.)

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
│ 540 kcal · 41 g protein · 35 min ·        │  per portion (time = total; hands-on on the page),
│   $2.10 a portion · $4.29 to buy today    │  then whole packages of what to buy now (M12)
│ Uses: chicken thigh, spinach, onion       │  your items (pantry or "have it")
│ Could buy: chickpeas $1.29 (Stop & Shop)  │  your "could buy" items, whole-package cost
│ Swap: lime juice instead of lemon         │  a substitute you have (M11): never "Missing"
│   (you have it)                           │
│ Missing: tomato · buy $0.79 (Stop & Shop) │  only what you'd need to buy
│ Uses up your spinach · ready in 35 min    │  "why" chips (never a repeat of the Uses line)
└───────────────────────────────────────────┘
```

- The numbers row follows your goals: with **Iron rich** on it adds "4.1 mg iron (1.6 mg heme, est.)"; with **High
  carb** it adds carbs.
- A missing item with no substitute shows its price ("Missing: lemon · buy $0.79"), or "no price yet". A missing
  item you can make with something you have is a **Swap** line instead (step 2b.4 approval, M11).
- **Buy today** (M12): "$4.29 to buy today" is the whole-package cost of everything the meal needs you to buy now
  (could-buy items, top-ups and missing items without a swap), "nothing to buy today" when there's none, and
  "+ unpriced items" when some have no price yet. With **Cheap** on, ranking uses it as well as the per-portion cost.
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
| **Rate-limit wait** | Never an error. When an LLM call would go over Groq's per-minute limit (a 429 reply, or the pacer predicting one from the rate-limit headers, e.g. More ideas tapped with no batch waiting, or a new idea opened right after a batch landed), Pottle shows the working state with "The recipe service needs a short breather" and a countdown from `wait_s`. **Short wait** (fits within `LLM_MAX_RATE_WAIT_SECONDS`, 60 s, and the request's time budget): the request waits and carries on by itself. **Longer wait:** the request ends gracefully with what it has and a `retry_after_s`. The button that asked for it shows "Ready in 0:45", counting down, and turns back into a normal button at zero; one tap continues. On the recipe page the countdown sits in the Steps section (C8). Only the daily token guard shows a different message: "That's today's new-idea allowance; back tomorrow." Your saved results stay on screen throughout. |

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
| Meal prep | Starts at C1 How much, pre-filled from your last meal-prep answers (until step 2b.7 it opens the existing plan flow, BUILD_PLAN H3) |
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

### C1b How do you want to cook? (meal prep)

*Replaced 2026-10-10 at the 2b.2 approval (BUILD_PLAN H5); built in 2b.5 (engine) and 2b.7 (screen). It replaces
the earlier two tiles, "Today, all at once" and "On my cook days". The route keeps `step=when`.*

**Four tiles, one choice:**

| Tile | Controls | What the plan does |
|---|---|---|
| **One big cook day** | Day chips (Today, Tomorrow, a date) and a **hands-on minutes** stepper for that day, pre-filled from that day's schedule (or your longest cook day). It goes well above the usual per-day minutes (up to 600, 15 min steps) | Everything is cooked that day |
| **A few sessions** | Day chips for the cook days, each with its minutes, pre-filled from your cook-day settings | Batches only on those days, each within its own minutes |
| **Same dish, many portions** | The day to cook (as above). The portion count comes from C1 | One recipe scaled to every portion. For this request the weekly 5-portions-per-recipe cap doesn't apply (§16 F22) |
| **Mix it up** | None | Today's behavior: your cook days and the variety rule |

- **Why line:** "Cooked food keeps 3 days in the fridge, so anything past that goes in the freezer."
- **Fridge and freezer:** portions eaten within the fridge window (`leftover_fridge_days`, 3) stay in the fridge.
  Later portions go to the freezer, with a plain instruction on the day before: "Thaw tomorrow's lunch in the fridge
  tonight." The plan states this for each day (C6).
- **Freezes well:** every recipe carries this flag (`freezer_friendly`, shown as "Freezes well"). Seed recipes are
  set by hand: rice dishes and curry gravies yes; yogurt sauces and fresh salads no, or yes with a note to freeze the
  base and add the fresh part later (for example: freeze the chicken and rice; make the yogurt sauce and salad
  fresh). LLM ideas include it as a field, and the idea checks fail an idea without it. **Portions past the fridge
  window may only use recipes that freeze well.** If none can fill them, the plan says so (C6 states).
- **Time on a big cook day:** code estimates the total hands-on time of every batch cooked that day and checks it
  against the minutes you set. If it doesn't fit, the plan is infeasible with a time fix ("Allow 150 min").
- **Prep order:** the cook day shows a simple order where the recipes allow it, built by code from the batches'
  step sections and durations: what to start first (the oven, rice, anything simmering or chilling), then what to
  cook while those run. One batch, or batches with only hands-on steps, show no order.

### C2 What are you in the mood for? (both modes)

- **Goal tiles (multi-select):** High protein 🍗 · High carb 🍚 · Cheap 🪙 · Quick ⏱️ · Iron rich 🥬 · Low calorie 🪶.
  - At most **two nutrition goals** (high protein, high carb, iron rich). The first you tap is primary, the second
    secondary. A third tap shows "Pick up to two nutrition goals" and swaps out the oldest.
  - **Quick** reveals an inline stepper, "Ready in 30 min" (meal now: total time; meal prep: hands-on per cook day).
- **Mood (segmented, one):** Simple · Medium · Fancy.
- **Meal (meal now only), changed at the 2b.4 approval (M9):** a visible choice of Breakfast, Lunch, Dinner, Snack
  and Dessert (the protein dessert), with **nothing preselected** and no guess from the clock (you often plan dinner
  in the morning; Same as last time covers repeats). Next waits for a pick: "Pick a meal". Results are only that
  meal's recipes. A people stepper sits under it, pre-filled from your household size. (Was: a "Dinner for 1 ▸" line
  guessed from the clock.)
- **Why line:** "Pick the meal; time rules recipes out, and the goals and mood change the order." (Mood is a
  preference since M10.)
- No goal selected is fine: your Settings priority applies. Goal mapping: §13.3.

### C3 What do you have? (both modes)

- **Your pantry,** grouped Fridge / Freezer / Pantry. Each item is a toggle row, **on** by default, with its amount and
  badges ("open", "use by Thu"). Turning one off means "not for this search" (saved with your answers, so next time it
  starts off too). Your **Always have** staples sit in one collapsed line ("Always have: rice, oil, salt and 9
  more") and can't be toggled here.
- **Add something:** a search field (typed entry, autocomplete from the ingredient list) and quick-add chips (your
  usual items). Each added item gets a segmented **Have it / Could buy**:
  - **Have it** means it's in your kitchen. Since step 2b.4 the add flow (P2) asks how much, with the same package
    sizes and Not sure (the usual size) as Pantry; an item with no sizes needs no amount (enough for one recipe).
    Before 2b.4: for meal now no amount is needed (code assumes enough for one recipe);
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
- **Strip while new ideas are written:** "Writing new ideas…". During a rate-limit wait it becomes the friendly
  wait state with a live countdown: "The recipe service needs a short breather. Writing your ideas in 0:23…" (5.5).
  When they land:
  they slide into their ranked places with a **New** badge, and a toast says "6 new ideas added". If generation fails:
  "I couldn't write new ideas just now. These are your saved ones." Nothing else changes.
- **New ideas are full cards at once.** Their numbers, coverage and why lines are computed from the idea's
  ingredients exactly like a saved recipe's; only the steps wait until you open one (C8).
- **Cards:** the top 12 recipe cards in rank order (5.3); **Show more** loads the rest.
- **Mood is a preference, not a filter** (step 2b.4 approval, M10): recipes in your mood come first, then a section
  **"A bit more effort"** (more involved) and then **"Simpler options"** (less involved), each with the rest that pass
  the hard filters (time, equipment, food rules). Only a recipe in your mood counts toward the gap rule.
- **More ideas** at the bottom:
  - **Until step 2b.3b** (built after 2b.4, BUILD_PLAN H3) it is shown disabled with "coming soon", and the cards
    come from seed and saved recipes only.
  - **The first tap in a search waits normally.** It makes one ideas call, with the "Writing new ideas…" strip. A
    short wait shows the countdown strip; a longer one shows "Ready in 0:45" on the button, counting down to a
    normal button. It never errors.
  - **Later taps are usually instant.** Once the first tap's ideas are on screen, the server writes the next batch
    in the background when the per-minute allowance has room (§14), and holds it. The next tap shows it at once, with
    New badges, and starts the following batch the same way. Nothing on screen shows the background work.
  - If that batch is still being written, the button reads "Writing…", ignores further taps, and the ideas appear
    when it lands. No second call is made.
  - With no batch waiting (it was skipped or failed), a later tap behaves like the first one.
  - When the daily guard is used up it says "That's today's new-idea allowance; back tomorrow."

| Tap | Does |
|---|---|
| A card | C8 recipe page in this search's context (same portions, same pantry coverage) |
| ♥ / 🔖 on a card | Toggles favorite / save for later in place (E7, E8) |
| Edit | Back to C2 with the answers kept |
| More ideas | First tap: one ideas call. Later taps: the held background batch at once, otherwise one ideas call. Every tap then writes the next batch in the background (E18) |

**States.**
- **Loading:** skeleton cards.
- **Empty** (nothing passes time and equipment): Pottle: "Nothing fits 20 minutes." Buttons come from the filter
  that removed the most recipes: "Allow 30 min", "Check your equipment", "Write new recipes". (Mood no longer
  empties the list, M10.)
- **Stream error** after some results: keep them, show "Lost the connection; these may be incomplete" with **Try
  again**.
- **Error before any results:** error pattern (5.5).

### C6 Results: meal prep (Step 4), also the current-plan view

- **Header:** "5 lunches · Wed 14 – Sun 18 · High protein · Simple", then a totals line from the API:
  "Groceries $24.10 + $62.50 stock-up" (pending fix: always shown separately) and "35 min hands-on today".
- **Segmented toggle:** **Recipes | Shopping list**.
- **Prep notes** (changed 2026-10-10, BUILD_PLAN H4): freeze and spoil warnings **never appear as a block above the
  days**. They collapse into one tappable row under the header, its text from the API: "Prep notes: 3 to freeze · 4
  may spoil". Tapping it opens a sheet with each item (what to freeze on the shopping day, what may spoil before it is
  used). No row when there is nothing to note.
- **Recipes view** (default). **It starts with Today** (H4):
  - **Days, Today first,** then the following days. Days before today fold into "Earlier in this plan".
  - **Day header:** "Today · Wed 14" + "1,780 kcal · 112 g protein · $8.40" (the cost of the food eaten that day).
  - **Cook session, inside its day:** "Cook: Chicken over rice, 5 portions (3 fridge, 2 freezer) · 35 min hands-on ·
    about 50 min start to finish" with a recipe card, and the **prep order** when there is one (C1b): "1. Start the
    rice · 2. Sheet-pan chicken in the oven · 3. Make the curry while both cook".
  - **Day note:** "Cook: Chicken over rice (5 portions)" on a cook day, or **"Nothing to cook, eating prepped
    meals"** on a day with nothing to cook (replaces "Cook day · 0 min hands-on").
  - **Shopping day:** its freeze steps are listed on that day too ("Freeze 1 pack of chicken thighs today"), not
    only in Prep notes.
  - **Fridge and freezer per day:** each meal row says where its portion is ("from the fridge", "from the
    freezer"), and the day before a freezer meal says "Thaw tomorrow's lunch in the fridge tonight" (C1b).
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
  Wednesday's calories and cook time" and offers **Write a new one** (one ideas call; the new recipe's steps are
  written when you open it, and its unused ideas stay saved for the next swap) or **Keep this one**. If that
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
- **Your terms** (step 2b.4, BUILD_PLAN J6): each ingredient you have says what the recipe uses of it, "uses 8 oz,
  about half your bag · 8 oz left after", from the same lots and order Mark cooked takes from, so the note and
  the deduction match to the gram; the rest stays in Pantry.
- **Ingredients** in practical quantities. A missing line shows "Don't have lemon? Bottled lime juice works (you have
  it): 2 tbsp" (code-computed amount) and "Numbers are for the recipe as written."
- **Steps** by section, with injected safety lines; then storage and reheating text, per-portion nutrition, heme iron
  "estimated", and cost per portion (all existing).
- **Steps for a new idea** are written the first time anyone opens it (E19, §13.5):
  - The header, numbers, ingredients and Before you start show at once. The Steps section shows the idea's one-line
    method and "Writing the steps for this one…" with Pottle working, then fills in, normally within 5–15 s.
  - If the call has to wait for the per-minute limit, the countdown wait state (5.5) shows in the Steps section.
  - The numbers never change when the steps arrive: the steps can't add or change an ingredient, an amount, the
    equipment or the times.
  - From then on the steps are saved with the recipe, so every later open (any device, cooking mode, a plan) is
    instant. Seed and saved recipes already have steps and never wait.
- **Sticky action bar:** **Cook this** (primary) · ♥ · 🔖. For a plan batch, **Mark cooked** replaces Cook this once
  you're in cooking mode or the batch's day has come. While an idea's steps are being written, Cook this reads
  "Writing steps…" and becomes active when they land.

| Tap | Does |
|---|---|
| Cook this (meal now or saved) | Saves this meal as a one-meal plan for today (E3), so inventory deduction, open packages and history work as for planned batches; then opens **cooking mode**. If you have could-buy or missing items, a **Buy first** checklist comes first (check-off and Done use the existing grocery endpoints). |
| Cook this (plan batch) | Opens cooking mode for that batch |
| Cooking mode | Large one-step-at-a-time view, back/next buttons, safety lines highlighted, the screen kept awake (browser Wake Lock), **Mark cooked** at the end |
| Mark cooked | Existing endpoint: deducts inventory FIFO (open packages first), records open-package remainders, and shows what was taken and any shortfall |
| ♥ / 🔖 | Toggle (E7, E8) |

**States.** Loading: skeleton. Not found: "This recipe isn't available anymore." Offline: cached recipe opens; Cook
this and Mark cooked are disabled; an idea without steps shows "The steps need a connection." Mark cooked twice:
"Already marked cooked on Wed 14" (the existing 409). Steps failed after the capped attempts: "I couldn't write the
steps just now." with **Try again** (the idea, its numbers and its place in your plan stay). Daily guard used up:
"That's today's recipe-writing allowance; back tomorrow. Saved recipes still open."

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

*Replaced in the app at step 2b.4 by the add flow below (BUILD_PLAN J5, D80). The API's `amount_options` stay.*

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

### P2 The add flow (step 2b.4, BUILD_PLAN J4–J5)

Adding an item to Pantry (a typed name or a quick pick) or to "What do you have?" opens one sheet, its steps
from `GET /ingredients/{id}/add-options`:

1. **Which version?** Only for a held item that comes in versions (pepperoni, salami, chicken bouillon): the
   question, "Check the label" guidance and each version with what it means ("Off your list: it contains
   beef", "Allowed; counts toward your pork limit", "Allowed", "Stays held until you check the label"). Each
   allowed version is its own ingredient; the add then continues for it. Choosing one never allows the held item.
2. **Which kind?** Only for a food with more than one form (fresh, frozen, canned, dried), each its own
   ingredient (nutrition and shelf life differ: frozen florets keep for months).
3. **Have it / Could buy** ("What do you have?" only).
4. **How much?** The form's common US package sizes as buttons (estimates, from the seed catalog), **Custom**
   (stepper and unit, the server converts) and **Not sure** (the default: the most common size, with the lot
   marked as an estimate). Pantry shows an "est. amount" badge and **Correct amount** on such a lot.
5. **Where** (Pantry, or "Save to pantry"), pre-filled from the form's usual place.

A held lot that comes in versions shows **Which version?** in Pantry and in "What do you have?"; it becomes a
lot of that version (`POST /inventory/{id}/version`).

*Changed at the 2b.4 approval:*
- **Correct amount on any lot (M2):** quick taps for ¾, ½ and ¼ of the package the lot came in (its first added
  amount), another package size, or Custom; the server works out every amount.
- **Your usual version (M3)** is saved in Settings on the server and marked "your usual" in the version sheet.
- **Chicken cuts (M4–M6):** thighs and breasts come in two forms, *Boneless, skinless* and *Bone-in, skin-on*;
  drumsticks, wings and whole chickens are bone-in and skin-on. Bone-in cuts are added and bought by weight with the
  bone; nutrition and portion weights count only the edible part (USDA SR28 refuse). Chicken is exact everywhere:
  "chicken thighs bone in" never offers boneless ones, and no substitute swaps one form for another.
- **Close matches (M7):** a name with no ingredient of its own ("canned peas", "garlic paste") shows its closest
  one, always labeled: "Closest match: peas, frozen". Never for chicken cuts. "Can't find it? Add from USDA" is
  deferred (BUILD_PLAN §12.5, DF1).

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
| C4 Building (meal now) | Loader (`build_problem` pieces), recipe pool, NDJSON streaming pattern, `generation_run` | `POST /cook/meal-now`, single-meal ranking (§14), the ideas pass (`recipe_ideas/1` with the meal-now additions, §13.5) |
| C4 Building (meal prep) | `POST /plans` stream, orchestrator stages, solver, rounding, absorption, validator, grocery list | `POST /cook/meal-prep`; friendly stage names and a real `pricing` stage; household multiplier; calendar-week caps |
| C5 Results (meal now) | Recipe validator, prose filter, safety injection, resolver, version view (scaled nutrition and cost), `plan_candidate` exposure log | Ranking + coverage + deterministic substitutes; streamed merge; search cache; More ideas (`POST /cook/searches/{id}/more`) and, after its first tap, the held background batch |
| C6 Results (meal prep) | `PlanSummaryOut` (days, meals, batches, costs, freeze notes), grocery list view, `accept` | Per-meal and per-day cost, `dish_category`, `cook_note`, `cash_split_display`, overlap-aware accept |
| C6 Swap | Solver, post-solve, validator, `save_plan`, `meal_plan.supersedes_plan_id`, accept | `POST /plans/{id}/meals/{meal_id}/swap`: pinned re-solve (`planning/pins.py`), check-off carry-over, `meal_swapped` event |
| C7 Saved lists | Version view | `GET /recipes/saved`, `PUT/DELETE /recipes/{id}/favorite` and `/saved`, `feedback_event` |
| C8 Recipe page | `GET /recipe-versions/{id}?portions=`, `GET /cook-batches/{id}`, `POST /cook-batches/{id}/cooked`, grocery item PATCH and `complete` | `POST /cook/meals` (one-meal plan), favorite/saved flags and `dish_category` in the version response, substitute lines; steps on first open (`POST /recipe-versions/{id}/steps`, `recipe_steps/1`) |
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
| E1 | `GET /cook/home` | Cook home data: last answers per mode with summary lines, the Today card, saved previews | JSON | 2b.3a |
| E2 | `POST /cook/meal-now` | Ranked suggestions: saved and seed first (2b.3a), then (gap rule) one ideas call's ideas merged in as they pass the checks (2b.3b). No background batch (§14) | NDJSON | 2b.3a / 2b.3b |
| E3 | `POST /cook/meals` | Cook this: saves one recipe at N portions as a one-meal plan for today (with its could-buy grocery list); returns the batch id | JSON | 2b.3a |
| E4 | `POST /cook/meal-prep` | A meal-prep plan from Cook answers (wraps the orchestrator) | NDJSON | 2b.5 |
| E5 | `POST /plans/{plan_id}/meals/{meal_id}/swap` | Replace one meal; the rest of the plan stays fixed | NDJSON | 2b.6 |
| E6 | `POST /plans/{plan_id}/accept` (changed) | Overlap-aware: 409 with the overlapping plan unless `replace_overlapping=true` | JSON | 2b.5 |
| E7 | `PUT` / `DELETE /recipes/{recipe_id}/favorite` | ♥ on or off (idempotent; offline-queueable) | 204 | 2b.1 |
| E8 | `PUT` / `DELETE /recipes/{recipe_id}/saved` | 🔖 on or off | 204 | 2b.1 |
| E9 | `GET /recipes/saved?list=favorites\|later` | Saved lists as cards (pantry coverage added in 2b.3a) | JSON | 2b.1 |
| E10 | `POST /grocery/advice` | What should I buy? | NDJSON | 2b.8 |
| E11 | `POST /settings/preview` | Validate settings without saving; computed summary lines and field errors | JSON | 2b.1 |
| E11a | `PATCH /settings` (added in 2b.1, BUILD_PLAN D44) | Change only the fields sent, e.g. just `onboarding_completed` for **Skip, use my current settings** | JSON | 2b.1 |
| E12 | `GET` / `POST /stores` | List your stores; add a grocery store by name | JSON | 2b.1 |
| E13 | `GET /inventory/quick-picks` (changed) | Adds `amount_options` and `custom_units` | JSON | 2b.1 |
| E14 | `POST /inventory/bulk` (changed) | Accepts `amount_option` or `custom_amount` + `custom_unit` | JSON | 2b.1 |
| E15 | `GET /plans/{id}` (changed) | Adds `kind`, per-meal and per-day cost, `dish_category`, `cook_note`, `cash_split_display` | JSON | 2b.1 |
| E16 | `GET /plans/{id}/grocery-list` (changed) | Water, 0 g and Always-have fixes; `cash_split_display` | JSON | 2b.1 |
| E17 | `GET /recipe-versions/{id}` (changed) | Adds `dish_category`, `is_favorite`, `is_saved`; with `search=<id>`, the coverage and substitute lines from that search (2b.3a); `steps_ready` (false for an idea whose steps aren't written yet; 2b.3b) | JSON | 2b.1 / 2b.3a / 2b.3b |
| E18 | `POST /cook/searches/{search_id}/more` | More ideas. The first tap in a search makes one ideas call. A later tap shows the held background batch at once (and logs those exposures), or makes one ideas call when none is held. Every tap then writes the next background batch | NDJSON | 2b.3b |
| E19 | `POST /recipe-versions/{version_id}/steps` | Writes an idea's steps on first open and saves them with the recipe (F19). Returns at once when they exist; a second request for the same recipe waits for the call already running instead of making another | NDJSON | 2b.3b |

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
    # C1b "How do you want to cook?" (H5, replaces cooking: "today" | "cook_days"):
    cook_style: Literal["big_day", "sessions", "same_dish", "mix"] = "mix"
    cook_day: Literal["today", "tomorrow"] | date = "today"         # big_day, same_dish
    cook_minutes: int | None = Field(default=None, ge=0, le=600)    # big_day: that day's hands-on minutes
    sessions: list[CookSession] = []                                 # sessions: (day, minutes) per cook day

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
    allow_llm: bool = True            # More ideas is its own endpoint (E18), so it isn't part of the answers

class SuggestionOut(BaseModel):       # one recipe card; every number is code-computed
    version_id: int; recipe_id: int; title: str; dish_category: str
    badges: list[Literal["favorite", "saved", "new", "draft"]]
    steps_ready: bool                 # False for an idea whose steps are written on first open
    portions: int; portions_display: str
    numbers: list[str]                # "540 kcal", "41 g protein", "35 min", "$2.10 a portion" (+ goal extras)
    uses: list[str]                   # your items
    could_buy: list[CostLineOut]      # name, cost_display, store, is_estimate
    missing: list[MissingLineOut]     # name, substitute (name, amount display, you_have), buy (cost_display, store) | None
    why: list[str]                    # templated from the score components
    score: Decimal                    # kept for the exposure log and debugging

class CookStreamEvent(BaseModel):       # E2 and E18 ("prefetched" only on E18)
    event: Literal["started", "progress", "heartbeat", "results", "prefetched", "result"]
    search_id: int; run_id: int; elapsed_s: float
    stage: str | None = None; message: str | None = None
    suggestions: list[SuggestionOut] | None = None   # "results": the full re-ranked list, replacing the last one;
                                                     # "prefetched": the list as it will look after More ideas,
                                                     # held by the app until you tap (never shown before)
    new_version_ids: list[int] = []
    status: Literal["succeeded", "partial", "failed"] | None = None   # "result" only
    wait_s: int | None = None          # "progress" with stage "waiting": seconds until the call can go (countdown)
    retry_after_s: int | None = None   # "result" with status "partial" after a wait too long for this request
    notes: list[str] = []; problem: ProblemOut | None = None
    llm_call_count: int | None = None; total_tokens: int | None = None

class StepsStreamEvent(BaseModel):     # E19
    event: Literal["started", "progress", "heartbeat", "result"]
    version_id: int; run_id: int | None; elapsed_s: float
    stage: Literal["writing_steps", "waiting", "checking"] | None = None
    wait_s: int | None = None          # stage "waiting": the countdown
    status: Literal["succeeded", "waiting", "failed"] | None = None   # "result": waiting = try at retry_after_s
    retry_after_s: int | None = None
    version: RecipeVersionOut | None = None   # "result" when succeeded: the recipe page payload, with its steps
    problem: ProblemOut | None = None

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
  allowance left, read from Groq's `x-ratelimit-*` headers. The estimate is calibrated from logged calls of the same
  purpose (§15.1).
- **If it doesn't fit** (or Groq replies 429), the call waits, and the stream sends `progress` with stage `waiting` and
  `wait_s`.
- **A wait longer than `LLM_MAX_RATE_WAIT_SECONDS` or the request's time budget** ends the request gracefully: status
  `partial` (`waiting` for a steps request), with everything already found and `retry_after_s`.
- **Calls you're waiting on come first.** The background batch (§14) never starts while a steps call for you is
  running or waiting. When it can't start within the wait limit and the time budget, it is skipped silently: the
  search still ends `succeeded`, and More ideas makes its own call later.
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

**The capped protein reward** (approved 2026-10-10, including the fallback for a target of 0):
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
- **Ideas without steps are full candidates.** An idea has everything the ranking and the solver read (ingredient
  lines, so nutrition and cost; times, equipment, mood, freezer-friendly), so it ranks and plans exactly like a saved
  recipe. Only cooking needs its steps (C8).
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
  results jsonb NULL          -- meal now: the ranked snapshot (version ids, scores, components, card lines),
                              -- plus the held background batch (version ids, shown yet or not)
  status text NN              -- running | done | failed
  created_at timestamptz NN
  IX (user_id, mode, created_at DESC) · IX (user_id, cache_key)

ALTER meal_plan ADD kind text NULL              -- meal_prep | single | grocery_advice; NULL = Phase 1–2 week plans

ALTER recipe_version ADD steps_status text NULL -- NULL = has its steps (every seed, Phase 1 and user version);
                                                -- pending = an idea whose steps are written on first open (F19)
```

- **Ideas are recipe versions** (`created_by = llm`, `prompt_version = recipe_ideas/1`) with their ingredient lines
  and no `recipe_step` rows. The idea's one-line method is stored in `description`, so no other column is needed.
- **Write-once steps (F19):** an idea's steps are inserted exactly once, in the same transaction that sets
  `steps_status` from `pending` to NULL. Nothing else on the version changes, then or later; `content_hash` stays
  the idea's (title, lines, servings), so deduplication works before and after. Every other version stays immutable
  exactly as before.

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
  pairs) and store nothing. Dish categories and prompt short names (§13.5) are computed.

### 13.5 Prompts: generation in two passes

Every 2b flow that writes recipes (meal now, meal prep, swap's "Write a new one", grocery advice with generation on)
does it in two passes. Each call then fits well inside Groq's 8K tokens a minute, and steps are written only for
recipes you open (§15). `POST /plans` (CLI and compatibility) keeps the Phase 1 prompts, `candidate_generation/1`
and `recipe_revision/1`, unchanged (F20).

**Reasoning effort.** Ideas, steps and idea-revision calls use the lowest reasoning effort the configured model
supports, if it has that setting:
- **The value** comes from `LLM_REASONING_EFFORT` (no model names in code). The default, `low`, is the lowest that
  Groq's `openai/gpt-oss-*` models accept. For another model, `.env.example` says to set the lowest value its Groq
  docs list, or leave it empty when the model has no such setting.
- **A rejected value** raises a configuration error that names the variable, as strict mode does.
- **Reasoning tokens count as completion**, so a lower effort directly shrinks each call. The 2b.3b live test
  records the tokens with this setting (§15.1).

**Pass 1: ideas (`recipe_ideas/1`, new).** One call returns 5–8 ideas; code picks the count so the call fits (§15.1).
The output models sit next to `GeneratedRecipe` in `app/schemas/llm_recipe.py`:

```python
class IdeaIngredient(_Strict):
    name: str                         # a short name from INGREDIENTS, exactly as listed
    quantity: float                   # raw, dry or as-sold, for base_servings (build plan §7.8)
    unit: LLMUnit
    role: IngredientRole

class RecipeIdea(_Strict):            # creative content only, like GeneratedRecipe, and no steps
    title: str                        # 3–80 characters
    method: str                       # ≤ 140: "Sear the chicken, simmer with tomato and spices, fold in spinach"
    meal_slots: list[MealSlot]        # 1–3
    mood: RecipeMood
    base_servings: int
    active_minutes: int; total_minutes: int
    equipment: list[Equipment]
    freezer_friendly: bool
    ingredients: list[IdeaIngredient] # 2–20: everything the cooking will use, water, salt and oil included

class RecipeIdeaBatch(_Strict):
    ideas: list[RecipeIdea]           # 1–8
```

- **Compared with `GeneratedRecipe`:** no steps, description, cuisine or flavor tags, and ingredient lines without
  preparation, component or optional. The transport schema is 1,835 characters instead of 3,324.
- **System rules:** today's rules without the step rules (doneness checks, prep and portioning steps, appliance
  temperatures), plus "list every ingredient the cooking will use, including water, salt and oil".
- **Checks:** everything the recipe validator does except the step checks: names, units and the as-sold rule;
  exclusions, held items and caps; equipment and mood; time limits; complete nutrition; the prose filter on the title
  and method.
- **What happens to a passing idea:** it is saved as a recipe version with `steps_status = pending` (§13.4) and gets
  code-computed nutrition and cost. It is then ranked (meal now) or offered to the solver (meal prep, swap, grocery
  advice) like any saved recipe.
- **A failing idea** is dropped, with its reasons logged.
- **Meal now** adds these lines to the request (as approved):
  - **must use:** up to 6 of your items, open packages and soonest-expiring first, then proteins;
  - **may buy:** your could-buy items;
  - **goal hints** as ingredient directions ("favor protein-rich ingredients such as eggs, chicken, Greek yogurt,
    chickpeas"); never as claims, and the prose filter still blocks claims in the output;
  - **avoid** the titles already on screen;
  - a **narrowed vocabulary:** your items, could-buys, Always-have and assume-in-stock staples, plus up to 30 common
    allowed ingredients your stores price (by how often your recipes use them). The never-use list is unchanged.
- **Meal prep, swap and grocery advice** send the slot, mood, minutes, equipment, the lots to use up and the titles
  to avoid, with the full allowed vocabulary (as `candidate_generation/1` does today).

**Short names (compact prompts).** Every prompt names an ingredient by its **short name**, never by a product
description:
- **The rule:** the canonical name up to its first comma or parenthesis, when that text is an alias of the same
  ingredient; otherwise the full canonical name.
- **Examples:** "chicken thigh, boneless skinless" becomes "chicken thigh", and "flour tortilla (Price Rite, 37 g)"
  becomes "flour tortilla". "milk, whole" and "milk, skim" keep their full names, because "milk" alone isn't an alias
  of either.
- **Measured on today's seed data:** 42 of the 51 names with a descriptor get shorter, and the full list drops from
  2,840 to 2,399 characters. No two ingredients share a short name.
- **How it maps back:** a short name is an alias, so the resolver maps it back exactly. It is computed in code
  (`domain/prompt_names.py`), with no data change.

**Pass 2: steps (`recipe_steps/1`, new).** The first time you open an idea (E19), one call writes its steps:

```python
class RecipeSteps(_Strict):
    steps: list[LLMStep]              # 3–30; LLMStep unchanged (section, text, duration, appliance temp, doneness)
```

- **The prompt** carries only the saved idea: title, method, mood, servings, minutes, equipment, and its ingredient
  lines in short names with the stored amounts. It adds the step rules. There is no vocabulary and no never-use list,
  because the ingredients are fixed.
- **Checks:** idea + steps are validated as one `GeneratedRecipe`, so the existing step checks run unchanged:
  - prep and portioning steps are present;
  - each section's equipment is in the idea's equipment;
  - oven and air-fryer steps state a temperature;
  - every ingredient a step uses is on the list, and doneness checks resolve;
  - the prose filter passes; then the food-safety lines are injected.
- **A failure** retries with the errors (rule 5, `LLM_MAX_ATTEMPTS`, short replies only, as since Phase 1).
- **The card's numbers never change,** because the steps can't add or change an ingredient, an amount, the
  equipment or the times.
- **Passing steps are saved with the recipe once** (F19). A second open, another device, Cook this and cooking mode
  make 0 calls. Seed recipes, Phase 1 recipes and anything saved with steps never call it.
- **One call per recipe at a time:** a second request for the same idea waits for the first one's result.

**Revisions (`idea_revision/1`, new).** It replaces `recipe_revision/1` in the 2b flows, and runs only when **no**
idea in a batch passes. It sends at most 3 failed ideas with their errors, so the call stays short.

**Background batch (meal now).** See the gap rule (§14).

### 13.6 Progress stages

| Friendly step | Server stages (real) | Notes |
|---|---|---|
| Checking your pantry | `constraints` (settings, diet, inventory, toggles, extras) | — |
| Finding recipes | `candidates`, `generating`, `waiting` | Meal now: `results` events arrive here. `waiting` carries `wait_s` and shows the countdown wait state, never an error |
| Balancing calories across the days | `solving`, `re-solving` | Meal prep, swap, grocery advice |
| Pricing your groceries | **`pricing`** (new): practical rounding, package absorption, packages, store choice, costs | Emitted after the solve, before `build_rounded_plan` |
| Double-checking every number | `validating` | Moves after `pricing` (today it is emitted before rounding) |
| *(nothing shown)* | `prefetching` (E18 only) | The background batch (§14), after a More ideas tap's `results`; More ideas reads "Writing…" while it runs |
| Steps section on C8 | `writing_steps`, `waiting`, `checking` (E19) | "Writing the steps for this one…"; `waiting` shows the countdown |

### 13.7 Logging for the future ranker

- **Exposures:** meal-now searches log every offered and filtered recipe in `plan_candidate` under a `generation_run`
  with purpose `meal_now`. Swaps log under `swap` and grocery advice under `grocery_advice`. Failed runs log nothing
  (D42 unchanged).
- **The background batch** is logged as exposures only when More ideas shows it (it was never offered before). Its
  ideas are saved and join the pool either way.
- **Steps calls** run under a `generation_run` with purpose `recipe_steps`. They change no exposure.
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
   - *As built in 2b.3a (BUILD_PLAN D66–D68):* "same role" means your recipes use the item in that role;
     seasoning, garnish and "other" lines get no pantry substitute; each item stands in for one line at most.
     A line you have some of is **short**: it shows as "(some)" with a top-up purchase and counts half toward
     pantry fit. With an empty pantry, the gap rule's good match is any recipe that passes the filters.
   - *Changed at the 2b.3a approval (BUILD_PLAN J2, built in 2b.4):* a vegetable or herb is swapped only for
     another member of its **culinary group** (onions and scallions, leafy cooking greens, sturdy green vegetables,
     sweet peppers…; seed data `pantry_catalog.json`, listed in `docs/review/pantry_catalog.md`), whatever role the
     line plays; one in no group, or alone in its group, gets no substitute. A yellow onion never becomes spinach.
     Accepted pairs still apply first.
5. **Score** = a weighted sum of components normalized across the eligible pool (initial weights, tuned with golden
   tests in step 2b.3a):

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
   they rank only on neutral grounds (§7.4). *As built (BUILD_PLAN D65):* bonuses are zero, and the penalty terms
   (missing, could buy, the Cheap cost term) take the pool's worst value, since a zero penalty would be an
   advantage.
6. **Sort** by score, then fewer missing items, then version id. Cards carry the components as "why" chips.

**Gap rule for new ideas:**
- A **good match** passes the filters, is in your mood (M10) and, if your pantry isn't empty, uses at least one of
  your items as its protein or carb with at most 2 missing items that have no substitute.
- With fewer than **6** good matches (M14, was 3: every search aims for 6–8 options), one **ideas call** writes 5–8
  ideas (§13.5). The ones that pass the checks are saved, scored by the same function and streamed into the list as
  soon as the call returns. Their steps are written later, when you open one.
- With 6 or more good matches, nothing is written (Q8 holds).
- A search never starts a background batch, whether or not it wrote ideas.

**The background batch** (so later More ideas taps are usually instant; F21):
- **When:** only after your **first More ideas tap** in a search. That tap makes its own ideas call and waits
  normally (the strip, or the countdown). Once its results are sent, the same stream stays open and writes the next
  batch when the per-minute allowance has room. That is typically 50–60 s after the tap's call (§15.1); the
  request's 180 s budget covers it.
- **Held, not shown:** the batch goes through the same checks and is saved, then sent as a `prefetched` event that the
  app keeps until your next More ideas tap (E18). That tap shows it, logs those exposures, and writes the following
  batch the same way.
- **No revision:** a background batch in which no idea passes is dropped silently, with no `idea_revision/1` call.
- **It yields:**
  - it never starts while a steps call for you is running or waiting, because opening a recipe comes first;
  - it is skipped, silently, when it can't start within `LLM_MAX_RATE_WAIT_SECONDS` and the time budget, or when it
    would leave less than `LLM_PREFETCH_DAILY_RESERVE` (30,000 tokens) of the daily guard for calls you ask for.
- **Nothing is wasted:** an unshown batch's ideas stay in the pool for later searches, meal prep and swaps.
- **If you leave the screen** before it lands, a call already running may be cut off with the request. Ideas already
  saved stay saved.

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

### 15.1 Limits, and what one call costs

**Limits** (build plan §7.6). Groq's free tier for the strict-output models allows:
- **8K tokens a minute**;
- 200K tokens a day (the app's own guard, `LLM_DAILY_TOKEN_BUDGET`, stops at 150K);
- 30 requests a minute and 1K a day.

Groq also seems to check each request's prompt **plus its maximum completion** against the minute's limit: the
Phase 1 HTTP 413 was for 11.4K "requested" tokens. So every call keeps its prompt estimate + `max_completion_tokens`
at or under 95% of the limit read from the headers, with a per-purpose maximum completion. The 2b.3b live test
confirms this.

**Why two stages.** One Phase 1 call wrote 2 complete recipes for ≈ 7.7K tokens, about a whole minute's allowance.
An idea is about a third of a full recipe's output, because it has no steps. So one call now brings 5–8 options, and
steps are written only for the recipes you open.

**What a call costs.** The Phase 1 live run measured a 2-recipe batch at **≈ 5.9K prompt + ≈ 1.8K completion**.
- **What we send:** by character count, the text explains only about 2.4K of that prompt. Measured today: system
  rules 1,649 characters, response schema 3,324, ingredient list 2,840, and the request about 600.
- **The rest, ≈ 3.5K,** is how Groq frames the request. It may be the structured-output schema being counted in an
  expanded form, which would shrink with the smaller ideas schema. Splitting it needs a live call, so the table gives
  two cases:
  - **Cautious** (used for planning): that ≈ 3.5K is a fixed cost on every call.
  - **If it scales:** it grows with what we send, so the prompt is ≈ 2.45 × our text.
- **Reasoning effort:** the Phase 1 run already used `low`, so its 1.8K completion includes low-effort reasoning.
  Ideas and steps calls use the lowest effort the model supports (§13.5), which is `low` for the current model.

| Call | Prompt, cautious (if it scales) | Completion | **Total, cautious** | Total, if it scales |
|---|---|---|---|---|
| Phase 1 batch: 2 full recipes (measured) | 5.9K | 1.8K | **7.7K** | 7.7K |
| Ideas, meal now: 6 ideas, ≈ 70 short names (≈ 900 characters instead of 2,840) | ≈ 5.0K (3.8K) | ≈ 1.8K (≈ 0.3K an idea) | **≈ 6.8K** | ≈ 5.6K |
| Ideas, meal prep / swap / grocery advice: 6 ideas, every allowed short name | ≈ 5.3K (4.5K) | ≈ 1.8K | **≈ 7.1K** | ≈ 6.3K |
| Steps for one recipe | ≈ 4.2K (1.7K) | ≈ 0.6K | **≈ 4.8K** | ≈ 2.3K |
| Idea revision (only when no idea in a batch passes) | ≈ 5.5K (4.6K) | ≈ 0.9K | **≈ 6.4K** | ≈ 5.5K |

- **Ideas per call:** code picks the largest count from 8 down to 5 for which the prompt estimate + count × 360 + 300
  (reasoning) fits in 95% of the minute's limit (330 before the live test). With the measured prompts that is
  always 8. If even 5 don't fit, no call is made.
- **Calibrated estimates:** the pacer and the daily guard estimate a call from its characters, messages and schema
  together (`CHARS_PER_TOKEN = 4`), scaled by the median ratio of real to estimated prompt tokens over the last 20
  logged calls of the same purpose (1.2 until five are logged; 2.5 before the live test showed 1.03–1.11), so
  predicted waits match Groq's.
- *The table above is the plan made before the live test; the measured calls are in the findings below.*
- **Timing:** a call with ≈ 1.8K of completion took 10–20 s in Phase 1. Groq refills the minute's allowance
  continuously (Phase 1's retry-after times were 7–39 s). So right after an ideas call, a steps call waits about
  15–30 s (cautious) or 5–15 s (if it scales), and the next ideas call (the background batch) about 50–60 s.

**The 2b.3b live test** (opt-in, about 4 calls, ≈ 25K tokens, a few minutes of pacing) records what is still
estimated here:
1. **Tokens per call** for one ideas call and one steps call, with the reasoning effort used.
2. **Whether the ≈ 3.5K shrinks with the smaller ideas schema:**
   - the same ideas messages are sent twice, once with the ideas schema and once in plain JSON mode with no schema;
     the difference in Groq's reported prompt tokens is what the schema costs;
   - this is compared with the Phase 1 batch (full schema) and the steps call (smallest schema);
   - if the model doesn't accept plain JSON mode, the three schema sizes against their prompt tokens show the trend
     instead.
3. **Whether Groq counts the maximum completion** in its per-minute check.

**Live findings (2b.3b, 2026-10-11).** `openai/gpt-oss-120b`, strict mode, reasoning effort `low` on every call;
two runs, the second after the fixes below. Measured in the second run:

| Call | Schema (characters) | Prompt | Completion | Total | What happened |
|---|---|---|---|---|---|
| Phase 1 batch: 2 full recipes | 3,324 | 2,428 | 1,709 | 4,137 | attempt 1 rejected by Groq (`json_validate_failed`, no usage reported); attempt 2 passed |
| Ideas: 8 asked, meal now | 1,947 | 1,533 | 3,117 | 4,650 | strict mode rejected the reply over one idea; the 7 valid ideas were kept (no retry), 5 passed the checks |
| The same ideas messages, plain JSON mode | none | 1,014 | 700 | – | the schema costs **519** tokens |
| Steps for one idea | 1,034 | 710 | 526 | 1,236 | passed on the first attempt |
| Probe: a 114-token prompt with a maximum completion of 8,000 (limit 8,000) | none | 114 | 28 | – | accepted |

1. **The ≈ 3.5K doesn't exist.** Every prompt is about (our text + the schema's JSON) ÷ 4 × 1.03–1.11, plus
   40–80 tokens of framing. The schema is counted at about its JSON size (519 tokens for 1,947 characters), so the
   three schema sizes (3,324 / 1,947 / 1,034 characters) track their prompts with no fixed overhead. Phase 1's
   5.9K isn't reproduced: today's Phase 1 batch prompt is 2.4K. The first run today showed where big prompts come
   from: a retry that re-sent the provider's whole error, failed reply included (4,445 tokens; fixed: retries now
   carry only the schema rule that failed).
2. **Groq doesn't count the maximum completion** against the minute: the probe asked for 8,114 tokens against
   an 8,000 limit and went through. The Phase 1 HTTP 413 was the oversized prompt of that retry. The pacer still
   checks prompt + maximum completion (it can only overestimate), and "≤ 95% of the minute" stays as the sizing
   rule for one call.
3. **An idea is about 360 completion tokens** with low reasoning (3,117 for 8), not 330. The count rule now uses
   360: with a 1.5K prompt, 8 ideas fit easily (1,533 + 8 × 360 + 300 ≈ 4.7K of 7.6K). Even 5 always fit.
4. **Strict mode still rejects about half the schema replies** (Phase 1 attempt 1 in both runs, the ideas call
   in both runs; one model listed "pot" as equipment). Two fixes: a rejected ideas batch keeps the ideas that
   validate on their own (the rest are dropped and logged, like ideas that fail the checks), and the ideas rules
   say pots and pans aren't equipment and fresh herbs go in grams.
5. **Calibration** starts at 1.2 (measured 1.03–1.11) instead of 2.5 until five calls of a purpose are logged.

**Ideas model comparison (2026-10-11, BUILD_PLAN P5).** The same meal-now ideas prompt (8 asked, 1,537 prompt
tokens), strict mode, low reasoning, 2 runs per model, alternating:

| Model | Run | Attempts | Latency of the passing call | Tokens | Ideas returned / passed (of 8) |
|---|---|---|---|---|---|
| `openai/gpt-oss-20b` | 1 | 2: both rejected by Groq (`json_validate_failed`, no usage reported); the second reply's valid ideas were kept | – (5.5 s for both) | not reported | 7 / 7 |
| `openai/gpt-oss-120b` | 1 | 1 | 6.9 s | 4,717 | 7 / 7 |
| `openai/gpt-oss-20b` | 2 | 1 | 3.1 s | 4,018 | 8 / 8 |
| `openai/gpt-oss-120b` | 2 | 1 | 7.4 s | 4,580 | 8 / 8 |

20b answered about **2.3× faster** (3.1 s vs 6.9–7.4 s a call; 5.5 s even with a rejected attempt) with the same
share of ideas passing (15 of 16 for each) and fewer completion tokens (2,481 vs 3,043–3,180). Its one rejected run is the same
strict-mode behavior as 120b's (finding 4), and salvage covered it. So the ideas pass (ideas and their revision)
now has its own model, `LLM_IDEAS_MODEL`, which docker compose defaults to `openai/gpt-oss-20b`; steps and planning
stay on `LLM_MODEL`. Groq counts each model's per-minute allowance on its own, and the app paces each model on its
own. The comparison used about 13.3K reported tokens plus the two unreported attempts, well under the 40K cap.

The planning numbers below now use the measured case. The ideas count (8), the background reserve (30K) and the
heavy-day estimate were re-checked against them.

### 15.2 Estimates per flow

Measured case (the 2b.3b live test, §15.1): an ideas call ≈ **4.7K** (1.5K prompt + 3.1K for 8 ideas), a steps
call ≈ **1.2K**, a revision ≈ 4K (estimated: three failed ideas sent back, about half a batch written). The
pre-test cautious figures are in brackets.

| Flow | Calls | Tokens, measured [cautious] | Worst case (capped) |
|---|---|---|---|
| **A meal now: the cards** | **0** when at least 6 saved or seed recipes are good matches (M14; cards in under a second). Otherwise **1** ideas call; its ideas land about 30–40 s after the saved cards (3.1K of completion) | 0, or ≈ 4.7K [6.8K] | 1 ideas call + 1 idea revision ≈ 9K [13K] |
| **More ideas, first tap in a search** | **1** ideas call (waits normally: the strip, or the countdown if the minute is used up), then **+1** background batch once the minute has room (≈ 15 s later) | ≈ 4.7K + 4.7K = 9.4K [13.6K] | 1 ideas call + 1 revision, then the background batch (never revised) ≈ 14K [20K] |
| **More ideas, later taps** | **0** before the cards when the held batch is ready (instant); otherwise 1 ideas call. Then **+1** background batch | ≈ 4.7K [6.8K] per tap | As the first tap |
| **Opening a new idea** | **1** steps call, the first time only. **0** for seed and saved recipes and every later open | ≈ 1.2K [4.8K] | 3 attempts (rule 5) ≈ 4K [14K] |
| **Meal prep** (5 lunches, or lunch + dinner Mon–Fri) | **0** with today's library: the lunch and dinner seeds cover a slot for up to 5 days each (variety rule) | 0 | One ideas call per uncovered meal slot, ≈ 4.7K [7.1K], each bringing 5–8 options instead of 2–3. Plus targeted rounds after an infeasible solve: the 180 s budget allows about **3 calls**, ≈ 14K [21K]. Steps only for the new recipes you open, ≈ 1.2K each |
| **Swap one meal** | **0** (other saved recipes fit) | 0 | **Write a new one:** 1 ideas call + at most 1 revision, ≈ 4.7–9K [7.1–13.5K]. Then the swapped-in recipe's steps when you open it, ≈ 1.2K. The call's other ideas join the pool, so the next swap of that meal usually needs no call |
| **What should I buy?** | **0** (generation is off by default) | 0 | As meal prep, if you turn on "include new recipes" |
| **Same as last time, reopening results** | **0** | 0 | 0 when nothing changed; otherwise as the flow |
| NL quick add (unchanged) | 1 per parse | ≈ 1–2K | 3 attempts |

**Days.**
- **A typical day:** one meal-now search that writes ideas, with one new idea opened and no More ideas:
  4.7 + 1.2 ≈ **6K** [11.6K], about 4% of the daily guard. Meal prep from the saved pool adds 0.
- **With the 6-match rule (M14)** more searches write ideas, mostly in the first weeks: a slot and mood needs 6 good
  matches before searches stop calling. A day of 3 searches that each write ideas and open one new idea each is
  3 × 5.9 ≈ **18K** [35K], about 12% of the guard.
- **A heavy day** (5 meal-now searches that each write ideas, 1 meal prep with one uncovered slot, 2 swaps from the
  pool), opening one new idea per search and both new meal-prep recipes: 5 × (4.7 + 1.2) + 4.7 + 2 × 1.2 ≈
  **37K** [75K], about 25% of the guard.
- **Each More ideas session costs extra:** a first tap and one later tap add ≈ 14K [20.4K]: the first tap's call,
  the batch held for the second tap, and the next batch written after it (it stays in the pool if you stop there).
  A heavy day with two such sessions is ≈ 65K [116K], about 43% of the guard.
- **The extras go first:** background batches stop when less than 30K of the daily guard would remain, so calls you
  ask for keep the rest. Re-checked with the measured numbers: 30K is still about six searches' worth (ideas and
  one steps call each). When the guard can't afford a call you asked for, flows fall back to saved recipes with a
  note (§15.3, item 8).
- **The pool grows fast:** each ideas call adds 5–8 saved recipes, so later searches more often find 6 good matches
  and make no call at all.
- **Per minute:** one ideas call uses about 4.7K of the 8K. A new idea opened right after it usually goes at once
  (1.2K more); the next ideas call (the background batch, or a quick second More ideas tap) waits about 15 s by the
  pacer's cautious check (prompt + maximum completion). A wait shows the friendly countdown (5.5), never an error.
  Requests per minute and per day never bind first.

### 15.3 What is cached or reused

1. **Every validated recipe is saved** and joins the pool for all flows (rule 7). Ideas written for one search become
   saved candidates for the next, so repeated pantries rarely need new calls.
2. **Search results** (`cook_search`) are keyed by answers + resolved dates + pantry snapshot + settings + recipe-pool
   version + price version. A repeat with nothing changed (Same as last time, reopening results, coming back to the
   tab) returns the stored result with 0 calls and no re-solve.
3. **The gap rule:** meal now generates only when the saved pool is thin; meal prep only for uncovered meal slots
   (existing `gap_analysis`). Each call now brings 5–8 ideas instead of 2–3 recipes.
4. **Steps are cached with the recipe** (written once, F19). Seed, Phase 1 and saved recipes never need a steps call,
   a recipe's second open makes none, and ideas you never open never cost one.
5. **Substitutes** are deterministic in 2b (accepted pairs + pantry items with the same role), so 0 calls. Phase 3's
   LLM substitution engine keeps its per-ingredient cache.
6. **Swaps** remember the recipes already swapped away for that meal, so repeated taps cycle through saved options
   instead of asking the LLM. The unused ideas from a "Write a new one" call are among them.
7. **Grocery advice** has LLM off by default and plans from the saved pool.
8. **The daily token guard:** when it can't afford another call, flows fall back to saved recipes with a note, never
   an error. The background batch keeps a 30K reserve (§14), so it stops before calls you ask for do.

---

## 16. Changes to earlier decisions (all approved 2026-10-10)

You approved all 18 changes on 2026-10-10, with the protein reward in F3 capped at 1.5 × the daily target. F19–F21
come from the two-stage generation you asked for later that day (table below this one). You approved F19 and F20 as
written, and F21 with the background batch starting only after the first More ideas tap.

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

**Added with two-stage generation (2026-10-10):**

| # | Earlier decision | Change | Why |
|---|---|---|---|
| F19 | Recipe versions are immutable once written (build plan §2 item 10, §4.4) | An idea is saved as a version **without steps** (`steps_status = pending`) and gets its steps **exactly once**, on first open. Nothing else on it ever changes, and every other version stays immutable. A user edit still creates a new version (CLAUDE.md) | Steps only for recipes you open, "cached with the recipe" |
| F20 | Meal prep, swap and grocery advice write recipes with `candidate_generation/1` (2–3 complete recipes a call), revised with `recipe_revision/1` (§13.5 as first approved) | They use the ideas pass (`recipe_ideas/1`, 5–8 a call), `idea_revision/1`, and steps on first open. `POST /plans` (CLI and compatibility) keeps the Phase 1 prompts and complete recipes unchanged | More options per call under 8K a minute, and one generation path for the new flows |
| F21 | More ideas is one LLM call when you tap it (`more_ideas: true` in `CookAnswers`) | **Tightened as approved:** the first More ideas tap in a search makes one ideas call and waits normally. Only after it does the stream write the next batch in the background, held and shown by the next tap (E18); each later tap starts the following batch. A search itself never starts one, so Q8 still holds. `more_ideas` leaves `CookAnswers` | Later More ideas taps are usually instant, and you pay for background batches only once you've asked for more |

Unchanged on purpose: the variety rule (Q14: at most 5 portions of one recipe a week for meals, never twice a day).
A user-editable variety cap stays deferred (your carried decision). The one exception is F22 below.

**Added at the 2b.2 approval (2026-10-10, BUILD_PLAN H5):**

| # | Earlier decision | Change | Why |
|---|---|---|---|
| F22 | Q14: at most 5 portions of one recipe a week for meals | **Same dish, many portions** (C1b) overrides the 5-portion cap for that request: one recipe scaled to any number of portions. Every other request keeps Q14 | You asked for one dish for many portions (e.g. 8) |

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
| Q8 | **Meal now** writes new ideas automatically only when fewer than 3 saved recipes fit well (plus More ideas)? | **Yes.** The background batch (F21) keeps this: it starts only after your first More ideas tap. **Changed 2026-10-10 (M14):** fewer than 6 |
| Q9 | **Phase 2 approval?** | **Approved 2026-10-10** |
| Q10 | **CLAUDE.md** phase outline update? | **Yes**; applied with the BUILD_PLAN §11 item 7 wording |
