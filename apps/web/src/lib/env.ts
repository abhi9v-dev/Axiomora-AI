/** Typed access to build-time/browser-exposed environment configuration. */
export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

/** Build-time UI gate for the Power BI action buttons
 * (docs/05_FRONTEND_UX.md: "Publish to Power BI when enabled"). The API
 * enforces POWER_BI_ENABLED server-side regardless of what the UI shows
 * -- this only controls whether the buttons are offered at all. */
export function isPowerBiEnabled(): boolean {
  return process.env.NEXT_PUBLIC_POWER_BI_ENABLED === "true";
}
