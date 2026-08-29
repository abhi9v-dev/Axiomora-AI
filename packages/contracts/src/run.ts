/**
 * TypeScript mirror of the backend's run/agent contracts
 * (docs/06_DATA_MODEL_API_CONTRACTS.md; apps/api/app/orchestrator/schema.py,
 * apps/api/app/nl2sql/schema.py, apps/api/app/validator/schema.py,
 * apps/api/app/insight/schema.py). Field names match the JSON the API
 * actually sends byte-for-byte (snake_case, same as every Pydantic
 * `model_dump_json()` response) -- no camelCase conversion layer, so a
 * response can be trusted as this shape with no transformation step.
 *
 * Keep in sync by hand: there is no schema-generation step in this project
 * (deliberately -- see docs/03_ARCHITECTURE.md's provider-interface /
 * typed-contract conventions elsewhere). If a Python contract changes,
 * update its mirror here in the same change.
 */

export type RunStatus =
  | "RECEIVED"
  | "RETRIEVING"
  | "GENERATING_SQL"
  | "VALIDATING"
  | "REPAIR_SQL"
  | "GENERATING_INSIGHT"
  | "READY"
  | "NEEDS_CLARIFICATION"
  | "FAILED"
  | "CANCELLED";

export const TERMINAL_STATUSES: readonly RunStatus[] = [
  "READY",
  "NEEDS_CLARIFICATION",
  "FAILED",
  "CANCELLED",
];

export type DocumentKind =
  | "table"
  | "column"
  | "relationship"
  | "glossary_term"
  | "measure"
  | "validation_rule";

export interface RetrievalResult {
  chunk_id: number;
  document_id: number;
  kind: DocumentKind;
  object_name: string;
  title: string;
  content: string;
  score: number;
  citation: string;
}

export type ParameterValue = string | number | boolean;

export interface NL2SQLOutput {
  sql: string;
  dialect: string;
  referenced_objects: string[];
  assumptions: string[];
  parameters: Record<string, ParameterValue>;
  confidence: number;
}

export interface ValidationCheck {
  name: string;
  status: "pass" | "fail" | "warning";
  details: string;
}

export interface QueryResult {
  columns: string[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
}

export interface ValidatorOutput {
  status: "pass" | "fail";
  checks: ValidationCheck[];
  repairable: boolean;
  feedback: string | null;
  result: QueryResult | null;
}

export interface Claim {
  text: string;
  evidence: string[];
}

export interface ChartSuggestion {
  type: string;
  x: string;
  y: string;
}

export interface InsightOutput {
  headline: string;
  narrative: string;
  claims: Claim[];
  chart: ChartSuggestion | null;
}

export interface AttemptRecord {
  attempt_no: number;
  nl2sql: NL2SQLOutput;
  validator: ValidatorOutput;
}

export interface RunSnapshot {
  run_id: string;
  tenant_id: string;
  source_id: string;
  question: string;
  status: RunStatus;
  retrieved_context: RetrievalResult[];
  attempts: AttemptRecord[];
  insight: InsightOutput | null;
  insight_error: string | null;
  clarification_question: string | null;
  clarification_options: string[] | null;
  clarification_answer: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface RunSummary {
  run_id: string;
  question: string;
  status: RunStatus;
  created_at: string;
}

export interface StartRunRequest {
  question: string;
  source_id?: string;
  timezone?: string;
}

export interface ClarificationRequest {
  answer: string;
}

export interface RunAcceptedResponse {
  run_id: string;
  status: RunStatus;
}

export function isTerminalStatus(status: RunStatus): boolean {
  return (TERMINAL_STATUSES as RunStatus[]).includes(status);
}

/** Only "export_excel" is implemented (Phase 7); the Power BI types exist
 * so the client can name a specific not-yet-available action rather than
 * only ever offering export -- see apps/api/app/action/schema.py. */
export type ActionType = "export_excel" | "power_bi_push" | "power_bi_refresh" | "power_bi_replace";

export interface ActionRequest {
  type: ActionType;
  idempotency_key: string;
}
