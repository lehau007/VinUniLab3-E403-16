import argparse
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from src.agent.agent_v1 import ReActAgentV1
from src.agent.agent_v2 import ReActAgentV2
from src.chatbot.chatbot import run_chatbot
from src.core.gemini_provider import GeminiProvider
from src.core.local_provider import LocalProvider
from src.core.llm_provider import LLMProvider
from src.core.openai_provider import OpenAIProvider
from src.prompts.system_prompts import (
    AGENT_V1_SYSTEM_PROMPT,
    AGENT_V2_SYSTEM_PROMPT,
    CHATBOT_SYSTEM_PROMPT,
)
from src.tools.registry import build_repository, create_tool_registry


def _format_prompt(template: str, tools: List[Dict[str, Any]]) -> str:
    """Inject tool descriptions into prompt template's {tool_descriptions} placeholder."""
    tool_descriptions = "\n".join(
        [f"- {t['name']}: {t['description']}" for t in tools]
    )
    return template.format(tool_descriptions=tool_descriptions)


def build_provider(provider_name: str, model_name: Optional[str] = None) -> LLMProvider:
    provider = provider_name.strip().lower()

    if provider == "openai":
        model = model_name or os.getenv("DEFAULT_MODEL", "gpt-4o")
        api_key = os.getenv("OPENAI_API_KEY")
        return OpenAIProvider(model_name=model, api_key=api_key)

    if provider in {"google", "gemini"}:
        model = model_name or os.getenv("DEFAULT_MODEL", "gemini-1.5-flash")
        api_key = os.getenv("GEMINI_API_KEY")
        return GeminiProvider(model_name=model, api_key=api_key)

    if provider == "local":
        model_path = os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")
        return LocalProvider(model_path=model_path)

    raise ValueError(f"Unsupported provider: {provider_name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive runner for chatbot / ReAct agent v1 / ReAct agent v2")
    parser.add_argument("--mode", choices=["chatbot", "v1", "v2"], default="v2")
    parser.add_argument("--provider", default=os.getenv("DEFAULT_PROVIDER", "gemini"))
    parser.add_argument("--model", default=os.getenv("DEFAULT_MODEL", ""))
    parser.add_argument("--backend", choices=["json", "sqlite"], default=os.getenv("DATA_BACKEND", "json"))
    parser.add_argument("--query", default="", help="Single-shot query. If empty, run interactive mode.")
    parser.add_argument("--max-steps", type=int, default=6)
    return parser.parse_args()


def run_once(mode: str, llm: LLMProvider, user_input: str, backend: str, max_steps: int) -> str:
    if mode == "chatbot":
        return run_chatbot(user_input=user_input, llm=llm, system_prompt=CHATBOT_SYSTEM_PROMPT)

    repo = build_repository(backend=backend)
    tools = create_tool_registry(repo=repo)

    if mode == "v1":
        formatted = _format_prompt(AGENT_V1_SYSTEM_PROMPT, tools)
        agent = ReActAgentV1(llm=llm, tools=tools, max_steps=max_steps)
        agent.get_system_prompt = lambda: formatted
        return agent.run(user_input)

    formatted = _format_prompt(AGENT_V2_SYSTEM_PROMPT, tools)
    agent = ReActAgentV2(llm=llm, tools=tools, max_steps=max_steps)
    agent.get_system_prompt = lambda: formatted
    return agent.run(user_input)


def run_once_with_trace(
    mode: str,
    llm: LLMProvider,
    user_input: str,
    backend: str,
    max_steps: int,
) -> Dict[str, Any]:
    if mode == "chatbot":
        answer = run_chatbot(user_input=user_input, llm=llm, system_prompt=CHATBOT_SYSTEM_PROMPT)
        return {
            "answer": answer,
            "reasoning": [
                {
                    "step": 1,
                    "status": "single_shot",
                    "llm_output": answer,
                }
            ],
        }

    repo = build_repository(backend=backend)
    tools = create_tool_registry(repo=repo)

    if mode == "v1":
        formatted = _format_prompt(AGENT_V1_SYSTEM_PROMPT, tools)
        agent = ReActAgentV1(llm=llm, tools=tools, max_steps=max_steps)
        agent.get_system_prompt = lambda: formatted
        answer = agent.run(user_input)
        reasoning: List[Dict[str, Any]] = getattr(agent, "last_loop_trace", [])
        return {"answer": answer, "reasoning": reasoning}

    formatted = _format_prompt(AGENT_V2_SYSTEM_PROMPT, tools)
    agent = ReActAgentV2(llm=llm, tools=tools, max_steps=max_steps)
    agent.get_system_prompt = lambda: formatted
    answer = agent.run(user_input)
    reasoning = getattr(agent, "last_loop_trace", [])
    return {"answer": answer, "reasoning": reasoning}


def main() -> None:
    load_dotenv()
    args = parse_args()

    llm = build_provider(provider_name=args.provider, model_name=args.model or None)

    if args.query:
        answer = run_once(
            mode=args.mode,
            llm=llm,
            user_input=args.query,
            backend=args.backend,
            max_steps=args.max_steps,
        )
        print(f"Assistant: {answer}")
        return

    print("Shop Assistant CLI")
    print(f"Mode={args.mode} | Provider={args.provider} | Backend={args.backend}")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            break

        try:
            answer = run_once(
                mode=args.mode,
                llm=llm,
                user_input=user_input,
                backend=args.backend,
                max_steps=args.max_steps,
            )
            print(f"Assistant: {answer}\n")
        except Exception as exc:
            print(f"Assistant Error: {exc}\n")


if __name__ == "__main__":
    main()
