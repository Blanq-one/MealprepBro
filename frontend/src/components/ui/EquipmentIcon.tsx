// Small in-house line icons for kitchen equipment (FLOW_SPEC §4.4): emoji don't cover ovens or air fryers well.
import type { ReactNode } from "react";

const PATHS: Record<string, ReactNode> = {
  stovetop: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <circle cx="8.5" cy="10" r="2" />
      <circle cx="15.5" cy="10" r="2" />
      <circle cx="8.5" cy="15.5" r="1.5" />
      <circle cx="15.5" cy="15.5" r="1.5" />
    </>
  ),
  oven: (
    <>
      <rect x="3.5" y="3" width="17" height="18" rx="2" />
      <path d="M3.5 7.5h17" />
      <rect x="7" y="10.5" width="10" height="7" rx="1" />
      <path d="M7 5.2h.01M10 5.2h.01M13 5.2h4" />
    </>
  ),
  air_fryer: (
    <>
      <path d="M6 4h12a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" />
      <circle cx="12" cy="8" r="1.6" />
      <path d="M4 12.5h16M9 16h6" />
    </>
  ),
  microwave: (
    <>
      <rect x="2.5" y="5" width="19" height="14" rx="2" />
      <rect x="5" y="8" width="10" height="8" rx="1" />
      <path d="M18 8.5h.01M18 11.5h.01M18 14.5h.01" />
    </>
  ),
  rice_cooker: (
    <>
      <path d="M5 11h14v6a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3z" />
      <path d="M4 11c0-3.5 3.6-6 8-6s8 2.5 8 6" />
      <path d="M10.5 5V3.8h3V5M9 15h6" />
    </>
  ),
  pressure_cooker: (
    <>
      <path d="M5 10h14v7.5a2.5 2.5 0 0 1-2.5 2.5h-9A2.5 2.5 0 0 1 5 17.5z" />
      <path d="M4 10h16M8 10V7.5a4 4 0 0 1 8 0V10M2 12.5h3M19 12.5h3" />
      <path d="M12 3.5v-1" />
    </>
  ),
  slow_cooker: (
    <>
      <ellipse cx="12" cy="14" rx="8" ry="6" />
      <path d="M5 11.5c1.5-2 4-3 7-3s5.5 1 7 3M2.5 13.5H4M20 13.5h1.5M11 8.5V7h2v1.5" />
    </>
  ),
  blender: (
    <>
      <path d="M7 3h10l-1.5 11h-7z" />
      <path d="M6 3h12M8.5 14h7l1 3H7.5z" />
      <rect x="6.5" y="17" width="11" height="4" rx="1" />
    </>
  ),
  food_processor: (
    <>
      <path d="M5 6h12v8H5z" />
      <path d="M17 7.5h2.5V12H17M9 10l4-1.5M11 6V3.5" />
      <rect x="4" y="14" width="14" height="6" rx="1.5" />
      <path d="M8 17h.01" />
    </>
  ),
  grill: (
    <>
      <path d="M3.5 9h17a8.5 8.5 0 0 1-17 0z" />
      <path d="M7 9V6.5M12 9V5.5M17 9V6.5M8.5 16.5 6 21.5M15.5 16.5l2.5 5M12 17.5v4" />
    </>
  ),
};

export function EquipmentIcon({ name, size = 32 }: { name: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name] ?? <rect x="4" y="4" width="16" height="16" rx="3" />}
    </svg>
  );
}

export const EQUIPMENT = [
  { key: "stovetop", label: "Stovetop" },
  { key: "oven", label: "Oven" },
  { key: "air_fryer", label: "Air fryer" },
  { key: "microwave", label: "Microwave" },
  { key: "rice_cooker", label: "Rice cooker" },
  { key: "pressure_cooker", label: "Pressure cooker" },
  { key: "slow_cooker", label: "Slow cooker" },
  { key: "blender", label: "Blender" },
  { key: "food_processor", label: "Food processor" },
  { key: "grill", label: "Grill" },
] as const;
