from typing import Optional

from core.llm_provider import LLMProvider
from telemetry.metrics import tracker


def run_chatbot(user_input: str, llm: LLMProvider, system_prompt: Optional[str] = None) -> str:
    """Baseline chatbot: direct single-shot response without tool usage."""
    result = llm.generate(user_input, system_prompt=system_prompt)
    tracker.track_request(
        provider=result.get("provider", "unknown"),
        model=llm.model_name,
        usage=result.get("usage", {}),
        latency_ms=result.get("latency_ms", 0),
    )
    result_str = result.get("content", "")
    return result_str
