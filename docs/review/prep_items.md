# Smart prep drafts: prep items and assemblies (step 2b.10)

Draft data for your review, like the M13 seeds. Generated from the seeded data: every number is computed by
code (nutrition from the USDA cache per portion, cost from the estimated prices, storage from
`domain/prep_storage.py` with your 3-day leftover setting). Files: `backend/app/seed/data/prep_items/` and
`backend/app/seed/data/assemblies/`. Change a file and re-seed: it becomes a new draft version (D107).

## Prep items (20)

Portions are the seed's base servings. Cost per portion is Stop & Shop / Price Rite, est.

| Item | Split from | Label · brings | Stages and storage | Per portion | Active / total |
|---|---|---|---|---|---|
| Spiced seared chicken thighs | 1a | spiced chicken · protein | marinated: 1 d, freezes; cooked: 3 d, freezes | 278 kcal, 34 g protein, $1.88 / $1.46 (serves 4) | 21 / 45 min |
| Broth rice | 1a | broth rice · base | cooked: 3 d, freezes | 296 kcal, 8 g protein, $0.56 / $0.42 (serves 4) | 6 / 30 min |
| Plain rice | 1b | rice · base | cooked: 3 d, freezes | 274 kcal, 5 g protein, $0.17 / $0.13 (serves 4) | 6 / 30 min |
| Air-fryer chicken breast | 1b | air-fryer chicken · protein | marinated: 1 d, freezes; cooked: 3 d, freezes | 225 kcal, 39 g protein, $1.90 / $1.52 (serves 4) | 10 / 30 min |
| Air-fryer broccoli | 1b | roasted broccoli · vegetables | cooked: 3 d, freezes | 43 kcal, 3 g protein, $0.58 / $0.47 (serves 4) | 6 / 15 min |
| Sheet-pan chicken and peppers | 1c | roasted chicken and peppers · protein | marinated: 1 d, freezes; cooked: 3 d, freezes | 312 kcal, 35 g protein, $2.78 / $2.07 (serves 4) | 18 / 45 min |
| Chicken curry | 2a | chicken curry · dish | cooked: 3 d, freezes | 356 kcal, 36 g protein, $2.47 / $1.93 (serves 4) | 33 / 55 min |
| Chicken and spinach curry | 2c | chicken spinach curry · dish | cooked: 3 d, freezes | 322 kcal, 37 g protein, $3.12 / $2.38 (serves 4) | 29 / 45 min |
| Chicken tikka | 7a | chicken tikka · protein | marinated: 1 d, freezes; cooked: 3 d, freezes | 277 kcal, 38 g protein, $2.04 / $1.60 (serves 4) | 15 / 60 min |
| Tandoori drumsticks | 8d | tandoori drumsticks · protein | marinated: 1 d, freezes; cooked: 3 d, freezes | 459 kcal, 45 g protein, $1.93 / $1.47 (serves 4) | 17 / 115 min |
| Chicken, broccoli and pepper stir-fry | 8j | chicken stir-fry · dish | cooked: 3 d, freezes | 340 kcal, 43 g protein, $3.29 / $2.54 (serves 4) | 20 / 20 min |
| Roast bone-in chicken breasts | 8l | roast chicken breast · protein | marinated: 1 d, freezes; cooked: 3 d, freezes | 483 kcal, 50 g protein, $2.19 / $1.81 (serves 4) | 14 / 55 min |
| Quinoa | 8l | quinoa · base | cooked: 3 d, freezes | 236 kcal, 9 g protein, $1.06 / $0.81 (serves 4) | 7 / 25 min |
| Roasted asparagus | 8l | roasted asparagus · vegetables | cooked: 3 d, doesn't freeze | 52 kcal, 2 g protein, $1.06 / $0.87 (serves 4) | 6 / 25 min |
| Roasted root vegetables | 8i | roasted root vegetables · base | cooked: 3 d, freezes | 184 kcal, 4 g protein, $0.62 / $0.49 (serves 6) | 16 / 60 min |
| Dal tadka | 7f | dal · dish | cooked: 3 d, freezes | 313 kcal, 16 g protein, $1.07 / $0.87 (serves 4) | 20 / 35 min |
| Black beans and corn | 7c | black beans and corn · protein | cooked: 3 d, freezes | 172 kcal, 9 g protein, $0.90 / $0.69 (serves 4) | 7 / 10 min |
| Garlic yogurt sauce | 1a | garlic yogurt sauce · sauce | raw: made on the eating day | 33 kcal, 5 g protein, $0.36 / $0.29 (serves 4) | 4 / 5 min |
| Cucumber raita | 8d | raita · sauce | raw: made on the eating day | 42 kcal, 6 g protein, $0.70 / $0.56 (serves 4) | 6 / 10 min |
| Chopped salad | 1a | chopped salad · vegetables | raw: made on the eating day | 54 kcal, 1 g protein, $0.85 / $0.66 (serves 4) | 7 / 10 min |

## Assemblies (12)

Item portions are per person: proteins and dishes in whole portions, bases and sides in halves (V3);
the range is what the solver may choose from 2b.11. Numbers are the items' portions plus the add-ons.

| Assembly | Items (portions, range) | Add-ons, per portion | Per portion | Eating-day instruction |
|---|---|---|---|---|
| Spiced chicken over broth rice with garlic yogurt sauce | Spiced seared chicken thighs 1 portion (1–2); Broth rice 1 portion (0.5–2); Garlic yogurt sauce 1 portion (1–1) | — | 607 kcal, 47 g protein, $2.80 / $2.17 | Reheat 1 portion spiced chicken and 1 portion broth rice to 165°F. Make the garlic yogurt sauce fresh (5 min) and add it cold. |
| Spiced chicken wrap with chopped salad and garlic yogurt sauce | Spiced seared chicken thighs 1 portion (1–2); Chopped salad 1 portion (0.5–1.5); Garlic yogurt sauce 1 portion (1–1) | 2 flour tortilla (Price Rite, 37 g) | 585 kcal, 46 g protein, $3.65 / $2.61 | Reheat 1 portion spiced chicken to 165°F. Make the chopped salad fresh (5 min) and add it cold. Make the garlic yogurt sauce fresh (5 min) and add it cold. Warm 2 flour tortillas; fill with the spiced chicken, chopped salad and garlic yogurt sauce. |
| Chicken curry with rice | Chicken curry 1 portion (1–2); Plain rice 1 portion (0.5–2) | — | 630 kcal, 41 g protein, $2.64 / $2.06 | Reheat 1 portion chicken curry and 1 portion rice to 165°F. |
| Chicken curry with flour tortillas | Chicken curry 1 portion (1–2) | 2 flour tortilla (Price Rite, 37 g) | 576 kcal, 42 g protein, $3.03 / $2.13 | Reheat 1 portion chicken curry to 165°F. Warm 2 flour tortillas to eat with it. |
| Chicken tikka over rice with raita | Chicken tikka 1 portion (1–2); Plain rice 1 portion (0.5–2); Cucumber raita 1 portion (1–1) | — | 593 kcal, 49 g protein, $2.91 / $2.29 | Reheat 1 portion chicken tikka and 1 portion rice to 165°F. Make the raita fresh (5 min) and add it cold. |
| Tandoori drumsticks over rice with raita | Tandoori drumsticks 1 portion (1–2); Plain rice 1 portion (0.5–2); Cucumber raita 1 portion (1–1) | — | 774 kcal, 56 g protein, $2.80 / $2.16 | Reheat 1 portion tandoori drumsticks and 1 portion rice to 165°F. Make the raita fresh (5 min) and add it cold. |
| Dal with rice | Dal tadka 1 portion (1–2); Plain rice 1 portion (0.5–2) | — | 587 kcal, 22 g protein, $1.24 / $1.00 | Reheat 1 portion dal and 1 portion rice to 165°F. |
| Air-fryer chicken over quinoa with roasted broccoli | Air-fryer chicken breast 1 portion (1–2); Quinoa 1 portion (0.5–2); Air-fryer broccoli 1 portion (0.5–1.5) | — | 504 kcal, 51 g protein, $3.54 / $2.80 | Reheat 1 portion air-fryer chicken, 1 portion quinoa and 1 portion roasted broccoli to 165°F. |
| Chicken burrito bowl (its own title) | Air-fryer chicken breast 1 portion (1–2); Plain rice 1 portion (0.5–2); Black beans and corn 1 portion (0.5–1.5) | 2 tbsp salsa; 30 g romaine lettuce | 685 kcal, 54 g protein, $3.42 / $2.69 | Reheat 1 portion air-fryer chicken, 1 portion rice and 1 portion black beans and corn to 165°F. Top with 2 tbsp salsa and 30 g romaine lettuce, shredded. |
| Roasted chicken and peppers wrap with salsa and romaine lettuce | Sheet-pan chicken and peppers 1 portion (1–2) | 2 flour tortilla (Price Rite, 37 g); 2 tbsp salsa; 20 g romaine lettuce | 545 kcal, 42 g protein, $3.71 / $2.56 | Reheat 1 portion roasted chicken and peppers to 165°F. Warm 2 flour tortillas; fill with the roasted chicken and peppers, 2 tbsp salsa and 20 g romaine lettuce, shredded. |
| Roast chicken breast with roasted root vegetables | Roast bone-in chicken breasts 1 portion (1–2); Roasted root vegetables 1 portion (0.5–1.5) | — | 668 kcal, 54 g protein, $2.81 / $2.30 | Reheat 1 portion roast chicken breast and 1 portion roasted root vegetables to 165°F. |
| Chicken stir-fry with rice | Chicken, broccoli and pepper stir-fry 1 portion (1–2); Plain rice 1 portion (0.5–2) | — | 614 kcal, 48 g protein, $3.46 / $2.67 | Reheat 1 portion chicken stir-fry and 1 portion rice to 165°F. |

Every dish is also a one-item assembly (computed, no data): its title, one portion, stored as today.
