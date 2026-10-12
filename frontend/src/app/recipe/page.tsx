"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useState } from "react";

import { useOnline } from "@/components/AppShell";
import { NotForMe } from "@/components/cook/NotForMe";
import { RecipeActions } from "@/components/cook/RecipeActions";
import { StepsPending } from "@/components/cook/StepsPending";
import { MarkCooked } from "@/components/MarkCooked";
import { Page } from "@/components/Page";
import { type RecipeLine, RecipeView } from "@/components/RecipeView";
import { ProblemNotice, SyncNote } from "@/components/Status";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/States";
import { ApiError } from "@/lib/api/client";
import type { BatchDetail, PortionSize, RecipeVersion, SearchContext } from "@/lib/api/types";
import { useSteps, writeSteps } from "@/lib/cook/steps";
import { dayLabel } from "@/lib/format/dates";
import { slotLabel } from "@/lib/format/labels";
import { useApi } from "@/lib/hooks/useApi";

const SIZES: PortionSize[] = ["small", "normal", "large", "extra_large"];
const MAX_COOK_PORTIONS = 8; // Cook this cooks for up to 8 (CookMealIn); bigger batches are meal prep

function Unavailable({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  if (error instanceof ApiError && error.status === 404) {
    return <EmptyState message="This recipe isn't available anymore." action={{ label: "Back to Cook", href: "/cook/" }} />;
  }
  return <ErrorState error={error} onRetry={onRetry} />;
}

/** The recipe's lines with each line's note from the server: what it uses of what you have, a substitute. */
function linesWith(recipe: RecipeVersion, details: Map<number, string>): RecipeLine[] {
  return recipe.lines.map((l, i) => ({
    key: `${l.ingredient_id}-${i}`,
    name: l.name,
    display: l.amount_display || l.display,
    preparation: l.preparation,
    optional: l.optional,
    detail: details.get(l.ingredient_id) ?? null,
    portionNote: l.portion_note ?? null,
  }));
}

/** "Before you start" for a meal now: what to buy, what's missing, and swaps with what you have (C8, M11). */
function BeforeYouStart({ context }: { context: SearchContext }) {
  const swaps = context.swaps ?? [];
  if (context.could_buy.length === 0 && context.missing.length === 0 && swaps.length === 0) return null;
  return (
    <section className="card" aria-labelledby="before-h">
      <h2 id="before-h">Before you start</h2>
      <ul className="list">
        {context.could_buy.map((line) => (
          <li key={`buy-${line.ingredient_id}`}>Could buy: {line.display}</li>
        ))}
        {swaps.map((line) => (
          <li key={`swap-${line.ingredient_id}`}>{line.display}</li>
        ))}
        {context.missing.map((line) => (
          <li key={`missing-${line.ingredient_id}`}>Missing: {line.display}</li>
        ))}
      </ul>
      <p className="small muted">{context.note}</p>
    </section>
  );
}

/** A new idea's steps, written on first open (E19): the Steps section's state and Cook this held until they
 * land. Nothing for a recipe that has its steps. */
function useIdeaSteps(recipe: RecipeVersion | null, query: string, online: boolean, reload: () => Promise<void>) {
  const onReady = useCallback(() => void reload(), [reload]);
  const state = useSteps(recipe?.version_id ?? null, recipe ? recipe.steps_ready : true, query, online, onReady);
  const pending = recipe !== null && !recipe.steps_ready;
  return {
    blocked: pending ? "Writing steps…" : null,
    slot: pending ? <StepsPending method={recipe.description} state={state} online={online} onRetry={() => writeSteps(recipe.version_id, query, onReady)} /> : undefined,
  };
}

function BatchRecipe({ batchId }: { batchId: string }) {
  const batch = useApi<BatchDetail>(`/api/v1/cook-batches/${batchId}`);
  const online = useOnline();
  const steps = useIdeaSteps(batch.data?.recipe ?? null, "", online, batch.reload);
  if (batch.loading && !batch.data) return <Skeleton cards={3} label="Loading the recipe" />;
  if (!batch.data) return <Unavailable error={batch.error} onRetry={() => void batch.reload()} />;
  const b = batch.data;
  const notes = new Map((b.pantry_notes ?? []).map((n) => [n.ingredient_id, n.note]));
  return (
    <>
      <SyncNote syncedAt={batch.syncedAt} fromCache={batch.fromCache} />
      <RecipeView
        recipe={b.recipe}
        stepsSlot={steps.slot}
        notes={[...b.package_notes, ...b.freeze_notes]}
        lines={b.lines.map((l, i) => ({
          key: `${l.ingredient_id}-${i}`,
          name: l.name,
          display: l.display,
          preparation: l.preparation,
          optional: l.optional,
          note: l.adjustment === "absorbed_full_package" ? "whole package" : l.adjustment === "substituted" ? "substituted" : null,
          detail: notes.get(l.ingredient_id) ?? null,
          portionNote: l.portion_note ?? null,
        }))}
      >
        <section className="card">
          <p>
            <strong>Cook on {dayLabel(b.cook_on)}</strong> · {b.portions} portions
            {b.portions_to_freeze > 0 ? `, freeze ${b.portions_to_freeze}` : ""}
          </p>
          <p className="small muted">
            Feeds:{" "}
            {b.meals.map((m) => `${dayLabel(m.eat_on)} ${slotLabel(m.slot).toLowerCase()}${m.kind === "assembly" ? ` (${m.title})` : ""}${m.from_freezer ? " (from freezer)" : ""}`).join(", ")}
          </p>
          {b.in_plan && <p className="small">{b.in_plan}</p>}
          <MarkCooked batchId={b.id} status={b.status} onCooked={() => void batch.reload()} />
        </section>
        {b.status !== "cooked" && <RecipeActions recipe={b.recipe} cook={{ batchId: b.id }} online={online} blocked={steps.blocked} />}
        <NotForMe recipeId={b.recipe.recipe_id} title={b.recipe.title} hidden={b.recipe.is_hidden} online={online} />
      </RecipeView>
    </>
  );
}

/** A recipe opened from a meal-now search: at the card's portions, with that search's coverage lines. */
function SearchRecipe({ versionId, searchId }: { versionId: string; searchId: string }) {
  const version = useApi<RecipeVersion>(`/api/v1/recipe-versions/${versionId}?search=${searchId}`);
  const online = useOnline();
  const steps = useIdeaSteps(version.data, `search=${searchId}`, online, version.reload);
  if (version.loading && !version.data) return <Skeleton cards={3} label="Loading the recipe" />;
  if (!version.data) return <Unavailable error={version.error} onRetry={() => void version.reload()} />;
  const recipe = version.data;
  const context = recipe.search_context ?? null;
  const details = new Map((context?.lines ?? []).filter((l) => l.note).map((l) => [l.ingredient_id, l.note ?? ""]));
  return (
    <>
      <SyncNote syncedAt={version.syncedAt} fromCache={version.fromCache} />
      <RecipeView recipe={recipe} lines={linesWith(recipe, details)} portionsLine={context?.portions_display ?? null} stepsSlot={steps.slot}>
        {context && <BeforeYouStart context={context} />}
        <RecipeActions
          recipe={recipe}
          cook={{ meal: { version_id: recipe.version_id, search_id: context ? context.search_id : null } }}
          online={online}
          blocked={steps.blocked}
        />
        <NotForMe recipeId={recipe.recipe_id} title={recipe.title} hidden={recipe.is_hidden} online={online} />
      </RecipeView>
    </>
  );
}

/** A saved (or any) recipe: pick the portions and portion size; Cook this cooks that many. */
function VersionRecipe({ versionId, portions, size }: { versionId: string; portions: string | null; size: string | null }) {
  const [count, setCount] = useState<number | null>(portions && /^\d+$/.test(portions) ? Number(portions) : null);
  const [portionSize, setPortionSize] = useState<PortionSize>(SIZES.includes(size as PortionSize) ? (size as PortionSize) : "normal");
  const query = new URLSearchParams({ portion_size: portionSize, ...(count ? { portions: String(count) } : {}) });
  const version = useApi<RecipeVersion>(`/api/v1/recipe-versions/${versionId}?${query.toString()}`);
  const online = useOnline();
  const steps = useIdeaSteps(version.data, query.toString(), online, version.reload);
  const shownCount = count ?? version.data?.portions ?? 1;
  if (version.loading && !version.data) return <Skeleton cards={3} label="Loading the recipe" />;
  if (!version.data) return <Unavailable error={version.error} onRetry={() => void version.reload()} />;
  return (
    <>
      <section className="card row" style={{ flexWrap: "wrap" }} aria-label="Portions">
        <button type="button" className="btn" aria-label="Fewer portions" onClick={() => setCount(Math.max(1, shownCount - 1))}>
          −
        </button>
        <strong aria-live="polite">{shownCount} portions</strong>
        <button type="button" className="btn" aria-label="More portions" onClick={() => setCount(Math.min(MAX_COOK_PORTIONS, shownCount + 1))}>
          +
        </button>
        <select aria-label="Portion size" value={portionSize} onChange={(e) => setPortionSize(e.target.value as PortionSize)} style={{ width: "auto" }}>
          {SIZES.map((s) => (
            <option key={s} value={s}>
              {s.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </section>
      <ProblemNotice error={version.error} />
      <RecipeView recipe={version.data} stepsSlot={steps.slot}>
        <RecipeActions
          recipe={version.data}
          cook={{ meal: { version_id: version.data.version_id, search_id: null, portions: shownCount } }}
          online={online}
          blocked={steps.blocked}
        />
        <NotForMe recipeId={version.data.recipe_id} title={version.data.title} hidden={version.data.is_hidden} online={online} />
      </RecipeView>
    </>
  );
}

function RecipeScreen() {
  const params = useSearchParams();
  const batch = params.get("batch");
  const version = params.get("version");
  const search = params.get("search");
  if (batch) return <BatchRecipe batchId={batch} />;
  if (version && search) return <SearchRecipe versionId={version} searchId={search} />;
  if (version) return <VersionRecipe versionId={version} portions={params.get("portions")} size={params.get("size")} />;
  return <EmptyState message="Open a recipe from Cook." action={{ label: "Back to Cook", href: "/cook/" }} />;
}

// C8 Recipe page (FLOW_SPEC §7): ?version=&search= (a meal-now card), ?batch= (a plan batch), ?version=
// (saved, with portions).
export default function RecipePage() {
  return (
    <Page>
      <RecipeScreen />
    </Page>
  );
}
