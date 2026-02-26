# Product Backlog (DocuChat Multi-App Platform)

Status: Active  
Branch baseline: `feat/eval-profiles`

## Priority Legend
- P0 = Must-have / reliability / release blocker
- P1 = High-value next features
- P2 = Strategic enhancements
- P3 = Nice-to-have

---

## P0 — Stabilization & Release Readiness

### 1) Merge eval-profile branch safely into integration
- **Why**: Consolidate current progress into `OpenClawTesting`
- **Scope**:
  - Rebase/merge `feat/eval-profiles`
  - Resolve any contract mismatches
  - Run CI + compile + tests
- **Acceptance**:
  - No merge conflicts
  - CI passes
  - Main endpoints smoke-tested

### 2) Regression gate (live mode) manual workflow
- **Why**: Move from contract-only to quality gating before significant merges
- **Scope**:
  - Add manual GitHub workflow to run `scripts/run_regression.py --mode live`
  - Document required runtime assumptions (Ollama/model availability)
- **Acceptance**:
  - Workflow manually runnable
  - Returns pass/fail based on profile thresholds

### 3) Test hardening for eval endpoints
- **Why**: New eval features need coverage
- **Scope**:
  - Add tests for `/eval/profiles`, `/eval/bootstrap`, `/eval/datasets`, `/eval` with profile thresholds
- **Acceptance**:
  - Positive/negative path tests added
  - Dataset/profile-not-found behavior validated

### 4) API docs sync
- **Why**: Current feature set is larger than README endpoint summary
- **Scope**:
  - Update README + docs with all new endpoints
  - Include sample payloads/responses
- **Acceptance**:
  - Endpoint list is current and usable for frontend integration

---

## P1 — High-Value Product Features

### 5) One-click eval run endpoint
- **Why**: Reduce friction for per-chatbot QA
- **Scope**:
  - Add endpoint: run latest dataset for chosen profile
  - Optional query params: dataset fallback behavior
- **Acceptance**:
  - Single call executes profile + dataset eval
  - Returns threshold pass/fail summary

### 6) Baseline-vs-candidate retrieval A/B eval
- **Why**: Prove retrieval changes with measurable win rate
- **Scope**:
  - Add mode selectors in eval (`baseline` vs `hybrid_rerank_router`)
  - Return comparative metrics
- **Acceptance**:
  - Outputs win/loss and delta metrics (pass_rate, confidence)

### 7) Dataset versioning + pinning
- **Why**: Stable reproducible QA over time
- **Scope**:
  - Add optional dataset version tags
  - Keep historical snapshots
- **Acceptance**:
  - Eval can target exact dataset version

### 8) Prompt version registry per project
- **Why**: Track impact of prompt changes systematically
- **Scope**:
  - Save prompt revisions with metadata
  - Attach prompt version to eval run logs
- **Acceptance**:
  - Query/eval responses include prompt_version

---

## P1 — Security & Governance

### 9) Tool/network boundary policy module
- **Why**: Guard against unsafe agent/tool behavior
- **Scope**:
  - Add outbound allowlist abstraction (future tool-calling paths)
  - Add policy checks + deny logs
- **Acceptance**:
  - Policy decisions are auditable
  - Denied calls logged with request_id

### 10) High-impact action approval hooks
- **Why**: Human-in-the-loop for sensitive operations
- **Scope**:
  - Add approval status fields to future action endpoints
  - Enforce pending -> approved flow for sensitive tasks
- **Acceptance**:
  - Sensitive actions cannot execute without approval token/state

### 11) API key auth (deferred by user)
- **Why**: Needed before external deployment
- **Scope**:
  - Header-based API key middleware
  - Per-workspace token support
- **Acceptance**:
  - Unauthorized requests rejected
  - Tokens rotatable without downtime

---

## P2 — Retrieval & Knowledge Quality

### 12) Cross-encoder reranker (optional path)
- **Why**: Higher precision than heuristic rerank
- **Scope**:
  - Plug-in reranker stage after RRF candidates
  - CPU-first default, optional GPU path
- **Acceptance**:
  - Measurable citation/faithfulness uplift on eval datasets

### 13) Metadata-aware filtering
- **Why**: Better precision for team/app contexts
- **Scope**:
  - Add filters by tags/source/date/type during retrieval
- **Acceptance**:
  - Query can constrain retrieval scope

### 14) Relationship query routing (GraphRAG pilot)
- **Why**: Better multi-hop answers in entity-rich corpora
- **Scope**:
  - Route selected query types to graph retrieval experiment
- **Acceptance**:
  - Pilot benchmark improvement on relationship-heavy eval set

---

## P2 — Platform Experience

### 15) Project templates
- **Why**: Faster setup for Support/Billing/Compliance bots
- **Scope**:
  - Preset prompts + retrieval defaults + eval profile defaults
- **Acceptance**:
  - New project can be bootstrapped from template in one call

### 16) Bulk import + manifest
- **Why**: Easier onboarding of larger corpora
- **Scope**:
  - Manifest-driven batch ingest
  - Better ingest reporting
- **Acceptance**:
  - Import status + failures clearly reported

---

## P3 — Strategic Future Bets

### 17) MCP adapter layer
- **Why**: Ecosystem interoperability for tools/assistants
- **Scope**:
  - Expose core doc tools over MCP-compatible interface
- **Acceptance**:
  - At least 1 external MCP client integration demo

### 18) Multimodal ingestion
- **Why**: Handle scanned docs/tables/screenshots
- **Scope**:
  - OCR + structure extraction path
- **Acceptance**:
  - Improved QA on image-heavy datasets

### 19) Cost/latency optimizer
- **Why**: Better budget control at scale
- **Scope**:
  - Route model choice by query type + SLA budget
- **Acceptance**:
  - Lower average latency/cost without quality regression

---

## Current recommendation (next execution order)
1. P0.1 Merge/stabilize branch into `OpenClawTesting`
2. P0.3 Add tests for eval endpoints
3. P0.2 Add manual live regression workflow
4. P1.5 One-click eval run endpoint
5. P1.6 Baseline vs candidate A/B eval
