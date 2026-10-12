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
**Recorded at the 2b.3b pre-work approval (2026-10-11), to build later:** the batch view, "cook once, eat many"
(C6, for 2b.7), and a **Not for me** action separate from Swap (C6, C8, S0, for 2b.6 and 2b.7); changes F23 and
F24 (§16). Meal prep's engine (2b.5) already returns what the batch view needs: each batch's portions with
fridge and freezer counts, each meal's source line, the thaw notes, and the Prep notes items.
**Designs for your review (2026-10-11, at the 2b.5 approval; nothing built):** smart prep, "Cook basics, mix and
match", a fifth meal-prep option where a few prep items combine into the week's meals (§19), and parallel cooking
on a cook day, a real schedule of hands-on and hands-off work per piece of equipment (§20). The proposed build
order, the token impact and the open questions are in §21; the earlier decisions they would change are F25–F32
(§16, proposed). The ideas pass now carries an optional freeze note (§13.5, built).
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
| 19 | Smart prep: "Cook basics, mix and match" (design for review) |
| 20 | Parallel cooking on a cook day (design for review) |
| 21 | Build order, LLM tokens and open questions for §19–§20 |

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

*As built (2b.7, D164):* "By days" is a day count (1–14) from the start day rather than chips for 14 days, since a
plan's days are consecutive; Starting offers the next 7 days as chips (Today, Tomorrow, Wed 14 …).

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

*Proposed fifth tile (design for review, §19):* **Cook basics, mix and match** ("Make a few basics and combine them
all week"): a few prep items cooked on as few of your cook days as fit, combined into every meal.

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
    rice · 2. Sheet-pan chicken in the oven · 3. Make the curry while both cook". *(Proposed: the cook-day timeline
    replaces the prep order, §20.4, F30.)*
  - **Day note:** "Cook: Chicken over rice (5 portions)" on a cook day, or **"Nothing to cook, eating prepped
    meals"** on a day with nothing to cook (replaces "Cook day · 0 min hands-on").
  - **Shopping day:** its freeze steps are listed on that day too ("Freeze 1 pack of chicken thighs today"), not
    only in Prep notes.
  - **Fridge and freezer per day:** each meal row says where its portion is ("from the fridge", "from the
    freezer"), and the day before a freezer meal says "Thaw tomorrow's lunch in the fridge tonight" (C1b).
  - **Meal row:** icon · meal label · name · "520 kcal · 38 g protein" · badges ("from the freezer: thaw Fri night",
    "Draft") · **⇄ Swap** (44 px).
- **Batch view, "cook once, eat many"** (recorded 2026-10-11 for 2b.7, F23):
  - Each cook day lists every batch with its portion count and where each portion goes, e.g. "Cook Air-fryer
    chicken over rice ×4 → Mon lunch, Tue dinner, Wed lunch, Sat dinner (1 to the freezer)".
  - Each meal row shows its source: "cooked Mon", or "from freezer, cooked Mon, thaw Fri night" (the API's
    `source_display`, 2b.5).
  - "Left out" recipe notes and freeze notes never appear as a block in the plan view: they go behind the Prep
    notes row or an **About this plan** tap.
- **Not for me** (recorded 2026-10-11 for 2b.6 and 2b.7, F24), on recipe pages (C8) and meal rows, separate from
  Swap: it hides that recipe from all future suggestions and plans, logs a feedback event, and can be undone from a
  **Hidden recipes** list in Settings (S0). Swap still replaces just one meal. *Built in 2b.7 (Z5): `recipe_hidden`
  (migration 0010), `PUT`/`DELETE /recipes/{id}/hidden`, `GET /recipes/hidden`; plans already made keep the meal;
  Undo right after, or Show again in Settings.*
- **Shopping list view:** the plan's grocery list exactly as on the Grocery tab (store groups, stock-up section,
  "check you have", unpriced), read-only here, with **Open in Grocery** to check things off.
- **Bottom bar:** **Use this plan** on a draft, "This is your current plan ✓" on the active one.
- **As built (2b.7, D161–D167):**
  - The Prep notes row also holds the plan's own notes and warnings (recipes left out, not proven best) under
    **About this plan** in the same sheet: "3 to freeze · 4 may spoil · About this plan". Nothing about freezing,
    spoiling or left-out recipes sits above the days.
  - A cook day shows "Cook · about 1 h start to finish · 35 min hands-on", each batch as "Cook Chicken over rice ×4"
    with "→ Mon lunch, Tue dinner, Sat dinner (1 to the freezer)" from the API, its freeze-today lines, and the
    timeline behind a tap with **Start cooking** (the cook-day cooking mode).
  - An assembled meal's row lists its items ("1 portion chicken curry · ½ portion rice") and its instruction, and
    opens the assembly's page.
  - Each meal row has a ⋯ beside it, opening a sheet with **Not for me** (Swap joins it in 2b.6).

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
| Cooking | Cook days · Time per cook day · Weeknight time (finishing prepped meals, V7; 2b.7) · Mood per cook day · Kitchen equipment · Fridge days for leftovers |
| Shopping | Stores and their order · Separate-store trip only if it saves at least $5 |
| Diet | Beef (locked) · Held items · Frequency caps (pork ≤ 1 a week, any other caps) · Daily caps · Excluded and disliked ingredients · **Hidden recipes** (Not for me, F24; 2b.7) |
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

**Migration `0007_recipe_freeze_note`** (step 2b.5, decided at the 2b.3b pre-work approval):

```
ALTER recipe_version ADD freeze_note text NULL  -- how to freeze a recipe that freezes well: "Freeze the chicken
                                                -- and rice; make the yogurt sauce fresh" (seeds now; your versions
                                                -- and generated recipes can carry one too)
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
    freeze_note: str | None           # added at the 2b.5 approval: the seeds' rules (5–200 characters, only
                                      # with freezer_friendly, prose filter); null when there's nothing to say
    ingredients: list[IdeaIngredient] # 2–20: everything the cooking will use, water, salt and oil included

class RecipeIdeaBatch(_Strict):
    ideas: list[RecipeIdea]           # 1–8
```

- **The freeze note (built at the 2b.5 approval, BUILD_PLAN D127):** the rules say when a dish freezes well (rice
  dishes, curries, gravies, cooked meats yes; mostly fresh, raw or creamy dishes no) and, when part of it is best
  fresh, to say what to freeze and what to make fresh ("Freeze the chicken and rice; make the yogurt sauce fresh").
  A note on a recipe that doesn't freeze well fails that idea (salvage keeps the others); a storage time in it fails
  the prose filter. A passing idea's note is saved on the version, so plans show it like a seed's. The prompts are
  now `recipe_ideas/2` and `idea_revision/2`.

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

**Recorded at the 2b.3b pre-work approval (2026-10-11), to build later:**

| # | Earlier decision | Change | Why |
|---|---|---|---|
| F23 | C6 lists days and meal rows; freeze and spoil notes collapse into one Prep notes row (H4) | **Batch view (2b.7):** each cook day lists every batch, its portion count and where each portion goes ("×4 → Mon lunch, Tue dinner, Wed lunch, Sat dinner (1 to the freezer)"); each meal row shows its source ("cooked Mon" / "from freezer, cooked Mon, thaw Fri night"); "Left out" notes and freeze notes only behind Prep notes or **About this plan** | "Cook once, eat many" |
| F24 | Swap is the only way to turn down a meal (E5) | **Not for me (2b.6, 2b.7):** on recipe pages and meal rows, separate from Swap; hides that recipe from every future suggestion and plan, logs a feedback event, undone from **Hidden recipes** in Settings. Swap still replaces just one meal | A recipe you never want again shouldn't need a swap every time |

**Added with the smart prep and parallel cooking designs (2026-10-11; approved the same day, BUILD_PLAN X1; §19–§21):**

| # | Earlier decision | Change | Why |
|---|---|---|---|
| F25 | C1b has four cook styles (H5) | A fifth: **Cook basics, mix and match** (`cook_style = "basics"`, §19) | Prep a few things once and combine them all week |
| F26 | A meal is one portion of one batch (build plan §2 item 3; C6) | In smart prep a meal is an **assembly** that draws portions from several prep batches, with **finish tasks** on the eating day that count as that day's time (days that aren't cook days had 0 minutes) | Mix and match; prep that stops at marinated and finishes on the day |
| F27 | A recipe is a whole dish | `recipe_version.kind`: **dish**, **prep item** (stages, each ending in a state) or **assembly** (items + fresh add-ons). Every dish also works as a one-item assembly | Prep items and assemblies reuse versioning, nutrition, costing, ♥, 🔖, ideas and steps-on-first-open |
| F28 | Every batch keeps for the cooked-leftover window (3 days, BUILD_PLAN Q4) | Storage per item **and** stored state from the FoodSafety.gov chart in the repo: raw and marinated proteins use their raw rows (poultry 1 day), cooked food your 3-day window; items the chart doesn't cover follow V1 (§21.3) | Raw marinated chicken doesn't keep like cooked curry |
| F29 | Q14/F22: at most 5 portions of one recipe a week | In smart prep the variety rule is per assembly (at most once a day and 3 times a week, V5); a prep item can feed any number of meals | Feeding many meals is the point of a prep item |
| F30 | C1 (2026-10-08): a cook day's minutes are hands-on minutes, added up; D121: hands-on doesn't grow with batch size; 2b.5's prep order (D122) | A cook day's minutes are **start to finish**, from a real schedule of hands-on and hands-off work per piece of equipment (§20, V11); hands-on grows with batch size, and big batches take extra rounds on their equipment; the **timeline** replaces the prep order | Parallel cooking makes a cook day shorter than its recipes in sequence, and big batches take longer |
| F31 | E19/F19: the steps can't change an idea's ingredients, amounts, equipment or times | Also: the steps' timing fields must match the idea's **tasks**; an idea's active and total minutes are computed by code from its tasks (no longer written by the LLM) | A plan's times never change when the steps arrive |
| F32 | E5: swap replaces one meal's recipe; F24: Not for me hides a recipe | Swap also works on an assembly and on one prep item ("Swap this item"); Not for me also hides an assembly (that combination) or a prep item (and its assemblies) | Smart prep meals are built from parts |

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

---

## 19. Smart prep: "Cook basics, mix and match" (design, approved 2026-10-11)

*Approved 2026-10-11 (BUILD_PLAN X1). The answered questions (V1–V17) are in §21.3, the build steps in BUILD_PLAN §9
(2b.10–2b.12, built in the order of X8), and the earlier decisions it changes are F25–F32 (§16).*

### 19.1 What it is

**The goal.** Prep once, efficiently and safely: each thing you make feeds 2–3 or more meals, nothing spoils, and
every day still meets your calorie and protein targets, your active goals and your caps (the daily protein powder
cap, the pork cap, the budget), with variety across the week.

**Where it lives.** A fifth tile on C1b, **Cook basics, mix and match** ("Make a few basics and combine them all
week"), with day chips for the days you could cook (pre-filled from your cook days). The plan uses as few of them as
fit. C1, C2, C3 and C3b are unchanged.

**An example:** lunch and dinner Monday to Thursday, cooking Sunday, with your 3-day fridge window.

| Sunday you make | Stops at | Feeds |
|---|---|---|
| Chicken curry ×3 | cooked | Mon dinner, Tue dinner; 1 to the freezer for Thu lunch |
| Roasted chicken thighs ×3 | cooked | Mon lunch, Tue lunch, Wed lunch |
| Tandoori-marinated chicken ×2 | marinated, frozen raw | Wed dinner, Thu dinner (thaw the night before, roast on the day) |
| Plain rice ×6 | cooked | Mon lunch, Mon dinner, Tue dinner, Wed lunch, Wed dinner; 1 to the freezer for Thu lunch |
| Roasted vegetables ×2 | cooked | Mon lunch, Wed lunch |

| Meal | Assembly | Eating-day instruction |
|---|---|---|
| Mon lunch, Wed lunch | Roasted chicken over rice with roasted vegetables | Reheat 1 portion chicken, 1 cup rice and 1 portion vegetables |
| Mon dinner, Tue dinner | Chicken curry with rice | Reheat 1 portion curry and 1 cup rice |
| Tue lunch | Roasted chicken wrap with peppers and hot sauce | Warm 1 tortilla; fill with 1 portion chicken, ¼ cup sliced peppers and 1 tbsp hot sauce |
| Wed dinner | Tandoori chicken with rice | Roast the thawed chicken (425°F, 25 min); reheat 1 cup rice |
| Thu lunch | Chicken curry with rice | From the freezer, thawed overnight: reheat 1 portion curry and 1 cup rice |
| Thu dinner | Tandoori chicken wrap with peppers | Roast the thawed chicken (425°F, 25 min); warm 1 tortilla and fill it |

Five items, one cook session, every item in at least two meals, five different meals, no portion past its window.
(Illustrative only; the solver chooses the items, amounts and days.)

### 19.2 The words

- **Prep item:** anything made in bulk and stored: a full dish (chicken curry, roasted chicken, veg pulao), a base
  (plain or flavored rice), a side (roasted veggies, salad, fresh veggies) or a partial prep (a marinade, marinated
  raw chicken, chopped vegetables). There are **no fixed main or side categories**. Code works out what an item
  *brings* (mostly protein, a carb base, vegetables, a sauce) from its lines and nutrition, and uses that only to
  name meals and suggest combinations. A full dish such as curry stands alone or takes a base.
- **Stages and states:** an item's steps are grouped into stages. After each stage it is in a **state**: raw,
  marinated, partly cooked or fully cooked. Prep can **stop after any stage** where storage allows it (§19.4).
- **Finish task:** what's left on the eating day: the remaining stages (roast, air fry) and the last touch (reheat,
  assemble, dress). It counts as that day's hands-on time and is scheduled on that day (§20.3).
- **Assembly:** a meal built from prep items plus fresh **add-ons** (a tortilla, sliced peppers, a spoon of hot
  sauce), e.g. "Roasted chicken over flavored rice".
- **Every dish also works as a prep item:** stored cooked (or as it is stored today) and eaten as a one-item
  assembly; its kind stays `dish`. So smart prep can use the whole library from day one, breakfasts, snacks and
  desserts included.

### 19.3 Data model

Prep items and assemblies are recipe versions, so versioning, nutrition, costing, rounding, ♥, 🔖, Not for me, the
exposure log, ideas and steps-on-first-open all work on them unchanged.

```
-- 0009_smart_prep (proposed; 0008 is the step timing of §20; later phases renumber by two)
ALTER recipe_version ADD kind text NOT NULL DEFAULT 'dish'  -- dish | prep_item | assembly
ALTER recipe_version ADD stages jsonb NULL      -- prep_item: [{"n": 1, "state": "marinated"}, {"n": 2, "state": "cooked"}]
ALTER recipe_version ADD pairs_with text[] NULL -- prep_item: style tags (indian, mexican, mediterranean,
                                                -- east_asian, american, any) for suggesting combinations
ALTER recipe_version ADD label text NULL        -- prep_item: "roasted chicken", for meal names and instructions
ALTER recipe_step   ADD stage smallint NULL     -- prep_item: the stage a step belongs to

assembly_component                              -- an assembly's prep items
  assembly_version_id FK→recipe_version, position smallint,
  component_recipe_id FK→recipe                 -- a lineage: a plan uses its default version when it's built
  portions numeric(3,1) NN                      -- usual portions per person
  min_portions, max_portions numeric(3,1) NN, step numeric(2,1) NN (0.5 or 1)
  PK (assembly_version_id, position)
-- an assembly's add-ons are its own recipe_ingredient rows, per portion (base_servings 1)

ALTER plan_cook_batch ADD stop_stage smallint NULL, ADD stop_state text NULL   -- prep batches
ALTER plan_cook_batch ADD fridge_until date NULL   -- last day a portion may come from the fridge (code, §19.4)
ALTER plan_meal       ADD assembly_version_id bigint NULL FK→recipe_version    -- NULL = a dish meal, as today

plan_meal_component                             -- an assembled meal's portions, one row per prep batch
  id, plan_meal_id FK, cook_batch_id FK, portions numeric(4,1) NN (per person), from_freezer bool NN,
  finish_task_id bigint NULL FK→plan_finish_task

plan_finish_task                                -- eating-day work
  id, meal_plan_id FK, day date NN, cook_batch_id FK, kind text NN (stage | reheat | assemble),
  portions numeric(4,1) NN, hands_on_minutes smallint NN, hands_off_minutes smallint NN,
  equipment text NULL, status text NN DEFAULT 'planned'   -- Done deducts that day's add-ons
```

| | Prep item | Dish (today's recipes) | Assembly |
|---|---|---|---|
| Stored as | `recipe_version`, kind `prep_item`, with stages | kind `dish` | kind `assembly` + `assembly_component` |
| Lines | its ingredients, raw/as-sold, for base servings | the same | its add-ons only, per portion |
| Steps | by stage, with §20's timing | with §20's timing | none: its instruction is composed by code (§19.5) |
| Nutrition and cost | per portion, by code | the same | its items' portions + add-ons, by code |
| In a plan | prep batches (`plan_cook_batch` + stop stage) | batches | `plan_meal` + `plan_meal_component` |
| ♥, 🔖, Not for me, Phase 3 ratings and edits | yes | yes | yes |

- A dish plan (the other four cook styles) is unchanged: one meal, one batch.
- Plans keep exact versions; an assembly's components resolve to their recipes' default versions when a plan is
  built, so your edited curry is used next time.
- Phase 3's `prepared_portion` (what's actually left in your fridge) is unchanged by this; prep batches are what
  the plan expects.

### 19.4 Storage per item and state (code; the LLM never sets these)

Code gives each prep batch a fridge window and a freezer rule from its lines and its stop state, using the
FoodSafety.gov chart already in the repo (`domain/storage_chart.py`) and the existing rules: the short end of the
chart's range, and your 3-day setting for cooked food.

| Stop state | The item has | Fridge window | Freezer | Chart row |
|---|---|---|---|---|
| raw or marinated | poultry pieces | 1 day (1 to 2 days) | yes, the same day; thaw in the fridge the night before its finish day | Fresh poultry, pieces |
| raw or marinated | ground meat or poultry | 1 day (1 to 2 days) | yes | Hamburger, ground meats and ground poultry |
| raw or marinated | fin fish | 1 day (1 to 3 days) | yes | Fin fish |
| raw or marinated | shrimp | 3 days (3 to 5 days) | yes | Shellfish: shrimp |
| raw or marinated | pork chops or roasts | 3 days (3 to 5 days) | yes | Fresh beef, veal, lamb and pork: chops |
| partly cooked | meat, poultry, fish or eggs | **not stored**: finished the same day (V2) | no | — |
| fully cooked | meat or poultry (curry, roasted chicken) | your 3 days (3 to 4 days) | only if it freezes well | Leftovers: cooked meat or poultry; Soups and stews |
| fully cooked | an egg dish | 3 days (3 to 4 days) | only if it freezes well | Casseroles with eggs |
| fully cooked | hard-cooked eggs | 7 days (1 week) | no ("Do not freeze") | Hard-cooked eggs |
| fully cooked | fish; shellfish | your 3 days (3 to 4 days) | only if it freezes well | **FoodKeeper** 148 Cooked fish; 162 Cooked shellfish (built in 2b.10) |
| fully cooked | no meat, fish or eggs (plain rice, veg pulao, roasted vegetables, dal) | your 3 days (3 to 4 days), as every cooked recipe today | only if it freezes well | **FoodKeeper** 174 Leftovers without meat, fish, poultry, or egg; plus 178 Cooked rice (4 to 6 days), 177 Cooked pasta (3 to 5) or 426 Quinoa, cooked (6 to 7) when it's only that grain (V1, built in 2b.10) |
| partly cooked | no meat, fish or eggs (par-boiled potatoes) | your 3 days | only if it freezes well | **FoodKeeper** 174, as cooked vegetables (2b.10) |
| raw or marinated | eggs beaten into a mixture | 2 days (2 to 4 days) | yes | Raw egg whites and yolks (2b.10) |
| raw, ready to eat | cut vegetables, salad, a yogurt sauce | made on the eating day as a 5-minute finish task: **FoodKeeper has no row either** (checked against every Product row, 2026-10-11) | no | — |
| as bought | whole produce, tortillas | the ingredient's own shelf life (seed data, D38) | — | — |

- **The strictest line wins:** a curry with shrimp takes the shorter of its rows.
- **Nothing is planned past its window.** A later meal can use the item only from the freezer, only if that stage
  freezes well (a cooked item: its freezes-well flag; raw or marinated meat, poultry or fish: the chart lists a
  freezer time), with "thaw in the fridge the night before".
- **Fresh items are eaten early:** the windows force it, and a small objective term prefers eating the
  shortest-window items first when there's a choice.
- **Safety lines are injected as today:** the safe internal temperature on the stage that cooks a protein (on the
  eating day when it's a finish task), and "reheat to 165°F" on every reheat.
- Raw ingredients bought on shopping day keep today's rule: what isn't prepped within its window is frozen on
  shopping day.

- **As built (2b.10):** `domain/prep_storage.py`, with the FoodKeeper rows in `domain/foodkeeper.py` (each cited by
  its Product ID, checked against `docs/sources/foodkeeper.json` by a test). A dish used as a prep item keeps as
  every dish does today (your leftover days, frozen when it freezes well). A raw item whose protein has no raw row
  (canned tuna in a salad) is made on the day too.

### 19.5 Assemblies: names and short instructions

**Names** are composed by code from each item's label and what it brings. An LLM-written assembly may carry its own
title (prose-filtered); otherwise it gets the composed name.

| Shape | Name | Example |
|---|---|---|
| a dish alone | its title | Chicken curry |
| a dish + a base | "{dish} with {base}" | Chicken curry with rice |
| protein + base (+ vegetables) | "{protein} over {base}" (+ "with {vegetables}") | Roasted chicken over flavored rice with roasted veggies |
| protein + vegetables | "{protein} with {vegetables}" | Roasted chicken with fresh veggies |
| with a flatbread add-on | "{protein} wrap with {add-ons}" | Roasted chicken wrap with peppers and hot sauce |
| plus a side | "… and a side {side}" | Chicken curry with rice and a side salad |

**Short instructions** per meal, from templates: amounts from code, appliance temperatures and times from the item's
tasks (§20.1), safety lines injected. The LLM writes none of this text.

| Component state | Instruction |
|---|---|
| cooked, from the fridge | "Reheat 1 portion curry and 1 cup rice." |
| from the freezer | "From the freezer, thawed overnight in the fridge: reheat 1 portion curry and 1 cup rice." |
| a finish stage | "Roast the marinated chicken: 425°F for 25 min, until it reaches 165°F. Reheat 1 cup rice." |
| add-ons | "Warm 1 tortilla; fill with 1 portion roasted chicken, ¼ cup sliced peppers and 1 tbsp hot sauce." |
| a fresh item made on the day | "Chop the salad (5 min) and add it cold." |

Amounts are portions of each item ("1 portion curry", "½ portion rice"); cups only where a reviewed cooked-volume
factor exists (V3).

**As built (2b.10)**, in `domain/assembly_text.py`:
- What an item brings is weighed in grams by its lines' roles (seasoning, fat, garnish and water left out):
  protein lines at least 25% bring protein, and with vegetables and sauce at least 40% it is a whole dish; a
  sauce is at least 35% sauce or dairy; a base at least 50% carbohydrate lines.
- Two shapes the table didn't have: a base that isn't a grain (roasted root vegetables) goes "with", not "over";
  a dish with a flatbread is "Chicken curry with flour tortillas", not a wrap.
- Every reheat says "to 165°F"; a dish with no cooking at all (overnight oats) says "Serve 1 portion … cold".
- No item has a reviewed cooked-volume factor yet, so every amount is in portions.

### 19.5a As built: the seed drafts (2b.10)

20 draft prep items and 12 draft assemblies, listed with their stages, storage and numbers in
`docs/review/prep_items.md`. The item and assembly names are the ones in that file.

### 19.6 Seed recipes → prep items

1. **All 47 seeds stay dishes,** each usable as a one-item assembly with today's numbers.
2. **New draft prep items, split from the lunch and dinner seeds** along their ingredient `component` tags (31 seeds
   tag components today: chicken, rice, sauce, salad, gravy, beans, …). About 16–20 items, for example: spiced
   seared chicken thighs and broth rice (1a), air-fryer chicken (1b), sheet-pan chicken and peppers (1c), chicken
   curry gravy (2a, 2b, 2c), tandoori drumsticks that can stop at marinated or cooked (8d), dal (7f), roasted root
   vegetables (8i), black beans (7c), quinoa (8l), plain rice.
   - Lines without a component (salt, garlic, lemon) are assigned by hand; each item keeps its seed's base
     servings.
   - Each item's steps are adapted from its seed's steps, grouped into stages and tagged with §20's timing.
   - Its family is the seed's family, and its draft note names the seed it came from.
3. **About 10 draft assemblies,** including wraps and bowls (tortillas are add-ons, never prep items).
4. Nutrition and cost by code. The full list goes in the step summary for your review, like M13's drafts. No pork
   component (CLAUDE.md).

### 19.7 The solver

A second model, `planning/smart/`, next to today's. The supply side (purchases, packages, inventory, stores, the
budget, waste: today's `solver/model.py` from "ingredient supply" on) is factored out into `solver/supply.py`
unchanged, and both models use it.

**Decisions**
- **Prep batches:** (item, cook day, stop stage), a yes/no and a yield in portions (whole, or half for items that
  allow half portions).
- **Meals:** each (day, meal) picks one assembly, and each of its items gets a portion count within the assembly's
  range (half or whole steps). The portion count of the base is the main lever for calories, much as people meal-prep:
  protein fixed, rice to taste.
- **Draws:** the portions a meal takes from each batch, from the fridge (only within the batch's window) or from
  its freezer share (only for stages that freeze).
- **Finish tasks:** one per (batch, eating day) when a meal that day draws from a batch stopped before its last stage
  (both portions roast together), and a reheat or assemble task per meal.
- **Cook sessions:** a yes/no per cook day.

**Hard limits**
- Every meal filled once; its portions drawn exactly; each batch's yield = its draws + its frozen extras, so no
  cooked food is left over to spoil.
- Windows and freezer rules (§19.4).
- Each prep batch feeds at least 2 meals (V4), whatever state it stops in.
- Variety: an assembly at most once a day and 3 times a week (V5).
- Calories and protein per day (strict or weekly mode, as today), the capped protein reward, daily amount caps,
  frequency caps per Monday–Sunday week (a meal counts when any of its items has a member), the purchase limit,
  "Use what I have", household size.
- Time: each cook day's schedule (§20.3); each eating day's finish tasks within that day's finish time (V7).
- Equipment and mood per cook day, from each stage's tasks.

**Objective** (maximized, in today's plan points; weights V6)
- minus **effort**: cook sessions (20 min each) + cook-day hands-on minutes + 1.5 × eating-day hands-on minutes;
- minus cost, waste and the slot-calorie deviation, as today;
- minus a variety penalty for each repeat of an assembly, plus a small reward for a third or later use of an item;
- plus your goals (the High protein reward up to its cap, nutrition priorities), ♥ on items or assemblies, and
  never-favored rules for pork components (unchanged).

**Size and speed.** An 8-meal plan with 12 shortlisted items (1–2 stop stages each, up to 3 cook days) and up to
30 assemblies is roughly 300–400 yes/no variables, 100 integers and 600 continuous ones: about today's weekly model
with its shortlist (a default week in about 6 s). The shortlist picks items by what they bring and how they pair;
assemblies come only from shortlisted items (seed assemblies, ideas, and code's own combinations of compatible
items: one item that brings protein, at most one base, at most one vegetable item). Target under 10 s; the K6 rules
hold (small instances, no wall-clock dependence in tests); the 30 s limit is unchanged.

**Rounding and checking.** Each prep batch is rounded like a recipe batch (practical amounts, packages) and its
per-portion nutrition recomputed on the rounded amounts; each meal's numbers are its portions of those rounded items
plus its add-ons. The validator checks that rounded plan:
- every existing check (calories, protein, caps, exclusions, equipment, money, safety lines, prose);
- draws within each batch's window for its stop state, and frozen draws only from stages that freeze;
- no stored partly cooked protein;
- yields equal draws + frozen extras;
- at least 2 uses per prep batch;
- finish tasks within their days.

The re-solve loop tightens per item as it does per recipe today.

### 19.8 The LLM ideas pass for prep items and assemblies

When the pool can't make a plan, or a meal has fewer than 3 workable assemblies, one `prep_ideas/1` call asks for
3–6 new prep items and 3–6 assemblies built from new and existing items:

```python
class PrepTask(_Strict):              # §20.1: one piece of work, on one piece of equipment
    component: str                    # ≤ 30: "rice", "chicken"
    equipment: Equipment | None       # None = hands only, or waiting (marinating, resting)
    hands_on_minutes: int             # 0–60
    hands_off_minutes: int            # 0–240
    appliance_temp_f: int | None      # oven and air fryer

class PrepStageIdea(_Strict):
    state: Literal["marinated", "partly_cooked", "cooked"]
    method: str                       # ≤ 100: "Roast until browned at the edges"
    tasks: list[PrepTask]             # 1–4

class PrepItemIdea(_Strict):
    title: str; label: str            # label ≤ 30: "roasted chicken"
    pairs_with: list[PairStyle]       # 1–3
    meal_slots: list[MealSlot]
    mood: RecipeMood
    base_servings: int
    stages: list[PrepStageIdea]       # 1–3, in order
    freezer_friendly: bool            # after its last stage
    freeze_note: str | None
    ingredients: list[IdeaIngredient] # 2–15

class AssemblyIdea(_Strict):
    title: str | None                 # None = code names it
    meal_slots: list[MealSlot]
    items: list[str]                  # 1–3 labels, new or from EXISTING ITEMS
    add_ons: list[IdeaIngredient]     # 0–4, per portion: tortilla, peppers, hot sauce

class PrepIdeaBatch(_Strict):
    items: list[PrepItemIdea]         # 1–6
    assemblies: list[AssemblyIdea]    # 1–6
```

- **Code derives** each stage's storage and whether prep may stop there (§19.4), the finish tasks, active and total
  minutes (from the tasks, §20), nutrition and cost per portion, and names for untitled assemblies.
- **Checks:**
  - every idea check today: names and units, the as-sold rule, exclusions and held items, caps, equipment, mood,
    and the prose filter on titles, labels, methods and the freeze note;
  - stages in order (raw → marinated → partly cooked → cooked);
  - task equipment you have, and plausible minutes;
  - an assembly's items exist (new or listed), and its add-ons are allowed ingredients;
  - complete nutrition.
- **When an idea fails:** an item that fails takes its assemblies with it; an assembly that fails is dropped
  alone; salvage keeps whatever validates, as today. One `prep_idea_revision/1` call runs only when nothing passes.
- **The prompt** sends the meals, the cook days' mood and minutes, your equipment, the vocabulary in short names,
  lots to use up, the existing items (label and pairing styles, at most 15) and the never-use list. It sends no
  nutrition numbers.
- **Steps on first open** (`prep_steps/1`): one call writes an item's steps, grouped by stage, with every step
  tagged with its component, equipment and minutes (§20.1). They are checked against the idea's stages and tasks, so
  no number changes when they arrive.

### 19.9 Swap and Not for me

| On | Swap | Not for me |
|---|---|---|
| A meal row (an assembly) | Replaces that meal's assembly. It tries combinations of items already in the plan first (no extra cooking), then a new batch on a cook day whose window covers the meal, then **Write a new one** (one prep ideas call). Every other meal keeps its assembly and portions; changed batch sizes are listed under "Also changed" | Hides that combination from future plans; its items stay. Logs `recipe_hidden` (kind assembly) |
| A prep item (from the batch view) | **Swap this item**: replaces it in every meal that uses it with another item that brings the same thing and pairs with the rest; those meals' names update; everything else stays | Hides the item and every assembly that uses it |

- **Two uses become a preference in a swap:** a swap that would leave an item feeding one meal pays a penalty
  instead of failing, and the sheet says so ("Rice now feeds 1 meal").
- Cooked batches and finished tasks stay fixed (E5).
- Events: `meal_swapped` (payload v2: the assembly and the items that changed) and `recipe_hidden`; exposures under
  `swap`. **Hidden recipes** in Settings lists dishes, assemblies and items, each with Undo.

### 19.10 Batch view, plan view and grocery list

- **A cook day** shows its timeline first (§20.4), then each item with its stop state and where its portions go:
  - "Chicken curry ×3, cooked → Mon dinner, Tue dinner (1 to the freezer for Thu lunch)";
  - "Tandoori chicken ×2, marinate only → freeze today; roast Wed and Thu";
  - "Fresh veggies: made on the day".
- **Each eating day** lists its finish tasks first ("Today: roast the tandoori chicken, 25 min, 5 hands-on"), then
  its meal rows: the assembly's name, kcal and protein, the short instruction, and badges such as "from the freezer:
  thaw Tue night".
- **The recipe page (C8):**
  - an **assembly** lists its items (each opens its own page), its add-ons, the instruction and the per-portion
    numbers;
  - a **prep item** shows its steps by stage, with "In this plan: marinate on Sun, roast on Wed".
- **Prep notes and About this plan** keep their rules (H4, F23).
- **The shopping list** is one list: every prep batch's ingredients plus the assemblies' add-ons, with packages,
  stores, stock-up and "check you have" exactly as today (the same grocery-list code).
  - Add-ons are bought on shopping day like everything else; perishable ones get today's freshness and waste rules
    (peppers keep as raw produce).
- **Mark cooked** on a prep batch deducts its ingredients (as today); **Done** on a finish task deducts that day's
  add-ons.

---

## 20. Parallel cooking on a cook day (design, approved 2026-10-11)

*Approved 2026-10-11 (BUILD_PLAN X1); built in step 2b.9. It applies to every meal-prep style (and to smart prep's
cook days and finish tasks), to swap, and to `POST /plans`.*

### 20.1 Timing on steps and ideas

**Each step gets four fields** (`recipe_step`, proposed migration `0008_step_timing`):

| Field | Meaning |
|---|---|
| `component` | the part of the dish it works on ("rice", "chicken"); none = shared (prep for everything, assembly, portioning) |
| `equipment` | what it occupies: oven, air fryer, a stovetop burner, rice cooker, pressure cooker, slow cooker, microwave, grill; none = hands only, or waiting |
| `hands_on_minutes` | you're busy: chopping, marinating, stirring, searing |
| `hands_off_minutes` | it runs on its own: simmering, baking, resting, chilling |

**How they're filled:**
- **Seeds:** tagged by hand, every step of all 47 seeds and of the new prep items, in a review table in the step
  summary. A seed whose tagged hands-on total differs from its stated active minutes by more than 5 minutes gets
  a revision (D107).
- **Ideas** have no steps, so each idea carries a compact **task list** instead: one task per component and piece of
  equipment (`PrepTask` in §19.8: component, equipment, hands-on, hands-off, appliance temperature). Code then
  computes the idea's **active minutes** (the hands-on total) and **total minutes** (its own schedule), so they
  always agree. The LLM no longer writes those two numbers.
- **The steps pass** (`recipe_steps/2`) writes the four fields on every step. The checks:
  - hands-on 0–60 and hands-off 0–240 (up to 720 for chilling or soaking);
  - the step's equipment is in the recipe's equipment and matches its section (oven steps on the oven);
  - per component, the steps' minutes match the idea's tasks within 25% or 3 minutes, whichever is larger.
  A failure retries with the errors (rule 5). So a card's or a plan's times never change when the steps arrive
  (F31).
- **Steps written before this** (Phase 1 recipes, ideas whose steps exist, and later your own edits without tags):
  code derives the fields from each step's section and duration, and the timeline marks them "estimated":
  - oven, air fryer, rice and cooker steps: 2 min hands-on, the rest hands-off;
  - stovetop, prep and assembly steps: all hands-on;
  - marinate and chill steps: waiting.

**The scheduler works on tasks:** consecutive steps of one component on one piece of equipment, added up. A seed's
tasks come from its tagged steps; an idea's are the idea's own.

### 20.2 Batch size

- **Hands-on time grows with portions, more slowly than the portions:** hands-on = base × (portions ÷ base
  servings)^0.6, rounded up, and never below the base (doubling a batch adds about half, V12). Hands-off time doesn't
  grow: a pot simmers as long for 8 as for 4.
- **Equipment capacity** (estimates, V13), in portions per round:

  | Equipment | Capacity | Notes |
  |---|---|---|
  | Oven | 8 | two sheet pans; tasks whose temperatures are within 25°F can share it (V14) |
  | Air fryer | 4 | one basket |
  | Stovetop | 4 burners | a skillet sears 4 portions per round, a pot holds 12; a mostly hands-on task (searing, stir-frying) counts as a skillet, a mostly hands-off one (simmering) as a pot |
  | Rice cooker | 10 | |
  | Pressure cooker | 8 | |
  | Slow cooker | 10 | |
  | Microwave | 2 | |
  | Grill | 6 | |

- **A batch above capacity takes extra rounds:** each round repeats the hands-off time and its share of the loading.
  For example, 8 portions of air-fryer chicken take 2 rounds of 18 minutes.
- This replaces D121 (a batch's hands-on time didn't grow).

### 20.3 The schedule

Each cook day is a schedule, built by `domain/cook_schedule.py`: pure code, deterministic, no LLM.

**Resources**
- **Your hands:** one hands-on task at a time.
- **Each piece of equipment:** one task at a time. The stovetop has 4 burners. The oven can hold several tasks at
  once when their portions fit its capacity and their temperatures are within 25°F.

**Order**
- Within a dish, each component's tasks run in order.
- Shared prep comes before the components it serves; assembly and portioning come after all of them.
- Different dishes don't depend on each other.

**A task** needs your hands for its hands-on minutes, at its start, and holds its equipment from its start to the end
of its hands-off minutes. Waiting tasks (marinating, resting) hold nothing. The oven preheats for 10 minutes
(hands-off) before its first task, overlapping other work.

**Algorithm:** list scheduling.
1. Take the ready task with the longest chain of work still behind it (ties: longer hands-off first, then dish
   order).
2. Place it at the earliest time its hands and its equipment are free.
3. Repeat the whole thing for every starting order of the day's dishes (up to 6 dishes, 720 orders) and keep the
   shortest; ties keep the first.

A cook day of up to 6 dishes (about 40 tasks) takes a few milliseconds per order, under 50 ms in all. Days with
more dishes use the priority order alone.

**Result:** the elapsed minutes (start to finish), the hands-on minutes, and the timeline.

**The cook-day time check uses the elapsed minutes** (V11):
- **In the solver,** linear limits that every schedule must meet: the day's hands-on total, each piece of
  equipment's busy minutes (per burner on the stovetop), and each dish's own chain each fit the day's minutes.
- **After the solve,** the exact schedule. A day over its minutes adds a cut (that set of batches can't share that
  day) and re-solves, like today's tightening loop, at most 2 rounds before the time fix.
- **The validator** schedules the rounded plan again, so no plan passes with a day over its minutes. The fix reads
  "Allow 1 h 35 min on Sunday" (rounded up to 5 minutes).

**Elsewhere**
- **Eating days:** finish tasks (§19) are scheduled the same way on their own day, against that day's finish time
  (V7).
- **Meal now:** a recipe's total time is its own schedule (its components in parallel); for seeds it should stay
  within a few minutes of today's numbers.

### 20.4 The timeline

```
Sunday · about 1 h start to finish · 35 min hands-on
0:00  Preheat the oven to 425°F
0:00  Chop the chicken, peppers and onion (12 min)
0:12  Chicken and peppers into the oven (35 min)
0:14  Rice on the stove (25 min)
0:16  Fish into the air fryer (12 min, flip at 0:22)
0:28  Make the yogurt sauce (5 min)
0:47  Portion everything out (10 min)
0:57  Done
```

- **Lines are templated by code** from each task's component, equipment and section; times come from the schedule.
  The LLM writes no timeline text.
- **API:** each cook day gets `timeline` (`at_min`, `at_display`, `text`, `kind` hands_on / runs / wait, `minutes`,
  `equipment`, `estimated`), `elapsed_minutes` and `hands_on_minutes`. They replace `prep_order` (2b.5
  deliverable 11, D122).
- **Cooking mode (2b.7)** gains a cook-day mode that steps through the timeline across dishes; each line opens its
  dish's steps.

### 20.5 Tests

- Three dishes, one each on the oven, the air fryer and the rice cooker, finish faster together than in sequence; the
  elapsed time is the longest chain plus the hands-on work that can't overlap.
- Two oven dishes can't overlap unless their portions fit the oven together and their temperatures are within 25°F;
  otherwise the second starts when the first ends.
- Hands-on work never overlaps; each piece of equipment runs one task at a time; the stovetop runs at most 4.
- A batch above capacity takes extra rounds; hands-on grows by the rule and never drops below the base.
- Determinism: the same day gives the same timeline, whatever order the dishes arrive in.
- Finish tasks are scheduled on their eating day only.
- Solver and validator agree: no plan passes with a cook day over its minutes, and the cut re-solve finds a plan
  that fits when one exists (a small instance solved to optimality, K6).
- Ideas: the task list is required and checked; active and total minutes are computed from it; steps that don't
  match it fail with the errors; a plan's numbers are unchanged after the steps arrive.
- Seeds: every step tagged; each seed's hands-on total within 5 minutes of its stated active minutes.
- Speed: a 6-dish day schedules in under 50 ms (opt-in timing test).

### 20.6 As built (step 2b.9)

Details the design left open, as decided while building (BUILD_PLAN 2b.9 outcome, D128–D142):
- **The fridge isn't the kitchen.** A dish's last wait with no appliance, in a no-cook, assembly or portioning
  step (overnight oats setting, a pudding chilling), runs after you leave: it counts toward when the food is
  ready, not toward the cook day's start-to-finish minutes. Overnight oats take 5 minutes of a cook day.
- **Storage and reheating steps aren't cook-day work** (tagged 0 and 0 on the seeds).
- **Merging steps into tasks** stops once a task has hands-off time, so a task's hands-on minutes always come
  first; the step with the waiting or running time names the task (a prep step plus a marinade is "Marinate").
- **Estimated timing (V15):** each appliance's steps form their own part of the dish, so different appliances run
  side by side; marinating belongs to the next cooking step that isn't the rice; steps without a duration share
  what's left of the recipe's hands-on minutes. A recipe with no steps at all is its stated minutes as one task.
- **Batch size and capacity** read the batch's portion count (everyone eating, frozen extras included); the tagged
  minutes already cover the rounds the recipe's own servings need (4 mug cakes, 2 at a time).
- **The order search** tries only the dish orders that change a tie, skipping orders that just swap two
  identical batches, and stops at the lower bound; at most 720.
- **In the solver:** before the first solve, pairs of batches that would run over a cook day together at the most
  portions each could cook are kept off the same day (if that leaves no plan, the week is solved without them);
  after each solve, a day over its minutes is cut on that day and on every cook day with no more minutes. When
  the cuts leave no plan, the answer is the time fix.
- **An idea's task** may have no part (`component` null = shared), like a step; its waits run up to 12 hours with
  no appliance, an appliance at most 4 hours. An idea's total minutes are when it's ready (a last chill
  included); meal prep also checks its start-to-finish minutes against the longest cook day.

---

## 21. Build order, LLM tokens and open questions for §19–§20

### 21.1 Build order

**Approved order (2026-10-11, BUILD_PLAN X8), for new screens and a live link sooner:** 2b.9 → 2b.10 → **2b.7** (the
plan screens for both single-recipe meals and assemblies) → **2b.13** (deploy: Vercel + Neon) → 2b.11 → 2b.12 → 2b.6
→ 2b.8. The swap screens and Not for me move to 2b.6, the read side of the plan view data to 2b.7, and the fifth tile
shows "coming soon" until 2b.11 (BUILD_PLAN §9). The table below is the order first proposed.

Four new steps before swap, because swap (2b.6) works on the plan shape these designs change. The step numbers
continue from 2b.8, so every earlier reference still points at the right step (as with H3). Details are in BUILD_PLAN
§9.

| Order | Step | What |
|---|---|---|
| 1 | **2b.9** Cook-day schedule (backend) | §20: step timing (migration `0008_step_timing`), the seeds tagged, the scheduler, the elapsed check in the solver and validator, ideas' task lists, the steps' timing fields, the timeline in place of the prep order |
| 2 | **2b.10** Smart prep: data, storage and seed prep items (backend) | §19.3–§19.6: migration `0009_smart_prep`, storage per item and state, the draft prep items and assemblies, names and instructions |
| 3 | **2b.11** Smart prep: solver and plan (backend) | §19.7, §19.10: the shared supply side, the smart model, its validator checks, `cook_style = "basics"` from the seed pool (0 LLM calls), the plan data and shopping list |
| 4 | **2b.12** Smart prep: ideas (backend) | §19.8: the prep ideas pass, its revision and the prep steps, with an opt-in live test |
| 5 | **2b.6** Swap (changed) | Also assemblies and "Swap this item" (§19.9), Not for me on dishes, assemblies and items, the time check through the schedule |
| 6 | **2b.7** Screens (changed) | The fifth tile; the cook-day timeline and cook-day cooking mode; finish tasks on eating days; the batch view with items and stop states; assembly and item pages; start-to-finish minutes in C1b and Settings |
| 7 | **2b.8** What should I buy? (unchanged) | It plans dishes as designed; smart prep for grocery advice goes to the backlog (V17) |

### 21.2 LLM token impact

Measured today (§15.1): an ideas call ≈ 4.7K (1.5K prompt + 3.1K for 8 ideas), a steps call ≈ 1.2K.

| Call | Today | With these designs | Why |
|---|---|---|---|
| Ideas (meal now, meal prep, swap) | ≈ 4.7K | ≈ 5.6K | The freeze note (built this session): +≈ 170 prompt tokens (rules and schema), +≈ 5 a null and ≈ 20 a note per idea. The task list (§20.1): +≈ 80 tokens an idea, schema +≈ 100. The count rule moves from 360 to about 450 tokens an idea; 8 ideas still fit (1.8K + 8 × 450 + 300 ≈ 5.7K of 7.6K) |
| Steps for one recipe | ≈ 1.2K | ≈ 1.45K | 4 fields a step (≈ +15 tokens), schema +≈ 90 |
| Prep ideas (new; smart prep gaps only) | – | ≈ 5K | ≈ 2.3K prompt (the full vocabulary, the rules, a larger schema, up to 15 existing items) + ≈ 2.6K for 5 items and 5 assemblies |
| Prep item steps (first open) | – | ≈ 1.4K | Like a recipe's steps, with stages |

- **Smart prep from the seed pool:** 0 calls. With a gap: 1 prep ideas call (≈ 5K), then ≈ 1.4K for each new item
  you open.
- **A typical day** (one meal-now search that writes ideas, one new idea opened): ≈ 6K → ≈ 7K.
- **The heavy day of §15.2:** ≈ 37K → ≈ 44K, about 29% of the daily guard. The 30K background reserve is still
  about five searches' worth.
- **Per minute:** an ideas call (5.6K) or a prep ideas call (5K), then a steps call (1.4K), still fits one minute's
  8K, so opening a new idea right after usually doesn't wait.
- The task lists and steps' fields get re-measured in 2b.9's opt-in live test (under 20K tokens), and the count rule
  uses what it finds.
- **Measured in 2b.9 (2026-10-11, `test_task_lists_token_report`, strict, both calls on `openai/gpt-oss-120b`:
  outside compose `LLM_IDEAS_MODEL` is unset; the app in compose sends ideas to 20b):**
  - an ideas call with task lists: 2,028 prompt + 4,078 completion = 6.1K for 8 ideas, all 8 passing the checks
    (about 470 completion tokens an idea after the reasoning, so the count rule now uses 480; 8 ideas still fit:
    2.0K + 8 × 480 + 300 ≈ 6.2K of 7.6K);
  - a steps call with each step's timing: 1,039 + 1,160 = 2.2K, matching the idea's tasks on the first try;
  - the run: 8.3K tokens in all.
  - So an ideas call then a steps call is about 8.3K, a little over one minute's 8K: opening a new idea right
    after a search can wait a few seconds (the countdown), where the estimate expected none. A typical day is
    about 8K instead of 7K.

### 21.3 Open questions (each with my recommended default)

**Answered 2026-10-11 (BUILD_PLAN X2–X7).** Every recommended default below was accepted, with these answers:
- **V1:** the second official source is the USDA FSIS **FoodKeeper** data (`docs/sources/foodkeeper.json`, English),
  transcribed in 2b.10 with a FoodKeeper citation per row (cooked rice and grains, cooked vegetables, cut fresh
  vegetables, salads, sauces and any other gaps). Without the file, today's 3-day rule and same-day fresh items stay.
- **V2:** never store partly cooked meat, poultry, fish or eggs.
- **V7:** a per-day weeknight time for finish tasks, default 30 minutes, editable per day.
- **V11:** cook-day time means start to finish; default 90 minutes; saved cook days are converted (doubled, at most
  600).
- **V16:** CLAUDE.md's phase outline is updated, and the build order changed (§21.1).

| # | Question | Recommended default |
|---|---|---|
| V1 | **Storage rows the chart doesn't have:** cooked rice and grains, cooked vegetables and dal, cut fresh vegetables and salads, sauces and dressings. The FoodSafety.gov chart in the repo covers meat, poultry, fish, eggs, soups and stews, and leftovers of cooked meat or poultry only | You save a second official source as a PDF in `docs/sources/` (the USDA FoodKeeper entries for those foods, or FSIS "Leftovers and Food Safety"), and I transcribe the rows, as for A1. Until then: cooked items use your 3-day leftover window (today's rule for every recipe, dal and rice included), and fresh items (salad, cut vegetables, yogurt sauces) are made on the eating day as a 5-minute finish task |
| V2 | **Partly cooked meat, poultry, fish or eggs:** may prep stop there? | No: those stop at raw, marinated or fully cooked; "partly cooked" can be stored only for items without them (par-boiled potatoes, blanched vegetables). USDA advises against partly cooking meat or poultry to finish later; I'd add that FSIS page to `docs/sources/` as the cited rule |
| V3 | **Portion steps and cups:** how are portions measured and shown? | Bases and sides in half portions, proteins and dishes in whole portions. Shown as "1 portion curry · ½ portion rice", and as cups only for grains with a reviewed cooked-volume factor in seed data (cited like D38) |
| V4 | **Uses per item:** at least 2 meals, or 3? | At least 2 (a hard limit), with a small reward for each use from the third on |
| V5 | **Variety in smart prep** | An assembly at most once a day and 3 times a week; with 6 or more meals, at least 2 different items that bring the protein |
| V6 | **Effort against money:** how much is a saved minute worth? | 10 minutes of cook-day hands-on time weighs like $1; a cook session like 20 minutes; a minute of eating-day hands-on time like 1.5 cook-day minutes. Tunable constants, like the other weights |
| V7 | **Finish time on eating days:** a new per-day setting? | Yes: every day gets a "weeknight time" for finish tasks, default 30 min start to finish (a 25-minute roast fits); reheats always fit. In Settings next to cook days |
| V8 | **Which cook days** does smart prep use? | Your cook days in the plan's range (or the days you pick on C1b), as few of them as fit |
| V9 | **Breakfasts, snacks and desserts** in smart prep | Whole dishes as today (one-item assemblies); split items only where seeds or ideas have them |
| V10 | **Assembly names** | Composed by code from the items (§19.5); an LLM-written assembly may keep its own title; renaming comes with Phase 3's editing |
| V11 | **Start to finish replaces hands-on for a cook day's minutes** (as you asked; this reverses C1 of 2026-10-08). 45 minutes start to finish is tight: most lunch and dinner seeds take 35–75 minutes start to finish on their own | One number per cook day, "time in the kitchen, start to finish", checked against the schedule; hands-on is shown but not limited (the mood still limits each recipe's hands-on). The default becomes 90 min, and your saved cook days double (45 → 90, at most 600) with a one-time note in Settings. Quick means "ready within N minutes, start to finish"; One big cook day's stepper is the same start-to-finish time |
| V12 | **How fast hands-on grows** with batch size | base × (portions ÷ base servings)^0.6: doubling adds about half, quadrupling about 130% |
| V13 | **Equipment capacity** | The §20.2 table as code constants; a size choice per appliance in Settings → Equipment goes to the backlog |
| V14 | **Oven sharing** | Two dishes share the oven when their portions fit (8) and their temperatures are within 25°F |
| V15 | **Recipes without timing tags** (Phase 1 recipes, ideas whose steps are already written) | Code derives the timing from each step's section and duration, marked "estimated" on the timeline; the seeds are tagged by hand |
| V16 | **Build order** | 2b.9 → 2b.10 → 2b.11 → 2b.12 → 2b.6 → 2b.7 → 2b.8 (§21.1). Phase 2b grows from 9 to 13 steps, so CLAUDE.md's phase outline needs your OK to update (as F18) |
| V17 | **Smart prep in What should I buy?** | Not in 2b.8 (grocery advice plans dishes, as designed); added to the backlog |
