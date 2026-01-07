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

from token_bot import app, bot, dp, on_startup

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@app.on_event("startup")
async def startup_event():
    """Run startup tasks"""
    logging.info("Starting TokenGen Bot...")
    
    # Set bot commands first
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
        logging.info("Bot commands set successfully")
    except Exception as e:
        logging.error(f"Error setting commands: {e}")
    
    # Auto-set webhook on startup
    webhook_url = os.environ.get("WEBHOOK_URL", "")
    if not webhook_url:
        # Auto-detect Render URL
        service_name = os.environ.get("RENDER_SERVICE_NAME", "")
        if service_name:
            webhook_url = f"https://{service_name}.onrender.com/webhook"
        else:
            # Get from request context (if available)
            webhook_url = "https://personal-api-generator.onrender.com/webhook"
    
    try:
        await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query", "pre_checkout_query"]
        )
        logging.info(f"✅ Webhook set to: {webhook_url}")
    except Exception as e:
        logging.error(f"❌ Error setting webhook: {e}")
        
    
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
        logging.info("Bot commands set successfully")
    except Exception as e:
        logging.error(f"Error setting commands: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logging.info("Shutting down...")
    await bot.session.close()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
