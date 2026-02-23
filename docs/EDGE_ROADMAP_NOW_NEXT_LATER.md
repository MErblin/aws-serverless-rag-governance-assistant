# Edge Roadmap — Now / Next / Later

Owner: Nilbre  
Platform: DocuChat multi-app (Ollama + LlamaIndex + FAISS + Next.js + FastAPI)

## NOW (this week)
1. Hybrid Retrieval 2.0 foundation
   - Add BM25 keyword retrieval alongside FAISS dense retrieval
   - Merge/re-rank top candidates
   - Add retrieval diagnostics in API response (internal/admin mode)

2. Eval pack + guardrails
   - Build 30–50 real prompt eval set
   - Add confidence threshold + abstain behavior checks
   - Track win/loss vs baseline

3. Next.js wiring to project-aware backend
   - Project selector in UI
   - Upload/query tied to `project_id`

Success target:
- +15–25% better top-3 retrieval hit quality on eval set
- Stable citations and fewer hallucinated answers

## NEXT (next 1–2 weeks)
1. Small-model routing (intent-based)
   - Intent classifier -> route to specialized Ollama model
   - Track latency/cost/quality per route

2. Admin observability panel
   - Query logs, latency, abstain rate, citation coverage

3. Thin-slice showcase modes
   - Support triage profile
   - Compliance profile

## LATER (after first traction)
1. Multimodal ingestion (OCR/layout/table-aware)
2. Async ingestion queue + background workers
3. Managed DB + auth hardening + deployment scaling
4. Kubernetes only when uptime/load justify cost

## Immediate execution order (starting now)
1) Implement BM25 + dense fusion in backend retrieval
2) Add diagnostics payload + confidence trace
3) Wire project-aware endpoints in Next.js
4) Run baseline vs upgraded eval and publish results
