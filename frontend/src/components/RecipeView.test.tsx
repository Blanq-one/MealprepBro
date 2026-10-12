import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { recipe } from "@/test/fixtures";

import { RecipeView } from "./RecipeView";

describe("RecipeView", () => {
  it("highlights the app's food-safety lines, including reheating", () => {
    render(<RecipeView recipe={recipe()} />);
    const notes = screen.getAllByTestId("safety-note").map((n) => n.textContent);
    expect(notes).toEqual(["Food safety: Cook chicken to 165°F (poultry).", "Food safety: Reheat leftovers to 165°F."]);
    expect(screen.getByRole("heading", { name: "Oven" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Reheating" })).toBeInTheDocument();
    expect(screen.getByText("425°F · 20 min")).toBeInTheDocument();
  });

  it("labels the heme / non-heme iron split as estimated", () => {
    render(<RecipeView recipe={recipe()} />);
    expect(screen.getByTestId("heme")).toHaveTextContent(
      "Iron, estimated split: 0.84 mg heme · 1.26 mg non-heme (estimated)",
    );
  });

  it("marks seed drafts and leaves other recipes unmarked", () => {
    const { unmount } = render(<RecipeView recipe={recipe()} />);
    expect(screen.getByText("Draft: adjust me")).toBeInTheDocument();
    unmount();
    render(<RecipeView recipe={recipe({ badge: null, origin: "llm", time_note: "est." })} />);
    expect(screen.queryByText("Draft: adjust me")).not.toBeInTheDocument();
    expect(screen.getByText(/\(est\.\)/)).toBeInTheDocument();
  });

  it("shows the server's lines, nutrition and per-portion cost", () => {
    render(<RecipeView recipe={recipe()} />);
    expect(screen.getByText("680 g")).toBeInTheDocument();
    expect(screen.getByText(/chicken thigh, boneless skinless, cubed/)).toBeInTheDocument();
    expect(screen.getByText("560 kcal")).toBeInTheDocument();
    expect(screen.getByText("42.0 g")).toBeInTheDocument();
    expect(screen.getByText(/\$3\.10 est\./)).toBeInTheDocument();
    expect(screen.getByText("About 350 g per container")).toBeInTheDocument();
  });

  it("shows each line's amount once, then the server's per-portion note (2b.4 approval, A1)", () => {
    render(<RecipeView recipe={recipe()} />);
    expect(screen.getByText("680 g")).toBeInTheDocument();
    expect(screen.getByText("170 g per portion · 680 g for the batch of 4")).toBeInTheDocument();
    expect(screen.queryByText(/680 g chicken thigh/)).toBeNull(); // the name isn't printed twice
  });

  it("a prep item shows its steps by stage, each with how it keeps when prep stops there (FLOW_SPEC §19.10)", () => {
    const storage = (note: string) => ({ stored: true, made_on_the_day: false, fridge_days: 1, freezer: true, note, sources: ["FoodSafety.gov Cold Food Storage Chart: Fresh poultry, pieces (1 to 2 days; 9 months)"] });
    const item = recipe({
      kind: "prep_item",
      title: "Tandoori drumsticks",
      prep: {
        label: "tandoori drumsticks",
        brings: "protein",
        pairs_with: ["indian"],
        stages: [
          { n: 1, state: "marinated", state_display: "Marinated", storage: storage("Keeps 1 day in the fridge, or freeze it the same day.") },
          { n: 2, state: "cooked", state_display: "Cooked", storage: storage("Keeps 3 days in the fridge (your setting).") },
        ],
      },
      steps: [
        { section: "marinate", text: "Coat the drumsticks in the yogurt marinade.", duration_minutes: 60, appliance_temp_f: null, safety_note: null, added_by_app: false, stage: 1 },
        { section: "oven", text: "Roast at 425°F for 40 minutes.", duration_minutes: 40, appliance_temp_f: 425, safety_note: "Cook chicken to 165°F (poultry).", added_by_app: false, stage: 2 },
      ],
    });
    render(<RecipeView recipe={item} />);
    expect(screen.getByRole("heading", { name: "Stage 1 · Marinated" })).toBeInTheDocument();
    expect(screen.getByText("Keeps 1 day in the fridge, or freeze it the same day.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Stage 2 · Cooked" })).toBeInTheDocument();
    expect(screen.getByText("Roast at 425°F for 40 minutes.")).toBeInTheDocument();
    expect(screen.getByText("Storage sources")).toBeInTheDocument();
  });

  it("an assembly lists its items (each opening its page), its add-ons and the eating-day instruction", () => {
    const meal = recipe({
      kind: "assembly",
      title: "Spiced chicken wrap",
      steps: [],
      lines: [{ ingredient_id: 5, name: "flour tortilla", display: "2 flour tortilla", amount_display: "2", portion_note: null, preparation: null, optional: false }],
      assembly: {
        name: "Spiced chicken wrap",
        items: [{ recipe_id: 40, version_id: 41, kind: "prep_item", title: "Spiced seared chicken thighs", label: "spiced chicken", brings: "protein", portions: "1.0", portions_display: "1 portion", min_portions: "1.0", max_portions: "2.0", step: "1.0", kcal: 320, protein_g: "38.0" }],
        instruction: "Reheat 1 portion spiced chicken to 165°F. Warm 2 flour tortillas; fill with the spiced chicken.",
      },
    });
    render(<RecipeView recipe={meal} />);
    expect(screen.getByRole("link", { name: /1 portion Spiced seared chicken thighs/ })).toHaveAttribute("href", expect.stringMatching(/^\/recipe\/?\?version=41$/));
    expect(screen.getByRole("heading", { name: "Add-ons, per portion" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "On the day" })).toBeInTheDocument();
    expect(screen.getByText(/Warm 2 flour tortillas; fill with the spiced chicken\./)).toBeInTheDocument();
  });

  it("shows a batch's own quantities and notes instead of the recipe's", () => {
    render(
      <RecipeView
        recipe={recipe()}
        notes={["Scaled up to use the whole package of chicken thigh."]}
        lines={[{ key: "a", name: "chicken thigh", display: "907 g", preparation: null, optional: false, note: "whole package" }]}
      />,
    );
    expect(screen.getByText("907 g")).toBeInTheDocument();
    expect(screen.queryByText("680 g")).not.toBeInTheDocument();
    expect(screen.getByText("Scaled up to use the whole package of chicken thigh.")).toBeInTheDocument();
  });
});
