"use client";

import { useState, type FormEvent } from "react";

const SAMPLE_QUESTIONS = [
  "Why did median task hold time spike for the Buyer department in Q2?",
  "How many stuck projects are there right now?",
  "Which task subtype has the highest claim wait time?",
];

interface Props {
  onSubmit: (question: string) => void;
  isSubmitting?: boolean;
}

/** docs/05_FRONTEND_UX.md's Ask page: "source selector, question composer,
 * sample questions and history." Only one demo source exists yet (see
 * app.api.runs's DEFAULT_SOURCE_ID), so there is no source selector -- a
 * real selector is deferred until a second source exists to choose between. */
export function QuestionComposer({ onSubmit, isSubmitting }: Props) {
  const [question, setQuestion] = useState("");

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (trimmed) onSubmit(trimmed);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <label htmlFor="question" className="block text-sm font-medium text-neutral-700">
        Ask a business question
      </label>
      <textarea
        id="question"
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        rows={3}
        placeholder="e.g. Why did median task hold time spike for the Buyer department in Q2?"
        className="w-full rounded-lg border border-neutral-300 p-3 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {SAMPLE_QUESTIONS.map((sample) => (
            <button
              key={sample}
              type="button"
              onClick={() => setQuestion(sample)}
              className="rounded-full border border-neutral-200 px-3 py-1 text-xs text-neutral-600 hover:border-accent hover:text-accent"
            >
              {sample}
            </button>
          ))}
        </div>
        <button
          type="submit"
          disabled={isSubmitting || !question.trim()}
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-50"
        >
          {isSubmitting ? "Asking…" : "Ask"}
        </button>
      </div>
    </form>
  );
}
