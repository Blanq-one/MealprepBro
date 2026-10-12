"use client";

import { Page } from "@/components/Page";
import { Redirect } from "@/components/Redirect";

// The old day screen (Phase 2), retired in step 2b.7: C6 shows every day; ?plan=&date= opens that plan at that
// day.
export default function DayPage() {
  return (
    <Page>
      <Redirect to="/cook/plan/" label="Open your plan" />
    </Page>
  );
}
