"use client";

import { Redirect } from "@/components/Redirect";

// Inventory is now the Pantry tab (FLOW_SPEC §3).
export default function InventoryRedirect() {
  return <Redirect to="/pantry/" label="Open your pantry" />;
}
