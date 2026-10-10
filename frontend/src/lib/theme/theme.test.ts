import { afterEach, describe, expect, it, vi } from "vitest";

import { applyTheme, readThemeChoice, resolveTheme, saveThemeChoice, THEME_KEY, THEME_SCRIPT } from "./theme";

function phone(dark: boolean) {
  window.matchMedia = vi.fn().mockReturnValue({ matches: dark, addEventListener: vi.fn(), removeEventListener: vi.fn() });
}

describe("theme", () => {
  afterEach(() => {
    delete document.documentElement.dataset.theme;
  });

  it("is light by default", () => {
    expect(readThemeChoice()).toBe("light");
    phone(true);
    expect(applyTheme(readThemeChoice())).toBe("light");
  });

  it("Match my phone follows the phone", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    phone(true);
    expect(saveThemeChoice("system")).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("system");
  });

  it("the head script applies the stored choice before the first paint, like applyTheme", () => {
    localStorage.setItem(THEME_KEY, "dark");
    phone(false);
    new Function(THEME_SCRIPT)();
    expect(document.documentElement.dataset.theme).toBe("dark");
    localStorage.setItem(THEME_KEY, "system");
    new Function(THEME_SCRIPT)();
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
