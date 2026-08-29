/** Typed HTTP + SSE client for the runs API (docs/06_DATA_MODEL_API_CONTRACTS.md). */
import type {
  ClarificationRequest,
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
