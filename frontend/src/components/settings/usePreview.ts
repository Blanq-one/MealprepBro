"use client";

import { useEffect, useState } from "react";

import type { UserSettings } from "@/lib/api/types";
import { errorsByField, type FieldErrors, previewSettings } from "@/lib/settings/fields";

/** "1,800 of 1,800 kcal a day planned" for a draft, from POST /settings/preview (debounced), plus the
 * draft's field errors. The phone adds nothing up itself. */
export function usePreview(draft: Partial<UserSettings> | null, enabled: boolean): { planned: string | null; errors: FieldErrors } {
  const [planned, setPlanned] = useState<string | null>(null);
  const [errors, setErrors] = useState<FieldErrors>({});
  const key = draft ? JSON.stringify(draft) : null;
  useEffect(() => {
    if (!enabled || key === null) return;
    let stale = false;
    const timer = setTimeout(() => {
      previewSettings(JSON.parse(key) as Partial<UserSettings>)
        .then((preview) => {
          if (stale) return;
          setPlanned(preview.kcal_planned_display);
          setErrors(errorsByField(preview.errors));
        })
        .catch(() => undefined);
    }, 300);
    return () => {
      stale = true;
      clearTimeout(timer);
    };
  }, [key, enabled]);
  return { planned, errors };
}
