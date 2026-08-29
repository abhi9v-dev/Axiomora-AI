import Link from "next/link";
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
          plain-English insight.
        </p>
        <Link
          href="/ask"
          className="mt-4 inline-block rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground"
        >
          Ask a question →
        </Link>
      </div>
      <HealthStatus />
    </main>
  );
}
