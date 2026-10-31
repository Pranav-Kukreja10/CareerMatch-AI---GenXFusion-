---
name: github-vibe-radar
description: Use when building Stage 2 GitHub API proof-of-work verification, Production Engineering Readiness scores, or Anti-Vibe-Coding authenticity detection.
---

<CRITICAL_CONSTRAINTS>
1. ASYNC GRAPHQL/REST: Use `httpx.AsyncClient` with GitHub token rotation and Redis/in-memory TTL caching so judge demos never hit rate limits.
2. PRODUCTION READINESS RUBRIC (0-100):
   - Presence of multi-stage `Dockerfile` or `docker-compose.yml` (+25)
   - Real test files (`test_*.py`, `*.spec.ts`) with assertions (+30)
   - `.github/workflows/*.yml` CI pipelines (+25)
   - Conventional commit message adherence (+20)
3. ANTI-VIBE-CODING AUTHENTICITY INDEX:
   - Flag repositories where >80% of lines were added in <=2 commits ("Single-Commit AI Dump Penalty").
   - Compute Commit Velocity Variance and AST/dependency imports vs. README claims.
</CRITICAL_CONSTRAINTS>
