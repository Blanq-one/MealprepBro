// POST /api/v1/plans answers with NDJSON: one JSON event per line while it plans the week.
import { problemFrom, redirectToLogin } from "./client";
import type { PlanRequestBody, PlanStreamEvent } from "./types";

/** Read a byte stream of newline-delimited JSON, calling onEvent for each complete line. Lines may be split
 * across chunks in any way. Returns the number of events read. */
export async function readNdjson<T>(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: T) => void,
): Promise<number> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let count = 0;
  const emit = (line: string) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    onEvent(JSON.parse(trimmed) as T);
    count += 1;
  };
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let newline = buffer.indexOf("\n");
    while (newline >= 0) {
      emit(buffer.slice(0, newline));
      buffer = buffer.slice(newline + 1);
      newline = buffer.indexOf("\n");
    }
  }
  buffer += decoder.decode();
  emit(buffer);
  return count;
}

/** Plan a week and stream its events. Throws ApiError when the request itself is refused (422, 401). */
export async function streamPlan(
  request: PlanRequestBody,
  onEvent: (event: PlanStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch("/api/v1/plans", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "application/x-ndjson" },
    body: JSON.stringify(request),
    signal,
  });
  if (!response.ok || !response.body) {
    const error = await problemFrom(response);
    if (response.status === 401) redirectToLogin();
    throw error;
  }
  await readNdjson<PlanStreamEvent>(response.body, onEvent);
}
