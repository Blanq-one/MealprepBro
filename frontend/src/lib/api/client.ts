// Same-origin JSON API calls. Problems (application/problem+json) become ApiError; a 401 sends you to
// sign in (except on the sign-in page itself).

export type Diagnostic = { code?: string; message: string; slot?: string; day?: string; amount?: number };
/** A validation error as the server sent it: the field path and the message. */
export type ValidationIssue = { loc: (string | number)[]; msg: string };

export class ApiError extends Error {
  readonly status: number;
  readonly title: string;
  readonly detail: string;
  readonly diagnostics: Diagnostic[];
  readonly retryAfterS: number | null;
  readonly errors: ValidationIssue[];
  /** The problem as sent, for its extra fields (a 409 plan_overlap's `overlapping`). */
  readonly body: Record<string, unknown> | null;

  constructor(
    status: number,
    title: string,
    detail: string,
    diagnostics: Diagnostic[] = [],
    retryAfterS: number | null = null,
    errors: ValidationIssue[] = [],
    body: Record<string, unknown> | null = null,
  ) {
    super(detail || title);
    this.name = "ApiError";
    this.status = status;
    this.title = title;
    this.detail = detail;
    this.diagnostics = diagnostics;
    this.retryAfterS = retryAfterS;
    this.errors = errors;
    this.body = body;
  }
}

export const LOGIN_PATH = "/login/";

function onLoginPage(): boolean {
  return typeof window !== "undefined" && window.location.pathname.startsWith("/login");
}

export function redirectToLogin(): void {
  if (typeof window !== "undefined" && !onLoginPage()) {
    window.location.assign(LOGIN_PATH);
  }
}

type RawProblem = {
  title?: unknown;
  detail?: unknown;
  diagnostics?: unknown;
  errors?: { msg?: string; loc?: unknown[] }[];
};

/** Turn a failed response into an ApiError, reading problem+json when the server sent it. */
export async function problemFrom(response: Response): Promise<ApiError> {
  const retry = response.headers.get("retry-after");
  const retryAfterS = retry !== null && /^\d+$/.test(retry) ? Number(retry) : null;
  const type = response.headers.get("content-type") ?? "";
  let body: unknown = null;
  try {
    body = type.includes("json") ? await response.json() : await response.text();
  } catch {
    body = null;
  }
  if (body && typeof body === "object") {
    const b = body as RawProblem;
    const errors = Array.isArray(b.errors) ? b.errors : [];
    const diagnostics: Diagnostic[] = Array.isArray(b.diagnostics)
      ? (b.diagnostics as Diagnostic[])
      : errors.map((e) => {
          const where = (e.loc ?? []).slice(1).join(".");
          return { message: where ? `${where}: ${e.msg ?? ""}` : (e.msg ?? "") };
        });
    return new ApiError(
      response.status,
      typeof b.title === "string" ? b.title : response.statusText || "Request failed",
      typeof b.detail === "string" ? b.detail : "",
      diagnostics,
      retryAfterS,
      errors.map((e) => ({ loc: Array.isArray(e.loc) ? (e.loc as (string | number)[]) : [], msg: e.msg ?? "" })),
      body as Record<string, unknown>,
    );
  }
  return new ApiError(
    response.status,
    response.statusText || "Request failed",
    typeof body === "string" ? body : "",
    [],
    retryAfterS,
  );
}

export type ApiInit = Omit<RequestInit, "body"> & { json?: unknown };

/** fetch for the API: same origin, JSON in and out. Throws ApiError on any non-2xx status. */
export async function api<T>(path: string, init: ApiInit = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  const response = await fetch(path, {
    credentials: "same-origin",
    ...rest,
    headers: {
      Accept: "application/json",
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(headers as Record<string, string> | undefined),
    },
    body: json !== undefined ? JSON.stringify(json) : undefined,
  });
  if (!response.ok) {
    const error = await problemFrom(response);
    if (response.status === 401) redirectToLogin();
    throw error;
  }
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

/** A short human message for any error (offline, problem+json or unexpected). */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) return error.detail ? `${error.title}: ${error.detail}` : error.title;
  if (error instanceof TypeError) return "You're offline or the server can't be reached.";
  return error instanceof Error ? error.message : String(error);
}
