import { describe, expect, it } from "vitest";

import { MemoryStorage } from "@/lib/offline/queue";

import { buildAnswers, draftFromAnswers, emptyDraft, loadPending, nextQuick, savePending } from "./answers";

describe("the meal-now answers", () => {
  it("only the pantry items you turned off are sent, and goals go out in tap order", () => {
    const draft = { ...emptyDraft(), goals: ["iron" as const, "quick" as const, "protein" as const], off: [4, 9] };
    const answers = buildAnswers(draft);
    expect(answers.pantry).toEqual([
      { ingredient_id: 4, include: false },
      { ingredient_id: 9, include: false },
    ]);
    expect(answers.goals).toEqual(["iron_rich", "quick", "high_protein"]);
    expect(answers.time_limit_minutes).toBe(30); // Quick with no minutes picked: the default
    expect(answers).toMatchObject({ schema_version: 1, mode: "now", slot: null, people: null, mood: null, allow_llm: true });
    expect(buildAnswers(emptyDraft()).pantry).toEqual([]); // nothing toggled: nothing sent
  });

  it("extras keep the server's amounts; could-buy items and amounts without Quick send none", () => {
    const answers = buildAnswers({
      ...emptyDraft(),
      quickMinutes: 45, // not sent without the Quick goal
      extras: [
        { ingredient_id: 61, name: "cauliflower, frozen", status: "have", preset: "16oz", presetLabel: "16 oz bag", quantity: "453.592", unit: "g" },
        { ingredient_id: 7, name: "chickpeas", status: "could_buy", quantity: "1", unit: "count" },
        { ingredient_id: 3, name: "garlic", status: "have" },
      ],
    });
    expect(answers.time_limit_minutes).toBeNull();
    expect(answers.extras).toEqual([
      { ingredient_id: 61, status: "have", quantity: "453.592", unit: "g", save_to_pantry: false },
      { ingredient_id: 7, status: "could_buy", quantity: null, unit: null, save_to_pantry: false },
      { ingredient_id: 3, status: "have", quantity: null, unit: null, save_to_pantry: false },
    ]);
  });

  it("last time's answers pre-fill the draft, but not the meal (M9) or last time's extras", () => {
    const draft = draftFromAnswers({ mode: "now", slot: "dinner", goals: ["high_protein", "cheap"], mood: "fancy", time_limit_minutes: 20, pantry: [{ ingredient_id: 4, include: false }], extras: [{ ingredient_id: 7, status: "could_buy", save_to_pantry: false }] });
    expect(draft).toEqual({ slot: null, people: null, goals: ["protein", "cheap"], quickMinutes: 20, mood: "fancy", off: [4], extras: [] });
  });

  it("pending answers are read back only under their own run key", () => {
    const storage = new MemoryStorage();
    const run = savePending(buildAnswers(emptyDraft()), storage);
    expect(loadPending(run, storage)?.mode).toBe("now");
    expect(loadPending(run, storage)).not.toBeNull(); // reading twice is fine (Strict Mode, reloads)
    expect(loadPending("someone-else", storage)).toBeNull();
    const next = savePending({ ...buildAnswers(emptyDraft()), mood: "simple" }, storage);
    expect(loadPending(run, storage)).toBeNull();
    expect(loadPending(next, storage)?.mood).toBe("simple");
  });

  it("the empty state's next limits", () => {
    expect(nextQuick(20)).toBe(30);
    expect(nextQuick(null)).toBe(45);
    expect(nextQuick(120)).toBeNull();
  });
});
