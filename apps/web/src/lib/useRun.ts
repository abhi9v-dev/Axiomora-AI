"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { RunSnapshot } from "@bi-copilot/contracts";
import { cancelRun, getRun, startRun, submitClarification, subscribeToRunEvents } from "@/lib/api";
import { getApiBaseUrl } from "@/lib/env";

interface UseRunResult {
  snapshot: RunSnapshot | null;
  error: string | null;
  isSubmitting: boolean;
  start: (question: string, sourceId?: string) => Promise<void>;
  answerClarification: (answer: string) => Promise<void>;
  cancel: () => Promise<void>;
}

/**
 * Drives one run's lifecycle end to end: start a fresh question (or watch
 * an existing `initialRunId`, for /runs/[id]), then keep `snapshot` in
 * sync via SSE (docs/05_FRONTEND_UX.md: "use server-sent events for
 * progress; reconnect by run_id") until it reaches a terminal status.
 */
export function useRun(initialRunId?: string): UseRunResult {
  const baseUrl = getApiBaseUrl();
  const [snapshot, setSnapshot] = useState<RunSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  const watch = useCallback(
    (runId: string) => {
      unsubscribeRef.current?.();
      unsubscribeRef.current = subscribeToRunEvents(baseUrl, runId, {
        onSnapshot: setSnapshot,
      });
    },
    [baseUrl],
  );

  useEffect(() => {
    if (!initialRunId) return undefined;
    let cancelled = false;

    getRun(baseUrl, initialRunId)
      .then((existing) => {
        if (!cancelled) setSnapshot(existing);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load run.");
      });
    watch(initialRunId);

    return () => {
      cancelled = true;
      unsubscribeRef.current?.();
    };
  }, [initialRunId, baseUrl, watch]);

  useEffect(() => {
    return () => unsubscribeRef.current?.();
  }, []);

  const start = useCallback(
    async (question: string, sourceId?: string) => {
      setError(null);
      setIsSubmitting(true);
      try {
        const accepted = await startRun(baseUrl, { question, source_id: sourceId });
        setSnapshot(null);
        watch(accepted.run_id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to start run.");
      } finally {
        setIsSubmitting(false);
      }
    },
    [baseUrl, watch],
  );

  const answerClarification = useCallback(
    async (answer: string) => {
      if (!snapshot) return;
      setError(null);
      setIsSubmitting(true);
      try {
        await submitClarification(baseUrl, snapshot.run_id, answer);
        watch(snapshot.run_id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to submit clarification.");
      } finally {
        setIsSubmitting(false);
      }
    },
    [baseUrl, snapshot, watch],
  );

  const cancel = useCallback(async () => {
    if (!snapshot) return;
    try {
      const cancelled = await cancelRun(baseUrl, snapshot.run_id);
      setSnapshot(cancelled);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel run.");
    }
  }, [baseUrl, snapshot]);

  return { snapshot, error, isSubmitting, start, answerClarification, cancel };
}
