"use client";

import { Redirect } from "@/components/Redirect";

// The app opens on the Cook tab.
export default function Home() {
  return <Redirect to="/cook/" label="Open Mealbro" />;
}
