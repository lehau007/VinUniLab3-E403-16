# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Name**: Trương Quang Lộc
- **ID**: 2A202600333
- **Date**: 2026-04-06

---

## I. Technical Contribution (15 Points)

**What I did:**
1. **Flowchart Design** - Created ReAct loop flowchart with error handling, fallback paths, all tool execution states ([View: flowchart.png](../../flowchart.png))

2. **Group Report** - Wrote Executive Summary, System Architecture, RCA (Root Cause Analysis), Ablation Studies, Production Readiness Review
3. **Input Validation Layer** (`src/tools/validator.py`)
   - Pydantic models for 7 tools: ProductLookup, Shipping, Pricing, Coupon
   - Type checking + normalization + range validation
   - Helpful error messages for LLM feedback
4. **Syntax Error Recovery** (`src/agent/agent_v1.py`) - Added `_attempt_syntax_fix()` method
   - Fixes missing closing parentheses automatically
5. **Validation Integration** (`src/agent/agent_v2.py`) - Pre-execution validation hook
   - Validates args before tool call
   - Logs validation errors
   - Graceful error recovery

---


## II. Debugging Case Study: Action Parser (10 Points)

**Problem**: Agent fails on malformed action syntax (missing closing paren, bad quotes)
- Example: `Action: check_stock(product_id='p001"` ← missing closing bracket
- Parser regex is strict: `r"([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*$"`
- Result: PARSER_ERROR, agent wastes loop, sometimes repeats same error

**Root Cause**: LLM occasionally outputs incomplete syntax. Parser gives up instead of recovery attempt.

**Solution Implemented**: `_attempt_syntax_fix()` method
- Detects unmatched parentheses
- Auto-adds missing closing parens

**Example**:
```python
# Before: fails
Thought: Tôi cần kiểm tra thông tin sản phẩm và tính thuế.
Action: calc_tax(amount=1000, region="VN"
# After syntax fix: works
Thought: Tôi cần kiểm tra thông tin sản phẩm và tính thuế.
Action: calc_tax(amount=1000, region="VN")
```

---


## III. Personal Insights: Chatbot vs ReAct (10 Points)

**1. Chatbot Weakness**: Fast but unreliable for factual queries
- Q: "Tôi muốn mua 2 chiếc iPhone 15 với code WINNER, tổng cộng bao nhiêu tiền?" 
- Chatbot: "~50 triệu VND" (invented, not verified)
- Agent: Calls tools → list_all_products() → get_product_by_id() → get_discount() → calc_shipping() → real verified answer

**2. Agent Weakness**: Slow on simple queries
- Q: "Bạn bán iPhone không?"
- Chatbot: "Có" (1 LLM call)
- Agent: list_all_products() → parse → answer (5+ steps, 1.7-3.7s latency)
- Trade-off: Reliability vs Speed

**3. Key Insight**: Observation (tool result) is the critical signal
- v1: Appends observations but doesn't validate (agent can hallucinate)
- v2: Forces list_all_products() first to ground agent with real data
- Without real feedback → agent invents products. With it → reliable lookup system

**Lesson**: Complex/factual queries → ReAct. Simple greeting → Chatbot.

---


## IV. Future Improvements (5 Points)

**1. Scalability (7 → 100+ tools)**
- Problem: Can't list all tools in system prompt (context bloat)
- Solution: Embed tool descriptions → retrieve top-5 relevant per step dynamically
- Benefit: -40% token usage

**2. Safety Layer**
- Problem: Agent claims "Stock: 50" but tool said "unavailable"
- Solution: Supervisor LLM validates final answer against observations
- Benefit: Prevents hallucinated details

**3. Performance (Caching + Async)**
- Problem: Sequential tool calls slow (1.7-3.7s latency)
- Solution: Cache catalog, run tools in parallel (calc_shipping + get_discount together)
- Benefit: 40-50% latency reduction

**4. Multi-Agent System**
- Split into: Product Agent, Pricing Agent, Shipping Agent (each owns tools)
- Benefit: Better separation, easier scaling

---

## V. Key Learnings

1. **Observability = Debugging**: Logs more valuable than code. Every failure is traceable.
2. **Prompt engineering ≠ Agent engineering**: Real work is error recovery, validation, guardrails
3. **Use right tool**: Chatbot fast (simple). ReAct reliable (complex).
