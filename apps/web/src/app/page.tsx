import { HealthStatus } from "@/components/HealthStatus";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-start gap-8 px-6 py-16">
      <div>
        <p className="text-sm font-semibold uppercase tracking-wide text-accent">
          NL-to-Insight BI Copilot
        </p>
        <h1 className="mt-2 text-3xl font-bold text-neutral-900">
          Governance-safe multi-agent BI Copilot
        </h1>
        <p className="mt-3 max-w-xl text-neutral-600">
          Ask a business question in plain English and get an answer grounded in your governed
          schema and glossary: retrieved context, validated SQL, a verified result and a cited,
          plain-English insight. This is the Phase 0 foundation shell; the{" "}
          <code className="rounded bg-neutral-100 px-1 py-0.5 text-sm">/ask</code> workspace arrives
          in Phase 6.
        </p>
      </div>
      <HealthStatus />
    </main>
  );
}
