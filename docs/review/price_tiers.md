# Budget tiers per ingredient (step 2b.6, AA6; four tiers since its approval): for your review

Each ingredient's price tier decides which plan tiers may buy it: **Broke mode** buys only the *staples*,
**Cheapest** adds the *cheap* items, **A bit better** the *better* ones, **Fancy** the *fancy* ones. Items with no
tier (seasonings, oils, condiments, sweeteners, stocks, baking items) work in every tier, and so does anything you
already have, your Always-have items and your could-buy items. Variety: at most 7 portions of one recipe a week in
Broke mode, 5 in Cheapest, 4 in A bit better, 3 in Fancy. A bit better includes upgrades (at least a quarter of
the lunches and dinners, 2 or more, use a better or fancy item for at least 25 g a portion); Fancy as many with a
premium protein (a fancy protein, at least 50 g a portion). Broke mode never buys protein powder and counts a
stock-up item at its whole pack.

**Basis:** *Broke staple* is your Broke list (rice, lentils, eggs, chickpeas, oats, frozen veg, tortillas,
family-pack chicken) plus the basics to cook them that I added (yellow onion, potato, carrot, green cabbage, canned
tomatoes, tomato sauce and paste, flour, 2% milk, canned black and kidney beans, banana): please check these;
*protein per $* is derived from the seed prices for foods bought for their protein (your stores' cheapest price;
at least 20 g of protein a dollar is cheap, at least 12 better, less fancy; Broke's chicken and eggs are staples);
*your example* follows your AA6 list (fresh vegetables in A bit better); *estimate* is my judgment where protein
per dollar doesn't fit or there's no price. Edit `price_tier` in `backend/app/seed/data/ingredients.json` and
re-seed to change one. An item with no price at your stores never counts as free in a tier plan: a recipe needing
one you don't have is left out of that tier.

From an empty pantry, Broke mode can make 8 of the 47 seed dishes, Cheapest 24, A bit better 41, Fancy 47
(a dish counts when every line, or its budget equivalent, is one the tier buys).

## Broke mode staples (34)

| Ingredient | Category | Basis | Protein per $ |
|---|---|---|---|
| milk, 2% | dairy | Broke staple | 23.1 g |
| banana | fruit | Broke staple | 8.4 g |
| all-purpose flour | grain | Broke staple | 67.1 g |
| brown rice (dry) | grain | Broke staple | no price |
| corn tortilla | grain | Broke staple | 16.5 g |
| flour tortilla (Price Rite, 37 g) | grain | Broke staple | 30.2 g |
| long-grain white rice (dry) | grain | Broke staple | 40.5 g |
| rolled oats | grain | Broke staple | 26.9 g |
| black beans, canned | legume | Broke staple | 16.3 g |
| brown lentils (dry) | legume | Broke staple | no price |
| chickpeas, canned, drained | legume | Broke staple | 18.0 g |
| chickpeas, dried | legume | Broke staple | no price |
| kidney beans, canned, drained | legume | Broke staple | no price |
| red lentils (dry) | legume | Broke staple | 54.5 g |
| chicken breast, bone-in skin-on | protein | Broke staple | 30.4 g |
| chicken breast, boneless skinless | protein | Broke staple | 25.6 g |
| chicken drumstick | protein | Broke staple | 36.8 g |
| chicken thigh, bone-in skin-on | protein | Broke staple | 27.5 g |
| chicken thigh, boneless skinless | protein | Broke staple | 25.6 g |
| egg, large | protein | Broke staple | 27.0 g |
| whole chicken | protein | Broke staple | 32.0 g |
| broccoli, frozen | vegetable | Broke staple | 5.3 g |
| carrot | vegetable | Broke staple | 4.2 g |
| cauliflower, frozen florets | vegetable | Broke staple | 3.8 g |
| corn kernels, frozen | vegetable | Broke staple | 6.9 g |
| diced tomatoes, canned | vegetable | Broke staple | 3.6 g |
| green beans, frozen | vegetable | Broke staple | 4.1 g |
| green cabbage | vegetable | Broke staple | no price |
| peas, frozen | vegetable | Broke staple | 11.9 g |
| russet potato | vegetable | Broke staple | 12.2 g |
| spinach, frozen | vegetable | Broke staple | 6.9 g |
| tomato paste | vegetable | Broke staple | 9.3 g |
| tomato sauce | vegetable | Broke staple | 5.9 g |
| yellow onion | vegetable | Broke staple | 5.0 g |

## Cheapest (24)

| Ingredient | Category | Basis | Protein per $ |
|---|---|---|---|
| Greek yogurt, plain nonfat | dairy | protein per $ | 20.6 g |
| milk, skim | dairy | estimate | no price |
| milk, whole | dairy | estimate | no price |
| chapati (roti) | grain | estimate | no price |
| pasta (dry) | grain | estimate | no price |
| whole wheat bread | grain | estimate | no price |
| whole wheat flour | grain | estimate | no price |
| black beans, dried | legume | estimate | no price |
| kidney beans, dried | legume | estimate | no price |
| refried beans, traditional | legume | estimate | no price |
| flaxseed | nut_seed | protein per $ | 20.8 g |
| peanut butter | nut_seed | protein per $ | 36.1 g |
| peanuts | nut_seed | estimate | no price |
| tuna, light, canned in water | protein | protein per $ | 29.4 g |
| protein powder, double chocolate | supplement | protein per $ | 28.1 g |
| celery | vegetable | estimate | 1.9 g |
| corn, canned, drained | vegetable | estimate | no price |
| cucumber | vegetable | estimate | 2.5 g |
| green beans, canned, drained | vegetable | estimate | no price |
| iceberg lettuce | vegetable | estimate | no price |
| red onion | vegetable | estimate | 2.9 g |
| romaine lettuce | vegetable | estimate | 2.1 g |
| sweet potato | vegetable | estimate | 6.0 g |
| tomato | vegetable | estimate | 2.0 g |

## A bit better (55)

| Ingredient | Category | Basis | Protein per $ |
|---|---|---|---|
| Greek yogurt, plain whole milk | dairy | your example | no price |
| cheddar cheese | dairy | estimate | no price |
| cottage cheese, 2% | dairy | estimate | no price |
| feta cheese | dairy | estimate | no price |
| heavy cream | dairy | estimate | 4.1 g |
| mozzarella, part-skim | dairy | estimate | no price |
| yogurt, plain whole milk | dairy | estimate | 8.3 g |
| apple | fruit | estimate | no price |
| avocado | fruit | estimate | no price |
| blueberries, frozen | fruit | estimate | no price |
| grapes | fruit | estimate | no price |
| mango | fruit | estimate | 2.8 g |
| orange | fruit | estimate | no price |
| raisins | fruit | estimate | no price |
| strawberries | fruit | estimate | 0.9 g |
| strawberries, frozen | fruit | estimate | 0.7 g |
| couscous (dry) | grain | estimate | no price |
| pita bread | grain | estimate | 13.2 g |
| quinoa (dry) | grain | estimate | 16.1 g |
| edamame, frozen | legume | protein per $ | 15.3 g |
| tofu, firm | legume | estimate | no price |
| sunflower seeds | nut_seed | estimate | no price |
| tahini | nut_seed | estimate | no price |
| bacon | protein | estimate | no price |
| chicken sausage | protein | protein per $ | 16.2 g |
| chicken wing | protein | protein per $ | 15.0 g |
| egg white | protein | protein per $ | 14.2 g |
| ground chicken | protein | protein per $ | 17.6 g |
| ground pork | protein | estimate | no price |
| ground turkey, 93% lean | protein | protein per $ | 17.0 g |
| ham, sliced deli | protein | estimate | no price |
| pepperoni | protein | estimate | no price |
| pepperoni, chicken | protein | estimate | no price |
| pepperoni, pork only | protein | estimate | no price |
| pepperoni, turkey | protein | estimate | no price |
| pork chop, boneless | protein | estimate | no price |
| pork sausage, Italian | protein | estimate | no price |
| pork tenderloin | protein | estimate | no price |
| salami | protein | estimate | no price |
| salami, chicken | protein | estimate | no price |
| salami, pork only | protein | estimate | no price |
| salami, turkey | protein | estimate | no price |
| tilapia fillet | protein | estimate | no price |
| turkey breast, boneless | protein | estimate | no price |
| bell pepper | vegetable | your example | 1.2 g |
| broccoli florets | vegetable | your example | 6.8 g |
| cauliflower | vegetable | your example | no price |
| eggplant | vegetable | your example | no price |
| green beans | vegetable | your example | 3.3 g |
| green bell pepper | vegetable | your example | no price |
| kale | vegetable | your example | no price |
| okra | vegetable | your example | no price |
| spinach, fresh | vegetable | your example | 3.3 g |
| white mushrooms | vegetable | your example | no price |
| zucchini | vegetable | your example | no price |

## Fancy (12)

| Ingredient | Category | Basis | Protein per $ |
|---|---|---|---|
| parmesan, grated | dairy | estimate | no price |
| blueberries | fruit | estimate | no price |
| dates, medjool | fruit | estimate | no price |
| almonds | nut_seed | protein per $ | 10.7 g |
| cashews | nut_seed | protein per $ | 8.3 g |
| chia seeds | nut_seed | protein per $ | 11.3 g |
| walnuts | nut_seed | estimate | no price |
| cod fillet | protein | estimate | no price |
| salmon, Atlantic, fillet | protein | protein per $ | 9.3 g |
| shrimp, raw | protein | protein per $ | 11.4 g |
| asparagus | vegetable | estimate | 3.0 g |
| brussels sprouts | vegetable | estimate | no price |

## Any tier (85)

brewed coffee, water, Worcestershire sauce, apple cider vinegar, beef bouillon cube, beef broth, chicken bouillon cube, chicken bouillon, contains beef, chicken bouillon, no beef listed, chicken broth, regular, coconut milk, canned, hot sauce, ketchup, low-sodium chicken broth, mayonnaise, salsa, soy sauce, sriracha, unsweetened cocoa powder, vanilla extract, vegetable broth, white vinegar, yellow mustard, butter, salted, butter, unsalted, beef tallow, coconut oil, ghee, lard, olive oil, sesame oil, vegetable oil, lemon, lemon juice, lime juice, cornstarch, sesame seeds, baking powder, baking soda, gelatin, bovine, gelatin, pork-derived, gelatin, unflavored, beef hot dog, beef steak, top sirloin, ground beef, 85% lean, pepperoni, pork and beef, salami, pork and beef, bay leaf, black pepper, cayenne pepper, chili powder, cumin seeds, curry powder, dried basil, dried oregano, dried thyme, fennel seeds, fenugreek seeds, garam masala, garlic powder, ground cardamom, ground cinnamon, ground cloves, ground coriander, ground cumin, ground ginger, ground turmeric, mustard seeds, onion powder, paprika, red pepper flakes, salt, smoked paprika, brown sugar, granulated sugar, honey, maple syrup, marshmallows, cilantro, garlic, ginger root, green onion, jalapeño, mint, parsley

## Classic and budget ingredients (the 2b.6 approval, item 4)

A line can name a budget equivalent from the same role. Broke mode and Cheapest cook with the cheaper one at your
stores; A bit better keeps the classic unless the budget one saves more than 25 cents a portion; Fancy and plans
without a tier keep the classic. On a recipe line's ⋯ you can fix it to one side for that recipe.

| Recipe | Classic | Budget equivalent | Cheaper at your stores |
|---|---|---|---|
| Air-fryer chicken over rice with broccoli | 400 g broccoli florets | 400 g broccoli, frozen | the classic, by $0.35 |
| Chicken and spinach gravy | 300 g spinach, fresh | 300 g spinach, frozen | the budget one, by $1.06 for the recipe |
| Chicken and spinach gravy | 2 count tomato | 240 ml diced tomatoes, canned | the budget one, by $0.54 for the recipe |
| Chicken keema with peas and tortillas | 2 count tomato | 240 ml diced tomatoes, canned | the budget one, by $0.54 for the recipe |
| Chicken shawarma pitas with garlic yogurt | 4 count pita bread | 8 count flour tortilla (Price Rite, 37 g) | the budget one, by $0.86 for the recipe |
| Chicken, broccoli and pepper stir-fry | 300 g broccoli florets | 300 g broccoli, frozen | the classic, by $0.26 |
| Chocolate protein mousse with strawberries | 250 g strawberries | 250 g strawberries, frozen | the budget one, by $0.28 for the recipe |
| Coconut shrimp curry with rice | 2 count tomato | 240 ml diced tomatoes, canned | the budget one, by $0.54 for the recipe |
| Dal tadka with rice | 2 count tomato | 240 ml diced tomatoes, canned | the budget one, by $0.54 for the recipe |
| Egg and veggie muffin cups | 100 g spinach, fresh | 100 g spinach, frozen | the budget one, by $0.35 for the recipe |
| Egg, spinach and pepper breakfast wraps | 100 g spinach, fresh | 100 g spinach, frozen | the budget one, by $0.35 for the recipe |
| Everyday chicken curry gravy | 3 count tomato | 360 ml diced tomatoes, canned | the budget one, by $0.81 for the recipe |
| Lemon garlic salmon with rice and broccoli | 400 g broccoli florets | 400 g broccoli, frozen | the classic, by $0.35 |
| Roast bone-in chicken breasts with quinoa and asparagus | 250 g quinoa (dry) | 250 g long-grain white rice (dry) | the budget one, by $1.76 for the recipe |
| Roast bone-in chicken breasts with quinoa and asparagus | 450 g asparagus | 450 g broccoli florets | the budget one, by $1.29 for the recipe |
| Shakshuka with warm tortillas | 800 ml diced tomatoes, canned | 6 count tomato | the classic, by $1.43 |
| Sheet-pan bone-in thighs with potatoes and green beans | 340 g green beans | 340 g green beans, frozen | the budget one, by $0.37 for the recipe |
| Strawberry protein yogurt parfaits | 300 g strawberries | 300 g strawberries, frozen | the budget one, by $0.33 for the recipe |

