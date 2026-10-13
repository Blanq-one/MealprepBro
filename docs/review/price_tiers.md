# Budget tiers per ingredient (step 2b.6, AA6): for your review

Each ingredient's price tier decides which plan tiers may buy it: Cheapest buys only *cheap* items, A bit
better adds *better* ones, Fancy adds *fancy* ones. Items with no tier (seasonings, oils, condiments,
sweeteners, stocks, baking items) work in every tier, and so does anything you already have, your Always-have
items and your could-buy items. The variety rule tightens with the tier: at most 5 portions of one recipe a week
in Cheapest, 4 in A bit better, 3 in Fancy.

**Basis:** *protein per $* is derived from the seed prices (your stores' cheapest price; at least 25 g of
protein a dollar is cheap, at least 12 better, less fancy), for foods bought for their protein; *your example*
follows your AA6 list (chicken thighs, eggs, lentils, rice, frozen veg and tortillas cheap; chicken breast,
ground turkey and more fresh veg better; salmon and shrimp fancy; some Greek yogurt and the basic salad
vegetables in Cheapest, since A bit better adds *more* of them); *estimate* is my judgment where protein per
dollar doesn't fit or there's no price. Edit `price_tier` in `backend/app/seed/data/ingredients.json` and
re-seed to change one.

Note: at the seed prices boneless chicken breast buys as much protein a dollar as boneless thighs (25.6 g);
it is in A bit better because your list puts it there. Canned beans and chickpeas buy 16-18 g a dollar
(better by the rule), but as everyday staples at about 40 cents per 100 g they're estimated cheap.

With these tiers, Cheapest can make 16 of the 47 seed dishes from an empty pantry, A bit better 40, Fancy all
47.

## Cheapest (56)

| Ingredient | Category | Basis | Protein per $ |
|---|---|---|---|
| Greek yogurt, plain nonfat | dairy | your example | 20.6 g |
| milk, 2% | dairy | estimate | 23.1 g |
| milk, skim | dairy | estimate | no price |
| milk, whole | dairy | estimate | no price |
| banana | fruit | estimate | 8.4 g |
| all-purpose flour | grain | estimate | 67.1 g |
| brown rice (dry) | grain | estimate | no price |
| chapati (roti) | grain | estimate | no price |
| corn tortilla | grain | your example | 16.5 g |
| flour tortilla (Price Rite, 37 g) | grain | your example | 30.2 g |
| long-grain white rice (dry) | grain | your example | 40.5 g |
| pasta (dry) | grain | estimate | no price |
| rolled oats | grain | estimate | 26.9 g |
| whole wheat bread | grain | estimate | no price |
| whole wheat flour | grain | estimate | no price |
| black beans, canned | legume | estimate | 16.3 g |
| black beans, dried | legume | estimate | no price |
| brown lentils (dry) | legume | your example | no price |
| chickpeas, canned, drained | legume | estimate | 18.0 g |
| chickpeas, dried | legume | estimate | no price |
| kidney beans, canned, drained | legume | estimate | no price |
| kidney beans, dried | legume | estimate | no price |
| red lentils (dry) | legume | your example | 54.5 g |
| refried beans, traditional | legume | estimate | no price |
| peanut butter | nut_seed | protein per $ | 36.1 g |
| peanuts | nut_seed | estimate | no price |
| chicken breast, bone-in skin-on | protein | protein per $ | 30.4 g |
| chicken drumstick | protein | protein per $ | 36.8 g |
| chicken thigh, bone-in skin-on | protein | protein per $ | 27.5 g |
| chicken thigh, boneless skinless | protein | your example | 25.6 g |
| egg, large | protein | your example | 27.0 g |
| tuna, light, canned in water | protein | protein per $ | 29.4 g |
| whole chicken | protein | protein per $ | 32.0 g |
| protein powder, double chocolate | supplement | protein per $ | 28.1 g |
| broccoli, frozen | vegetable | your example | no price |
| carrot | vegetable | estimate | 4.2 g |
| cauliflower, frozen florets | vegetable | your example | no price |
| celery | vegetable | estimate | 1.9 g |
| corn kernels, frozen | vegetable | your example | 6.9 g |
| corn, canned, drained | vegetable | estimate | no price |
| cucumber | vegetable | estimate | 2.5 g |
| diced tomatoes, canned | vegetable | estimate | 3.6 g |
| green beans, canned, drained | vegetable | estimate | no price |
| green beans, frozen | vegetable | your example | no price |
| green cabbage | vegetable | estimate | no price |
| iceberg lettuce | vegetable | estimate | no price |
| peas, frozen | vegetable | your example | 11.9 g |
| red onion | vegetable | estimate | 2.9 g |
| romaine lettuce | vegetable | estimate | 2.1 g |
| russet potato | vegetable | estimate | 12.2 g |
| spinach, frozen | vegetable | your example | no price |
| sweet potato | vegetable | estimate | 6.0 g |
| tomato | vegetable | estimate | 2.0 g |
| tomato paste | vegetable | estimate | 9.3 g |
| tomato sauce | vegetable | estimate | 5.9 g |
| yellow onion | vegetable | estimate | 5.0 g |

## A bit better (57)

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
| strawberries, frozen | fruit | estimate | no price |
| couscous (dry) | grain | estimate | no price |
| pita bread | grain | estimate | 13.2 g |
| quinoa (dry) | grain | estimate | 16.1 g |
| edamame, frozen | legume | protein per $ | 15.3 g |
| tofu, firm | legume | estimate | no price |
| flaxseed | nut_seed | protein per $ | 20.8 g |
| sunflower seeds | nut_seed | estimate | no price |
| tahini | nut_seed | estimate | no price |
| bacon | protein | estimate | no price |
| chicken breast, boneless skinless | protein | your example | 25.6 g |
| chicken sausage | protein | protein per $ | 16.2 g |
| chicken wing | protein | protein per $ | 15.0 g |
| egg white | protein | protein per $ | 14.2 g |
| ground chicken | protein | protein per $ | 17.6 g |
| ground pork | protein | estimate | no price |
| ground turkey, 93% lean | protein | your example | 17.0 g |
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
| salmon, Atlantic, fillet | protein | your example | 9.3 g |
| shrimp, raw | protein | your example | 11.4 g |
| asparagus | vegetable | estimate | 3.0 g |
| brussels sprouts | vegetable | estimate | no price |

## Any tier (85)

brewed coffee, water, Worcestershire sauce, apple cider vinegar, beef bouillon cube, beef broth, chicken bouillon cube, chicken bouillon, contains beef, chicken bouillon, no beef listed, chicken broth, regular, coconut milk, canned, hot sauce, ketchup, low-sodium chicken broth, mayonnaise, salsa, soy sauce, sriracha, unsweetened cocoa powder, vanilla extract, vegetable broth, white vinegar, yellow mustard, butter, salted, butter, unsalted, beef tallow, coconut oil, ghee, lard, olive oil, sesame oil, vegetable oil, lemon, lemon juice, lime juice, cornstarch, sesame seeds, baking powder, baking soda, gelatin, bovine, gelatin, pork-derived, gelatin, unflavored, beef hot dog, beef steak, top sirloin, ground beef, 85% lean, pepperoni, pork and beef, salami, pork and beef, bay leaf, black pepper, cayenne pepper, chili powder, cumin seeds, curry powder, dried basil, dried oregano, dried thyme, fennel seeds, fenugreek seeds, garam masala, garlic powder, ground cardamom, ground cinnamon, ground cloves, ground coriander, ground cumin, ground ginger, ground turmeric, mustard seeds, onion powder, paprika, red pepper flakes, salt, smoked paprika, brown sugar, granulated sugar, honey, maple syrup, marshmallows, cilantro, garlic, ginger root, green onion, jalapeño, mint, parsley
