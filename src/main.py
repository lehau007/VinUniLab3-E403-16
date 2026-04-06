import os

from dotenv import load_dotenv

from chatbot.chatbot import run_chatbot
from core.gemini_provider import GeminiProvider
from core.local_provider import LocalProvider
from core.openai_provider import OpenAIProvider
from telemetry.logger import logger

# 1. Load configuration from .env
load_dotenv()

if __name__ == "__main__":
    provider_type = os.getenv("DEFAULT_PROVIDER", "openai").lower()
    model_name = os.getenv("DEFAULT_MODEL", "gpt-4o")

    # 2. Setup the LLM Provider based on config
    llm = None
    if provider_type == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        llm = OpenAIProvider(model_name=model_name, api_key=api_key)
    elif provider_type in ["gemini", "google"]:
        api_key = os.getenv("GEMINI_API_KEY")
        llm = GeminiProvider(model_name=model_name, api_key=api_key)
    elif provider_type == "local":
        model_path = os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")
        llm = LocalProvider(model_path=model_path)
    else:
        logger.error(f"❌ Error: Unsupported provider '{provider_type}'")
        exit(1)

    logger.info(f"\n🚀 Baseline Chatbot initialized with {provider_type} ({model_name})")
    logger.info("Type 'exit' or 'quit' to stop.")

    # 3. Simple CLI Loop
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                break

            logger.info("Chatbot: ")
            response = run_chatbot(user_input, llm)
            logger.info(response)
        except KeyboardInterrupt:
            logger.info("\nExiting...")
            break
        except Exception as e:
            logger.error(f"\n❌ Error: {e}")
