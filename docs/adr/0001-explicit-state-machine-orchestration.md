# ADR 0001: Explicit state machine orchestration instead of agent conversation

## Status

Accepted (established in the Phase 0 foundation).

## Context

Multi-agent systems are commonly built as an unconstrained conversation loop
where agents call each other or a shared LLM decides what happens next. That
pattern is hard to audit, hard to bound (repair loops can run forever), and
makes it easy for a compromised or confused agent to trigger an unintended
tool call. This project's governance requirements — bounded SQL repair
attempts, mandatory validation before insight/action, full run
reproducibility — need a control flow that can be reasoned about and tested
independently of any LLM's behavior.

## Decision

The orchestrator is an explicit, typed state machine implemented in
application code (`RECEIVED → RETRIEVING → GENERATING_SQL →
STATIC_VALIDATION → EXECUTING → RESULT_VALIDATION → GENERATING_INSIGHT →
READY`, with a bounded `REPAIR_SQL` loop capped at two attempts, and
`NEEDS_CLARIFICATION` / `FAILED` / `CANCELLED` reachable from any state). See
[docs/03_ARCHITECTURE.md](../03_ARCHITECTURE.md#orchestration-state).

Each "agent" is a bounded, typed component: it receives a defined input
contract, returns a defined output contract, and never calls another agent
or an external tool directly. Only the orchestrator decides which component
runs next, based on the current state and the previous component's typed
output.

## Consequences

- Every transition is testable in isolation without any LLM call.
- The repair loop cannot exceed `MAX_SQL_REPAIRS` (default 2) by
  construction, not by convention.
- Adding a new agent capability means adding a new state and transition, not
  granting broader autonomy to an existing agent.
- Some flexibility that a free-form agent conversation would offer (e.g. an
  agent improvising a new tool call) is deliberately unavailable — this is
  the intended trade-off for auditability and safety.
