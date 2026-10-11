import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SettingsPreview, UserSettings } from "@/lib/api/types";
import { DRAFT_KEY, newDraft } from "@/lib/onboarding/draft";
import { type Call, mockApi, type Reply } from "@/test/api";
import { preview, settingsOut, stores, userSettings } from "@/test/fixtures";

import { Onboarding, STEPS, type Step } from "./Onboarding";

function Wizard({ start = "welcome", onDone = () => undefined, online = true }: { start?: Step; onDone?: () => void; online?: boolean }) {
  const [step, setStep] = useState<Step>(start);
  return (
    <>
      <output aria-label="step">{step}</output>
      <Onboarding step={step} navigate={(to) => setStep(to)} onDone={onDone} online={online} />
    </>
  );
}

function api(overrides: { saved?: Partial<UserSettings>; preview?: (body: unknown) => SettingsPreview; put?: (call: Call) => Reply } = {}) {
  return mockApi((call) => {
    if (call.path === "/api/v1/settings" && call.method === "GET") return { body: settingsOut(overrides.saved) };
    if (call.path === "/api/v1/stores" && call.method === "GET") return { body: stores };
    if (call.path === "/api/v1/stores" && call.method === "POST") {
      return { status: 201, body: { id: 9, name: (call.body as { name: string }).name, priority: 4, order: null } };
    }
    if (call.path === "/api/v1/settings/preview") return { body: overrides.preview ? overrides.preview(call.body) : preview() };
    if (call.path === "/api/v1/settings" && call.method === "PUT") {
      return overrides.put?.(call) ?? { body: settingsOut({ ...(call.body as UserSettings) }) };
    }
    if (call.path === "/api/v1/settings" && call.method === "PATCH") return { body: settingsOut({ onboarding_completed: true }) };
    return undefined;
  });
}

const step = () => screen.getByLabelText("step").textContent;
const continueButton = () => screen.getByRole("button", { name: "Continue" });
const storedDraft = () => JSON.parse(localStorage.getItem(DRAFT_KEY) ?? "null");

async function continueTo(next: Step) {
  await userEvent.click(continueButton());
  await waitFor(() => expect(step()).toBe(next));
}

describe("onboarding", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("is nine screens, keeps a device draft, and saves once with one PUT", async () => {
    const calls = api();
    const onDone = vi.fn();
    render(<Wizard onDone={onDone} />);
    expect(STEPS).toHaveLength(9);

    expect(await screen.findByRole("heading", { name: "Welcome to Mealbro" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Let's go" }));
    expect(step()).toBe("household");
    expect(screen.getByRole("img", { name: "Step 1 of 7" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "More people" }));
    expect(storedDraft().settings.household_size).toBe(2); // the draft stays on the device as you go
    await continueTo("targets");
    await userEvent.click(screen.getByRole("button", { name: "Less protein" }));
    await continueTo("meals");
    expect(await screen.findByText("1,800 of 1,800 kcal a day planned")).toBeInTheDocument(); // from the API
    await continueTo("cooking");
    await continueTo("kitchen");
    await continueTo("stores");
    await continueTo("rules");
    await continueTo("done");
    expect(await screen.findByText("1,800 kcal · 100 g protein")).toBeInTheDocument();

    expect(calls.filter((c) => c.method === "PUT")).toHaveLength(0); // nothing saved while you go
    await userEvent.click(screen.getByRole("button", { name: "Start cooking" }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());

    const puts = calls.filter((c) => c.method === "PUT");
    expect(puts).toHaveLength(1);
    expect(puts[0]?.path).toBe("/api/v1/settings");
    expect(puts[0]?.body).toEqual({ ...userSettings(), household_size: 2, daily_protein_target_g: 95, onboarding_completed: true });
    expect(calls.filter((c) => c.method === "PATCH")).toHaveLength(0);
    expect(localStorage.getItem(DRAFT_KEY)).toBeNull();
  }, 15_000); // nine screens of clicks: about 1.5 s alone, over 5 s when every test file runs at once

  it("Skip, use my current settings sends only the onboarding flag", async () => {
    const calls = api();
    const onDone = vi.fn();
    render(<Wizard onDone={onDone} />);
    await userEvent.click(await screen.findByRole("button", { name: "Skip, use my current settings" }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    const writes = calls.filter((c) => c.method !== "GET");
    expect(writes).toEqual([{ method: "PATCH", path: "/api/v1/settings", body: { onboarding_completed: true } }]);
  });

  it("paired screens validate both controls through the API", async () => {
    api({
      preview: () =>
        preview({
          valid: false,
          summary: [],
          errors: [
            { loc: ["daily_kcal_target"], msg: "Input should be a multiple of 50" },
            { loc: ["daily_protein_target_g"], msg: "Input should be at most your calories allow" },
          ],
        }),
    });
    render(<Wizard start="targets" />);
    await screen.findByRole("heading", { name: "Your daily targets" });
    await userEvent.click(continueButton());
    expect(await screen.findByText("Input should be a multiple of 50")).toBeInTheDocument();
    expect(screen.getByText("Input should be at most your calories allow")).toBeInTheDocument();
    expect(step()).toBe("targets"); // stays until both are fixed

    // each message sits under its own control
    const calories = screen.getByRole("group", { name: "Calories a day" });
    const protein = screen.getByRole("group", { name: "Protein" });
    expect(calories.nextElementSibling).toHaveTextContent("Input should be a multiple of 50");
    expect(protein.nextElementSibling).toHaveTextContent("Input should be at most your calories allow");
  });

  it("checks both controls on the device too: an out-of-range value disables Continue", async () => {
    api();
    render(<Wizard start="targets" />);
    await screen.findByRole("heading", { name: "Your daily targets" });
    await userEvent.click(screen.getByRole("button", { name: /Protein: 100/ }));
    const typed = screen.getByRole("textbox", { name: "Protein, type a number" });
    await userEvent.clear(typed);
    await userEvent.type(typed, "500{Enter}");
    expect(continueButton()).toBeDisabled();
    expect(screen.getByText("Pick your protein target.")).toBeInTheDocument();
  });

  it("pre-fills from saved settings, resumes a saved draft, and doesn't run again once done", async () => {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(newDraft(userSettings({ household_size: 3 }))));
    api();
    render(<Wizard start="household" />);
    expect(await screen.findByRole("button", { name: /People: 3/ })).toBeInTheDocument();

    localStorage.clear();
    vi.unstubAllGlobals();
    api({ saved: { onboarding_completed: true } });
    const onDone = vi.fn();
    render(<Wizard start="welcome" onDone={onDone} />);
    await waitFor(() => expect(onDone).toHaveBeenCalled());
  });

  it("a meal you add needs its calories before Continue", async () => {
    api();
    render(<Wizard start="meals" />);
    await screen.findByRole("heading", { name: "Which meals should I plan?" });
    await userEvent.click(screen.getByRole("button", { name: "Snack" }));
    expect(screen.getByRole("button", { name: "Snack" })).toHaveAttribute("aria-pressed", "true");
    expect(continueButton()).toBeDisabled();
    expect(screen.getByText("Snack needs its calories.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "More snack" }));
    expect(continueButton()).toBeEnabled();
    expect(storedDraft().settings.slot_allocations.map((a: { slot: string }) => a.slot)).toEqual([
      "breakfast",
      "lunch",
      "dinner",
      "protein_dessert",
      "snack",
    ]);
  });

  it("a store you type in is created when you save, then saved in your order", async () => {
    const calls = api();
    const onDone = vi.fn();
    render(<Wizard start="stores" onDone={onDone} />);
    await screen.findByRole("heading", { name: "Where do you shop?" });
    await userEvent.type(screen.getByRole("textbox", { name: "Store name" }), "Market Basket");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByRole("button", { name: /Market Basket/ })).toHaveAttribute("aria-pressed", "true");
    await continueTo("rules");
    await continueTo("done");
    // the preview never sees a store that doesn't exist yet
    for (const call of calls.filter((c) => c.path === "/api/v1/settings/preview")) {
      expect((call.body as UserSettings).store_order).toEqual(["Stop & Shop", "Price Rite"]);
    }
    expect(await screen.findByText("1 Stop & Shop · 2 Price Rite · 3 Market Basket")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Start cooking" }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    const writes = calls.filter((c) => c.method !== "GET" && c.path !== "/api/v1/settings/preview");
    expect(writes.map((c) => `${c.method} ${c.path}`)).toEqual(["POST /api/v1/stores", "PUT /api/v1/settings"]);
    expect((writes[1]?.body as UserSettings).store_order).toEqual(["Stop & Shop", "Price Rite", "Market Basket"]);
  });

  it("a save error stays on All set, shows next to its row and keeps the draft", async () => {
    api({
      put: () => ({
        status: 422,
        body: { title: "Invalid settings", detail: "", errors: [{ loc: ["body", "daily_kcal_target"], msg: "Input should be less than or equal to 6000" }] },
      }),
    });
    const onDone = vi.fn();
    render(<Wizard start="done" onDone={onDone} />);
    await userEvent.click(await screen.findByRole("button", { name: "Start cooking" }));
    expect(await screen.findByText("Input should be less than or equal to 6000")).toBeInTheDocument();
    const row = screen.getByRole("button", { name: /Daily targets/ });
    expect(row.nextElementSibling).toHaveTextContent("Input should be less than or equal to 6000");
    expect(onDone).not.toHaveBeenCalled();
    expect(storedDraft()).not.toBeNull();
  });

  it("offline: you can step through, but saving says it needs a connection", async () => {
    api();
    render(<Wizard start="done" online={false} />);
    expect(await screen.findByRole("button", { name: "Needs a connection to save" })).toBeDisabled();
  });

  it("every screen reserves the Continue footer's height, so the minutes stepper is never behind it", async () => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      const h = this.dataset.testid === "question-footer" ? 136 : 0;
      return { x: 0, y: 0, top: 0, left: 0, right: 375, bottom: h, width: 375, height: h, toJSON: () => ({}) } as DOMRect;
    });
    api();
    for (const start of STEPS) {
      const { unmount } = render(<Wizard start={start} />);
      const question = await screen.findByTestId("question-screen");
      expect(question.style.getPropertyValue("--footer-height")).toBe("136px");
      if (start === "cooking") {
        await screen.findByRole("heading", { name: "When do you cook?" });
        const footer = screen.getByTestId("question-footer");
        const minutes = screen.getAllByRole("button").filter((b) => /minutes/i.test(b.getAttribute("aria-label") ?? ""));
        expect(minutes.length).toBeGreaterThan(0);
        for (const b of minutes) expect(footer).not.toContainElement(b);
      }
      unmount();
    }
    vi.restoreAllMocks();
  });
});
