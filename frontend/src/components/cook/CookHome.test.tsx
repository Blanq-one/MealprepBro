import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";

import { cookHome } from "@/test/fixtures";

import { CookHomeView, MEAL_NOW_HREF, MEAL_PREP_HREF } from "./CookHome";

function view(props: Partial<Parameters<typeof CookHomeView>[0]> = {}) {
  return render(<CookHomeView greeting="Evening" home={cookHome()} loading={false} error={null} online onRetry={() => undefined} onSameAgain={() => undefined} {...props} />);
}

describe("the Cook home (C0)", () => {
  it("puts the two choice buttons first, with only the one-line greeting above them", () => {
    const { container } = view();
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Evening! What are we making?");
    const choices = screen.getByTestId("choices");
    // nothing but the greeting comes before the choices
    const before = [...container.children].slice(0, [...container.children].indexOf(choices));
    expect(before).toHaveLength(1);
    expect(before[0]).toContainElement(heading);
    const links = within(choices).getAllByRole("link");
    expect(links.map((l) => l.textContent)).toEqual(["🍳A meal nowOne meal, ready to cook", "🍱Meal prepPortions for the days ahead"]);
    // every other section comes after them, in order
    const sections = ["Same as last time", "Saved"].map((name) => screen.getByRole("region", { name }));
    for (const section of sections) expect(choices.compareDocumentPosition(section) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("A meal now starts the questions; Meal prep opens the existing plan flow until step 2b.7", () => {
    view();
    // (the test Link drops the trailing slash the static export keeps)
    const choices = within(screen.getByTestId("choices"));
    expect(MEAL_NOW_HREF).toBe("/cook/ask/?mode=now&step=goals&fresh=1");
    expect(choices.getByRole("link", { name: /A meal now/ })).toHaveAttribute("href", "/cook/ask?mode=now&step=goals&fresh=1");
    expect(MEAL_PREP_HREF).toBe("/plan/new/");
    expect(choices.getByRole("link", { name: /Meal prep/ })).toHaveAttribute("href", expect.stringMatching(/^\/plan\/new\/?$/));
  });

  it("the choices are at least 120 px tall, so both fit above the fold on a 375 x 667 phone", () => {
    const css = readFileSync(join(process.cwd(), "src/components/cook/CookHome.module.css"), "utf8");
    const choice = /\.choice \{([^}]*)\}/.exec(css)?.[1] ?? "";
    expect(choice).toMatch(/min-height: 120px/);
    expect(choice).toMatch(/width: 100%/);
    // the greeting is one line: 32 px Pottle and a small title, no block of its own above the buttons
    expect(/\.greeting \{([^}]*)\}/.exec(css)?.[1]).toMatch(/min-height: 40px/);
  });

  it("Same as last time sends those answers again; saved cards open for your household", async () => {
    const onSameAgain = vi.fn();
    view({ onSameAgain });
    await userEvent.click(screen.getByRole("button", { name: "A meal now · Dinner for 1 · Quick (30 min) · + chickpeas (could buy)" }));
    expect(onSameAgain).toHaveBeenCalledWith(cookHome().last[0]);
    expect(screen.getByRole("link", { name: /Everyday chicken curry/ })).toHaveAttribute("href", expect.stringMatching(/^\/recipe\/?\?version=21&portions=2&size=normal$/));
    expect(screen.getByRole("link", { name: "See all" })).toHaveAttribute("href", expect.stringMatching(/^\/cook\/saved\/?\?list=favorites$/));
  });

  it("first ever: just the choices and a hint under Saved", () => {
    view({ home: cookHome({ last: [], favorites: [], favorites_count: 0 }) });
    expect(screen.queryByRole("region", { name: "Same as last time" })).not.toBeInTheDocument();
    expect(screen.getByText("Tap ♥ on a recipe to keep it here.")).toBeInTheDocument();
  });

  it("offline, the choices and Same as last time need a connection", () => {
    view({ online: false });
    const choices = within(screen.getByTestId("choices"));
    expect(choices.queryByRole("link")).not.toBeInTheDocument();
    expect(choices.getByRole("button", { name: /A meal now/ })).toBeDisabled();
    expect(choices.getByRole("button", { name: /Meal prep/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Dinner for 1/ })).toBeDisabled();
    expect(screen.getByText("Needs a connection")).toBeInTheDocument();
  });

  it("loading shows skeletons; an error keeps the choices working and offers a retry", async () => {
    const { rerender } = view({ home: null, loading: true });
    expect(screen.getByRole("status", { name: "Loading your Cook home" })).toBeInTheDocument();
    const onRetry = vi.fn();
    rerender(<CookHomeView greeting="Evening" home={null} loading={false} error={new Error("down")} online onRetry={onRetry} onSameAgain={() => undefined} />);
    expect(within(screen.getByTestId("choices")).getByRole("link", { name: /A meal now/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalled();
  });
});
