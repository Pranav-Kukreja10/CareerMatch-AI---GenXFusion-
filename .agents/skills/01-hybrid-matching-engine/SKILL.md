---
name: hybrid-matching-engine
description: Use when building Stage 1 PDF resume parsing, 4-Tier ontological skill extraction, or the 3-Signal Hybrid Vector Search (Jaccard + BGE 384d + Postgres FTS).
---

<CRITICAL_CONSTRAINTS>
1. ZERO DISK LEAKAGE: Process all uploaded Resume PDFs strictly in-memory using `io.BytesIO` and `pypdf`/`fitz`. Never write user PDFs to disk.
2. 4-TIER ONTOLOGY: Every extracted skill from Resume or JD MUST be classified into: `CORE_TECH`, `FRAMEWORK`, `TOOL`, or `SOFT_SKILL`.
3. EXACT FUSION FORMULA: Never approximate similarity. Compute exact hybrid score:
   `FusionScore = (0.40 * jaccard_score) + (0.45 * bge_384d_cosine) + (0.15 * postgres_fts_rank)`
4. CLASSIFICATION THRESHOLDS:
   - `Sim >= 0.82`: DIRECT_MATCH
   - `0.55 <= Sim < 0.82`: TRANSFERABLE_ADJACENT (e.g., Django DRF -> FastAPI)
   - `Sim < 0.55`: TRUE_MISSING_GAP
</CRITICAL_CONSTRAINTS>

### Implementation Contract
- Embedding model: `BAAI/bge-small-en-v1.5` (384 dimensions) via `pgvector` cosine distance (`<=>`).
- Return structured Pydantic v2 models containing per-tier breakdown and transferable skill explanations.
