from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rubpy import Client
import asyncio

app = FastAPI()

# تنظیم CORS برای اجازه دسترسی از دامنه‌های مختلف
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # در آینده به جای * آدرس سایت خودت را بگذار
    allow_methods=["*"],
    allow_headers=["*"],
)

class BotRequest(BaseModel):
    token: str

# این دیکشنری ربات‌های فعال را نگه می‌دارد (فقط تا وقتی سرور روشن است)
active_bots = {}

@app.post("/register-bot")
async def register_bot(data: BotRequest):
    token = data.token
    
    # تست کردن توکن با کتابخانه rubpy
    try:
        bot = Client(session=token)
        me = await bot.get_me()
        
        # اگر توکن درست بود، ذخیره می‌کنیم
        active_bots[token] = {"name": me.first_name, "status": "active"}
        
        return {"status": "success", "message": f"ربات {me.first_name} با موفقیت فعال شد."}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail="توکن نامعتبر است یا مشکلی پیش آمد.")

@app.get("/")
def read_root():
    return {"status": "Server is running"}
