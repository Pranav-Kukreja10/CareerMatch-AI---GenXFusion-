# CareerMatch AI (Skill Setu — Track #16) Agent Contract

## Architecture Overview
4-Stage Closed-Loop Evidence-Verified Competency Engine:
1. **Stage 1 (Ingestion & 3-Signal Hybrid Search):** In-memory PDF parsing -> 4 Ontological Tiers (`CORE_TECH`, `FRAMEWORK`, `TOOL`, `SOFT_SKILL`) -> `FusionScore = 0.40(Jaccard) + 0.45(BGE-384d-Cosine) + 0.15(Postgres-FTS)`. Bands: `>=0.82` Direct, `0.55-0.82` Transferable, `<0.55` Missing.
2. **Stage 2 (GitHub Anti-Vibe-Coding Radar):** Async GitHub inspection scoring Production Engineering Readiness (Docker, tests, CI/CD, Conventional Commits) and flagging single-commit AI dumps.
3. **Stage 3 (Repo-Grounded Adaptive Viva & Calibration):** 5-question code-grounded viva with Time-Decay Multiplier ($M_t$) and Capped-Root Attestation Penalty:
   `CS = A_s * [1 - 0.40 * sqrt(max(0, R_s - A_s) / 100)]`
4. **Stage 4 (ROI Learning DAG & Bridge Generator):** Gemini 3.5 Flash-Lite powered acyclic skill graph quantifying `% match boost` per node + personalized Weekend Bridge Project generator.

## Commands & Verification
- Backend Test & Lint: `pytest -q --tb=short && ruff check . --quiet`
- Frontend Typecheck: `npm run typecheck` (or `npx tsc --noEmit`)
- Working Style: Read target files before editing. Make minimal diffs. Never silence errors with `any` or bare `except:`.
