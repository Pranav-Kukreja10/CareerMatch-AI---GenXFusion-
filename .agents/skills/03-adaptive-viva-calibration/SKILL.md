---
name: adaptive-viva-calibration
description: Use when implementing Stage 3 Repo-Grounded Adaptive Viva generation, MCQ Time-Decay Multiplier, or the Capped-Root Attestation Penalty Formula (CS).
---

<CRITICAL_CONSTRAINTS>
1. REPO-GROUNDED QUESTIONS ONLY: Viva questions MUST reference actual file paths, function names, or architectural choices fetched from the user's GitHub repo—never generic trivia.
2. TIME-DECAY MULTIPLIER (M_t): Track client-side response latency and `visibilitychange` (tab-switch) events. Penalize latency >25s per MCQ or tab blur events.
3. EXACT ATTESTATION FORMULA:
   Given Resume Claim Score `R_s` (0-100) and Audited Viva+GitHub Score `A_s` (0-100):
   `CS = A_s * (1.0 - 0.40 * math.sqrt(max(0.0, R_s - A_s) / 100.0))`
   Include unit tests proving:
   - Honest student (`R_s = 80, A_s = 85`) -> `CS = 85.0` (0 penalty)
   - Padded resume (`R_s = 95, A_s = 31`) -> `CS = 31 * (1 - 0.40 * 0.8) = 21.08`
</CRITICAL_CONSTRAINTS>
