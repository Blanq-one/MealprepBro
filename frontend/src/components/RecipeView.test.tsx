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
