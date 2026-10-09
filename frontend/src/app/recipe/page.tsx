"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { MarkCooked } from "@/components/MarkCooked";
import { Page } from "@/components/Page";
import { RecipeView } from "@/components/RecipeView";
import { ProblemNotice, Spinner, SyncNote } from "@/components/Status";
import type { BatchDetail, PortionSize, RecipeVersion } from "@/lib/api/types";
import { dayLabel } from "@/lib/format/dates";
import { slotLabel } from "@/lib/format/labels";
import { useApi } from "@/lib/hooks/useApi";

const SIZES: PortionSize[] = ["small", "normal", "large", "extra_large"];

function BatchRecipe({ batchId }: { batchId: string }) {
  const batch = useApi<BatchDetail>(`/api/v1/cook-batches/${batchId}`);
  if (batch.loading) return <Spinner />;
  if (batch.error || !batch.data) return <ProblemNotice error={batch.error} />;
  const b = batch.data;
  return (
    <>
      <SyncNote syncedAt={batch.syncedAt} fromCache={batch.fromCache} />
      <RecipeView
        recipe={b.recipe}
        notes={[...b.package_notes, ...b.freeze_notes]}
        lines={b.lines.map((l, i) => ({
          key: `${l.ingredient_id}-${i}`,
          name: l.name,
          display: l.display,
          preparation: l.preparation,
          optional: l.optional,
          note: l.adjustment === "absorbed_full_package" ? "whole package" : l.adjustment === "substituted" ? "substituted" : null,
        }))}
      >
        <section className="card">
          <p>
            <strong>Cook on {dayLabel(b.cook_on)}</strong> · {b.portions} portions
            {b.portions_to_freeze > 0 ? `, freeze ${b.portions_to_freeze}` : ""}
          </p>
          <p className="small muted">
            Feeds:{" "}
            {b.meals.map((m) => `${dayLabel(m.eat_on)} ${slotLabel(m.slot).toLowerCase()}${m.from_freezer ? " (from freezer)" : ""}`).join(", ")}
          </p>
          <MarkCooked batchId={b.id} status={b.status} />
        </section>
      </RecipeView>
    </>
  );
}

function VersionRecipe({ versionId, portions, size }: { versionId: string; portions: string | null; size: string | null }) {
  const [count, setCount] = useState<number | null>(portions && /^\d+$/.test(portions) ? Number(portions) : null);
  const [portionSize, setPortionSize] = useState<PortionSize>(SIZES.includes(size as PortionSize) ? (size as PortionSize) : "normal");
  const query = new URLSearchParams({ portion_size: portionSize, ...(count ? { portions: String(count) } : {}) });
  const version = useApi<RecipeVersion>(`/api/v1/recipe-versions/${versionId}?${query.toString()}`);
  const shownCount = count ?? version.data?.portions ?? 1;
  return (
    <>
      <section className="card row" style={{ flexWrap: "wrap" }} aria-label="Portions">
        <button type="button" className="btn" aria-label="Fewer portions" onClick={() => setCount(Math.max(1, shownCount - 1))}>
          −
        </button>
        <strong aria-live="polite">{shownCount} portions</strong>
        <button type="button" className="btn" aria-label="More portions" onClick={() => setCount(Math.min(40, shownCount + 1))}>
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
      {version.loading && !version.data && <Spinner />}
      <ProblemNotice error={version.error} />
      {version.data && <RecipeView recipe={version.data} />}
    </>
  );
}

function RecipeScreen() {
  const params = useSearchParams();
  const batch = params.get("batch");
  const version = params.get("version");
  if (batch) return <BatchRecipe batchId={batch} />;
  if (version) return <VersionRecipe versionId={version} portions={params.get("portions")} size={params.get("size")} />;
  return <p>Open a recipe from your week.</p>;
}

export default function RecipePage() {
  return (
    <Page>
      <RecipeScreen />
    </Page>
  );
}
