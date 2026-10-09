import { type ReactNode, Suspense } from "react";

import { Spinner } from "./Status";

/** Pages read their ids from the query string (static export: no dynamic segments), which needs Suspense. */
export function Page({ children }: { children: ReactNode }) {
  return <Suspense fallback={<Spinner />}>{children}</Suspense>;
}
