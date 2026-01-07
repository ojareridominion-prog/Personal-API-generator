# ===================================================
# FILE: main.py
# MAIN APPLICATION ENTRY POINT FOR RENDER
# ===================================================

import os
import sys
import asyncio
import logging

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from token_bot import app, bot, dp
from token_bot import on_startup

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def startup():
    """Run startup tasks"""
    await on_startup()
    
    # Get webhook URL from environment
    webhook_url = os.environ.get("WEBHOOK_URL", "")
    if webhook_url:
        await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True
        )
        logging.info(f"Webhook set to: {webhook_url}")
    else:
        logging.warning("WEBHOOK_URL not set, using polling mode")

# Run startup on app startup
@app.on_event("startup")
async def app_startup():
    await startup()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
