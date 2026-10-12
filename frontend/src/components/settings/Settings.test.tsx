import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { UserSettings } from "@/lib/api/types";
import { THEME_KEY } from "@/lib/theme/theme";
import { mockApi } from "@/test/api";
import { preview, settingsOut } from "@/test/fixtures";

import { SettingsEditor } from "./SettingsEditor";
import { SettingsList } from "./SettingsList";

function settingsApi(saved: Partial<UserSettings> = {}, patch?: (body: unknown) => { status: number; body: unknown }) {
  return mockApi((call) => {
    if (call.path === "/api/v1/settings" && call.method === "GET") return { body: settingsOut(saved) };
    if (call.path === "/api/v1/settings/preview") return { body: preview() };
    if (call.path === "/api/v1/settings" && call.method === "PATCH") return patch ? patch(call.body) : { body: settingsOut({ ...saved, ...(call.body as object) }) };
    return undefined;
  });
}

describe("Settings list (S0)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows the weekly daily range only in weekly mode", async () => {
    settingsApi();
    const { rerender } = render(<SettingsList out={settingsOut()} onSignOut={() => undefined} />);
    const meals = screen.getByRole("region", { name: "Meals" });
    expect(within(meals).getByText("Weekly · each day within ±150 kcal")).toBeInTheDocument();

    rerender(<SettingsList out={settingsOut({ calorie_mode: "strict_daily" })} onSignOut={() => undefined} />);
    expect(within(screen.getByRole("region", { name: "Meals" })).getByText("Strict daily")).toBeInTheDocument();
    expect(screen.queryByText(/within ±/)).not.toBeInTheDocument();
    await screen.findByText("1 Stop & Shop · 2 Price Rite"); // the summary lines arrive
  });

  it("every row opens its editor, and the summary lines come from the API", async () => {
    settingsApi();
    render(<SettingsList out={settingsOut()} onSignOut={() => undefined} />);
    expect(await screen.findByText("1 Stop & Shop · 2 Price Rite")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Calories per day/ })).toHaveAttribute("href", expect.stringMatching(/^\/settings\/edit\/?\?field=daily_kcal_target$/));
    expect(screen.getByRole("link", { name: /Always have/ })).toHaveAttribute("href", expect.stringMatching(/^\/settings\/edit\/?\?field=always_have$/));
    expect(screen.queryByRole("link", { name: /Beef/ })).not.toBeInTheDocument(); // locked
    expect(screen.getByText("2 held, 0 allowed")).toBeInTheDocument();
    const diet = screen.getByRole("region", { name: "Diet" });
    expect(within(diet).getByRole("link", { name: /Daily caps/ })).toHaveAttribute("href", expect.stringMatching(/^\/settings\/edit\/?\?field=daily_amount_caps$/));
    expect(within(diet).getByText("Protein powder: usually 1 scoop a day, at most 2 scoops")).toBeInTheDocument();
  });

  it("switches the theme: Light, Dark and Match my phone, stored on this device", async () => {
    settingsApi();
    render(<SettingsList out={settingsOut()} onSignOut={() => undefined} />);
    const light = screen.getByRole("button", { name: /^✓?Light$/ });
    expect(light).toHaveAttribute("aria-pressed", "true"); // light is the default

    await userEvent.click(screen.getByRole("button", { name: /Dark/ }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");

    window.matchMedia = vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() });
    await userEvent.click(screen.getByRole("button", { name: /Match my phone/ }));
    expect(localStorage.getItem(THEME_KEY)).toBe("system");
    expect(document.documentElement.dataset.theme).toBe("light"); // the phone is in light mode
    await userEvent.click(screen.getByRole("button", { name: /Light/ }));
    expect(document.documentElement.dataset.theme).toBe("light");
    await screen.findByText("1 Stop & Shop · 2 Price Rite");
  });
});

describe("Settings editors (S1)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("the calorie mode editor hides the daily range in strict mode", async () => {
    settingsApi();
    render(<SettingsEditor field="calorie_mode" online onDone={() => undefined} />);
    expect(await screen.findByRole("group", { name: "Each day within ±" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Strict daily/ }));
    expect(screen.queryByRole("group", { name: "Each day within ±" })).not.toBeInTheDocument();
  });

  it("Save sends only that field, then goes back", async () => {
    const calls = settingsApi();
    const onDone = vi.fn();
    render(<SettingsEditor field="daily_kcal_target" online onDone={onDone} />);
    await userEvent.click(await screen.findByRole("button", { name: "More calories a day" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(calls.filter((c) => c.method === "PATCH")).toEqual([{ method: "PATCH", path: "/api/v1/settings", body: { daily_kcal_target: 1850 } }]);
  });

  it("a save error keeps your edit and shows the server's message under the control", async () => {
    settingsApi({}, () => ({
      status: 422,
      body: { title: "Invalid settings", detail: "", errors: [{ loc: [], msg: "Value error, slot allocations exceed the daily kcal target" }] },
    }));
    const onDone = vi.fn();
    render(<SettingsEditor field="meal_calories" online onDone={onDone} />);
    await userEvent.click(await screen.findByRole("button", { name: "More dinner" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Slot allocations exceed the daily kcal target")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Dinner: 675/ })).toBeInTheDocument(); // the edit is kept
    expect(onDone).not.toHaveBeenCalled();
  });

  it("the daily caps editor sets the usual and the most a day, and refuses a usual above the most", async () => {
    const calls = settingsApi();
    const onDone = vi.fn();
    render(<SettingsEditor field="daily_amount_caps" online onDone={onDone} />);
    expect(await screen.findByRole("button", { name: /Protein powder usually: 1/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Protein powder at most: 2/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "More protein powder usually" }));
    await userEvent.click(screen.getByRole("button", { name: "More protein powder usually" }));
    await userEvent.click(screen.getByRole("button", { name: "More protein powder usually" }));
    expect(screen.getByText("The usual amount can't be more than the most.")).toBeInTheDocument(); // 2.5 > 2
    await userEvent.click(screen.getByRole("button", { name: "More protein powder at most" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(calls.filter((c) => c.method === "PATCH")).toEqual([
      {
        method: "PATCH",
        path: "/api/v1/settings",
        body: { daily_amount_caps: [{ label: "Protein powder", ingredient: "protein-powder-double-chocolate", unit: "scoop", usual: 2.5, maximum: 2.5 }] },
      },
    ]);
  });

  it("the weeknight time (V7): one value for every day, or different each day, saved in the cook schedule", async () => {
    const calls = settingsApi();
    const onDone = vi.fn();
    render(<SettingsList out={settingsOut()} onSignOut={() => undefined} />);
    const cooking = screen.getByRole("region", { name: "Cooking" });
    expect(within(cooking).getByRole("link", { name: /Weeknight time/ })).toHaveTextContent("30 min a day");
    render(<SettingsEditor field="weeknight_minutes" online onDone={onDone} />);
    await userEvent.click(await screen.findByRole("button", { name: "Different each day" }));
    await userEvent.click(screen.getByRole("button", { name: "More friday" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    const [patch] = calls.filter((c) => c.method === "PATCH");
    const schedule = (patch?.body as { cook_schedule: UserSettings["cook_schedule"] }).cook_schedule;
    expect(schedule.map((d) => d.weeknight_minutes)).toEqual([30, 30, 30, 30, 35, 30, 30]);
    expect(schedule.map((d) => d.cook_minutes)).toEqual([90, 0, 90, 90, 0, 90, 90]); // cook days unchanged
  });

  it("offline, Save says it needs a connection", async () => {
    settingsApi();
    render(<SettingsEditor field="household_size" online={false} onDone={() => undefined} />);
    expect(await screen.findByRole("button", { name: "Needs a connection" })).toBeDisabled();
  });
});
