# Using Graphify with Outpost

Graphify is used here as a development-time architecture explorer. It is not an
Outpost runtime dependency and its raw visual output is not part of the
recruiter-facing product walkthrough.

The workflow is pinned to `graphifyy==0.9.32` because Graphify is pre-1.0 and
changing quickly.

## Run through GitHub Actions

The `Graphify architecture exploration` workflow runs automatically on a pull
request that changes the workflow, Graphify scope, application code, or the
three product-defining documents.

It performs code-only AST extraction. No API key or model call is used. The run
uploads a temporary `outpost-graphify-code-map` artifact containing:

- `graph.json` — the queryable knowledge graph.
- `GRAPH_REPORT.md` — graph statistics, hubs, communities, and suggested questions.
- `graph.html` — the interactive force-directed graph.
- `outpost-callflow.html` — an experimental call-flow export.

Workflow artifacts are retained for 14 days. Re-run the workflow to regenerate
them after expiry.

## Run locally

Requirements: Python 3.10+ and `uv`.

```bash
uv tool install graphifyy==0.9.32

graphify extract . --code-only --timing
graphify cluster-only . --no-label --timing
graphify export html --graph graphify-out/graph.json
graphify export callflow-html --output graphify-out/outpost-callflow.html
```

Open `graphify-out/graph.html` in a browser.

To refresh after application changes:

```bash
graphify update .
graphify cluster-only . --no-label
graphify export html --graph graphify-out/graph.json
```

## Useful queries

```bash
graphify explain "Brief"
graphify explain "Candidate"
graphify query "Trace campaign creation from intake through discovery and scoring"
graphify query "How do live providers fall back to seeded data?"
graphify query "What code enforces workspace isolation?"
graphify query "Trace draft generation through routing, evaluation and approval"
graphify path "create_draft" "evaluate_draft"
```

## Baseline result — 2 August 2026

The first code-only run completed in 1.7 seconds with no model tokens:

- 20 code files
- 436 nodes
- 1,081 edges
- 17 detected communities
- 92% extracted edges
- 8% inferred edges
- no import cycles

The central abstractions were `Brief`, `Candidate`, `get_connection()`,
`SourceResult`, and `SourceStatus`. This supports the intended architecture:
a shared campaign/evidence contract connects replaceable discovery sources to
one scoring, drafting, approval, and pipeline engine.

Graphify accurately recovered these important paths:

```text
create_campaign()
  -> parse_brief()
  -> discover()
  -> score_batch()
  -> assert_grounded()
  -> add_scored_targets()

create_draft()
  -> route_and_draft()
      -> draft_outreach()
      -> evaluate_draft()
  -> create_draft_with_routing()

draft_action() -> approve_draft()
update_target_stage() -> set_target_stage()
```

It also made two structural facts obvious:

1. `app/db.py` is the largest architectural concentration: 95 graph nodes, with
   33 extracted calls from `app/main.py`. This is acceptable for the current
   local prototype but is the first module likely to become difficult to change.
2. Shared Pydantic models are genuine cross-module bridges, particularly
   `Brief` and `Candidate`. Provider-specific data remains behind the shared
   source contract as intended.

## Interpretation rules

Treat `EXTRACTED` edges as source-backed relationships. Treat `INFERRED`
edges as prompts for inspection, not facts.

In this baseline, all inferred edges had confidence 0.5 and several were clearly
over-broad—for example, Graphify claimed unrelated database exception classes
"use" `Candidate` and `TargetScore`. Those relationships should not be used
to justify an architectural decision.

The interactive `graph.html` is useful for engineering exploration. The
current automatic call-flow export is not suitable for the public README: it
produced generic or incorrect section names such as "CLI & Skill Installers"
and "Serving API" and fragmented `db.py` into several indistinct sections.
Use Graphify to discover and verify structure, then create a smaller curated
product-flow diagram for recruiter communication.
