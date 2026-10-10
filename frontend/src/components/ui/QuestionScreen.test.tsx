// The fixed Continue button must never hide content (2b.2 fix): the screen reserves bottom padding equal to the
// footer's measured height, and keeps it current as the footer resizes.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { QuestionScreen } from "./QuestionScreen";

let footerHeight = 0;
const observers: { callback: ResizeObserverCallback; targets: Element[] }[] = [];

class FakeResizeObserver {
  private entry: { callback: ResizeObserverCallback; targets: Element[] };
  constructor(callback: ResizeObserverCallback) {
    this.entry = { callback, targets: [] };
    observers.push(this.entry);
  }
  observe(target: Element) {
    this.entry.targets.push(target);
  }
  unobserve() {}
  disconnect() {
    this.entry.targets = [];
  }
}

function measureFooterAs(height: number) {
  footerHeight = height;
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    const h = this.dataset.testid === "question-footer" ? footerHeight : 0;
    return { x: 0, y: 0, top: 0, left: 0, right: 375, bottom: h, width: 375, height: h, toJSON: () => ({}) } as DOMRect;
  });
}

function resizeFooter(height: number) {
  footerHeight = height;
  act(() => {
    for (const o of observers) if (o.targets.length > 0) o.callback([], {} as ResizeObserver);
  });
}

const reserved = () => screen.getByTestId("question-screen").style.getPropertyValue("--footer-height");

describe("QuestionScreen footer space", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    observers.length = 0;
  });

  it("reserves the footer's measured height, including a secondary button and a note", () => {
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    measureFooterAs(171.4);
    render(
      <QuestionScreen title="When do you cook?" primaryLabel="Continue" onPrimary={() => undefined} secondary={<button type="button">Other</button>} footerNote="A note">
        <p>Hands-on minutes</p>
      </QuestionScreen>,
    );
    expect(reserved()).toBe("172px"); // rounded up, never short
  });

  it("follows the footer when it grows or shrinks", () => {
    vi.stubGlobal("ResizeObserver", FakeResizeObserver);
    measureFooterAs(80);
    render(
      <QuestionScreen title="Q" primaryLabel="Continue" onPrimary={() => undefined}>
        <p>Body</p>
      </QuestionScreen>,
    );
    expect(reserved()).toBe("80px");
    resizeFooter(130); // e.g. larger iOS text, or a footer note appearing
    expect(reserved()).toBe("130px");
    resizeFooter(96);
    expect(reserved()).toBe("96px");
  });

  it("still reserves the measured height without ResizeObserver", () => {
    vi.stubGlobal("ResizeObserver", undefined);
    measureFooterAs(112);
    render(
      <QuestionScreen title="Q" primaryLabel="Continue" onPrimary={() => undefined}>
        <p>Body</p>
      </QuestionScreen>,
    );
    expect(reserved()).toBe("112px");
  });

  it("keeps every control above the footer in the document", () => {
    measureFooterAs(80);
    render(
      <QuestionScreen title="Q" primaryLabel="Continue" onPrimary={() => undefined}>
        <button type="button">+ minutes</button>
      </QuestionScreen>,
    );
    const footer = screen.getByTestId("question-footer");
    expect(footer).not.toContainElement(screen.getByRole("button", { name: "+ minutes" }));
    expect(footer).toContainElement(screen.getByRole("button", { name: "Continue" }));
  });
});

describe("layout check: the footer space rule", () => {
  const SRC = join(process.cwd(), "src");
  const css = readFileSync(join(SRC, "components/ui/QuestionScreen.module.css"), "utf8");

  it("pads the screen by the measured footer height plus a gap", () => {
    const screenRule = /\.screen\s*\{([^}]*)\}/.exec(css)?.[1] ?? "";
    expect(screenRule).toMatch(/padding-bottom:\s*calc\(var\(--footer-height,[^;]*\)\s*\+\s*var\(--footer-gap\)\)/);
  });

  it("has no other fixed bottom button: every question screen uses QuestionScreen", () => {
    const files = (function walk(dir: string): string[] {
      return readdirSync(dir).flatMap((name) => {
        const path = join(dir, name);
        return statSync(path).isDirectory() ? walk(path) : /\.module\.css$/.test(name) ? [path] : [];
      });
    })(SRC);
    const fixed = files
      .filter((path) => /position:\s*fixed/.test(readFileSync(path, "utf8")))
      .map((path) => relative(SRC, path).replace(/\\/g, "/"))
      .sort();
    // The tab bar and the bottom sheet are fixed too, but neither sits over a question screen's content.
    expect(fixed).toEqual(["components/BottomNav.module.css", "components/ui/BottomSheet.module.css", "components/ui/QuestionScreen.module.css"]);
  });
});
