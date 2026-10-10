// Light / Dark / Match my phone (FLOW_SPEC §4.2), stored per device. The choice is applied as
// <html data-theme="light|dark">; "system" follows the phone's setting and keeps following it.

export type ThemeChoice = "light" | "dark" | "system";
export type Theme = "light" | "dark";

export const THEME_KEY = "mealbro.theme";
const THEME_COLORS: Record<Theme, string> = { light: "#fff8f1", dark: "#1c1714" };
const DARK_QUERY = "(prefers-color-scheme: dark)";

function isChoice(value: unknown): value is ThemeChoice {
  return value === "light" || value === "dark" || value === "system";
}

export function readThemeChoice(): ThemeChoice {
  try {
    const stored = window.localStorage.getItem(THEME_KEY);
    return isChoice(stored) ? stored : "light";
  } catch {
    return "light";
  }
}

export function prefersDark(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia(DARK_QUERY).matches;
}

export function resolveTheme(choice: ThemeChoice, systemDark: boolean): Theme {
  if (choice === "system") return systemDark ? "dark" : "light";
  return choice;
}

/** Put the theme on the page (and the browser's toolbar color). */
export function applyTheme(choice: ThemeChoice): Theme {
  const theme = resolveTheme(choice, prefersDark());
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLORS[theme]);
  return theme;
}

export function saveThemeChoice(choice: ThemeChoice): Theme {
  try {
    window.localStorage.setItem(THEME_KEY, choice);
  } catch {
    // storage blocked: the choice lasts for this page only
  }
  return applyTheme(choice);
}

/** While "Match my phone" is chosen, follow the phone switching between light and dark. */
export function followSystemTheme(): () => void {
  if (typeof window.matchMedia !== "function") return () => undefined;
  const media = window.matchMedia(DARK_QUERY);
  const update = () => {
    if (readThemeChoice() === "system") applyTheme("system");
  };
  media.addEventListener?.("change", update);
  return () => media.removeEventListener?.("change", update);
}

/** Runs in <head> before the first paint, so a dark choice never flashes light. Mirrors applyTheme. */
export const THEME_SCRIPT = `(function(){try{var c=localStorage.getItem(${JSON.stringify(THEME_KEY)});var d=window.matchMedia&&window.matchMedia(${JSON.stringify(DARK_QUERY)}).matches;var t=c==="dark"||(c==="system"&&d)?"dark":"light";document.documentElement.dataset.theme=t;var m=document.querySelector('meta[name="theme-color"]');if(m)m.setAttribute("content",t==="dark"?${JSON.stringify(THEME_COLORS.dark)}:${JSON.stringify(THEME_COLORS.light)});}catch(e){}})();`;
