---
name: dynamic-feature-injector
description: Use whenever the user asks to add a new feature, mid-hackathon pivot, mentor suggestion, bonus module, or extension to CareerMatch AI.
---

<ADDITIVE_ARCHITECTURE_LAWS>
1. OPEN-CLOSED PRINCIPLE (NO CORE MUTATION):
   - NEVER modify the core mathematical formulas in Stage 1 (`FusionScore`) or Stage 3 (`CS` Attestation Calibration).
   - NEVER break existing Pydantic response fields used by teammates. If adding data to an existing schema, all new fields MUST be `Optional[T] = None` with safe defaults so existing frontend components never crash.
2. ISOLATED MODULE SLICES:
   - Backend: Create a new router module under `backend/routers/ext_<feature_name>.py` and register it via `app.include_router(...)`. Do not bloat existing route files.
   - Frontend: Create a self-contained folder `frontend/src/features/<feature-name>/` with its own hook, UI card, and mock fallback data.
3. INSTANT DEMO SEEDING:
   - Every new feature added mid-hackathon MUST include pre-computed fallback/seed state so the "Judge Demo Mode" works immediately even if an external API fails.
4. AUTO-DOCUMENT FOR TEAMMATES:
   - Upon completing the feature, append its endpoint signature, Pydantic schema, and UI entry point to `FEATURES.md` and `AGENTS.md` so other teammates' agents know it exists.
</ADDITIVE_ARCHITECTURE_LAWS>

### 4-Step Feature Injection Workflow
1. **Contract First:** Define the new `Optional` Pydantic schema and TypeScript interface first.
2. **Stitch UI / Component:** If the feature needs UI, call Stitch MCP (`generate_screen_from_text` + `apply_design_system`) or build an isolated card matching `DESIGN.md`.
3. **Wire & Smoke Test:** Connect the isolated FastAPI router, run `pytest -q` and `tsc --noEmit` to prove 0 regressions on Stages 1-4.
4. **Update Registry:** Log the completed feature in `FEATURES.md` and commit.
