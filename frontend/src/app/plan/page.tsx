"use client";

import { Page } from "@/components/Page";
import { Redirect } from "@/components/Redirect";

// The old week screen (Phase 2), retired in step 2b.7: plans open in C6, /cook/plan/ (keeps ?id=).
export default function WeekPage() {
  return (
    <Page>
      <Redirect to="/cook/plan/" label="Open your plan" />
    </Page>
  );
}
