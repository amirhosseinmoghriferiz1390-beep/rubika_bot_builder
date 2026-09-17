import os
import asyncio
from typing import Dict, Any
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Rubika Bot Builder API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)

# Demo storage. For production, replace with a database/secret store.
bots: Dict[str, Dict[str, Any]] = {}
tasks: Dict[str, asyncio.Task] = {}

API_BASE = "https://botapi.rubika.ir/v1"

class ConnectRequest(BaseModel):
    token: str

class ConfigRequest(BaseModel):
    token: str
    welcome: str = "سلام! به ربات خوش آمدی."
    fallback: str = "پیامت دریافت شد."

async def rubika(method: str, token: str, data: dict | None = None):
    # Rubika Bot API uses token in the URL path for the documented API.
    url = f"{API_BASE}/{token}/{method}"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, json=data or {})
        if r.status_code >= 400:
            raise HTTPException(502, f"Rubika API error: {r.text[:500]}")
        return r.json()

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/connect")
async def connect(req: ConnectRequest):
    token = req.token.strip()
    if not token:
        raise HTTPException(400, "Token is required")
    result = await rubika("getMe", token)
    if not result.get("ok", True):
        raise HTTPException(400, "توکن معتبر نیست")
    bot = result.get("data", {}).get("bot", result.get("bot", {}))
    bots[token] = {
        "welcome": "سلام! به ربات خوش آمدی.",
        "fallback": "پیامت دریافت شد.",
        "enabled": True,
        "name": bot.get("first_name") or bot.get("username") or "Rubika Bot",
    }
    if token not in tasks or tasks[token].done():
        tasks[token] = asyncio.create_task(poll_bot(token))
    return {"ok": True, "bot": bot}

@app.post("/config")
async def config(req: ConfigRequest):
    if req.token not in bots:
        raise HTTPException(404, "ابتدا ربات را متصل کنید")
    bots[req.token].update({
        "welcome": req.welcome[:4000],
        "fallback": req.fallback[:4000],
    })
    return {"ok": True, "config": bots[req.token]}

@app.post("/disconnect")
async def disconnect(req: ConnectRequest):
    task = tasks.pop(req.token, None)
    if task:
        task.cancel()
    bots.pop(req.token, None)
    return {"ok": True}

async def send_message(token: str, chat_id: str, text: str):
    return await rubika("sendMessage", token, {
        "chat_id": chat_id,
        "text": text,
    })

def extract_updates(payload: dict):
    # Accommodates common response shapes used by Rubika Bot API wrappers.
    data = payload.get("data", payload)
    updates = data.get("updates", []) if isinstance(data, dict) else []
    return updates or []

def extract_message(update: dict):
    # Flexible parser because update schemas can differ between API versions.
    msg = update.get("message") or update.get("inline_message") or update
    if not isinstance(msg, dict):
        return None
    text = msg.get("text")
    chat_id = msg.get("chat_id") or msg.get("object_guid") or msg.get("chat_guid")
    return text, chat_id

async def poll_bot(token: str):
    offset = None
    while token in bots and bots[token].get("enabled"):
        try:
            data = {}
            if offset is not None:
                data["offset_id"] = offset
            result = await rubika("getUpdates", token, data)
            for upd in extract_updates(result):
                offset = upd.get("update_id") or upd.get("id") or offset
                parsed = extract_message(upd)
                if not parsed:
                    continue
                text, chat_id = parsed
                if not text or not chat_id:
                    continue
                text = text.strip()
                if text == "/start":
                    await send_message(token, chat_id, bots[token]["welcome"])
                else:
                    await send_message(token, chat_id, bots[token]["fallback"])
        except asyncio.CancelledError:
            break
        except Exception as e:
            print("poll error:", e)
            await asyncio.sleep(5)
        await asyncio.sleep(1)

# NOTE: This sample intentionally uses the documented Bot API shape.
# If Rubika changes the API response/request schema, adjust extract_message/extract_updates.
