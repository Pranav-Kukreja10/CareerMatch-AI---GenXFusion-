# FEATURES.md — Feature Registry

**Core rule for all agents:** every new feature is an *additive plugin* (new route file + isolated frontend component) that **consumes** the immutable Stage 1–4 pipeline state. Never mutate existing working files.

## How to propose a feature (5-line spec)
Copy the template below, fill it in, and ask your agent:
> "Use `dynamic-feature-injector` to add <feature name>."

```
### <Feature name>
- Why: <mentor / judge / user need>
- Inputs: <which Stage 1-4 fields it reads>
- Endpoint: <METHOD /api/v1/ext/...>
- UI entry point: <src/features/<name>/...>
- Seed data: <demo candidates / fallback>
```

## Proposed
<!-- drop specs here -->

## Completed
<!-- agents append: endpoint signature, Pydantic schema, UI entry point -->
