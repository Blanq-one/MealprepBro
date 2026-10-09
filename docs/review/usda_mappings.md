# USDA mapping review

Generated 2026-10-09 by `uv run python -m app.cli mapping-review` from the seeded database. Regenerate after changing mappings; don't edit this file by hand.

- **Sorted by** each ingredient's share of the calories in all seed recipes (base servings, optional lines excluded), highest first. Ingredients no seed uses come last, alphabetically.
- **State** is the state the nutrition mapping describes, read from the USDA description (package labels are as-sold). Recipe quantities are raw / dry / as-sold weights unless a line says otherwise.
- **Auto-flags:** `state:` = the mapping's state doesn't match how recipes use it. `description says '…'` = the USDA description contains fried / breaded / with skin / cooked / canned / sweetened while the ingredient's name, aliases and products imply otherwise. Package-label ingredients aren't checked for description issues. `note:` = other things worth a look.
- The top 25 rows are marked **Krish to review** until you approve them; approved rows show the approval date.

## Flag summary

- description says 'canned': 3 (low-sodium chicken broth, beef broth, refried beans, traditional)
- note: approximate mapping (no exact USDA food): 1 (garam masala)
- note: no energy_kcal, protein_g, carbohydrate_g, fat_g in the mapping: 1 (pepperoni)

## Mappings (185)

| # | Ingredient | Nutrition source | USDA description | FDC id | State | kcal per 100 g | % of seed calories | Flags |
|---|---|---|---|---|---|---|---|---|
| 1 | chicken thigh, boneless skinless | USDA | Chicken, broilers or fryers, dark meat, thigh, meat only, raw | 173627 | raw | 121 | 23.7% | approved 2026-10-08 |
| 2 | flour tortilla (Price Rite, 37 g) | package label (+ USDA for nutrients not on the label) | Tortillas, ready-to-bake or -fry, flour, shelf stable | 167535 | as-sold | 297 | 20.3% | approved 2026-10-08 |
| 3 | long-grain white rice (dry) | USDA | Rice, white, long-grain, regular, raw, enriched | 168877 | dry | 365 | 18.9% | approved 2026-10-08 |
| 4 | vegetable oil | USDA | Oil, canola | 172336 | as-sold | 884 | 5.0% | approved 2026-10-08 |
| 5 | chicken breast, boneless skinless | USDA | Chicken, broiler or fryers, breast, skinless, boneless, meat only, raw | 171077 | raw | 120 | 4.7% | approved 2026-10-08 |
| 6 | olive oil | USDA | Oil, olive, salad or cooking | 171413 | as-sold | 884 | 4.1% | approved 2026-10-08 |
| 7 | Greek yogurt, plain nonfat | USDA | Yogurt, Greek, plain, nonfat (Includes foods for USDA's Food Distribution Program) | 170894 | as-sold | 59 | 3.9% | approved 2026-10-08 |
| 8 | protein powder, double chocolate | package label | — | — | as-sold | 387 | 3.5% | approved 2026-10-08 |
| 9 | egg, large | USDA | Egg, whole, raw, fresh | 171287 | raw | 143 | 3.3% | approved 2026-10-08 |
| 10 | milk, 2% | USDA | Milk, reduced fat, fluid, 2% milkfat, with added vitamin A and vitamin D | 171267 | as-sold | 50 | 2.2% | approved 2026-10-08 |
| 11 | rolled oats | USDA | Cereals, oats, regular and quick, not fortified, dry | 173904 | dry | 379 | 1.7% | approved 2026-10-08 |
| 12 | chia seeds | USDA | Seeds, chia seeds, dried | 170554 | dry | 486 | 1.5% | approved 2026-10-08 |
| 13 | yellow onion | USDA | Onions, raw | 170000 | raw | 40 | 1.4% | approved 2026-10-08 |
| 14 | tomato | USDA | Tomatoes, red, ripe, raw, year round average | 170457 | raw | 18 | 0.9% | approved 2026-10-08 |
| 15 | broccoli florets | USDA | Broccoli, flower clusters, raw | 169330 | raw | 28 | 0.6% | approved 2026-10-08 |
| 16 | bell pepper | USDA | Peppers, sweet, red, raw | 170108 | raw | 26 | 0.5% | approved 2026-10-08 |
| 17 | spinach, fresh | USDA | Spinach, raw | 168462 | raw | 23 | 0.5% | approved 2026-10-08 |
| 18 | low-sodium chicken broth | USDA | Soup, chicken broth, low sodium, canned | 171609 | as-sold | 16 | 0.5% | approved 2026-10-08; description says 'canned' |
| 19 | red onion | USDA | Onions, red, raw | 790577 | raw | 44 | 0.5% | approved 2026-10-08 |
| 20 | garlic | USDA | Garlic, raw | 169230 | raw | 149 | 0.5% | approved 2026-10-08 |
| 21 | ground cumin | USDA | Spices, cumin seed | 170923 | dry | 375 | 0.2% | approved 2026-10-08 |
| 22 | ginger root | USDA | Ginger root, raw | 169231 | raw | 80 | 0.2% | approved 2026-10-08 |
| 23 | garam masala | USDA | Spices, curry powder | 170924 | dry | 325 | 0.2% | approved 2026-10-08; note: approximate mapping (no exact USDA food) |
| 24 | tomato paste | USDA | Tomato products, canned, paste, without salt added (Includes foods for USDA's Food Distribution Program) | 170459 | as-sold | 82 | 0.2% | approved 2026-10-08 |
| 25 | romaine lettuce | USDA | Lettuce, cos or romaine, raw | 169247 | raw | 17 | 0.1% | approved 2026-10-08 |
| 26 | unsweetened cocoa powder | USDA | Cocoa, dry powder, unsweetened | 169593 | dry | 228 | 0.1% | — |
| 27 | chili powder | USDA | Spices, chili powder | 171319 | dry | 282 | 0.1% | — |
| 28 | ground coriander | USDA | Spices, coriander seed | 170922 | dry | 298 | 0.1% | — |
| 29 | garlic powder | USDA | Spices, garlic powder | 171325 | dry | 331 | 0.1% | — |
| 30 | paprika | USDA | Spices, paprika | 171329 | dry | 282 | 0.1% | — |
| 31 | ground turmeric | USDA | Spices, turmeric, ground | 172231 | dry | 312 | 0.1% | — |
| 32 | lemon juice | USDA | Lemon juice, raw | 167747 | raw | 22 | 0.1% | — |
| 33 | black pepper | USDA | Spices, pepper, black | 170931 | dry | 251 | 0.1% | — |
| 34 | dried oregano | USDA | Spices, oregano, dried | 171328 | dry | 265 | 0.1% | — |
| 35 | smoked paprika | USDA | Spices, paprika | 171329 | dry | 282 | 0.0% | — |
| 36 | Greek yogurt, plain whole milk | USDA | Yogurt, Greek, plain, whole milk | 171304 | as-sold | 97 | 0.0% | — |
| 37 | Worcestershire sauce | USDA | Sauce, worcestershire | 171610 | as-sold | 77 | 0.0% | — |
| 38 | all-purpose flour | USDA | Wheat flour, white, all-purpose, enriched, bleached | 168894 | as-sold | 364 | 0.0% | — |
| 39 | almonds | USDA | Nuts, almonds | 170567 | as-sold | 579 | 0.0% | — |
| 40 | apple | USDA | Apples, raw, with skin (Includes foods for USDA's Food Distribution Program) | 171688 | raw | 52 | 0.0% | — |
| 41 | apple cider vinegar | USDA | Vinegar, cider | 173469 | as-sold | 21 | 0.0% | — |
| 42 | asparagus | USDA | Asparagus, raw | 168389 | raw | 20 | 0.0% | — |
| 43 | avocado | USDA | Avocados, raw, all commercial varieties | 171705 | raw | 160 | 0.0% | — |
| 44 | bacon | USDA | Pork, cured, bacon, unprepared | 168277 | as-sold | 393 | 0.0% | — |
| 45 | baking powder | USDA | Leavening agents, baking powder, double-acting, sodium aluminum sulfate | 172803 | as-sold | 53 | 0.0% | — |
| 46 | baking soda | USDA | Leavening agents, baking soda | 175040 | as-sold | 0 | 0.0% | — |
| 47 | banana | USDA | Bananas, raw | 173944 | raw | 89 | 0.0% | — |
| 48 | bay leaf | USDA | Spices, bay leaf | 170917 | dry | 313 | 0.0% | — |
| 49 | beef bouillon cube | USDA | Soup, beef broth, cubed, dry | 171561 | dry | 170 | 0.0% | — |
| 50 | beef broth | USDA | Soup, beef broth or bouillon canned, ready-to-serve | 171538 | as-sold | 7 | 0.0% | description says 'canned' |
| 51 | beef hot dog | USDA | Frankfurter, beef, unheated | 173862 | raw | 315 | 0.0% | — |
| 52 | beef steak, top sirloin | USDA | Beef, top sirloin, steak, separable lean and fat, trimmed to 1/8" fat, all grades, raw | 168726 | raw | 201 | 0.0% | — |
| 53 | beef tallow | USDA | Fat, beef tallow | 171400 | as-sold | 902 | 0.0% | — |
| 54 | black beans, canned | USDA | Beans, black turtle, mature seeds, canned | 175188 | as-sold | 91 | 0.0% | — |
| 55 | blueberries | USDA | Blueberries, raw | 171711 | raw | 57 | 0.0% | — |
| 56 | brewed coffee | USDA | Beverages, coffee, brewed, prepared with tap water | 171890 | as-sold | 1 | 0.0% | — |
| 57 | brown lentils (dry) | USDA | Lentils, raw | 172420 | dry | 352 | 0.0% | — |
| 58 | brown rice (dry) | USDA | Rice, brown, long-grain, raw (Includes foods for USDA's Food Distribution Program) | 169703 | dry | 367 | 0.0% | — |
| 59 | brown sugar | USDA | Sugars, brown | 168833 | as-sold | 380 | 0.0% | — |
| 60 | brussels sprouts | USDA | Brussels sprouts, raw | 170383 | raw | 43 | 0.0% | — |
| 61 | butter, salted | USDA | Butter, salted | 173410 | as-sold | 717 | 0.0% | — |
| 62 | butter, unsalted | USDA | Butter, without salt | 173430 | as-sold | 717 | 0.0% | — |
| 63 | carrot | USDA | Carrots, raw | 170393 | raw | 41 | 0.0% | — |
| 64 | cashews | USDA | Nuts, cashew nuts, raw | 170162 | raw | 553 | 0.0% | — |
| 65 | cauliflower | USDA | Cauliflower, raw | 169986 | raw | 25 | 0.0% | — |
| 66 | cayenne pepper | USDA | Spices, pepper, red or cayenne | 170932 | dry | 318 | 0.0% | — |
| 67 | celery | USDA | Celery, raw | 169988 | raw | 14 | 0.0% | — |
| 68 | chapati (roti) | USDA | Bread, chapati or roti, plain, commercially prepared | 171844 | as-sold | 297 | 0.0% | — |
| 69 | cheddar cheese | USDA | Cheese, cheddar | 328637 | as-sold | 408 | 0.0% | — |
| 70 | chicken bouillon cube | USDA | Soup, chicken broth or bouillon, dry | 171562 | dry | 267 | 0.0% | — |
| 71 | chicken broth, regular | USDA | Soup, chicken broth, ready-to-serve | 174536 | as-sold | 6 | 0.0% | — |
| 72 | chicken sausage | USDA | Sausage, chicken or turkey, Italian style,  lower sodium | 173880 | raw | 183 | 0.0% | — |
| 73 | chickpeas, canned, drained | USDA | Chickpeas (garbanzo beans, bengal gram), mature seeds, canned, drained solids | 173800 | as-sold | 139 | 0.0% | — |
| 74 | cilantro | USDA | Coriander (cilantro) leaves, raw | 169997 | raw | 23 | 0.0% | — |
| 75 | coconut milk, canned | USDA | Nuts, coconut milk, canned (liquid expressed from grated meat and water) | 170173 | as-sold | 197 | 0.0% | — |
| 76 | coconut oil | USDA | Oil, coconut | 171412 | as-sold | 892 | 0.0% | — |
| 77 | cod fillet | USDA | Fish, cod, Atlantic, raw | 171955 | raw | 82 | 0.0% | — |
| 78 | corn kernels, frozen | USDA | Corn, sweet, yellow, frozen, kernels cut off cob, unprepared (Includes foods for USDA's Food Distribution Program) | 168398 | as-sold | 88 | 0.0% | — |
| 79 | corn tortilla | USDA | Tortillas, ready-to-bake or -fry, corn | 175036 | as-sold | 218 | 0.0% | — |
| 80 | cornstarch | USDA | Cornstarch | 169698 | as-sold | 381 | 0.0% | — |
| 81 | cottage cheese, 2% | USDA | Cheese, cottage, lowfat, 2% milkfat | 172182 | as-sold | 81 | 0.0% | — |
| 82 | couscous (dry) | USDA | Couscous, dry | 169699 | dry | 376 | 0.0% | — |
| 83 | cucumber | USDA | Cucumber, with peel, raw | 168409 | raw | 15 | 0.0% | — |
| 84 | cumin seeds | USDA | Spices, cumin seed | 170923 | dry | 375 | 0.0% | — |
| 85 | curry powder | USDA | Spices, curry powder | 170924 | dry | 325 | 0.0% | — |
| 86 | dates, medjool | USDA | Dates, medjool | 168191 | raw | 277 | 0.0% | — |
| 87 | diced tomatoes, canned | USDA | Tomatoes, red, ripe, canned, packed in tomato juice | 170051 | as-sold | 16 | 0.0% | — |
| 88 | dried basil | USDA | Spices, basil, dried | 171317 | dry | 233 | 0.0% | — |
| 89 | dried thyme | USDA | Spices, thyme, dried | 170938 | dry | 276 | 0.0% | — |
| 90 | edamame, frozen | USDA | Edamame, frozen, unprepared | 168410 | as-sold | 109 | 0.0% | — |
| 91 | egg white | USDA | Egg, white, raw, fresh | 172183 | raw | 52 | 0.0% | — |
| 92 | eggplant | USDA | Eggplant, raw | 169228 | raw | 25 | 0.0% | — |
| 93 | fennel seeds | USDA | Spices, fennel seed | 171323 | dry | 345 | 0.0% | — |
| 94 | fenugreek seeds | USDA | Spices, fenugreek seed | 171324 | dry | 323 | 0.0% | — |
| 95 | feta cheese | USDA | Cheese, feta | 173420 | as-sold | 265 | 0.0% | — |
| 96 | flaxseed | USDA | Seeds, flaxseed | 169414 | as-sold | 534 | 0.0% | — |
| 97 | gelatin, bovine | USDA | Gelatins, dry powder, unsweetened | 169599 | dry | 335 | 0.0% | — |
| 98 | gelatin, pork-derived | USDA | Gelatins, dry powder, unsweetened | 169599 | dry | 335 | 0.0% | — |
| 99 | gelatin, unflavored | USDA | Gelatins, dry powder, unsweetened | 169599 | dry | 335 | 0.0% | — |
| 100 | ghee | USDA | Butter oil, anhydrous | 173412 | as-sold | 876 | 0.0% | — |
| 101 | granulated sugar | USDA | Sugars, granulated | 169655 | as-sold | 387 | 0.0% | — |
| 102 | grapes | USDA | Grapes, red or green (European type, such as Thompson seedless), raw | 174683 | raw | 69 | 0.0% | — |
| 103 | green beans | USDA | Beans, snap, green, raw | 169961 | raw | 31 | 0.0% | — |
| 104 | green bell pepper | USDA | Peppers, sweet, green, raw | 170427 | raw | 20 | 0.0% | — |
| 105 | green cabbage | USDA | Cabbage, raw | 169975 | raw | 25 | 0.0% | — |
| 106 | green onion | USDA | Onions, spring or scallions (includes tops and bulb), raw | 170005 | raw | 32 | 0.0% | — |
| 107 | ground beef, 85% lean | USDA | Beef, ground, 85% lean meat / 15% fat, raw (Includes foods for USDA's Food Distribution Program) | 171796 | raw | 215 | 0.0% | — |
| 108 | ground cardamom | USDA | Spices, cardamom | 170919 | dry | 311 | 0.0% | — |
| 109 | ground chicken | USDA | Chicken, ground, raw | 171116 | raw | 143 | 0.0% | — |
| 110 | ground cinnamon | USDA | Spices, cinnamon, ground | 171320 | dry | 247 | 0.0% | — |
| 111 | ground cloves | USDA | Spices, cloves, ground | 171321 | dry | 274 | 0.0% | — |
| 112 | ground ginger | USDA | Spices, ginger, ground | 170926 | dry | 335 | 0.0% | — |
| 113 | ground pork | USDA | Pork, fresh, ground, raw | 167902 | raw | 263 | 0.0% | — |
| 114 | ground turkey, 93% lean | USDA | Turkey, ground, 93% lean, 7% fat, raw | 172850 | raw | 150 | 0.0% | — |
| 115 | ham, sliced deli | USDA | Ham, sliced, pre-packaged, deli meat (96%fat free, water added) | 173863 | as-sold | 107 | 0.0% | — |
| 116 | heavy cream | USDA | Cream, fluid, heavy whipping | 170859 | as-sold | 340 | 0.0% | — |
| 117 | honey | USDA | Honey | 169640 | as-sold | 304 | 0.0% | — |
| 118 | hot sauce | USDA | Sauce, ready-to-serve, pepper or hot | 174527 | as-sold | 11 | 0.0% | — |
| 119 | iceberg lettuce | USDA | Lettuce, iceberg (includes crisphead types), raw | 169248 | raw | 14 | 0.0% | — |
| 120 | jalapeño | USDA | Peppers, jalapeno, raw | 168576 | raw | 29 | 0.0% | — |
| 121 | kale | USDA | Kale, raw | 168421 | raw | 35 | 0.0% | — |
| 122 | ketchup | USDA | Catsup | 168556 | as-sold | 101 | 0.0% | — |
| 123 | kidney beans, canned, drained | USDA | Beans, kidney, red, mature seeds, canned, drained solids | 174285 | as-sold | 124 | 0.0% | — |
| 124 | lard | USDA | Lard | 171401 | as-sold | 902 | 0.0% | — |
| 125 | lemon | USDA | Lemons, raw, without peel | 167746 | raw | 29 | 0.0% | — |
| 126 | lime juice | USDA | Lime juice, raw | 168156 | raw | 25 | 0.0% | — |
| 127 | mango | USDA | Mangos, raw | 169910 | raw | 60 | 0.0% | — |
| 128 | maple syrup | USDA | Syrups, maple | 169661 | as-sold | 260 | 0.0% | — |
| 129 | marshmallows | USDA | Candies, marshmallows | 167995 | as-sold | 318 | 0.0% | — |
| 130 | mayonnaise | USDA | Salad dressing, mayonnaise, regular | 171009 | as-sold | 680 | 0.0% | — |
| 131 | milk, skim | USDA | Milk, nonfat, fluid, with added vitamin A and vitamin D (fat free or skim) | 171269 | as-sold | 34 | 0.0% | — |
| 132 | milk, whole | USDA | Milk, whole, 3.25% milkfat, with added vitamin D | 171265 | as-sold | 61 | 0.0% | — |
| 133 | mint | USDA | Spearmint, fresh | 173475 | raw | 44 | 0.0% | — |
| 134 | mozzarella, part-skim | USDA | Cheese, mozzarella, part skim milk | 170847 | as-sold | 254 | 0.0% | — |
| 135 | mustard seeds | USDA | Spices, mustard seed, ground | 170929 | dry | 508 | 0.0% | — |
| 136 | okra | USDA | Okra, raw | 169260 | raw | 33 | 0.0% | — |
| 137 | onion powder | USDA | Spices, onion powder | 171327 | dry | 341 | 0.0% | — |
| 138 | orange | USDA | Oranges, raw, all commercial varieties | 169097 | raw | 47 | 0.0% | — |
| 139 | parmesan, grated | USDA | Cheese, parmesan, grated | 171247 | as-sold | 420 | 0.0% | — |
| 140 | parsley | USDA | Parsley, fresh | 170416 | raw | 36 | 0.0% | — |
| 141 | pasta (dry) | USDA | Pasta, dry, enriched | 169736 | dry | 371 | 0.0% | — |
| 142 | peanut butter | USDA | Peanut butter, smooth style, with salt (Includes foods for USDA's Food Distribution Program) | 174266 | as-sold | 598 | 0.0% | — |
| 143 | peanuts | USDA | Peanuts, all types, raw | 172430 | raw | 567 | 0.0% | — |
| 144 | peas, frozen | USDA | Peas, green, frozen, unprepared (Includes foods for USDA's Food Distribution Program) | 170016 | as-sold | 77 | 0.0% | — |
| 145 | pepperoni | USDA | Pepperoni, beef and pork, sliced | 2759006 | as-sold | — | 0.0% | note: no energy_kcal, protein_g, carbohydrate_g, fat_g in the mapping |
| 146 | pita bread | USDA | Bread, pita, white, enriched | 174915 | as-sold | 275 | 0.0% | — |
| 147 | pork chop, boneless | USDA | Pork, fresh, loin, top loin (chops), boneless, separable lean and fat, raw | 167839 | raw | 155 | 0.0% | — |
| 148 | pork sausage, Italian | USDA | Sausage, Italian, pork, mild, raw | 171631 | raw | 290 | 0.0% | — |
| 149 | pork tenderloin | USDA | Pork, fresh, loin, tenderloin, separable lean and fat, raw | 168312 | raw | 120 | 0.0% | — |
| 150 | quinoa (dry) | USDA | Quinoa, uncooked | 168874 | dry | 368 | 0.0% | — |
| 151 | raisins | USDA | Raisins, dark, seedless (Includes foods for USDA's Food Distribution Program) | 168165 | raw | 299 | 0.0% | — |
| 152 | red lentils (dry) | USDA | Lentils, pink or red, raw | 174284 | dry | 358 | 0.0% | — |
| 153 | red pepper flakes | USDA | Spices, pepper, red or cayenne | 170932 | dry | 318 | 0.0% | — |
| 154 | refried beans, traditional | USDA | Refried beans, canned, traditional style | 172438 | as-sold | 90 | 0.0% | description says 'canned' |
| 155 | russet potato | USDA | Potatoes, russet, flesh and skin, raw (Includes foods for USDA's Food Distribution Program) | 170027 | raw | 79 | 0.0% | — |
| 156 | salami | USDA | Salami, dry or hard, pork | 172938 | dry | 407 | 0.0% | — |
| 157 | salmon, Atlantic, fillet | USDA | Fish, salmon, Atlantic, farmed, raw | 175167 | raw | 208 | 0.0% | — |
| 158 | salsa | USDA | Sauce, salsa, ready-to-serve | 174524 | as-sold | 29 | 0.0% | — |
| 159 | salt | USDA | Salt, table | 173468 | dry | 0 | 0.0% | — |
| 160 | sesame oil | USDA | Oil, sesame, salad or cooking | 171016 | as-sold | 884 | 0.0% | — |
| 161 | sesame seeds | USDA | Seeds, sesame seeds, whole, dried | 170150 | dry | 573 | 0.0% | — |
| 162 | shrimp, raw | USDA | Crustaceans, shrimp, raw | 175179 | raw | 85 | 0.0% | — |
| 163 | soy sauce | USDA | Soy sauce made from soy and wheat (shoyu) | 174277 | as-sold | 53 | 0.0% | — |
| 164 | spinach, frozen | USDA | Spinach, frozen, chopped or leaf, unprepared (Includes foods for USDA's Food Distribution Program) | 169287 | as-sold | 29 | 0.0% | — |
| 165 | sriracha | USDA | Sauce, hot chile, sriracha | 171186 | as-sold | 93 | 0.0% | — |
| 166 | strawberries | USDA | Strawberries, raw | 167762 | raw | 32 | 0.0% | — |
| 167 | sunflower seeds | USDA | Seeds, sunflower seed kernels, dried | 170562 | dry | 584 | 0.0% | — |
| 168 | sweet potato | USDA | Sweet potato, raw, unprepared (Includes foods for USDA's Food Distribution Program) | 168482 | raw | 86 | 0.0% | — |
| 169 | tahini | USDA | Seeds, sesame butter, tahini, from roasted and toasted kernels (most common type) | 170189 | as-sold | 595 | 0.0% | — |
| 170 | tilapia fillet | USDA | Fish, tilapia, raw | 175176 | raw | 96 | 0.0% | — |
| 171 | tofu, firm | USDA | Tofu, firm, prepared with calcium sulfate and magnesium chloride (nigari) | 172448 | as-sold | 78 | 0.0% | — |
| 172 | tomato sauce | USDA | Tomato products, canned, sauce | 170054 | as-sold | 24 | 0.0% | — |
| 173 | tuna, light, canned in water | USDA | Fish, tuna, light, canned in water, drained solids (Includes foods for USDA's Food Distribution Program) | 173709 | as-sold | 86 | 0.0% | — |
| 174 | turkey breast, boneless | USDA | Turkey, retail parts, breast, meat only, raw | 174515 | raw | 114 | 0.0% | — |
| 175 | vanilla extract | USDA | Vanilla extract | 173471 | as-sold | 288 | 0.0% | — |
| 176 | vegetable broth | USDA | Soup, vegetable broth, ready to serve | 171583 | as-sold | 5 | 0.0% | — |
| 177 | walnuts | USDA | Nuts, walnuts, english | 170187 | as-sold | 654 | 0.0% | — |
| 178 | water | USDA | Beverages, water, tap, drinking | 173647 | as-sold | 0 | 0.0% | — |
| 179 | white mushrooms | USDA | Mushrooms, white, raw | 169251 | raw | 22 | 0.0% | — |
| 180 | white vinegar | USDA | Vinegar, distilled | 172237 | as-sold | 18 | 0.0% | — |
| 181 | whole wheat bread | USDA | Bread, whole-wheat, commercially prepared | 172688 | as-sold | 252 | 0.0% | — |
| 182 | whole wheat flour | USDA | Wheat flour, whole-grain (Includes foods for USDA's Food Distribution Program) | 168893 | as-sold | 340 | 0.0% | — |
| 183 | yellow mustard | USDA | Mustard, prepared, yellow | 172234 | as-sold | 60 | 0.0% | — |
| 184 | yogurt, plain whole milk | USDA | Yogurt, plain, whole milk | 171284 | as-sold | 61 | 0.0% | — |
| 185 | zucchini | USDA | Squash, summer, zucchini, includes skin, raw | 169291 | raw | 17 | 0.0% | — |
