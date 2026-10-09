"use client";

import { useEffect, useState } from "react";

import { ProblemNotice, Spinner, SyncNote } from "@/components/Status";
import { api } from "@/lib/api/client";
import type { SettingsOut, UserSettings } from "@/lib/api/types";
import { humanize, slotLabel } from "@/lib/format/labels";
import { centsToInput, parseDollarsToCents } from "@/lib/format/money";
import { useApi } from "@/lib/hooks/useApi";

import styles from "./settings.module.css";

const EQUIPMENT = [
  "stovetop",
  "oven",
  "air_fryer",
  "microwave",
  "rice_cooker",
  "pressure_cooker",
  "slow_cooker",
  "blender",
  "food_processor",
  "grill",
] as const;
const PRIORITIES = ["protein", "carb", "iron", "balanced"] as const;
const MOODS = ["simple", "medium", "fancy"] as const;
const WEEKDAYS: Record<string, string> = { mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun" };

function int(value: string, fallback: number): number {
  return /^\d+$/.test(value) ? Number.parseInt(value, 10) : fallback;
}

export default function SettingsPage() {
  const loaded = useApi<SettingsOut>("/api/v1/settings");
  const [draft, setDraft] = useState<UserSettings | null>(null);
  const [threshold, setThreshold] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (loaded.data) {
      setDraft(loaded.data.settings);
      setThreshold(centsToInput(loaded.data.settings.store_split_min_savings_cents));
    }
  }, [loaded.data]);

  if (loaded.loading && !loaded.data) return <Spinner />;
  if (!loaded.data || !draft) return <ProblemNotice error={loaded.error} />;
  const s = draft;
  const thresholdCents = parseDollarsToCents(threshold);

  function set<K extends keyof UserSettings>(key: K, value: UserSettings[K]) {
    setSaved(false);
    setDraft((d) => (d ? { ...d, [key]: value } : d));
  }

  async function save() {
    if (thresholdCents === undefined) return;
    setSaving(true);
    setError(null);
    try {
      const body = { ...s, store_split_min_savings_cents: thresholdCents ?? 0 };
      loaded.setData(await api<SettingsOut>("/api/v1/settings", { method: "PUT", json: body }));
      setSaved(true);
    } catch (e) {
      setError(e);
    } finally {
      setSaving(false);
    }
  }

  async function decide(ingredientId: number, allow: boolean) {
    setError(null);
    try {
      if (allow) {
        loaded.setData(
          await api<SettingsOut>(`/api/v1/settings/ingredient-preferences/${ingredientId}`, {
            method: "PUT",
            json: { preference: "allow", reason: "reviewed in the app" },
          }),
        );
      } else {
        await api(`/api/v1/settings/ingredient-preferences/${ingredientId}`, { method: "DELETE" });
        await loaded.reload();
      }
    } catch (e) {
      setError(e);
    }
  }

  async function logout() {
    try {
      await api("/api/v1/auth/logout", { method: "POST" });
      navigator.serviceWorker?.controller?.postMessage("clear-api-cache"); // no offline copy once signed out
    } finally {
      window.location.assign("/login/");
    }
  }

  const moveStore = (index: number, delta: number) => {
    const order = [...s.store_order];
    const target = index + delta;
    if (target < 0 || target >= order.length) return;
    [order[index], order[target]] = [order[target] as string, order[index] as string];
    set("store_order", order);
  };

  return (
    <>
      <h1>Settings</h1>
      <SyncNote syncedAt={loaded.syncedAt} fromCache={loaded.fromCache} />

      <section className="card">
        <h2>Calories and protein</h2>
        <label htmlFor="kcal">Calories per day</label>
        <input id="kcal" inputMode="numeric" value={s.daily_kcal_target} onChange={(e) => set("daily_kcal_target", int(e.target.value, s.daily_kcal_target))} />
        <label id="cal-mode">Calorie mode</label>
        <div className="segmented" role="group" aria-labelledby="cal-mode">
          <button type="button" aria-pressed={s.calorie_mode === "weekly"} onClick={() => set("calorie_mode", "weekly")}>
            Weekly
          </button>
          <button type="button" aria-pressed={s.calorie_mode === "strict_daily"} onClick={() => set("calorie_mode", "strict_daily")}>
            Strict daily
          </button>
        </div>
        {s.calorie_mode === "weekly" && (
          <>
            <label htmlFor="band">Each day within ± (kcal)</label>
            <input id="band" inputMode="numeric" value={s.daily_band_kcal} onChange={(e) => set("daily_band_kcal", int(e.target.value, s.daily_band_kcal))} />
          </>
        )}
        <label htmlFor="protein">Protein target (g per day)</label>
        <input id="protein" inputMode="numeric" value={s.daily_protein_target_g} onChange={(e) => set("daily_protein_target_g", int(e.target.value, s.daily_protein_target_g))} />
        <h3 className={styles.sub}>Calories per meal</h3>
        {s.slot_allocations.map((a, i) => (
          <div key={a.slot} className="row-between">
            <span>{slotLabel(a.slot)}</span>
            <input
              aria-label={`${slotLabel(a.slot)} kcal`}
              inputMode="numeric"
              className={styles.narrow}
              value={a.kcal}
              onChange={(e) =>
                set(
                  "slot_allocations",
                  s.slot_allocations.map((x, j) => (j === i ? { ...x, kcal: int(e.target.value, x.kcal) } : x)),
                )
              }
            />
          </div>
        ))}
      </section>

      <section className="card">
        <h2>Focus and shopping</h2>
        <label htmlFor="priority">Nutrition focus</label>
        <select id="priority" value={s.nutrition_priority} onChange={(e) => set("nutrition_priority", e.target.value as UserSettings["nutrition_priority"])}>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {humanize(p)}
            </option>
          ))}
        </select>
        <label htmlFor="secondary">Second focus</label>
        <select
          id="secondary"
          value={s.secondary_priority ?? ""}
          onChange={(e) => set("secondary_priority", (e.target.value || null) as UserSettings["secondary_priority"])}
        >
          <option value="">None</option>
          {PRIORITIES.filter((p) => p !== s.nutrition_priority).map((p) => (
            <option key={p} value={p}>
              {humanize(p)}
            </option>
          ))}
        </select>
        <label htmlFor="grocery-mode">Grocery mode</label>
        <select id="grocery-mode" value={s.grocery_mode} onChange={(e) => set("grocery_mode", e.target.value as UserSettings["grocery_mode"])}>
          {["balanced", "cheapest", "healthier", "seasonal"].map((m) => (
            <option key={m} value={m}>
              {humanize(m)}
            </option>
          ))}
        </select>
        <h3 className={styles.sub}>Stores (first = where you shop)</h3>
        <ol className="list">
          {s.store_order.map((store, i) => (
            <li key={store} className="row-between">
              <span>
                {i + 1}. {store}
              </span>
              <span className="row">
                <button type="button" className="btn btn-small" aria-label={`Move ${store} up`} onClick={() => moveStore(i, -1)} disabled={i === 0}>
                  ↑
                </button>
                <button
                  type="button"
                  className="btn btn-small"
                  aria-label={`Move ${store} down`}
                  onClick={() => moveStore(i, 1)}
                  disabled={i === s.store_order.length - 1}
                >
                  ↓
                </button>
              </span>
            </li>
          ))}
        </ol>
        <label htmlFor="split">Only split the trip if it saves at least ($)</label>
        <input id="split" inputMode="decimal" value={threshold} onChange={(e) => setThreshold(e.target.value)} aria-invalid={thresholdCents === undefined} />
      </section>

      <section className="card">
        <h2>Cooking</h2>
        <p className="muted small">Hands-on minutes on each cook day; non-cook days eat leftovers.</p>
        {s.cook_schedule.map((d, i) => (
          <div key={d.weekday} className={styles.cookRow}>
            <label className={styles.inline}>
              <input
                type="checkbox"
                checked={d.is_cook_day}
                onChange={(e) =>
                  set(
                    "cook_schedule",
                    s.cook_schedule.map((x, j) => (j === i ? { ...x, is_cook_day: e.target.checked } : x)),
                  )
                }
              />
              {WEEKDAYS[d.weekday] ?? d.weekday}
            </label>
            <input
              aria-label={`${WEEKDAYS[d.weekday]} minutes`}
              inputMode="numeric"
              className={styles.narrow}
              value={d.cook_minutes}
              disabled={!d.is_cook_day}
              onChange={(e) =>
                set(
                  "cook_schedule",
                  s.cook_schedule.map((x, j) => (j === i ? { ...x, cook_minutes: int(e.target.value, x.cook_minutes) } : x)),
                )
              }
            />
            <select
              aria-label={`${WEEKDAYS[d.weekday]} mood`}
              value={d.mood}
              disabled={!d.is_cook_day}
              onChange={(e) =>
                set(
                  "cook_schedule",
                  s.cook_schedule.map((x, j) => (j === i ? { ...x, mood: e.target.value as (typeof MOODS)[number] } : x)),
                )
              }
            >
              {MOODS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        ))}
        <label htmlFor="fridge">Leftovers keep in the fridge (days, 4 at most)</label>
        <input
          id="fridge"
          inputMode="numeric"
          value={s.leftover_fridge_days}
          onChange={(e) => set("leftover_fridge_days", int(e.target.value, s.leftover_fridge_days))}
        />
        <h3 className={styles.sub}>Equipment</h3>
        <div className={styles.checks}>
          {EQUIPMENT.map((eq) => (
            <label key={eq} className={styles.inline}>
              <input
                type="checkbox"
                checked={s.equipment.includes(eq)}
                onChange={(e) => set("equipment", e.target.checked ? [...s.equipment, eq] : s.equipment.filter((x) => x !== eq))}
              />
              {humanize(eq)}
            </label>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>Frequency caps</h2>
        <p className="muted small">At most this many meals a week; capped foods are never favored.</p>
        {(s.frequency_caps ?? []).map((cap, i) => (
          <div key={cap.label} className="row-between">
            <span>
              {cap.label} <span className="muted small">({cap.target_type}: {cap.target})</span>
            </span>
            <input
              aria-label={`${cap.label}: meals per week`}
              inputMode="numeric"
              className={styles.narrow}
              value={cap.max_meals_per_week}
              onChange={(e) =>
                set(
                  "frequency_caps",
                  (s.frequency_caps ?? []).map((x, j) => (j === i ? { ...x, max_meals_per_week: int(e.target.value, x.max_meals_per_week) } : x)),
                )
              }
            />
          </div>
        ))}
      </section>

      <ProblemNotice error={error} />
      {saved && (
        <p className="notice" role="status">
          Saved.
        </p>
      )}
      <button type="button" className="btn btn-primary btn-block" onClick={save} disabled={saving || thresholdCents === undefined}>
        {saving ? "Saving…" : "Save settings"}
      </button>

      <section className="card" style={{ marginTop: 16 }}>
        <h2>Possibly beef: review</h2>
        <p className="muted small">Held items stay out of plans until you allow them. Beef itself is always excluded.</p>
        {(loaded.data.diet_review ?? []).length === 0 && <p className="muted small">Nothing to review.</p>}
        <ul className="list">
          {(loaded.data.diet_review ?? []).map((item) => (
            <li key={item.ingredient_id} className={styles.review}>
              <div>
                <strong>{item.name}</strong>{" "}
                <span className={item.decision === "allowed" ? "badge badge-accent" : "badge badge-warn"}>{item.decision}</span>
                {item.note && <p className="small muted">{item.note}</p>}
              </div>
              {item.decision === "held" ? (
                <button type="button" className="btn btn-small" onClick={() => void decide(item.ingredient_id, true)}>
                  Allow
                </button>
              ) : (
                <button type="button" className="btn btn-small" onClick={() => void decide(item.ingredient_id, false)}>
                  Hold again
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>

      <button type="button" className="btn btn-block" onClick={() => void logout()} style={{ marginTop: 8 }}>
        Sign out
      </button>
    </>
  );
}
