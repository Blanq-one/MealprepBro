import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

type SwExports = {
  strategyFor: (url: string, method?: string) => string;
  assetsIn: (html: string) => string[];
  SHELL_PAGES: string[];
};

// public/sw.js is a plain script (no build step). Evaluate it as the browser would, without a `self`, and
// read what it exposes for tests.
function loadServiceWorker(): SwExports {
  const code = readFileSync(join(process.cwd(), "public", "sw.js"), "utf8");
  const module = { exports: {} as SwExports };
  new Function("module", "self", code)(module, undefined);
  return module.exports;
}

const sw = loadServiceWorker();

describe("service worker routing", () => {
  it.each([
    ["/plan/", "GET", "page"],
    ["/cook/", "GET", "page"],
    ["/welcome/?step=targets", "GET", "page"],
    ["/settings/edit/?field=always_have", "GET", "page"],
    ["/recipe/?batch=12", "GET", "page"],
    ["/inventory", "GET", "page"],
    ["/plan/index.txt", "GET", "data"],
    ["/__next._full.txt", "GET", "data"],
    ["/_next/static/chunks/abc.js", "GET", "static"],
    ["/icons/icon-192.png", "GET", "static"],
    ["/api/v1/plans/3", "GET", "api"],
    ["/api/v1/plans/3/grocery-list?group_by=store", "GET", "api"],
    ["/api/v1/auth/session", "GET", "network"],
    ["/api/v1/grocery-items/4", "PATCH", "network"],
    ["/api/v1/plans", "POST", "network"],
    ["/health", "GET", "network"],
    ["/sw.js", "GET", "network"],
    ["/manifest.webmanifest", "GET", "network"],
  ])("%s %s -> %s", (url, method, expected) => {
    expect(sw.strategyFor(url, method)).toBe(expected);
  });

  it("never caches anything that changes data", () => {
    for (const method of ["POST", "PUT", "PATCH", "DELETE"]) {
      expect(sw.strategyFor("/api/v1/inventory", method)).toBe("network");
      expect(sw.strategyFor("/plan/", method)).toBe("network");
    }
  });

  it("precaches every screen of the app shell", () => {
    expect(sw.SHELL_PAGES).toEqual(
      expect.arrayContaining([
        "/cook/",
        "/welcome/",
        "/plan/",
        "/plan/new/",
        "/day/",
        "/recipe/",
        "/pantry/",
        "/inventory/",
        "/grocery/",
        "/settings/",
        "/settings/edit/",
        "/login/",
      ]),
    );
  });

  it("finds the build files a page loads", () => {
    const html =
      '<script src="/_next/static/chunks/a.js" async=""></script><link rel="stylesheet" href="/_next/static/chunks/b.css"/>' +
      '<script src="/_next/static/chunks/a.js"></script><img src="/icons/icon-192.png"/>';
    expect(sw.assetsIn(html)).toEqual(["/_next/static/chunks/a.js", "/_next/static/chunks/b.css"]);
  });
});
