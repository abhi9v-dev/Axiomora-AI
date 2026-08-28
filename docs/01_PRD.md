# Product Requirements Document (PRD)

## Product vision

Enable analysts and business users to ask governed questions of warehouse
data and receive a verified answer that can update an artifact used by the
business.

## Problem

Business users wait for analysts to translate questions into SQL, validate
outputs and update reports. Generic chat-to-SQL systems hallucinate schemas,
generate unsafe queries and provide narratives without traceable evidence.

## Primary personas

| Persona          | Need                                             | Permission level                |
| ----------------- | ------------------------------------------------- | -------------------------------- |
| Operations user  | Ask task throughput, hold-time and stuck-project questions | Approved semantic views only |
| BI analyst       | Review SQL, validation and lineage                 | Query and approve actions        |
| Data steward     | Maintain glossary and constraints                  | Govern schema knowledge          |
| Administrator    | Configure connections and policies                 | System administration            |

## Core user story

As an operations user, I ask "Why did median task hold time spike for the
Buyer department in Q2?" The system retrieves the correct definitions,
clarifies ambiguity if necessary, executes safe SQL, validates the result,
explains the drivers with cited numbers, and exports or publishes an
approved artifact.

## Goals

- Ground SQL generation in an indexed business glossary and schema catalog.
- Block unsafe, invalid or implausible queries before results reach users.
- Make every answer reproducible with question, schema context, SQL, result
  fingerprint and validation record.
- Complete common analytical questions in under 20 seconds for the demo
  dataset.
- Export a formatted `.xlsx` report in the MVP.
- Support Power BI publishing through an optional, approval-gated adapter.

## Non-goals for MVP

- Arbitrary write access to source warehouses.
- Fully autonomous production report changes.
- Support for every SQL dialect.
- Training a custom foundation model.
- Replacing enterprise semantic models or data governance platforms.

## User journey

1. User signs in and selects an approved data source.
2. User asks a question and optionally adds filters.
3. System shows progress across retrieval, SQL, validation and insight.
4. If ambiguity is material, the system asks one concise clarification.
5. User receives KPIs, a chart/table, narrative, SQL and validation status.
6. User exports to Excel or requests a Power BI action.
7. High-impact actions require explicit approval and are audit logged.

## Success metrics

| Metric                                     | MVP target |
| ------------------------------------------- | ---------- |
| Executable SQL on benchmark set             | 90%        |
| Semantically correct answers                | 80%        |
| Unsafe SQL reaching execution               | 0          |
| Numerical claims traceable to result cells  | 100%       |
| P95 response time on sample warehouse       | 20 s       |
| Export success rate                         | 95%        |

## MVP acceptance

The product is accepted when 20 benchmark questions can be run from the UI,
protected by read-only SQL controls, with stored traces; at least 16 return
correct results and grounded narratives, and successful runs can produce a
formatted Excel workbook.
