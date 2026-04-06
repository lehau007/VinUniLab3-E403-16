import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker
from src.tools.validator import ToolValidator

from src.agent.agent_v1 import ReActAgentV1


class ReActAgentV2(ReActAgentV1):
    """ReAct agent v2 with failure-driven prompt and execution guardrails."""

    def __init__(
        self,
        llm: LLMProvider,
        tools: List[Dict[str, Any]],
        max_steps: int = 6,
        failure_traces: Optional[List[str]] = None,
    ):
        super().__init__(llm=llm, tools=tools, max_steps=max_steps)
        self.failure_traces = failure_traces or []

    def get_system_prompt(self) -> str:
        base = super().get_system_prompt()
        trace_block = ""
        if self.failure_traces:
            formatted = "\n".join([f"- {t}" for t in self.failure_traces[:5]])
            trace_block = (
                "\nKnown failures from previous runs (avoid repeating these):\n"
                f"{formatted}\n"
            )

        guardrails = (
            "\nAdditional guardrails (v2):\n"
            "1) If Action parsing failed previously, switch to strict function call syntax: "
            "Action: tool_name(key='value').\n"
            "2) Never call unknown tools; use only tool names listed in system prompt.\n"
            "3) If the same tool call repeats with same arguments, change plan or finish safely.\n"
            "4) If user describes product vaguely, call list_all_products then map description to product id.\n"
            "5) Do not claim any product detail unless it appears in a tool Observation.\n"
            "6) If observation does not contain required data, call the proper id-based tool before Final Answer.\n"
        )
        return base + trace_block + guardrails

    def run(self, user_input: str) -> str:
        logger.log_event("AGENT_START", {"version": "v2", "input": user_input, "model": self.llm.model_name})

        scratchpad = ""
        action_counter: Dict[str, int] = defaultdict(int)
        parse_error_count = 0
        hallucinated_tool_count = 0
        catalog_loaded = False

        for step in range(1, self.max_steps + 1):
            # Guardrail: force catalog grounding for product-related requests when available.
            if not catalog_loaded and "list_all_products" in self.tool_map:
                forced_observation = self._execute_tool("list_all_products", {})
                catalog_loaded = True
                self.last_loop_trace.append(
                    {
                        "step": step,
                        "status": "guardrail_forced_tool",
                        "tool": "list_all_products",
                        "args": {},
                        "observation": forced_observation,
                    }
                )
                scratchpad += (
                    "\nLLM Output:\n"
                    "Thought: I should ground on real inventory first.\n"
                    "Action: list_all_products()\n"
                    f"Observation: {forced_observation}\n"
                )
                logger.log_event(
                    "AGENT_GUARDRAIL",
                    {"version": "v2", "step": step, "type": "forced_catalog_load"},
                )
                continue

            llm_input = self._build_input(user_input, scratchpad)
            result = self.llm.generate(llm_input, system_prompt=self.get_system_prompt())
            tracker.track_request(
                provider=result.get("provider", "unknown"),
                model=self.llm.model_name,
                usage=result.get("usage", {}),
                latency_ms=result.get("latency_ms", 0),
            )
            content = (result.get("content") or "").strip()
            
            # Ngăn chặn LLM hallucination
            obs_match = re.search(r'Observation:', content, flags=re.IGNORECASE)
            if obs_match:
                content = content[:obs_match.start()].strip()
                
            logger.log_event("AGENT_STEP", {"version": "v2", "step": step, "llm_output": content})

            final_answer = self._extract_final_answer(content)
            if final_answer:
                logger.log_event("AGENT_END", {"version": "v2", "steps": step, "status": "final_answer"})
                return final_answer

            tool_name, args_payload, parse_error = self._parse_action(content)
            if parse_error:
                parse_error_count += 1
                observation = (
                    "PARSER_ERROR: Could not parse action. "
                    "Use format exactly: Action: tool_name(key='value')."
                )
                logger.log_event(
                    "AGENT_PARSE_ERROR",
                    {
                        "version": "v2",
                        "step": step,
                        "error": parse_error,
                        "parse_error_count": parse_error_count,
                    },
                )
                scratchpad += f"\nLLM Output:\n{content}\nObservation: {observation}\n"
                if parse_error_count >= 2:
                    return "I am stopping to avoid repeated parser errors. Please rephrase your request more specifically."
                continue

            signature = self._action_signature(tool_name, args_payload)
            action_counter[signature] += 1
            if action_counter[signature] >= 3:
                logger.log_event(
                    "AGENT_LOOP_GUARD",
                    {"version": "v2", "step": step, "signature": signature, "count": action_counter[signature]},
                )
                return "I detected a repeated reasoning loop. Please confirm the exact product you want."

            if tool_name not in self.tool_map:
                hallucinated_tool_count += 1
                observation = json.dumps({"error": "hallucinated_tool", "tool": tool_name}, ensure_ascii=False)
                logger.log_event(
                    "AGENT_HALLUCINATED_TOOL",
                    {
                        "version": "v2",
                        "step": step,
                        "tool": tool_name,
                        "hallucinated_tool_count": hallucinated_tool_count,
                    },
                )
                scratchpad += f"\nLLM Output:\n{content}\nObservation: {observation}\n"
                if hallucinated_tool_count >= 2:
                    return "I cannot continue because requested tools are unavailable. Please clarify your request."
                continue

            # Validate tool arguments before execution
            is_valid, error_msg, validated_args = ToolValidator.validate(tool_name, args_payload)
            if not is_valid:
                observation = json.dumps(
                    {"error": "invalid_arguments", "message": error_msg},
                    ensure_ascii=False
                )
                logger.log_event(
                    "AGENT_VALIDATION_ERROR",
                    {
                        "version": "v2",
                        "step": step,
                        "tool": tool_name,
                        "error": error_msg,
                    },
                )
                scratchpad += f"\nLLM Output:\n{content}\nObservation: {observation}\n"
                continue

            observation = self._execute_tool(tool_name, validated_args)
            logger.log_event(
                "AGENT_TOOL_CALL",
                {
                    "version": "v2",
                    "step": step,
                    "tool": tool_name,
                    "args": args_payload,
                    "observation": observation,
                },
            )
            scratchpad += f"\nLLM Output:\n{content}\nObservation: {observation}\n"

        logger.log_event("AGENT_END", {"version": "v2", "steps": self.max_steps, "status": "max_steps"})
        return "I could not complete this request in the allowed number of steps."

    def _action_signature(self, tool_name: Optional[str], args_payload: Any) -> str:
        if isinstance(args_payload, dict):
            try:
                normalized_args = json.dumps(args_payload, sort_keys=True, ensure_ascii=False)
            except TypeError:
                normalized_args = str(args_payload)
        else:
            normalized_args = str(args_payload)
        return f"{tool_name}|{normalized_args}"
