# ===================================================
# FILE: deployment.py
# DEPLOYMENT CONFIGURATION
# ===================================================

"""
Deployment Instructions:

1. Set up environment variables:
export BOT_TOKEN="your_bot_token_from_@BotFather"
export SUPABASE_URL="your_supabase_url"
export SUPABASE_KEY="your_supabase_anon_key"
export ADMIN_ID="your_telegram_id"
export JWT_SECRET="generate_with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"

2. For payment setup:
- Talk to @BotFather
- Send /mybots
- Select your bot
- Select Payments
- Follow setup with provider (Telegram uses Fragment for Stars)

3. Deploy to Railway/Render:
- Create new project
- Connect GitHub repository
- Add environment variables
- Deploy!

4. Set webhook after deployment:
GET https://your-domain.com/set-webhook

5. For local development:
uvicorn token_bot:app --reload --port 8000
"""

import os
from dotenv import load_dotenv

load_dotenv()

class DeploymentConfig:
    # Railway/Render specific
    PORT = int(os.getenv("PORT", 8000))
    HOST = "0.0.0.0"
    
    # Webhook URL (set after deployment)
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
    
    # SSL certificate (for webhook)
    SSL_CERTIFICATE = os.getenv("SSL_CERTIFICATE", "")
    SSL_PRIVATE_KEY = os.getenv("SSL_PRIVATE_KEY", "")
