import os
from threading import Lock
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from src.core.llm_provider import LLMProvider
from run_agent import build_provider, run_once_with_trace

load_dotenv()

app = FastAPI(title="Shop Advisor Chat UI")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

_provider_cache: Dict[Tuple[str, str], LLMProvider] = {}
_provider_lock = Lock()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    mode: str = Field(default="v2", pattern="^(chatbot|v1|v2)$")
    provider: str = Field(default="gemini")
    model: str = Field(default="")
    backend: str = Field(default="json", pattern="^(json|sqlite)$")
    max_steps: int = Field(default=6, ge=1, le=20)


class ChatResponse(BaseModel):
    answer: str
    reasoning: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)


def _get_or_build_provider(provider: str, model: str):
    normalized_provider = provider.strip().lower()
    normalized_model = model.strip()
    key = (normalized_provider, normalized_model)

    with _provider_lock:
        if key in _provider_cache:
            return _provider_cache[key]

        llm = build_provider(provider_name=normalized_provider, model_name=normalized_model or None)
        _provider_cache[key] = llm
        return llm


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        llm = _get_or_build_provider(provider=payload.provider, model=payload.model)
        result = run_once_with_trace(
            mode=payload.mode,
            llm=llm,
            user_input=message,
            backend=payload.backend,
            max_steps=payload.max_steps,
        )
        return ChatResponse(
            answer=result.get("answer", ""), 
            reasoning=result.get("reasoning", []),
            metrics=result.get("metrics", {})
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/health")
def health_check():
    return {"status": "ok", "default_provider": os.getenv("DEFAULT_PROVIDER", "gemini")}
