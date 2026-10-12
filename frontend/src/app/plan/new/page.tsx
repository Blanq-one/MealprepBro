"use client";

import { Page } from "@/components/Page";
import { Redirect } from "@/components/Redirect";

// The old "Plan a week" form (Phase 2), retired in step 2b.7: Meal prep's questions plan any days (C1).
export default function NewPlanPage() {
  return (
    <Page>
      <Redirect to="/cook/ask/?mode=prep&step=amount&fresh=1" label="Meal prep" />
    </Page>
  );
}
