# Seed step timing (step 2b.9): for your review

Every step of the 47 seeds was tagged by hand with the part of the dish it works on (blank = shared:
prep for everything, assembly, portioning), the appliance it occupies (blank = hands only, or
waiting), and its hands-on and hands-off minutes (FLOW_SPEC §20.1). Storage and reheating steps are
0 and 0 (after cooking, or on the eating day), and are left out below. Each seed's own schedule, at its
base servings, gives its start-to-finish time in the kitchen and when it's ready (a last wait in the
fridge, like overnight oats setting, counts toward ready but not toward the kitchen).

Checks (tested in `seed/tests/test_step_timing.py`): the tagged hands-on total is within 5 minutes of
the stated active minutes; the schedule's ready time is within 5 minutes of the stated total. Eleven
seeds' stated totals were off by more than 5 minutes and now use their schedule's time, rounded to 5
(marked *was*). Since step 2b.6 (AA7) every schedule chops and marinates first, then cooks, then portions:
five seeds' own times grew by 3–7 minutes, and the burrito bowls' total went from 30 to 35.

## Summary

| Seed | Active (stated) | Hands-on (tagged) | Total (stated) | In the kitchen | Ready |
|---|---|---|---|---|---|
| 10a_chocolate_peanut_butter_yogurt_bowl Chocolate peanut butter protein yogurt bowl | 5 | 5 | 5 | 5 min | 5 min |
| 10b_strawberry_protein_parfait Strawberry protein yogurt parfaits | 15 | 15 | 15 | 15 min | 15 min |
| 10c_chocolate_protein_mug_cakes Chocolate protein mug cakes | 10 | 10 | 15 | 13 min | 13 min |
| 10d_mango_lassi_smoothie Mango lassi smoothie | 10 | 10 | 10 | 10 min | 10 min |
| 10e_chocolate_protein_mousse_strawberries Chocolate protein mousse with strawberries | 20 | 20 | 80 | 20 min | 1 h 20 min |
| 1a_chicken_over_rice_garlic_yogurt Chicken over rice with garlic yogurt sauce | 35 | 32 | 50 | 51 min | 51 min |
| 1b_air_fryer_chicken_rice_broccoli Air-fryer chicken over rice with broccoli | 15 | 17 | 40 (*was* 30) | 39 min | 39 min |
| 1c_sheet_pan_chicken_peppers_rice Sheet-pan chicken and peppers over rice | 20 | 22 | 45 | 43 min | 43 min |
| 2a_everyday_chicken_curry_gravy Everyday chicken curry gravy | 35 | 37 | 55 (*was* 50) | 56 min | 56 min |
| 2b_yogurt_chicken_gravy Yogurt chicken gravy | 35 | 36 | 70 (*was* 80) | 1 h 12 min | 1 h 12 min |
| 2c_chicken_spinach_gravy Chicken and spinach gravy | 30 | 33 | 45 | 49 min | 49 min |
| 3a_double_chocolate_protein_pudding Double chocolate protein pudding | 5 | 5 | 35 | 5 min | 35 min |
| 3b_chocolate_protein_chia_pudding Chocolate protein chia pudding | 5 | 5 | 125 | 10 min | 2 h 10 min |
| 4a_egg_spinach_pepper_breakfast_wraps Egg, spinach and pepper breakfast wraps | 20 | 24 | 25 | 24 min | 24 min |
| 5a_chocolate_protein_overnight_oats Chocolate protein overnight oats | 5 | 5 | 485 | 5 min | 8 h 5 min |
| 6a_masala_egg_scramble_tortillas Masala egg scramble with tortillas | 15 | 18 | 20 | 18 min | 18 min |
| 6b_chicken_sausage_egg_burritos Chicken sausage and egg breakfast burritos | 25 | 26 | 30 | 27 min | 27 min |
| 6c_peanut_butter_banana_overnight_oats Peanut butter banana overnight oats | 10 | 10 | 490 | 10 min | 8 h 10 min |
| 6d_egg_white_veggie_muffin_cups Egg and veggie muffin cups | 15 | 16 | 40 | 38 min | 38 min |
| 6e_shakshuka_with_tortillas Shakshuka with warm tortillas | 20 | 21 | 35 | 35 min | 35 min |
| 6f_turkey_sweet_potato_hash Turkey and sweet potato breakfast hash | 25 | 25 | 35 | 31 min | 31 min |
| 6g_egg_kathi_rolls_green_chutney Egg kathi rolls with green chutney | 30 | 29 | 30 | 31 min | 31 min |
| 7a_chicken_tikka_rice_bowls Chicken tikka rice bowls | 25 | 22 | 60 | 1 h 2 min | 1 h 2 min |
| 7b_yogurt_chicken_salad_wraps Yogurt chicken salad wraps | 20 | 17 | 35 | 37 min | 37 min |
| 7c_chicken_black_bean_burrito_bowls Chicken and black bean burrito bowls | 25 | 23 | 35 (*was* 40, then 30) | 36 min | 36 min |
| 7d_tuna_chickpea_salad_bowls Tuna and chickpea salad bowls | 15 | 15 | 15 | 15 min | 15 min |
| 7e_egg_fried_rice_peas_carrots Egg fried rice with peas and carrots | 20 | 23 | 50 | 52 min | 52 min |
| 7f_dal_tadka_with_rice Dal tadka with rice | 20 | 23 | 35 (*was* 45) | 36 min | 36 min |
| 7g_chicken_shawarma_pitas Chicken shawarma pitas with garlic yogurt | 30 | 27 | 75 | 1 h 14 min | 1 h 14 min |
| 7h_ground_turkey_tacos Ground turkey tacos | 20 | 21 | 25 | 25 min | 25 min |
| 8a_butter_chicken_with_rice Butter chicken with rice | 40 | 36 | 55 (*was* 75) | 60 min | 60 min |
| 8b_chicken_korma_with_tortillas Chicken korma with tortillas | 40 | 37 | 55 (*was* 65) | 54 min | 54 min |
| 8c_chicken_chana_masala_with_rice Chicken chana masala with rice | 30 | 31 | 50 (*was* 55) | 49 min | 49 min |
| 8d_tandoori_drumsticks_rice_raita Tandoori-style drumsticks with rice and raita | 25 | 26 | 115 (*was* 90) | 1 h 57 min | 1 h 57 min |
| 8e_sheet_pan_bone_in_thighs_potatoes Sheet-pan bone-in thighs with potatoes and green beans | 15 | 17 | 55 | 59 min | 59 min |
| 8f_lemon_garlic_salmon_rice_broccoli Lemon garlic salmon with rice and broccoli | 15 | 15 | 35 | 40 min | 40 min |
| 8g_coconut_shrimp_curry_rice Coconut shrimp curry with rice | 20 | 22 | 35 (*was* 40) | 34 min | 34 min |
| 8h_chicken_keema_matar_tortillas Chicken keema with peas and tortillas | 30 | 33 | 40 | 39 min | 39 min |
| 8i_whole_roast_chicken_root_vegetables Whole roast chicken with root vegetables | 30 | 32 | 130 (*was* 110) | 2 h 10 min | 2 h 10 min |
| 8j_chicken_broccoli_pepper_stir_fry Chicken, broccoli and pepper stir-fry | 20 | 23 | 35 | 35 min | 35 min |
| 8k_air_fryer_wings_sweet_potato_wedges Air-fryer chicken wings with sweet potato wedges | 20 | 20 | 55 | 56 min | 56 min |
| 8l_bone_in_chicken_breast_quinoa_asparagus Roast bone-in chicken breasts with quinoa and asparagus | 20 | 20 | 55 | 56 min | 56 min |
| 9a_masala_roasted_chickpeas Masala roasted chickpeas | 10 | 11 | 45 | 49 min | 49 min |
| 9b_yogurt_cucumber_dip_pita Garlic yogurt cucumber dip with pita | 10 | 10 | 10 | 10 min | 10 min |
| 9c_egg_chaat Spiced egg chaat | 10 | 11 | 25 | 26 min | 26 min |
| 9d_air_fryer_chicken_tikka_bites Air-fryer chicken tikka bites | 15 | 14 | 50 | 54 min | 54 min |
| 9e_chili_lime_edamame Chili-lime edamame | 5 | 5 | 10 | 9 min | 9 min |

## Steps

**10a_chocolate_peanut_butter_yogurt_bowl Chocolate peanut butter protein yogurt bowl** (3 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 2 | 0 | Slice the banana. Warm the peanut butter for 10 seconds so it drizz... |
| 2 | no_cook |  |  | 2 | 0 | Whisk the protein powder, cocoa and milk into a paste, then whisk i... |
| 3 | portioning |  |  | 1 | 0 | Divide among 3 bowls, swirl in the peanut butter and top with the b... |

**10b_strawberry_protein_parfait Strawberry protein yogurt parfaits** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 4 | 0 | Slice the strawberries and chop the almonds. |
| 2 | stovetop | crunch | stovetop | 4 | 0 | Toast the oats and almonds in a dry pan over medium heat, stirring,... |
| 3 | no_cook | yogurt |  | 3 | 0 | Whisk the protein powder with the milk into a paste and stir it int... |
| 4 | portioning |  |  | 4 | 0 | Layer the yogurt and strawberries in 4 jars; pack the oat-almond cr... |

**10c_chocolate_protein_mug_cakes Chocolate protein mug cakes** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 4 | 0 | Whisk the protein powder, flour, cocoa, baking powder and sugar. Wh... |
| 2 | assembly |  |  | 2 | 0 | Stir the wet into the dry until just smooth and divide among 4 grea... |
| 3 | microwave | cakes | microwave | 2 | 3 | Microwave one mug at a time on high 60 to 75 seconds, until risen a... |
| 4 | portioning |  |  | 2 | 0 | Serve one mug each, warm. |

**10d_mango_lassi_smoothie Mango lassi smoothie** (3 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 6 | 0 | Peel the mangoes and mash the flesh to a smooth purée with a fork o... |
| 2 | no_cook |  |  | 3 | 0 | Whisk the mango purée with the yogurt, milk, honey and cardamom unt... |
| 3 | portioning |  |  | 1 | 0 | Pour into 3 glasses. |

**10e_chocolate_protein_mousse_strawberries Chocolate protein mousse with strawberries** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 4 | 0 | Slice the strawberries. Chill a bowl for whipping the cream. |
| 2 | no_cook |  |  | 5 | 0 | Whisk the protein powder, cocoa and milk to a paste and stir it int... |
| 3 | no_cook |  |  | 7 | 0 | Whip the cream to soft peaks and fold it gently into the chocolate ... |
| 4 | portioning |  |  | 4 | 60 | Layer the mousse and strawberries in 4 glasses and chill at least 1... |

**1a_chicken_over_rice_garlic_yogurt Chicken over rice with garlic yogurt sauce** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep | chicken |  | 10 | 0 | Cut the chicken thighs into large pieces. Mince the garlic. Chop th... |
| 2 | marinate | chicken |  | 3 | 15 | Toss the chicken with the olive oil, half the lemon juice, two-thir... |
| 3 | rice | rice | stovetop | 2 | 23 | Bring the broth to a boil, add the rinsed rice, cover and simmer on... |
| 4 | stovetop | chicken | stovetop | 8 | 4 | Heat a large skillet over medium-high heat. Sear the chicken in bat... |
| 5 | stovetop | chicken |  | 2 | 5 | Rest the chicken 5 minutes, then slice it. |
| 6 | assembly | sauce |  | 3 | 0 | Stir the yogurt with the remaining lemon juice, garlic and salt to ... |
| 7 | portioning |  |  | 4 | 0 | Divide the rice and chicken among 4 containers. Pack the sauce and ... |

**1b_air_fryer_chicken_rice_broccoli Air-fryer chicken over rice with broccoli** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep | chicken |  | 6 | 0 | Cut the chicken into even 1-inch-thick pieces. Toss with half the o... |
| 2 | rice | rice | stovetop | 2 | 23 | Bring the water to a boil, add the rinsed rice and a pinch of salt,... |
| 3 | air_fryer | chicken | air_fryer | 2 | 16 | Air fry the chicken in a single layer at 400F for 18 minutes, flipp... |
| 4 | air_fryer | broccoli | air_fryer | 2 | 8 | Toss the broccoli with the remaining oil and salt. Air fry at 400F ... |
| 5 | assembly | sauce |  | 2 | 0 | Stir the yogurt with the lemon juice and a pinch of salt for the sa... |
| 6 | portioning |  |  | 3 | 0 | Divide the rice, chicken and broccoli among 4 containers, with the ... |

**1c_sheet_pan_chicken_peppers_rice Sheet-pan chicken and peppers over rice** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep | chicken |  | 10 | 0 | Preheat the oven to 425°F. Cut the chicken into 1½-inch pieces, sli... |
| 2 | prep | chicken |  | 3 | 0 | Toss the chicken, peppers and onion with the oil, paprika, cumin, g... |
| 3 | oven | chicken | oven | 2 | 24 | Roast at 425°F for about 25 minutes, stirring once, until the chick... |
| 4 | rice | rice | stovetop | 2 | 23 | Meanwhile, bring the water to a boil, add the rinsed rice, cover an... |
| 5 | assembly | sauce |  | 2 | 0 | Stir the yogurt with the lemon juice and a pinch of salt. |
| 6 | portioning |  |  | 3 | 0 | Divide the rice, chicken and vegetables among 4 containers; pack th... |

**2a_everyday_chicken_curry_gravy Everyday chicken curry gravy** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep | gravy |  | 10 | 0 | Cut the chicken into bite-size pieces. Finely chop the onions and t... |
| 2 | stovetop | gravy | stovetop | 10 | 2 | Heat the oil in a heavy pot over medium heat. Cook the onions, stir... |
| 3 | stovetop | gravy | stovetop | 6 | 3 | Add the ginger-garlic paste and cook 1 minute. Add the tomatoes, tu... |
| 4 | stovetop | gravy | stovetop | 2 | 16 | Add the chicken and stir to coat. Pour in the water, cover and simm... |
| 5 | stovetop | gravy | stovetop | 2 | 0 | Stir in the garam masala and simmer 2 minutes more. Finish with cho... |
| 6 | assembly | tortillas | stovetop | 4 | 0 | Warm each tortilla on a dry pan about 30 seconds per side, like cha... |
| 7 | portioning |  |  | 3 | 0 | Divide the gravy among 4 containers. Keep 2 tortillas per serving w... |

**2b_yogurt_chicken_gravy Yogurt chicken gravy** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep | chicken |  | 10 | 0 | Cut the chicken into bite-size pieces. Thinly slice the onions. Gra... |
| 2 | marinate | chicken |  | 4 | 30 | Mix half the yogurt with half the garam masala, the turmeric, chili... |
| 3 | stovetop | gravy | stovetop | 10 | 2 | Heat the oil over medium heat and cook the onions until golden, abo... |
| 4 | stovetop |  | stovetop | 2 | 16 | Add the chicken with its marinade and the water. Cover and simmer 1... |
| 5 | stovetop | gravy | stovetop | 3 | 0 | Take the pot off the heat for 1 minute, then stir in the remaining ... |
| 6 | assembly | tortillas | stovetop | 4 | 0 | Warm each tortilla on a dry pan about 30 seconds per side, like cha... |
| 7 | portioning |  |  | 3 | 0 | Divide the gravy among 4 containers, with 2 tortillas per serving p... |

**2c_chicken_spinach_gravy Chicken and spinach gravy** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep | gravy |  | 9 | 0 | Cut the chicken into bite-size pieces. Chop the onion and tomatoes.... |
| 2 | stovetop | spinach | stovetop | 4 | 1 | Wilt the spinach in a large pot with a splash of water, about 2 min... |
| 3 | stovetop | gravy | stovetop | 10 | 5 | Heat the oil over medium heat. Cook the onion until golden, about 8... |
| 4 | stovetop | gravy | stovetop | 2 | 13 | Add the chicken and water, cover and simmer about 15 minutes, until... |
| 5 | stovetop |  | stovetop | 1 | 2 | Stir in the chopped spinach and garam masala and simmer 3 minutes. |
| 6 | assembly | tortillas | stovetop | 4 | 0 | Warm each tortilla on a dry pan about 30 seconds per side, like cha... |
| 7 | portioning |  |  | 3 | 0 | Divide the gravy among 4 containers, with 2 tortillas per serving p... |

**3a_double_chocolate_protein_pudding Double chocolate protein pudding** (2 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 1 | 0 | Measure the protein powder, cocoa and milk into a mixing bowl. |
| 2 | no_cook |  |  | 2 | 0 | Whisk the protein powder, cocoa and milk into a smooth paste with n... |
| 3 | no_cook |  |  | 1 | 0 | Fold the paste into the Greek yogurt with the vanilla until evenly ... |
| 4 | portioning |  |  | 1 | 30 | Divide into 2 cups and chill at least 30 minutes before serving. |

**3b_chocolate_protein_chia_pudding Chocolate protein chia pudding** (2 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 1 | 0 | Set out 2 jars with lids and measure the milk, protein powder and c... |
| 2 | no_cook |  |  | 2 | 0 | Whisk the protein powder and cocoa into the milk until smooth, then... |
| 3 | no_cook |  |  | 1 | 5 | Stir in the chia seeds, wait 5 minutes, then stir again to break up... |
| 4 | portioning |  |  | 1 | 120 | Divide between the 2 jars, seal and chill at least 2 hours, or over... |

**4a_egg_spinach_pepper_breakfast_wraps Egg, spinach and pepper breakfast wraps** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 7 | 0 | Dice the bell pepper and onion and roughly chop the spinach. Whisk ... |
| 2 | stovetop | filling | stovetop | 6 | 0 | Heat the oil in a large nonstick pan over medium heat. Cook the pep... |
| 3 | stovetop | filling | stovetop | 4 | 0 | Pour in the eggs and stir gently until fully set with no runny egg ... |
| 4 | assembly |  | stovetop | 5 | 0 | Warm the tortillas on a dry pan about 30 seconds per side. Spoon th... |
| 5 | portioning |  |  | 2 | 0 | Pack 2 wraps per container. To freeze, wrap each one in foil first. |

**5a_chocolate_protein_overnight_oats Chocolate protein overnight oats** (1 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 1 | 0 | Set out a jar with a lid. Slice the banana only when serving. |
| 2 | no_cook |  |  | 1 | 0 | Whisk the protein powder into the milk until smooth. |
| 3 | no_cook |  |  | 2 | 0 | Stir in the Greek yogurt, oats and chia seeds until evenly combined. |
| 4 | portioning |  |  | 1 | 480 | Spoon into the jar, seal and refrigerate overnight so the oats soften. |
| 5 | assembly |  |  | 0 | 0 | Stir, then top with sliced banana when serving. |

**6a_masala_egg_scramble_tortillas Masala egg scramble with tortillas** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 4 | 0 | Chop the onion and tomatoes, mince the jalapeño and beat the eggs w... |
| 2 | stovetop | scramble | stovetop | 6 | 1 | Heat the oil in a skillet over medium heat. Cook the onion and jala... |
| 3 | stovetop | scramble | stovetop | 4 | 0 | Pour in the eggs and stir gently until softly set and no liquid egg... |
| 4 | assembly | tortillas | stovetop | 2 | 0 | Warm each tortilla on a dry pan about 30 seconds per side, like cha... |
| 5 | portioning |  |  | 2 | 0 | Divide the scramble among 4 plates with 2 tortillas each, topped wi... |

**6b_chicken_sausage_egg_burritos Chicken sausage and egg breakfast burritos** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 7 | 0 | Slice the sausage, dice the pepper and onion, and beat the eggs wit... |
| 2 | stovetop | filling | stovetop | 7 | 1 | Heat the oil in a large skillet over medium-high heat. Brown the sa... |
| 3 | stovetop | filling | stovetop | 3 | 0 | Lower the heat, pour in the eggs and stir until softly set with no ... |
| 4 | assembly |  | stovetop | 6 | 0 | Warm the tortillas, spoon in the filling and roll them up tightly. |
| 5 | portioning |  |  | 3 | 0 | Wrap 2 burritos per serving. Pack the salsa separately. |

**6c_peanut_butter_banana_overnight_oats Peanut butter banana overnight oats** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 4 | 0 | Slice the bananas. Stir the peanut butter with a splash of the milk... |
| 2 | no_cook |  |  | 3 | 0 | Mix the oats, milk, yogurt, peanut butter, flaxseed, cinnamon and h... |
| 3 | portioning |  |  | 3 | 480 | Divide among 4 jars, top with the banana and chill overnight. |

**6d_egg_white_veggie_muffin_cups Egg and veggie muffin cups** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 7 | 0 | Heat the oven to 350F and oil a 12-cup muffin pan. Chop the spinach... |
| 2 | assembly |  |  | 5 | 0 | Whisk the eggs, egg whites, milk, garlic powder, salt and pepper. D... |
| 3 | oven | cups | oven | 1 | 22 | Bake at 350F for 20 to 22 minutes, until puffed and set in the center. |
| 4 | portioning |  |  | 3 | 0 | Cool 5 minutes, then pack 3 cups per serving. |

**6e_shakshuka_with_tortillas Shakshuka with warm tortillas** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 5 | 0 | Dice the onion, slice the peppers and garlic. |
| 2 | stovetop | shakshuka | stovetop | 7 | 2 | Heat the oil in a wide skillet over medium heat. Cook the onion and... |
| 3 | stovetop | shakshuka | stovetop | 1 | 9 | Add the tomatoes and salt and simmer until thickened, about 10 minu... |
| 4 | stovetop | shakshuka | stovetop | 3 | 5 | Make 8 wells, crack in the eggs, cover and cook until the whites ar... |
| 5 | assembly | tortillas | stovetop | 3 | 0 | Warm each tortilla on a dry pan about 30 seconds per side, like cha... |
| 6 | portioning |  |  | 2 | 0 | Serve 2 eggs with sauce and 2 tortillas per person, topped with cil... |

**6f_turkey_sweet_potato_hash Turkey and sweet potato breakfast hash** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 8 | 0 | Dice the sweet potatoes, onion and pepper. Mince the garlic. |
| 2 | stovetop | hash | stovetop | 4 | 8 | Heat the oil in a large skillet over medium-high heat. Cook the swe... |
| 3 | stovetop | hash | stovetop | 7 | 1 | Push the potatoes aside, add the turkey, onion, pepper, garlic and ... |
| 4 | stovetop | eggs | stovetop | 3 | 1 | Fry the eggs in a separate pan until the whites are set. |
| 5 | portioning |  |  | 3 | 0 | Divide the hash among 4 plates and top each with an egg. |

**6g_egg_kathi_rolls_green_chutney Egg kathi rolls with green chutney** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 10 | 0 | Chop the cilantro, mint and jalapeño as finely as you can and stir ... |
| 2 | stovetop | rolls | stovetop | 14 | 2 | Heat a little oil in a skillet over medium heat. Pour in 1 beaten e... |
| 3 | assembly |  |  | 4 | 0 | Fill each roll with onion, cucumber and chutney, egg side in, and r... |
| 4 | portioning |  |  | 1 | 0 | Serve 2 rolls per person. |

**7a_chicken_tikka_rice_bowls Chicken tikka rice bowls** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep | chicken |  | 10 | 0 | Cut the chicken into large chunks. Grate the garlic and ginger. Dic... |
| 2 | marinate | chicken |  | 3 | 30 | Mix the yogurt, lemon juice, garlic, ginger, spices, oil and 1 tsp ... |
| 3 | rice | rice | stovetop | 2 | 23 | Bring 540 ml of water to a boil, add the rinsed rice, cover and sim... |
| 4 | air_fryer | chicken | air_fryer | 2 | 14 | Air fry the chicken in one layer at 400F for 14 to 16 minutes, turn... |
| 5 | assembly | salad |  | 2 | 0 | Toss the cucumber and onion with the remaining salt. |
| 6 | portioning |  |  | 3 | 0 | Divide the rice and chicken among 4 containers. Pack the salad sepa... |

**7b_yogurt_chicken_salad_wraps Yogurt chicken salad wraps** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep | salad |  | 6 | 0 | Dice the celery and red onion. Shred the romaine. |
| 2 | stovetop | chicken | stovetop | 4 | 20 | Cover the chicken with cold salted water, bring to a simmer and coo... |
| 3 | assembly |  |  | 4 | 0 | Stir the yogurt, lemon juice, mustard, salt and pepper; fold in the... |
| 4 | portioning |  |  | 3 | 0 | Pack the chicken salad in 4 containers, with the romaine and 2 tort... |

**7c_chicken_black_bean_burrito_bowls Chicken and black bean burrito bowls** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep | chicken |  | 7 | 0 | Dice the chicken and toss it with the chili powder, cumin, garlic p... |
| 2 | rice | rice | stovetop | 2 | 23 | Bring 540 ml of water to a boil, add the rinsed rice, cover and sim... |
| 3 | stovetop | chicken | stovetop | 8 | 2 | Heat the oil in a large skillet over medium-high heat and cook the ... |
| 4 | stovetop | chicken | stovetop | 2 | 1 | Warm the beans and corn in the same pan, 3 minutes. |
| 5 | portioning |  |  | 4 | 0 | Divide the rice, chicken, beans and corn among 4 containers. Pack t... |

**7d_tuna_chickpea_salad_bowls Tuna and chickpea salad bowls** (3 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 9 | 0 | Drain the tuna and chickpeas. Dice the cucumber, tomatoes and onion... |
| 2 | no_cook |  |  | 3 | 0 | Whisk the lemon juice, olive oil, salt and pepper. Toss everything ... |
| 3 | portioning |  |  | 3 | 0 | Divide among 3 containers with the dressing in a small jar. |

**7e_egg_fried_rice_peas_carrots Egg fried rice with peas and carrots** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep | vegetables |  | 6 | 0 | Dice the carrots, slice the green onions, mince the garlic and beat... |
| 2 | rice | rice | stovetop | 3 | 32 | Cook the rice: bring 540 ml of water to a boil, add the rice, cover... |
| 3 | stovetop | vegetables | stovetop | 3 | 0 | Heat half the vegetable oil in a wok or large skillet over high hea... |
| 4 | stovetop |  | stovetop | 8 | 0 | Add the remaining oil, the carrots and garlic and stir-fry 3 minute... |
| 5 | portioning |  |  | 3 | 0 | Divide among 4 containers. |

**7f_dal_tadka_with_rice Dal tadka with rice** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep | dal |  | 6 | 0 | Rinse the lentils. Chop the onion and tomatoes, slice the garlic an... |
| 2 | stovetop | dal | stovetop | 3 | 22 | Simmer the lentils with the water, turmeric and tomatoes, partly co... |
| 3 | rice | rice | stovetop | 2 | 23 | Bring 540 ml of water to a boil, add the rinsed rice, cover and sim... |
| 4 | stovetop | tadka | stovetop | 9 | 0 | For the tadka, heat the ghee in a small pan. Add the cumin seeds un... |
| 5 | portioning |  |  | 3 | 0 | Divide the dal and rice among 4 containers; top with cilantro. |

**7g_chicken_shawarma_pitas Chicken shawarma pitas with garlic yogurt** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep | salad |  | 8 | 0 | Grate the garlic. Slice the tomatoes and cucumber and shred the rom... |
| 2 | marinate | chicken |  | 4 | 30 | Toss the chicken with 2 tbsp of the oil, the lemon juice, two-third... |
| 3 | oven | chicken | oven | 6 | 25 | Roast on a lined sheet at 425F for 22 to 25 minutes, until browned ... |
| 4 | assembly |  |  | 5 | 0 | Stir the yogurt with the remaining garlic, oil and salt. Warm the p... |
| 5 | portioning |  |  | 4 | 0 | Pack the chicken in 4 containers with a pita, the salad and the gar... |

**7h_ground_turkey_tacos Ground turkey tacos** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 4 | 0 | Dice the onion and shred the romaine. |
| 2 | stovetop | filling | stovetop | 9 | 1 | Heat the oil in a skillet over medium-high heat. Cook the onion 3 m... |
| 3 | stovetop | filling | stovetop | 1 | 4 | Stir in the tomato sauce and simmer 5 minutes. Add the lime juice. |
| 4 | assembly | tortillas | stovetop | 4 | 0 | Warm the corn tortillas in a dry pan until soft and lightly charred. |
| 5 | portioning |  |  | 3 | 0 | Divide the filling among 4 containers, with 3 tortillas, romaine an... |

**8a_butter_chicken_with_rice Butter chicken with rice** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 10 | 0 | Cut the chicken into bite-size pieces. Chop the onion and grate the... |
| 2 | marinate | chicken |  | 4 | 20 | Toss the chicken with the yogurt, half the garam masala, the chili ... |
| 3 | rice | rice | stovetop | 2 | 23 | Bring 540 ml of water to a boil, add the rinsed rice, cover and sim... |
| 4 | stovetop | sauce | stovetop | 9 | 0 | Melt half the butter in a heavy pot over medium heat. Cook the onio... |
| 5 | stovetop | sauce | stovetop | 2 | 8 | Add the tomato sauce, fenugreek, sugar and remaining salt and simme... |
| 6 | stovetop |  | stovetop | 5 | 12 | Add the chicken with its marinade and simmer, covered, until cooked... |
| 7 | portioning |  |  | 4 | 0 | Divide the rice and curry among 4 containers; top with cilantro. |

**8b_chicken_korma_with_tortillas Chicken korma with tortillas** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep | cashews |  | 12 | 15 | Soak the cashews in hot water 15 minutes, drain, then mash them to ... |
| 2 | stovetop | korma | stovetop | 10 | 1 | Heat the ghee in a heavy pot over medium heat with the bay leaf, ca... |
| 3 | stovetop |  | stovetop | 8 | 12 | Add the chicken and cook 5 minutes. Lower the heat, stir in the cas... |
| 4 | assembly | tortillas | stovetop | 4 | 0 | Warm each tortilla on a dry pan about 30 seconds per side, like cha... |
| 5 | portioning |  |  | 3 | 0 | Divide the korma among 4 containers. Keep 2 tortillas per serving w... |

**8c_chicken_chana_masala_with_rice Chicken chana masala with rice** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 10 | 0 | Cut the chicken. Chop the onion, grate the ginger and garlic, drain... |
| 2 | rice | rice | stovetop | 2 | 23 | Bring 540 ml of water to a boil, add the rinsed rice, cover and sim... |
| 3 | stovetop | curry | stovetop | 10 | 1 | Heat the oil in a heavy pot over medium heat. Cook the onion until ... |
| 4 | stovetop | curry | stovetop | 5 | 18 | Add the tomatoes and salt and cook until thick, 8 minutes. Add the ... |
| 5 | portioning |  |  | 4 | 0 | Divide the rice and curry among 4 containers; top with cilantro. |

**8d_tandoori_drumsticks_rice_raita Tandoori-style drumsticks with rice and raita** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep | chicken |  | 10 | 0 | Slash the drumsticks to the bone in 2 or 3 places. Grate the garlic... |
| 2 | marinate | chicken |  | 4 | 60 | Mix the whole-milk yogurt, lemon juice, garlic, ginger, paprika, ch... |
| 3 | rice | rice | stovetop | 2 | 23 | Bring 540 ml of water to a boil, add the rinsed rice, cover and sim... |
| 4 | oven | chicken | oven | 3 | 37 | Roast on a rack over a lined sheet at 425F for 35 to 40 minutes, tu... |
| 5 | assembly | raita |  | 4 | 0 | Stir the Greek yogurt with the cucumber, mint, the remaining cumin ... |
| 6 | portioning |  |  | 3 | 0 | Divide the rice and drumsticks among 4 containers; pack the raita s... |

**8e_sheet_pan_bone_in_thighs_potatoes Sheet-pan bone-in thighs with potatoes and green beans** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 7 | 0 | Heat the oven to 425F. Cut the potatoes into wedges and trim the gr... |
| 2 | assembly |  |  | 4 | 0 | Toss the potatoes with half the oil and seasoning and spread on a l... |
| 3 | oven | tray | oven | 3 | 42 | Roast at 425F for 25 minutes. Add the green beans, toss them in the... |
| 4 | portioning |  |  | 3 | 0 | Divide among 4 containers; squeeze the lemon over. |

**8f_lemon_garlic_salmon_rice_broccoli Lemon garlic salmon with rice and broccoli** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 5 | 0 | Heat the oven to 400F. Cut the broccoli into florets and mince the ... |
| 2 | rice | rice | stovetop | 2 | 23 | Bring 540 ml of water to a boil, add the rinsed rice, cover and sim... |
| 3 | oven | tray | oven | 2 | 10 | Toss the broccoli with 2 tbsp of the oil and half the salt and roas... |
| 4 | oven | tray | oven | 3 | 12 | Add the salmon to the pan, brush with the remaining oil, the lemon ... |
| 5 | portioning |  |  | 3 | 0 | Divide the rice, broccoli and salmon among 4 containers; top with p... |

**8g_coconut_shrimp_curry_rice Coconut shrimp curry with rice** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 6 | 0 | Peel and devein the shrimp if needed. Chop the onion and tomatoes; ... |
| 2 | rice | rice | stovetop | 2 | 23 | Bring 540 ml of water to a boil, add the rinsed rice, cover and sim... |
| 3 | stovetop | curry | stovetop | 8 | 4 | Heat the oil in a pan over medium heat. Cook the onion until soft, ... |
| 4 | stovetop | curry | stovetop | 3 | 6 | Stir in the coconut milk and salt and simmer 5 minutes. Add the shr... |
| 5 | portioning |  |  | 3 | 0 | Divide the rice and curry among 4 containers; top with cilantro. |

**8h_chicken_keema_matar_tortillas Chicken keema with peas and tortillas** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 8 | 0 | Chop the onions and tomatoes; grate the ginger and garlic. |
| 2 | stovetop | keema | stovetop | 10 | 1 | Heat the oil in a wide pan over medium heat. Cook the onions until ... |
| 3 | stovetop | keema | stovetop | 8 | 6 | Add the ground chicken and cook, breaking it up, until no pink rema... |
| 4 | assembly | tortillas | stovetop | 4 | 0 | Warm each tortilla on a dry pan about 30 seconds per side, like cha... |
| 5 | portioning |  |  | 3 | 0 | Divide the keema among 4 containers. Keep 2 tortillas per serving w... |

**8i_whole_roast_chicken_root_vegetables Whole roast chicken with root vegetables** (6 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 12 | 0 | Heat the oven to 425F. Pat the chicken dry. Cut the vegetables into... |
| 2 | assembly |  |  | 10 | 0 | Rub the butter under and over the skin. Put the lemon halves and wh... |
| 3 | oven | chicken | oven | 2 | 83 | Roast at 425F for 70 to 85 minutes, until the skin is deep golden a... |
| 4 | assembly | chicken |  | 0 | 15 | Rest the chicken 15 minutes before carving. |
| 5 | portioning |  |  | 8 | 0 | Carve and divide the chicken and vegetables among 6 containers. |

**8j_chicken_broccoli_pepper_stir_fry Chicken, broccoli and pepper stir-fry** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 7 | 0 | Slice the chicken thinly. Cut the broccoli and peppers. Whisk the s... |
| 2 | rice | rice | stovetop | 2 | 23 | Bring 540 ml of water to a boil, add the rinsed rice, cover and sim... |
| 3 | stovetop | stir-fry | stovetop | 6 | 0 | Heat half the oil in a wok over high heat. Stir-fry the chicken unt... |
| 4 | stovetop | stir-fry | stovetop | 5 | 0 | Add the rest of the oil, the broccoli, peppers, garlic and ginger a... |
| 5 | portioning |  |  | 3 | 0 | Divide the rice and stir-fry among 4 containers; sprinkle with sesa... |

**8k_air_fryer_wings_sweet_potato_wedges Air-fryer chicken wings with sweet potato wedges** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 10 | 0 | Pat the wings very dry and toss with the baking powder, smoked papr... |
| 2 | air_fryer | wedges | air_fryer | 2 | 16 | Air fry the wedges at 400F for 16 to 18 minutes, shaking halfway; k... |
| 3 | air_fryer | wings | air_fryer | 2 | 23 | Air fry the wings in one layer at 400F for 22 to 25 minutes, flippi... |
| 4 | stovetop | wings | stovetop | 3 | 0 | Melt the butter with the hot sauce in a small pan and toss the wing... |
| 5 | portioning |  |  | 3 | 0 | Divide the wings and wedges among 4 containers. |

**8l_bone_in_chicken_breast_quinoa_asparagus Roast bone-in chicken breasts with quinoa and asparagus** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep | chicken |  | 8 | 0 | Heat the oven to 400F. Rub the chicken with 2 tbsp of the oil, the ... |
| 2 | oven | chicken | oven | 2 | 38 | Roast the chicken skin side up at 400F for 35 to 40 minutes, until ... |
| 3 | stovetop | quinoa | stovetop | 3 | 17 | Meanwhile simmer the quinoa in the broth, covered, 15 minutes; rest... |
| 4 | oven | asparagus | oven | 2 | 10 | For the last 12 minutes, roast the asparagus tossed with the remain... |
| 5 | portioning |  |  | 5 | 0 | Slice the chicken off the bone and divide it with the quinoa and as... |

**9a_masala_roasted_chickpeas Masala roasted chickpeas** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 4 | 0 | Heat the oven to 400F. Drain the chickpeas and pat them very dry. |
| 2 | oven | chickpeas | oven | 3 | 32 | Toss with the oil and roast on a sheet at 400F for 30 to 35 minutes... |
| 3 | assembly |  |  | 2 | 0 | Toss the hot chickpeas with the spices, salt and lime juice. |
| 4 | portioning |  |  | 2 | 0 | Cool completely and divide into 4 small jars. |

**9b_yogurt_cucumber_dip_pita Garlic yogurt cucumber dip with pita** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 5 | 0 | Grate the cucumber and squeeze out the liquid. Grate the garlic and... |
| 2 | no_cook |  |  | 3 | 0 | Stir the yogurt, cucumber, garlic, lemon juice, mint and salt; driz... |
| 3 | portioning |  |  | 2 | 0 | Divide the dip into 4 containers with a pita, cut in wedges, each. |

**9c_egg_chaat Spiced egg chaat** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep | topping |  | 3 | 0 | Finely dice the onion and tomato. |
| 2 | stovetop | eggs | stovetop | 2 | 15 | Lower the eggs into boiling water and cook 10 minutes, then cool th... |
| 3 | assembly |  |  | 5 | 0 | Peel and quarter the eggs; top with the onion, tomato, lemon juice,... |
| 4 | portioning |  |  | 1 | 0 | Serve 2 eggs per person. |

**9d_air_fryer_chicken_tikka_bites Air-fryer chicken tikka bites** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 6 | 0 | Cut the chicken into bite-size cubes and grate the garlic and ginger. |
| 2 | marinate |  |  | 4 | 30 | Mix the yogurt, lemon juice, garlic, ginger, spices and salt; coat ... |
| 3 | air_fryer |  | air_fryer | 2 | 10 | Air fry in one layer at 400F for 10 to 12 minutes, shaking halfway,... |
| 4 | portioning |  |  | 2 | 0 | Divide among 4 containers. |

**9e_chili_lime_edamame Chili-lime edamame** (4 servings)

| # | Section | Part | Appliance | Hands-on | Hands-off | Step |
|---|---|---|---|---|---|---|
| 1 | prep |  |  | 1 | 0 | Put the frozen edamame in a microwave-safe bowl with 2 tbsp of wate... |
| 2 | microwave |  | microwave | 2 | 4 | Microwave on high 4 to 5 minutes, stirring halfway, until hot. Drain. |
| 3 | assembly |  |  | 1 | 0 | Toss with the lime juice, chili powder and salt. |
| 4 | portioning |  |  | 1 | 0 | Divide among 4 containers. |

