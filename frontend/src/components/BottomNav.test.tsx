import { describe, expect, it } from "vitest";

import { showsTabs } from "./BottomNav";

describe("the tab bar", () => {
  it("hides inside question flows and cooking mode, and shows everywhere else", () => {
    for (const path of ["/cook/ask/", "/cook/cooking/", "/welcome/", "/settings/edit/", "/login/"]) expect(showsTabs(path)).toBe(false);
    for (const path of ["/cook/", "/cook/results/", "/cook/saved/", "/cook/buy/", "/recipe/", "/pantry/", "/grocery/", "/settings/"]) {
      expect(showsTabs(path)).toBe(true);
    }
  });
});
