---
name: roi-dag-bridge-generator
description: Use when building Stage 4 ROI-Ranked Learning DAGs, hiring boost calculations, or Gemini 3.5 Flash-Lite Weekend Bridge Capstone generators.
---

<CRITICAL_CONSTRAINTS>
1. VALID DAG TOPOLOGY: Output nodes and directed edges (`source -> target`) guaranteed to be acyclic (verify via topological sort before returning to frontend).
2. QUANTIFIED HIRING ROI: Every missing skill node must include `roi_boost_pct` (e.g., `+16% match boost`) and `active_roles_unlocked` count.
3. WEEKEND BRIDGE PROJECT SPEC: Prompt Gemini 3.5 Flash-Lite with structured JSON schema output to combine the student's VERIFIED skills with their MISSING JD skills into a 48-hour buildable repo specification (including exact folder structure, test cases to pass, and verification rubric).
</CRITICAL_CONSTRAINTS>
