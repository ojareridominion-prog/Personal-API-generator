# ===================================================
# FILE: main.py
# MAIN APPLICATION ENTRY POINT FOR RENDER
# ===================================================

import os
import sys
import asyncio
import logging
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from token_bot import app, bot, dp

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("main")

# Import pinger after setting up logging
from ping import RenderPinger

# Global pinger instance
_pinger = None

async def setup_pinger():
    """Setup the auto-pinger service"""
    global _pinger
    
    # Don't run pinger in development mode or if disabled
    if os.environ.get("DISABLE_PINGER", "").lower() == "true":
        logger.info("⚠️ Auto-pinger disabled by DISABLE_PINGER environment variable")
        return
    
    try:
        # Get the correct URL for pinging
        webhook_url = os.environ.get("WEBHOOK_URL", "")
        if not webhook_url:
            # Auto-detect Render URL
            service_name = os.environ.get("RENDER_SERVICE_NAME", "")
            if service_name:
                webhook_url = f"https://{service_name}.onrender.com/webhook"
            else:
                webhook_url = "https://personal-api-generator.onrender.com/webhook"
        
        # Extract base URL (remove /webhook)
        base_url = webhook_url.replace("/webhook", "")
        logger.info(f"🌐 Pinger will use base URL: {base_url}")
        
        # Create and start pinger
        _pinger = RenderPinger(ping_url=base_url, interval_minutes=8)  # Ping every 8 minutes
        asyncio.create_task(_pinger.start())
        logger.info("✅ Auto-pinger started successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to start pinger: {e}")

@app.on_event("startup")
async def startup_event():
    """Run startup tasks"""
    logger.info("🚀 Starting TokenGen Bot...")
    
    # Set bot commands
    from aiogram.types import BotCommand
    commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="gentoken", description="Generate a token"),
        BotCommand(command="mycredits", description="Check your credits"),
        BotCommand(command="buycredits", description="Buy more credits"),
        BotCommand(command="help", description="Show help")
    ]
    
    try:
        await bot.set_my_commands(commands)
        logger.info("✅ Bot commands set successfully")
    except Exception as e:
        logger.error(f"❌ Error setting commands: {e}")
    
    # Start pinger FIRST (so it can warm up the server)
    await setup_pinger()
    
    # Wait a moment for pinger to initialize
    await asyncio.sleep(2)
    
    # Auto-set webhook
    webhook_url = os.environ.get("WEBHOOK_URL", "")
    if not webhook_url:
        # Auto-detect Render URL
        service_name = os.environ.get("RENDER_SERVICE_NAME", "")
        if service_name:
            webhook_url = f"https://{service_name}.onrender.com/webhook"
        else:
            webhook_url = "https://personal-api-generator.onrender.com/webhook"
    
    try:
        await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query", "pre_checkout_query"]
        )
        logger.info(f"✅ Webhook set to: {webhook_url}")
        
        # Test the webhook immediately
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(webhook_url.replace("/webhook", "/health"))
                logger.info(f"✅ Health check response: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Could not test health endpoint: {e}")
            
    except Exception as e:
        logger.error(f"❌ Error setting webhook: {e}")
        # Fallback to polling if webhook fails (for development)
        if os.environ.get("USE_POLLING", "").lower() == "true":
            logger.info("⚠️ Falling back to polling mode...")
            asyncio.create_task(dp.start_polling(bot))
    
    logger.info("✅ Bot startup complete!")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global _pinger
    logger.info("🛑 Shutting down...")
    
    if _pinger:
        await _pinger.stop()
    
    await bot.session.close()
    logger.info("✅ Cleanup complete")

@app.get("/health")
async def health_check():
    """Enhanced health check endpoint"""
    return {
        "status": "healthy",
        "service": "TokenGen Bot",
        "timestamp": datetime.utcnow().isoformat(),
        "ping": "active"
    }

@app.get("/")
async def root():
    """Root endpoint with service info"""
    return {
        "message": "TokenGen Bot API",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "health": "/health",
            "set_webhook": "/set-webhook",
            "docs": "/docs"
        },
        "ping_service": "active (every 8 minutes)" if _pinger else "inactive"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    logger.info(f"🌐 Starting server on {host}:{port}")
    uvicorn.run(
        app, 
        host=host, 
        port=port,
        # These settings help with Render's timeout issues
        timeout_keep_alive=65,
        access_log=True
    )
