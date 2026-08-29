"use client";

import { useState, type FormEvent } from "react";

interface Props {
  question: string;
  options: string[] | null;
  onSubmit: (answer: string) => void;
  isSubmitting?: boolean;
}

/** docs/05_FRONTEND_UX.md's Clarification state: "one focused question with
 * selectable interpretations" -- plus a free-text fallback, since NL2SQL's
 * assumptions are a best-effort hint, not an exhaustive list. */
export function ClarificationCard({ question, options, onSubmit, isSubmitting }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const [freeText, setFreeText] = useState("");

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const answer = selected ?? freeText.trim();
    if (answer) onSubmit(answer);
  };

  return (
    <form
      onSubmit={handleSubmit}
      aria-label="Clarification needed"
      className="space-y-3 rounded-lg border border-warning/40 bg-amber-50 p-4"
    >
      <p className="font-medium text-neutral-900">{question}</p>

      {options && options.length > 0 ? (
        <div
          role="radiogroup"
          aria-label="Suggested interpretations"
          className="flex flex-col gap-2"
        >
          {options.map((option) => (
            <label key={option} className="flex items-start gap-2 text-sm text-neutral-700">
              <input
                type="radio"
                name="clarification-option"
                value={option}
                checked={selected === option}
                onChange={() => {
                  setSelected(option);
                  setFreeText("");
                }}
                className="mt-0.5"
              />
              {option}
            </label>
          ))}
        </div>
      ) : null}

      <label className="block text-sm text-neutral-700">
        Or explain in your own words:
        <textarea
          value={freeText}
          onChange={(event) => {
            setFreeText(event.target.value);
            setSelected(null);
          }}
          rows={2}
          className="mt-1 w-full rounded-md border border-neutral-300 p-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        />
      </label>

      <button
        type="submit"
        disabled={isSubmitting || (!selected && !freeText.trim())}
        className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-50"
      >
        {isSubmitting ? "Sending…" : "Continue"}
      </button>
    </form>
  );
}
