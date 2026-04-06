import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional

from src.agent.agent_v1 import ReActAgentV1
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker
from src.tools.validator import ToolValidator


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
            trace_block = f"\nKnown failures from previous runs (avoid repeating these):\n{formatted}\n"

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
        self.last_loop_trace = []
        self.last_run_metrics = {
            "total_latency_ms": 0,
            "total_tokens": 0,
            "loop_count": 0,
            "parse_errors": 0,
            "hallucinated_tools": 0,
            "status": "success",
        }
        action_counter: Dict[str, int] = defaultdict(int)
        parse_error_count = 0
        hallucinated_tool_count = 0

        for step in range(1, self.max_steps + 1):
            llm_input = self._build_input(user_input, scratchpad)
            result = self.llm.generate(llm_input, system_prompt=self.get_system_prompt())

            latency = result.get("latency_ms", 0)
            tokens = result.get("usage", {}).get("total_tokens", 0)

            self.last_run_metrics["total_latency_ms"] += latency
            self.last_run_metrics["total_tokens"] += tokens
            self.last_run_metrics["loop_count"] = step

            tracker.track_request(
                provider=result.get("provider", "unknown"),
                model=self.llm.model_name,
                usage=result.get("usage", {}),
                latency_ms=latency,
            )
            content = (result.get("content") or "").strip()

            # Ngăn chặn LLM hallucination
            obs_match = re.search(r"Observation:", content, flags=re.IGNORECASE)
            if obs_match:
                content = content[: obs_match.start()].strip()

            logger.log_event("AGENT_STEP", {"version": "v2", "step": step, "llm_output": content})
            thought, action_block = self._extract_thought_action(content)
            step_trace: Dict[str, Any] = {
                "step": step,
                "llm_output": content,
                "thought": thought,
                "action": action_block,
            }

            final_answer = self._extract_final_answer(content)
            if final_answer:
                step_trace["status"] = "final_answer"
                step_trace["final_answer"] = final_answer
                self.last_loop_trace.append(step_trace)
                logger.log_event("AGENT_END", {"version": "v2", "steps": step, "status": "final_answer"})
                return final_answer

            tool_name, args_payload, parse_error = self._parse_action(content)
            if parse_error:
                parse_error_count += 1
                self.last_run_metrics["parse_errors"] = parse_error_count
                observation = (
                    "PARSER_ERROR: Could not parse action. Use format exactly: Action: tool_name(key='value')."
                )
                step_trace["status"] = "parse_error"
                step_trace["parse_error"] = parse_error
                step_trace["observation"] = observation
                self.last_loop_trace.append(step_trace)
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
                    self.last_run_metrics["status"] = "stopped_parse_error"
                    return (
                        "I am stopping to avoid repeated parser errors. Please rephrase your request more specifically."
                    )
                continue

            signature = self._action_signature(tool_name, args_payload)
            action_counter[signature] += 1
            if action_counter[signature] >= 3:
                logger.log_event(
                    "AGENT_LOOP_GUARD",
                    {"version": "v2", "step": step, "signature": signature, "count": action_counter[signature]},
                )
                self.last_run_metrics["status"] = "stopped_loop_guard"
                return "I detected a repeated reasoning loop. Please confirm the exact product you want."

            if tool_name not in self.tool_map:
                hallucinated_tool_count += 1
                self.last_run_metrics["hallucinated_tools"] = hallucinated_tool_count
                observation = json.dumps({"error": "hallucinated_tool", "tool": tool_name}, ensure_ascii=False)

                step_trace["status"] = "hallucinated_tool"
                step_trace["tool"] = tool_name
                step_trace["observation"] = observation
                self.last_loop_trace.append(step_trace)

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
                    self.last_run_metrics["status"] = "stopped_hallucinated_tool"
                    return "I cannot continue because requested tools are unavailable. Please clarify your request."
                continue

            # Validate tool arguments before execution
            is_valid, error_msg, validated_args = ToolValidator.validate(tool_name, args_payload)
            if not is_valid:
                observation = json.dumps({"error": "invalid_arguments", "message": error_msg}, ensure_ascii=False)
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
            observation = self._execute_tool(tool_name, args_payload)
            step_trace["status"] = "tool_call"
            step_trace["tool"] = tool_name
            step_trace["args"] = args_payload
            step_trace["observation"] = observation
            self.last_loop_trace.append(step_trace)

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
        self.last_run_metrics["status"] = "max_steps"
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
