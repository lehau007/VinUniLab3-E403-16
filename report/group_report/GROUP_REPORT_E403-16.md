# Group Report: Lab 3 - Production-Grade Agentic System

- **Team Name**: E403-16
- **Team Members**: Lê Văn Hậu (2A202600110), Nguyễn Bá Hào (2A202600133), Trương Quang Lộc(2A202600333),  Ngô Anh Tú (2A202600128)
- **Deployment Date**: 2026-04-06

---

## 1. Executive Summary

Our goal was to build a production-style shopping advisor that can handle vague product descriptions and complete multi-step reasoning with tools (stock, discount, shipping, and total estimation).

- **Success Rate**: 100% on 4 sampled interactive Agent v2 sessions from `logs/2026-04-06.log` (all sessions reached `AGENT_END` with `status=final_answer`).
- **Key Outcome**: Compared to direct chat behavior, the ReAct pipeline improved reliability in product-detail requests by forcing tool-grounded steps (`list_all_products` for discovery, then `get_product_by_id` for factual details).

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation

Our implementation follows this control flow:

1. User query enters Agent.
2. Agent runs `Thought -> Action` generation.
3. Action parser validates action format (JSON/function-like call).
4. Tool executes and returns Observation.
5. Observation is appended to context for next step.
6. Agent stops on `Final Answer` or `max_steps`.

Agent versions:
- **v1**: Robust parsing + multi-tool execution + telemetry per LLM call.
- **v2**: Adds guardrails (forced catalog grounding, parse error handling, unknown tool handling, repeated-loop detection).

### 2.2 Tool Definitions (Inventory)

| Tool Name | Input Format | Use Case |
| :--- | :--- | :--- |
| `list_all_products` | none | Discovery-only lookup, returns product `id`, `name`, `price`, `stock` for description-to-id mapping. |
| `search_products` | `keyword: string` | Search products by keyword (fuzzy match), returns matching items. |
| `compare_products` | `product_id_1, product_id_2: string` | Compare two products side-by-side by their IDs. |
| `check_stock` | `item_name: string` | Check stock by exact name, returns product id if found. |
| `check_stock_by_id` | `product_id: string` | Check stock by canonical id (preferred after discovery). |
| `get_product_by_id` | `product_id: string` | Fetch full product details (price, stock, weight). |
| `list_coupons` | none | List all available coupon codes and their discount percentages. |
| `get_discount` | `coupon_code: string` | Return discount percentage from coupon table. |
| `calc_shipping` | `weight: float, destination: string` | Estimate shipping fee (includes dynamic surcharge for certain cities). |
| `estimate_total` | `product_id, quantity, coupon_code?, destination?` | End-to-end total estimation (subtotal, discount, shipping, final total). |

### 2.3 LLM Providers Used

- **Primary**: Gemini Flash-lite family (`gemini-3.1-flash-lite-preview` and `gemini-2.5-flash-lite` during development).
- **Secondary (Backup)**: OpenAI provider and Local GGUF provider are implemented and switchable via the shared provider interface.

---

## 3. Telemetry & Performance Dashboard

Metrics below are computed from sampled `LLM_METRIC` events in `logs/2026-04-06.log` (8 requests across 4 sessions):

- **Average Latency (P50)**: ~1745 ms
- **Max Latency (P99 proxy)**: 3765 ms
- **Average Tokens per Task**: ~898 total tokens per LLM request
- **Total Cost of Sampled Suite**: ~0.0718 (mock cost unit from telemetry formula)

Observed reliability indicators:
- Parse errors occurred in some conversational turns but were recovered by subsequent loops.
- Tool-grounded product detail query (`bạn cho tôi thông tin iphone 15`) completed with explicit id-based lookup before final answer.

---

## 4. Root Cause Analysis (RCA) - Failure Traces

### Case Study: Parse error on conversational query

- **Input**: "hello, bạn là AI bán hàng à"
- **Observation**: At one step, model produced natural language without `Action:` line, triggering `AGENT_PARSE_ERROR` (`No Action line found`).
- **Root Cause**: Prompt allowed conversational style that occasionally skipped strict ReAct action format.
- **Fix Applied**:
  - Strengthened prompt rules to enforce strict tool discipline.
  - Added v2 guardrails to recover from parser errors and continue safely.
  - Added rule that `list_all_products` is discovery-only and detailed facts must come from id-based tools to reduce hallucinated details.

---

## 5. Ablation Studies & Experiments

### Experiment 1: Prompt v1 vs Prompt v2

- **Diff**:
  - v2 introduced stricter grounding language and anti-hallucination constraints.
  - Added explicit rule: do not output missing numeric facts unless observed from tool output.
  - Added explicit workflow: discover product id first, then fetch details by id.
- **Result**:
  - Reduced incorrect direct detail responses after catalog listing.
  - Improved factual consistency for product-specific requests.
  - Better recovery from parser-format mistakes in mixed conversational inputs.

### Experiment 2: Chatbot vs Agent

| Case | Chatbot Result | Agent Result | Winner |
| :--- | :--- | :--- | :--- |
| Greeting / simple identity question | Usually correct | Correct (with occasional extra loop) | Draw |
| Product info by vague description | Prone to guessed details | Resolves to product id then fetches details | **Agent** |
| Multi-step pricing (discount + shipping) | High risk of arithmetic/grounding errors | Uses tools for decomposition and factual outputs | **Agent** |

---

## 6. Production Readiness Review

- **Security**:
  - Input validation is present at API boundaries (FastAPI + Pydantic).
  - Recommended next step: sanitize/validate tool arguments more strictly by schema per tool.
- **Guardrails**:
  - `max_steps` cap prevents runaway loops.
  - v2 includes parser error handling, unknown-tool control, and repeated-action loop detection.
- **Scaling**:
  - Repository abstraction already supports JSON and SQLite backends.
  - Recommended next step: migrate orchestration to graph/state-machine style for more complex branching and asynchronous tool execution.

---

## Appendix: Submission Notes

- This report uses real project telemetry logs and current implementation state.
- This report uses real project telemetry logs and current implementation state.
