"""
Hands AI Daemon — FastAPI server on port 7721
Exposes REST + WebSocket endpoints for AI routing.
"""

import asyncio
import json
import logging
from typing import AsyncIterator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import config
from router import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Hands AI] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Hands AI Daemon", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["null", "http://localhost", "http://127.0.0.1"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic models ─────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    stream: bool = True
    history: list[dict] = Field(default_factory=list)  # previous messages for context


class SetModelRequest(BaseModel):
    provider: str
    model: str


class ConfigUpdateRequest(BaseModel):
    active_provider: str | None = None
    active_model: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    ollama_host: str | None = None


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    status = await router.get_status()
    return {
        "status": "ok",
        "active_provider": status["active_provider"],
        "active_model": status["active_model"],
        "providers": status["providers"],
    }


@app.get("/models")
async def list_models():
    models = await router.list_all_models()
    return {"models": models}


@app.post("/model/set")
async def set_model(req: SetModelRequest):
    provider_instance = router.get_provider(req.provider)
    if not provider_instance:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")

    # Validate model actually exists in this provider
    if req.model not in ("auto",):
        available = await provider_instance.list_models()
        model_ids = {m["id"] for m in available} | {m["name"] for m in available}
        if available and req.model not in model_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Model '{req.model}' not found in provider '{req.provider}'. "
                       f"Available: {sorted(model_ids)}",
            )

    config.update({
        "active_provider": req.provider,
        "active_model": req.model,
    })
    return {
        "ok": True,
        "active_provider": req.provider,
        "active_model": req.model,
    }


@app.get("/config")
async def get_config():
    return config.get_public()


@app.post("/config")
async def update_config(req: ConfigUpdateRequest):
    partial = {k: v for k, v in req.model_dump().items() if v is not None}
    config.update(partial)
    return {"ok": True, "config": config.get_public()}


CHAT_TIMEOUT_SECS = 120  # max seconds any single chat request may run server-side


@app.post("/chat")
async def chat(req: ChatRequest):
    # Reject absurdly large payloads before they hit the model
    total_chars = sum(len(m.get("content", "")) for m in req.history) + len(req.message)
    if total_chars > 500_000:
        raise HTTPException(status_code=413, detail="Request payload too large (>500k chars)")

    # Build message list: history + new message
    messages = list(req.history)
    messages.append({"role": "user", "content": req.message})

    if req.stream:
        async def generate() -> AsyncIterator[str]:
            try:
                async with asyncio.timeout(CHAT_TIMEOUT_SECS):
                    async for token in router.route_chat(messages, stream=True):
                        yield f"data: {json.dumps({'token': token})}\n\n"
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'token': '[Hands AI] Request timed out.'})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        try:
            full = []
            async with asyncio.timeout(CHAT_TIMEOUT_SECS):
                async for token in router.route_chat(messages, stream=False):
                    full.append(token)
            return {"response": "".join(full)}
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Request timed out after 120s")


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket client connected")

    conversation: list[dict] = []

    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue

            action = payload.get("action", "chat")

            if action == "chat":
                message = payload.get("message", "")
                if not message:
                    await websocket.send_json({"error": "Empty message"})
                    continue

                # Support resetting history from client
                if "history" in payload:
                    conversation = payload["history"]

                conversation.append({"role": "user", "content": message})

                await websocket.send_json({"type": "start"})

                full_response = []
                try:
                    async for token in router.route_chat(conversation, stream=True):
                        full_response.append(token)
                        await websocket.send_json({"type": "token", "token": token})
                except Exception as e:
                    await websocket.send_json({"type": "error", "error": str(e)})
                    continue

                assistant_text = "".join(full_response)
                conversation.append({"role": "assistant", "content": assistant_text})
                await websocket.send_json({"type": "done", "full_response": assistant_text})

            elif action == "clear":
                conversation = []
                await websocket.send_json({"type": "cleared"})

            elif action == "status":
                status = await router.get_status()
                await websocket.send_json({"type": "status", **status})

            else:
                await websocket.send_json({"error": f"Unknown action: {action}"})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "error": str(e)})
        except Exception:
            pass
