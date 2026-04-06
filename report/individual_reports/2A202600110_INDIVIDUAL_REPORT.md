# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Lê Văn Hậu
- **Student ID**: 2A202600110
- **Date**: 2026-04-06

---

## I. Technical Contribution (15 Points)

My contribution scope was focused on data layer and core agent implementation only.

- **Modules Implemented**:
  - `src/repositories/json_repo.py`
  - `src/repositories/sqlite_repo.py`
  - `data/products.sample.json`
  - `data/coupons.sample.json`
  - `db/schema.sql`
  - `scripts/init_sqlite.py`
  - `src/agent/agent_v1.py`
  - `src/agent/agent_v2.py`
  - `src/tools/registry.py`

- **Code Highlights**:
  - Designed dual data backends (JSON and SQLite) under a shared repository abstraction.
  - Implemented initialization pipeline to build SQLite data from JSON seed files.
  - Implemented ReAct loop with robust action parsing (function-style + JSON action format).
  - Added v2 guardrails for parser errors, unknown tools, repeated loop actions, and product-id grounding.
  - Added telemetry integration for latency/tokens/cost estimates via project logging and metrics modules.

- **Documentation / Integration Notes**:
  - Tools are backend-agnostic through `build_repository(...)` and `create_tool_registry(...)`.
  - Agent logic consumes tools from registry and executes `Thought -> Action -> Observation` until `Final Answer` or `max_steps`.

([View: Commit history](./commit_src/2A202600110_LeVanHau_commits.png))
---

## II. Debugging Case Study (10 Points)

- **Problem Description**:
  - In early runs, the agent sometimes generated natural language without a valid `Action:` line.
  - Another issue was model behavior after product listing: it could output details not yet confirmed by id-based tools.

- **Log Source**:
  - `logs/2026-04-06.log`
  - Representative events: `AGENT_PARSE_ERROR`, `AGENT_STEP`, `AGENT_TOOL_CALL`, `AGENT_END`.

- **Diagnosis**:
  - Root cause 1: Prompt discipline was not strict enough, so conversational outputs occasionally skipped action format.
  - Root cause 2: Product grounding policy was too loose, allowing response generation immediately after listing candidates.

- **Solution**:
  - Strengthened prompt rules so `list_all_products` is discovery-only.
  - Enforced id-based follow-up (`get_product_by_id`, `check_stock_by_id`) for detailed facts.
  - Added v2 runtime guardrails to recover from parse errors and reduce loop instability.
  - Improved trace visibility to inspect loop-by-loop outputs for debugging.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning**:
   - ReAct is more reliable for shopping tasks because it separates planning from acting and uses tool observations as factual anchors.
   - A plain chatbot can sound fluent but is more likely to infer missing details.

2. **Reliability**:
   - ReAct can perform worse on very simple greetings because it may spend extra loop steps.
   - Chatbot can be faster on simple small-talk but weaker on multi-step, data-grounded tasks.

3. **Observation Feedback Effect**:
   - Observation is the key control signal. Once the agent observes canonical `product_id`, subsequent actions and final answer become more consistent.
   - Without proper observation grounding, hallucination risk increases.

---

## IV. Future Improvements (5 Points)

- **Scalability**:
  - Add async tool execution and caching for repeated catalog queries.
  - Move orchestration to a graph/state-machine style flow for larger toolsets.

- **Safety**:
  - Add strict schema validation per tool argument before execution.
  - Add response verifier to reject unsupported claims not backed by observations.

- **Performance**:
  - Add selective context compression to reduce token usage in long loop histories.
  - Add response templates for common intents (stock check, pricing summary) to reduce latency.
