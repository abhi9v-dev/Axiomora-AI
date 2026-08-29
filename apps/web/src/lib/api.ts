/** Typed HTTP + SSE client for the runs API (docs/06_DATA_MODEL_API_CONTRACTS.md). */
import type {
  ActionRequest,
  ActionType,
  ClarificationRequest,
  PowerBiActionResponse,
  RunAcceptedResponse,
  RunSnapshot,
  RunSummary,
  StartRunRequest,
} from "@bi-copilot/contracts";

interface ErrorBody {
  detail?: string;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => undefined)) as ErrorBody | undefined;
    throw new Error(body?.detail ?? `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function startRun(
  baseUrl: string,
  body: StartRunRequest,
): Promise<RunAcceptedResponse> {
  return request(`${baseUrl}/api/v1/runs`, { method: "POST", body: JSON.stringify(body) });
}

export async function getRun(baseUrl: string, runId: string): Promise<RunSnapshot> {
  return request(`${baseUrl}/api/v1/runs/${runId}`);
}

export async function listRuns(baseUrl: string, limit = 20): Promise<RunSummary[]> {
  return request(`${baseUrl}/api/v1/runs?limit=${limit}`);
}

export async function submitClarification(
  baseUrl: string,
  runId: string,
  answer: string,
): Promise<RunAcceptedResponse> {
  const body: ClarificationRequest = { answer };
  return request(`${baseUrl}/api/v1/runs/${runId}/clarification`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function cancelRun(baseUrl: string, runId: string): Promise<RunSnapshot> {
  return request(`${baseUrl}/api/v1/runs/${runId}/cancel`, { method: "POST" });
}

interface ExcelExport {
  blob: Blob;
  filename: string;
}

function parseFilename(contentDisposition: string | null, fallback: string): string {
  const match = contentDisposition ? /filename="?([^";]+)"?/.exec(contentDisposition) : null;
  return match?.[1] ?? fallback;
}

/**
 * Requests the Summary/Data/SQL & Evidence/Validation workbook for a
 * validated run (docs/06's `POST /api/v1/runs/{run_id}/actions`). A fresh
 * idempotency key per call is correct here: each call represents one new
 * user-initiated export request, not a retry of a prior one -- the
 * backend's idempotency guarantee exists to make network-level retries of
 * *the same* request safe, not to deduplicate deliberate repeat clicks.
 */
export async function requestExcelExport(baseUrl: string, runId: string): Promise<ExcelExport> {
  const body: ActionRequest = { type: "export_excel", idempotency_key: crypto.randomUUID() };
  const response = await fetch(`${baseUrl}/api/v1/runs/${runId}/actions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const errorBody = (await response.json().catch(() => undefined)) as ErrorBody | undefined;
    throw new Error(errorBody?.detail ?? `Export failed with status ${response.status}`);
  }
  const blob = await response.blob();
  const filename = parseFilename(
    response.headers.get("content-disposition"),
    `bi-copilot-run-${runId}.xlsx`,
  );
  return { blob, filename };
}

/** Saves a client-fetched blob as a file via a throwaway anchor element --
 * the standard browser pattern for a JS-triggered download (this is a
 * real app running in a real browser, not a sandboxed preview). */
export function triggerBrowserDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Requests a Power BI action (`power_bi_push`/`power_bi_refresh`, Phase 8
 * -- only available once the API's `POWER_BI_ENABLED` flag is set). Unlike
 * `requestExcelExport`, the response body is a small JSON receipt, not a
 * file -- there is nothing to download. A fresh idempotency key per call
 * is correct for the same reason `requestExcelExport` uses one: each call
 * is a new user-initiated request, not a retry of a prior one.
 */
export async function requestPowerBiAction(
  baseUrl: string,
  runId: string,
  type: Extract<ActionType, "power_bi_push" | "power_bi_refresh">,
): Promise<PowerBiActionResponse> {
  const body: ActionRequest = { type, idempotency_key: crypto.randomUUID() };
  return request(`${baseUrl}/api/v1/runs/${runId}/actions`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/**
 * Subscribes to a run's live progress (docs/05_FRONTEND_UX.md: "use
 * server-sent events for progress; reconnect by run_id"). Returns an
 * unsubscribe function. The connection closes on its own once the server
 * sends a terminal-status snapshot (app.orchestrator.events.RunEventBus);
 * calling the returned unsubscribe function early (e.g. on unmount) closes
 * it regardless.
 */
export function subscribeToRunEvents(
  baseUrl: string,
  runId: string,
  handlers: { onSnapshot: (snapshot: RunSnapshot) => void; onError?: (event: Event) => void },
): () => void {
  const source = new EventSource(`${baseUrl}/api/v1/runs/${runId}/events`);

  source.addEventListener("run_update", (event) => {
    const messageEvent = event as MessageEvent<string>;
    const snapshot = JSON.parse(messageEvent.data) as RunSnapshot;
    handlers.onSnapshot(snapshot);
  });

  if (handlers.onError) {
    source.addEventListener("error", handlers.onError);
  }

  return () => source.close();
}
