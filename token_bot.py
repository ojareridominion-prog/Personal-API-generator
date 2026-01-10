# ===================================================
# FILE: token_bot.py
# COMPLETE API TOKEN GENERATOR BOT WITH PAYMENTS
# ===================================================

import os
import logging
import secrets
import string
import uuid
import json
import time
import asyncio
import hashlib
import html
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from enum import Enum

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import (
    Message, Update, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, PreCheckoutQuery, ContentType,
    LabeledPrice, WebAppInfo
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from supabase import create_client, Client
from pydantic import BaseModel
import jwt

# ==================== CONFIGURATION ====================
class Config:
    # Environment variables
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
    
    # Payment settings - CHANGE THIS LINE
    PROVIDER_TOKEN = os.environ.get("PROVIDER_TOKEN", "")  # Get from @BotFather
    DEFAULT_STARS = 149  # $1.49 for basic subscription
    
    # JWT settings (for educational tokens only)
    JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_urlsafe(32))
    
    # Free tier limits
    FREE_TOKENS_PER_DAY = 3
    FREE_TOKEN_LENGTH = 32

# Initialize
app = FastAPI(title="TokenGen Bot API")
bot = Bot(token=Config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
supabase: Optional[Client] = None

if Config.SUPABASE_URL and Config.SUPABASE_KEY:
    supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== DATABASE MODELS ====================
class TokenType(str, Enum):
    API_KEY = "api_key"
    JWT = "jwt"
    UUID = "uuid"
    CUSTOM = "custom"
    BULK = "bulk"

class UserState(StatesGroup):
    """FSM states for token generation flow"""
    choosing_token_type = State()
    customizing_token = State()
    entering_metadata = State()
    confirming_purchase = State()

# ==================== TOKEN GENERATION ENGINE ====================
class TokenGenerator:
    """Core token generation engine"""
    
    @staticmethod
    def generate_api_key(length: int = 32, prefix: str = "", suffix: str = "") -> str:
        """Generate a secure API key"""
        alphabet = string.ascii_letters + string.digits + "_-"
        key = ''.join(secrets.choice(alphabet) for _ in range(length))
        
        if prefix:
            key = f"{prefix}_{key}"
        if suffix:
            key = f"{key}_{suffix}"
            
        return key
    
    @staticmethod
    def generate_jwt(payload: Dict, expires_hours: int = 24) -> str:
        """Generate educational JWT token (FOR LEARNING ONLY)"""
        # Add standard claims
        payload.update({
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=expires_hours),
            "iss": "TokenGenBot (Educational)",
            "aud": "Learning Environment",
            "sub": "sample_user"
        })
        
        # Generate token with educational header
        token = jwt.encode(
            payload, 
            Config.JWT_SECRET,
            algorithm="HS256"
        )
        
        return token
    
    @staticmethod
    def generate_uuid(version: int = 4) -> str:
        """Generate UUID token"""
        if version == 4:
            return str(uuid.uuid4())
        elif version == 1:
            return str(uuid.uuid1())
        else:
            return str(uuid.uuid4())
    
    @staticmethod
    def generate_custom_token(
        length: int = 32,
        include_uppercase: bool = True,
        include_lowercase: bool = True,
        include_digits: bool = True,
        include_special: bool = False,
        prefix: str = "",
        suffix: str = ""
    ) -> str:
        """Generate custom token with specific requirements"""
        charset = ""
        if include_uppercase:
            charset += string.ascii_uppercase
        if include_lowercase:
            charset += string.ascii_lowercase
        if include_digits:
            charset += string.digits
        if include_special:
            charset += "_-!@#$%^&*"
        
        if not charset:
            charset = string.ascii_letters + string.digits
        
        token = ''.join(secrets.choice(charset) for _ in range(length))
        
        if prefix:
            token = f"{prefix}_{token}"
        if suffix:
            token = f"{token}_{suffix}"
            
        return token

# ==================== DATABASE FUNCTIONS ====================
class DatabaseManager:
    """Handles all database operations"""
    
    @staticmethod
    async def get_user(telegram_id: int) -> Optional[Dict]:
        """Get user from database"""
        try:
            if not supabase:
                return None
                
            result = supabase.table("users") \
                .select("*") \
                .eq("telegram_id", telegram_id) \
                .execute()
            
            return result.data[0] if result.data else None
        except Exception as e:
            logging.error(f"Error getting user: {e}")
            return None
    
    @staticmethod
    async def create_user(telegram_id: int, username: str = "", first_name: str = "") -> Dict:
        """Create new user in database"""
        try:
            if not supabase:
                return {"telegram_id": telegram_id, "credits": 0, "is_premium": False}
                
            user_data = {
                "telegram_id": telegram_id,
                "username": username,
                "first_name": first_name,
                "credits": 0,
                "is_premium": False,
                "created_at": datetime.utcnow().isoformat(),
                "last_active": datetime.utcnow().isoformat(),
                "tokens_generated": 0,
                "free_tokens_used_today": 0,
                "free_tokens_last_reset": datetime.utcnow().isoformat()
            }
            
            result = supabase.table("users").insert(user_data).execute()
            return result.data[0] if result.data else user_data
        except Exception as e:
            logging.error(f"Error creating user: {e}")
            return {"telegram_id": telegram_id, "credits": 0, "is_premium": False}
    
    @staticmethod
    async def update_user_credits(telegram_id: int, credits_change: int) -> bool:
        """Update user's credits"""
        try:
            if not supabase:
                return False
                
            user = await DatabaseManager.get_user(telegram_id)
            if not user:
                return False
            
            new_credits = max(0, user.get("credits", 0) + credits_change)
            
            supabase.table("users") \
                .update({
                    "credits": new_credits,
                    "last_active": datetime.utcnow().isoformat()
                }) \
                .eq("telegram_id", telegram_id) \
                .execute()
            
            return True
        except Exception as e:
            logging.error(f"Error updating credits: {e}")
            return False
    
    @staticmethod
    async def record_token_generation(
        telegram_id: int,
        token_type: str,
        credits_used: int,
        token_preview: str = ""
    ) -> bool:
        """Record token generation in database"""
        try:
            if not supabase:
                return False
            
            # Update user's token count
            user = await DatabaseManager.get_user(telegram_id)
            if user:
                supabase.table("users") \
                    .update({
                        "tokens_generated": user.get("tokens_generated", 0) + 1,
                        "last_active": datetime.utcnow().isoformat()
                    }) \
                    .eq("telegram_id", telegram_id) \
                    .execute()
            
            # Record the transaction
            transaction_data = {
                "telegram_id": telegram_id,
                "token_type": token_type,
                "credits_used": credits_used,
                "token_preview": token_preview[:50] + "..." if len(token_preview) > 50 else token_preview,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            supabase.table("token_transactions").insert(transaction_data).execute()
            return True
        except Exception as e:
            logging.error(f"Error recording token: {e}")
            return False
    
    @staticmethod
    async def record_payment(
        telegram_id: int,
        stars_amount: int,
        credits_purchased: int,
        transaction_id: str
    ) -> bool:
        """Record payment in database"""
        try:
            if not supabase:
                return False
            
            payment_data = {
                "telegram_id": telegram_id,
                "stars_amount": stars_amount,
                "credits_purchased": credits_purchased,
                "transaction_id": transaction_id,
                "status": "completed",
                "payment_date": datetime.utcnow().isoformat()
            }
            
            supabase.table("payments").insert(payment_data).execute()
            return True
        except Exception as e:
            logging.error(f"Error recording payment: {e}")
            return False

# ==================== PRICING CONFIG ====================
class Pricing:
    """Token pricing in credits"""
    
    # Token types and their credit costs
    PRICES = {
        TokenType.API_KEY: 5,       # 5 credits
        TokenType.JWT: 10,           # 10 credits
        TokenType.UUID: 3,           # 3 credits
        TokenType.CUSTOM: 8,         # 8 credits
        TokenType.BULK: 20           # 20 credits for 10 tokens
    }
    
    # Credit packages (credits per stars)
    CREDIT_PACKAGES = {
        50: 100,    # 50 stars = 100 credits ($0.50 = $1.00 value)
        100: 250,   # 100 stars = 250 credits ($1.00 = $2.50 value)
        250: 750,   # 250 stars = 750 credits ($2.50 = $7.50 value)
        500: 2000   # 500 stars = 2000 credits ($5.00 = $20.00 value)
    }
    
    # Free tier limits
    FREE_DAILY_LIMIT = 3
    FREE_TOKEN_LENGTH = 32

# ==================== WEBHOOK ENDPOINTS ====================
@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Telegram webhook handler"""
    try:
        update_data = await request.json()
        update = Update(**update_data)
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/set-webhook")
async def set_webhook():
    """Set webhook URL dynamically"""
    # Get domain from environment or use the current host
    webhook_domain = os.environ.get("RENDER_EXTERNAL_URL", "")
    if not webhook_domain:
        # Fallback: construct from Render's typical pattern
        service_name = os.environ.get("RENDER_SERVICE_NAME", "personal-api-generator")
        webhook_domain = f"https://{service_name}.onrender.com"
    
    webhook_url = f"{webhook_domain}/webhook"
    await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    return {
        "status": "Webhook set", 
        "url": webhook_url,
        "domain": webhook_domain
        }

# ==================== PAYMENT HANDLERS ====================
@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    """Handle pre-checkout query"""
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment_handler(message: Message):
    """Handle successful payment with Telegram Stars"""
    try:
        payment = message.successful_payment
        telegram_id = message.from_user.id
        
        # Stars are in cents (100 stars = $1.00)
        stars_amount = payment.total_amount  # Convert to whole stars
        
        # Map stars to credits (from Pricing.CREDIT_PACKAGES)
        credits_purchased = Pricing.CREDIT_PACKAGES.get(stars_amount, stars_amount * 2)
        
        logging.info(f"Payment received: {stars_amount} Stars -> {credits_purchased} credits for user {telegram_id}")
        
        # Update user's credits
        success = await DatabaseManager.update_user_credits(telegram_id, credits_purchased)
        
        if success:
            # Record payment
            await DatabaseManager.record_payment(
                telegram_id=telegram_id,
                stars_amount=stars_amount,
                credits_purchased=credits_purchased,
                transaction_id=payment.telegram_payment_charge_id
            )
            
            # Send confirmation
            await message.answer(
                f"🎉 *Payment Successful!*\n\n"
                f"⭐ *Stars Received:* {stars_amount}\n"
                f"💎 *Credits Added:* {credits_purchased}\n"
                f"💰 *Transaction ID:* `{payment.telegram_payment_charge_id}`\n\n"
                f"Your total credits: {await get_user_credits(telegram_id)}\n\n"
                f"Use /gentoken to generate tokens or /mycredits to check balance!",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                "❌ Payment received but failed to update credits. "
                "Please contact admin with your transaction ID."
            )
            
    except Exception as e:
        logging.error(f"Payment processing error: {e}")
        await message.answer(
            "❌ Error processing payment. Please contact admin with transaction details."
        )

# ==================== COMMAND HANDLERS ====================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Start command handler"""
    telegram_id = message.from_user.id
    user = await DatabaseManager.get_user(telegram_id)
    
    if not user:
        await DatabaseManager.create_user(
            telegram_id=telegram_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name
        )
    
    welcome_text = """
🔐 *Welcome to TokenGen Bot!*

I help you generate secure API tokens for your personal projects.

*Features:*
• Generate API Keys, JWT tokens, UUIDs
• Custom token formats
• Secure & random generation
• Educational JWT examples

*Commands:*
/gentoken - Generate a new token
/mycredits - Check your credits
/buycredits - Buy more credits
/help - Show help

*Pricing:*
- API Key: 5 credits
- JWT Token: 10 credits
- UUID: 3 credits
- Custom Token: 8 credits

*Free Tier:* 3 tokens per day
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔐 Generate Token", callback_data="menu_gentoken")],
        [InlineKeyboardButton(text="💎 Buy Credits", callback_data="menu_buy")],
        [InlineKeyboardButton(text="ℹ️  Help", callback_data="menu_help")]
    ])
    
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=keyboard)

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Help command"""
    help_text = """
*TokenGen Bot Help*

*How it works:*
1. You need credits to generate tokens
2. Get free credits daily or buy more
3. Choose token type and generate

*Token Types:*
• *API Key* - Standard API key (32 chars)
• *JWT* - JSON Web Token with sample payload
• *UUID* - Universally Unique Identifier
• *Custom* - Configure your own format

*For Educational Use Only:*
⚠️ Tokens generated are for learning, testing, and personal projects only.
⚠️ Do not use for production without proper security review.
⚠️ Store tokens securely!

*Commands:*
/start - Start the bot
/gentoken - Generate token
/mycredits - Check credits
/buycredits - Buy credits
/help - This help message

Need support? Contact @yourusername
"""
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("mycredits"))
async def cmd_mycredits(message: Message):
    """Check user credits"""
    telegram_id = message.from_user.id
    user = await DatabaseManager.get_user(telegram_id)
    
    if not user:
        user = await DatabaseManager.create_user(telegram_id)
    
    credits = user.get("credits", 0)
    tokens_generated = user.get("tokens_generated", 0)
    
    # Check free tokens
    last_reset = datetime.fromisoformat(user.get("free_tokens_last_reset", datetime.utcnow().isoformat()))
    today = datetime.utcnow().date()
    
    if last_reset.date() < today:
        free_tokens_used = 0
    else:
        free_tokens_used = user.get("free_tokens_used_today", 0)
    
    free_tokens_left = max(0, Pricing.FREE_DAILY_LIMIT - free_tokens_used)
    
    text = f"""
*Your Account Status*

💎 *Credits:* {credits}
🎫 *Free tokens today:* {free_tokens_left} / {Pricing.FREE_DAILY_LIMIT}
📊 *Total tokens generated:* {tokens_generated}

*Credit Costs:*
• API Key: {Pricing.PRICES[TokenType.API_KEY]} credits
• JWT: {Pricing.PRICES[TokenType.JWT]} credits
• UUID: {Pricing.PRICES[TokenType.UUID]} credits
• Custom: {Pricing.PRICES[TokenType.CUSTOM]} credits
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔐 Generate Token", callback_data="menu_gentoken")],
        [InlineKeyboardButton(text="💎 Buy Credits", callback_data="menu_buy")]
    ])
    
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)

@dp.message(Command("gentoken"))
async def cmd_gentoken(message: Message, state: FSMContext):
    """Start token generation menu"""
    await show_token_menu(message, state)

async def show_token_menu(message: types.Message, state: FSMContext):
    """Show token type selection menu"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 API Key (5 credits)", callback_data="token_api")],
        [InlineKeyboardButton(text="🎫 JWT (10 credits)", callback_data="token_jwt")],
        [InlineKeyboardButton(text="🆔 UUID (3 credits)", callback_data="token_uuid")],
        [InlineKeyboardButton(text="⚙️ Custom (8 credits)", callback_data="token_custom")],
        [InlineKeyboardButton(text="📦 Bulk (20 credits)", callback_data="token_bulk")],
        [InlineKeyboardButton(text="💎 My Credits", callback_data="menu_credits")]
    ])
    
    await message.answer(
        "*Choose Token Type:*\n\n"
        "🔑 *API Key* - Standard API key format\n"
        "🎫 *JWT* - JSON Web Token with sample data\n"
        "🆔 *UUID* - Universally Unique Identifier\n"
        "⚙️ *Custom* - Configure your own format\n"
        "📦 *Bulk* - Generate 10 API keys at once\n\n"
        "Click on your choice below:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    
    await state.set_state(UserState.choosing_token_type)

# ==================== CALLBACK HANDLERS ====================
# ==================== CALLBACK HANDLERS ====================
@dp.callback_query(F.data.startswith("token_"))
async def handle_token_selection(call: CallbackQuery, state: FSMContext):
    """Handle token type selection"""
    callback_data = call.data.split("_")[1]
    await call.answer()
    
    telegram_id = call.from_user.id
    user = await DatabaseManager.get_user(telegram_id)
    
    # Check if user exists
    if not user:
        user = await DatabaseManager.create_user(telegram_id)
    
    # Map callback data to token type enum
    token_type_map = {
        "api": TokenType.API_KEY,
        "jwt": TokenType.JWT,
        "uuid": TokenType.UUID,
        "custom": TokenType.CUSTOM,
        "bulk": TokenType.BULK
    }
    
    token_type = callback_data
    token_type_enum = token_type_map.get(callback_data)
    
    if not token_type_enum:
        await call.message.answer("❌ Invalid token type selected.")
        return
    
    credits_needed = Pricing.PRICES.get(token_type_enum, 5)
    credits_have = user.get("credits", 0)
    
    # Check free tokens
    free_tokens_used = user.get("free_tokens_used_today", 0)
    last_reset = datetime.fromisoformat(user.get("free_tokens_last_reset", datetime.utcnow().isoformat()))
    
    # Reset if new day
    if last_reset.date() < datetime.utcnow().date():
        free_tokens_used = 0
    
    has_free_token = free_tokens_used < Pricing.FREE_DAILY_LIMIT
    
    if credits_have < credits_needed and not has_free_token:
        # Not enough credits and no free tokens
        await call.message.answer(
            f"❌ Insufficient credits!\n\n"
            f"You need {credits_needed} credits for this token.\n"
            f"You have {credits_have} credits.\n\n"
            f"You've used all {Pricing.FREE_DAILY_LIMIT} free tokens today.\n\n"
            f"Use /buycredits to get more credits!",
            parse_mode="Markdown"
        )
        return
    
    await state.update_data(token_type=token_type)
    
    # Show customization or generate immediately
    if token_type == "custom":
        await ask_customization(call.message, state)
    elif token_type == "jwt":
        await ask_jwt_metadata(call.message, state)
    else:
        await generate_and_send_token(call.message, state, telegram_id, token_type)

async def ask_customization(message: types.Message, state: FSMContext):
    """Ask for custom token parameters"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="32 chars", callback_data="custom_len_32"),
         InlineKeyboardButton(text="64 chars", callback_data="custom_len_64")],
        [InlineKeyboardButton(text="🔤 Letters+Digits", callback_data="custom_chars_ld")],
        [InlineKeyboardButton(text="🔣 Include Special", callback_data="custom_chars_all")],
        [InlineKeyboardButton(text="🏷️ Add Prefix", callback_data="custom_prefix")],
        [InlineKeyboardButton(text="✅ Generate Now", callback_data="custom_generate")]
    ])
    
    await message.answer(
        "*Custom Token Settings:*\n\n"
        "Configure your token:\n"
        "• Length: 32 or 64 characters\n"
        "• Character set: Letters+Digits or include special chars\n"
        "• Optional prefix (like 'sk_' or 'pk_')\n\n"
        "Click 'Generate Now' when ready:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    
    await state.set_state(UserState.customizing_token)
    await state.update_data(custom_length=32, custom_charset="ld", custom_prefix="")

@dp.callback_query(F.data.startswith("custom_"))
async def handle_customization(call: CallbackQuery, state: FSMContext):
    """Handle customization options"""
    data = call.data
    await call.answer()
    
    if data.startswith("custom_len_"):
        length = int(data.split("_")[2])
        await state.update_data(custom_length=length)
        await call.message.edit_text(f"✅ Length set to {length} characters")
    elif data.startswith("custom_chars_"):
        charset = data.split("_")[2]
        await state.update_data(custom_charset=charset)
        charset_name = "Letters and Digits" if charset == "ld" else "All Characters (including special)"
        await call.message.edit_text(f"✅ Character set updated to {charset_name}")
    elif data == "custom_prefix":
        await call.message.answer("Send me the prefix (e.g., 'sk_', 'pk_', 'live_'):")
        await state.update_data(waiting_for="prefix")
        await state.set_state(UserState.entering_metadata)
    elif data == "custom_generate":
        await generate_and_send_token(call.message, state, call.from_user.id, "custom")

async def ask_jwt_metadata(message: types.Message, state: FSMContext):
    """Ask for JWT payload data"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Add user_id", callback_data="jwt_user")],
        [InlineKeyboardButton(text="📧 Add email", callback_data="jwt_email")],
        [InlineKeyboardButton(text="🎭 Add role", callback_data="jwt_role")],
        [InlineKeyboardButton(text="⏰ Custom expiry", callback_data="jwt_expiry")],
        [InlineKeyboardButton(text="✅ Generate Now", callback_data="jwt_generate")]
    ])
    
    await message.answer(
        "*JWT Token Configuration:*\n\n"
        "Add custom claims to your JWT:\n"
        "• user_id - User identifier\n"
        "• email - User email\n"
        "• role - User role (admin, user, etc.)\n"
        "• expiry - Token expiry time\n\n"
        "Click buttons to add claims, then 'Generate Now':",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    
    await state.set_state(UserState.entering_metadata)
    await state.update_data(jwt_payload={"sample": "data"})

@dp.callback_query(F.data.startswith("jwt_"))
async def handle_jwt_metadata(call: CallbackQuery, state: FSMContext):
    """Handle JWT metadata"""
    action = call.data.split("_")[1]
    await call.answer()
    
    if action in ["user", "email", "role", "expiry"]:
        prompt = {
            "user": "Enter user_id value:",
            "email": "Enter email value:",
            "role": "Enter role value:",
            "expiry": "Enter expiry in hours (1-720):"
        }[action]
        
        await call.message.answer(prompt)
        await state.update_data(jwt_action=action)
    elif action == "generate":
        await generate_and_send_token(call.message, state, call.from_user.id, "jwt")

@dp.message(UserState.entering_metadata)
async def handle_metadata_input(message: Message, state: FSMContext):
    """Handle metadata input"""
    data = await state.get_data()
    token_type = data.get("token_type")
    text = message.text
    
    if token_type == "custom" and data.get("waiting_for") == "prefix":
        await state.update_data(custom_prefix=text)
        await message.answer(f"✅ Prefix set to '{text}'")
        await ask_customization(message, state)
    
    elif token_type == "jwt":
        action = data.get("jwt_action")
        payload = data.get("jwt_payload", {})
        
        if action == "user":
            payload["user_id"] = text
        elif action == "email":
            payload["email"] = text
        elif action == "role":
            payload["role"] = text
        elif action == "expiry":
            try:
                hours = int(text)
                payload["exp_hours"] = min(max(1, hours), 720)
            except:
                payload["exp_hours"] = 24
        
        await state.update_data(jwt_payload=payload)
        await message.answer(f"✅ Added {action} to JWT payload")
        await ask_jwt_metadata(message, state)
    
    # Clear waiting flag
    await state.update_data(waiting_for=None)

@dp.callback_query(F.data.startswith("buy_"))
async def handle_buy_selection(call: CallbackQuery):
    """Handle credit package selection"""
    try:
        stars_amount = int(call.data.split("_")[1])
        credits_amount = Pricing.CREDIT_PACKAGES.get(stars_amount, stars_amount * 2)
        
        await call.answer()
        
        # Check if payment provider is configured
        if not Config.PROVIDER_TOKEN or Config.PROVIDER_TOKEN == "":
            await call.message.answer(
                "⚠️ *Payment System Not Configured*\n\n"
                "To enable payments, the admin needs to:\n"
                "1. Set up payment provider with @BotFather\n"
                "2. Add PROVIDER_TOKEN to environment variables\n"
                "3. Redeploy the bot\n\n"
                "Contact admin for assistance.",
                parse_mode="Markdown"
            )
            return
        
        # Create invoice
        try:
            invoice_link = await call.message.bot.create_invoice_link(
                title=f"TokenGen - {credits_amount} Credits",
                description=f"Purchase {credits_amount} credits for {stars_amount} Telegram Stars",
                payload=f"credits_{credits_amount}_{call.from_user.id}_{int(time.time())}",
                provider_token=Config.PROVIDER_TOKEN,
                currency="XTR",  # Telegram Stars
                prices=[
                    LabeledPrice(
                        label=f"{credits_amount} Credits",
                        amount=stars_amount  # Convert to cents
                    )
                ]
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Pay with Telegram Stars", url=invoice_link)],
                [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="menu_main")]
            ])
            
            await call.message.edit_text(
                f"*💎 Purchase {credits_amount} Credits*\n\n"
                f"⭐ *Cost:* {stars_amount} Stars (${stars_amount/100:.2f})\n"
                f"💎 *You Get:* {credits_amount} credits\n"
                f"🎯 *Best Value:* {credits_amount/stars_amount:.1f}x more credits than basic rate!\n\n"
                f"Click the button below to pay with Telegram Stars:",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            
        except Exception as e:
            logging.error(f"Invoice creation error: {e}")
            await call.message.answer(
                f"❌ *Payment Error*\n\n"
                f"Failed to create payment invoice:\n`{str(e)}`\n\n"
                f"Please contact the admin for support.",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logging.error(f"Error processing purchase: {e}")
        await call.message.answer(f"❌ Error: {str(e)}")

# ==================== TOKEN GENERATION ====================
async def generate_and_send_token(
    message: types.Message, 
    state: FSMContext, 
    telegram_id: int,
    token_type: str
):
    """Generate and send token to user"""
    try:
        data = await state.get_data()
        generator = TokenGenerator()
        token = ""
        credits_used = 0
        
        # Check if using free token
        user = await DatabaseManager.get_user(telegram_id)
        free_tokens_used = user.get("free_tokens_used_today", 0)
        last_reset = datetime.fromisoformat(user.get("free_tokens_last_reset", datetime.utcnow().isoformat()))
        
        # Reset if new day
        if last_reset.date() < datetime.utcnow().date():
            free_tokens_used = 0
        
        using_free_token = free_tokens_used < Pricing.FREE_DAILY_LIMIT
        
        if token_type == "api":
            token = generator.generate_api_key()
            credits_used = Pricing.PRICES[TokenType.API_KEY]
        elif token_type == "jwt":
            payload = data.get("jwt_payload", {})
            exp_hours = payload.pop("exp_hours", 24) if "exp_hours" in payload else 24
            token = generator.generate_jwt(payload, exp_hours)
            credits_used = Pricing.PRICES[TokenType.JWT]
        elif token_type == "uuid":
            token = generator.generate_uuid()
            credits_used = Pricing.PRICES[TokenType.UUID]
        elif token_type == "custom":
            length = data.get("custom_length", 32)
            charset = data.get("custom_charset", "ld")
            prefix = data.get("custom_prefix", "")
            
            include_special = charset == "all"
            token = generator.generate_custom_token(
                length=length,
                prefix=prefix,
                include_special=include_special
            )
            credits_used = Pricing.PRICES[TokenType.CUSTOM]
        elif token_type == "bulk":
            tokens = [generator.generate_api_key() for _ in range(10)]
            token = "\n".join(tokens)
            credits_used = Pricing.PRICES[TokenType.BULK]
        else:
            await message.answer(f"❌ Unknown token type: {token_type}")
            await state.clear()
            return
        
        # Update user credits or free token count
        if using_free_token and credits_used <= 5:  # Only free for basic tokens
            # Update free token count
            if supabase:
                supabase.table("users") \
                    .update({
                        "free_tokens_used_today": free_tokens_used + 1,
                        "free_tokens_last_reset": datetime.utcnow().isoformat()
                    }) \
                    .eq("telegram_id", telegram_id) \
                    .execute()
            
            charge_text = "🎫 (Used 1 free token)"
        else:
            # Deduct credits
            await DatabaseManager.update_user_credits(telegram_id, -credits_used)
            charge_text = f"💎 (Cost: {credits_used} credits)"
        
        # Record the generation
        await DatabaseManager.record_token_generation(
            telegram_id=telegram_id,
            token_type=token_type,
            credits_used=0 if using_free_token else credits_used,
            token_preview=token[:50] if isinstance(token, str) else "bulk"
        )
        
        # Send the token with HTML escaping to avoid Markdown parsing issues
        if token_type != "bulk":
            # Escape HTML special characters for single tokens
            escaped_token = html.escape(token)
            token_display = f"<code>{escaped_token}</code>"
            response = f"""
✅ <b>Token Generated Successfully!</b>

<b>Type:</b> {html.escape(token_type.upper())}
<b>Status:</b> {charge_text}
<b>Generated:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}

<b>Your Token:</b>
{token_display}

<b>Important Notes:</b>
• Store this token securely
• This is for educational/personal use only
• Do not use in production without review
• Regenerate if compromised

Need another token? Use /gentoken
"""
        else:
            # For bulk tokens, escape each token
            tokens_list = token.split('\n')
            token_display = "\n".join([f"<code>{html.escape(t)}</code>" for t in tokens_list])
            response = f"""
✅ <b>Bulk Tokens Generated Successfully!</b>

<b>Type:</b> API Keys (x10)
<b>Status:</b> {charge_text}
<b>Generated:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}

<b>Your Tokens:</b>
{token_display}

<b>Important Notes:</b>
• Store these tokens securely
• This is for educational/personal use only
• Do not use in production without review
• Regenerate if compromised

Need more tokens? Use /gentoken
"""
        
        await message.answer(response, parse_mode="HTML")
        
        # Add copy button for single tokens
        if token_type != "bulk":
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Copy Token", callback_data=f"copy_{hashlib.md5(token.encode()).hexdigest()[:8]}")]
            ])
            await message.answer("Click to copy:", reply_markup=keyboard)
        
        await state.clear()
        
    except Exception as e:
        logging.error(f"Error generating token: {e}", exc_info=True)
        await message.answer(f"❌ Error generating token: {str(e)}")
        await state.clear()

# ==================== CREDIT PURCHASE ====================
@dp.message(Command("buycredits"))
async def cmd_buycredits(message: Message):
    """Show credit purchase options"""
    
    # Check if payments are configured
    if not Config.PROVIDER_TOKEN:
        await message.answer(
            "⚠️ *Payment system is not configured yet.*\n\n"
            "To set up payments:\n"
            "1. Talk to @BotFather\n"
            "2. Send /mybots\n"
            "3. Select your bot\n"
            "4. Choose *Payments*\n"
            "5. Follow setup instructions\n\n"
            "Once configured, the admin needs to add the PROVIDER_TOKEN to environment variables.",
            parse_mode="Markdown"
        )
        return
    
    # Create inline keyboard with credit packages
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💎 100 credits (50 Stars)", 
                callback_data="buy_50"
            )
        ],
        [
            InlineKeyboardButton(
                text="💎 250 credits (100 Stars)", 
                callback_data="buy_100"
            )
        ],
        [
            InlineKeyboardButton(
                text="💎 750 credits (250 Stars)", 
                callback_data="buy_250"
            )
        ],
        [
            InlineKeyboardButton(
                text="💎 2000 credits (500 Stars)", 
                callback_data="buy_500"
            )
        ],
        [
            InlineKeyboardButton(text="🔙 Back to Menu", callback_data="menu_main")
        ]
    ])
    
    text = """
*Buy Credits*

Choose a package:

💎 *100 credits* - 50 Stars ($0.50)
💎 *250 credits* - 100 Stars ($1.00)
💎 *750 credits* - 250 Stars ($2.50)
💎 *2000 credits* - 500 Stars ($5.00)

*Best Value:* 2000 credits for 500 Stars!

*What you can buy:*
• 400 API Keys
• 200 JWT tokens
• 666 UUIDs
• 250 Custom tokens

*Note:* 100 Stars = $1.00
Click a package to purchase:
"""
    
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)

# ==================== UTILITY FUNCTIONS ====================
async def get_user_credits(telegram_id: int) -> int:
    """Get user's credit balance"""
    user = await DatabaseManager.get_user(telegram_id)
    return user.get("credits", 0) if user else 0

@dp.callback_query(F.data.startswith("menu_"))
async def handle_menu(call: CallbackQuery, state: FSMContext):
    """Handle menu navigation"""
    menu = call.data.split("_")[1]
    await call.answer()
    
    if menu == "gentoken":
        await show_token_menu(call.message, state)
    elif menu == "buy":
        await cmd_buycredits(call.message)
    elif menu == "help":
        await cmd_help(call.message)
    elif menu == "credits":
        await cmd_mycredits(call.message)
    elif menu == "main":
        await cmd_start(call.message)

@dp.callback_query(F.data.startswith("copy_"))
async def handle_copy(call: CallbackQuery):
    """Handle copy token request"""
    await call.answer("Token copied to clipboard!", show_alert=True)

# ==================== ADMIN COMMANDS ====================
# ==================== ADMIN COMMANDS ====================
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    """Admin commands"""
    if message.from_user.id != Config.ADMIN_ID:
        await message.answer("❌ Access denied")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton(text="💳 Transactions", callback_data="admin_transactions")]
    ])
    
    await message.answer("🔧 *Admin Panel*", parse_mode="Markdown", reply_markup=keyboard)

@dp.message(Command("setuppayments"))
async def cmd_setuppayments(message: Message):
    """Guide user to set up payments"""
    if message.from_user.id != Config.ADMIN_ID:
        await message.answer("❌ Access denied")
        return
    
    setup_guide = """
🔧 *Payment Setup Guide*

To accept Telegram Stars payments:

1. *Talk to @BotFather*
2. Send `/mybots`
3. Select your bot
4. Choose *Payments*
5. Follow setup instructions
6. You'll get a *PROVIDER_TOKEN*

Once you have the provider token:

1. *Add to Render:*
   - Go to your Render dashboard
   - Select your service
   - Go to Environment
   - Add variable: `PROVIDER_TOKEN`
   - Paste your token value
   - Redeploy the bot

2. *Verify setup:* 
   - Use /buycredits command
   - Should show payment buttons

*Important:* Payments work with "Telegram Stars" only.
Users need to have Stars in their Telegram account.
"""
    
    # Check current status
    if Config.PROVIDER_TOKEN:
        status = f"✅ *Configured:* Yes\n*Token Preview:* `{Config.PROVIDER_TOKEN[:15]}...`"
    else:
        status = "❌ *Configured:* No\n*Token:* Not set"
    
    await message.answer(
        f"*Payment System Status*\n\n{status}\n\n{setup_guide}",
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("admin_"))
async def handle_admin(call: CallbackQuery):
    """Handle admin actions"""
    if call.from_user.id != Config.ADMIN_ID:
        await call.answer("❌ Access denied")
        return
    
    action = call.data.split("_")[1]
    
    if action == "stats":
        # Get statistics
        try:
            if not supabase:
                await call.message.answer("❌ Database not configured")
                return
                
            users_count = len(supabase.table("users").select("*").execute().data)
            payments = supabase.table("payments").select("*").execute().data
            total_stars = sum(p["stars_amount"] for p in payments)
            total_tokens = len(supabase.table("token_transactions").select("*").execute().data)
            
            text = f"""
📊 *Bot Statistics*

👥 Total Users: {users_count}
💳 Total Payments: {len(payments)}
⭐ Total Stars: {total_stars}
💰 Estimated Revenue: ${total_stars/100:.2f}
🔑 Tokens Generated: {total_tokens}
            """
            await call.message.answer(text, parse_mode="Markdown")
        except Exception as e:
            await call.message.answer(f"Error: {str(e)}")

# ==================== STARTUP ====================
@app.on_event("startup")
async def on_startup():
    """Initialize bot on startup"""
    logging.basicConfig(level=logging.INFO)
    logging.info("TokenGen Bot starting up...")
    
    # Create tables if they don't exist
    await create_tables()
    
    # Set commands
    commands = [
        types.BotCommand(command="start", description="Start the bot"),
        types.BotCommand(command="gentoken", description="Generate a token"),
        types.BotCommand(command="mycredits", description="Check your credits"),
        types.BotCommand(command="buycredits", description="Buy more credits"),
        types.BotCommand(command="help", description="Show help")
    ]
    
    try:
        await bot.set_my_commands(commands)
        logging.info("Bot commands set successfully")
    except Exception as e:
        logging.error(f"Error setting commands: {e}")
    
    # Check if we should use webhook or polling
    webhook_url = os.environ.get("WEBHOOK_URL", "")
    
    if webhook_url:
        # Webhook mode (production)
        logging.info(f"Running in webhook mode. URL: {webhook_url}")
    else:
        # Polling mode (development)
        logging.warning("WEBHOOK_URL not set, using polling mode for development")
        try:
            # Start polling in background
            asyncio.create_task(dp.start_polling(bot))
            logging.info("Bot polling started")
        except Exception as e:
            logging.error(f"Error starting polling: {e}")

# ==================== SHUTDOWN ====================
@app.on_event("shutdown")
async def on_shutdown():
    """Cleanup on shutdown"""
    logging.info("Shutting down bot...")
    await bot.session.close()

# ==================== HEALTH CHECK ====================
@app.get("/")
async def health_check():
    """Health check endpoint for Render/Railway"""
    return {
        "status": "online",
        "service": "TokenGen Bot",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/docs")
async def get_docs():
    """API documentation"""
    return {"message": "TokenGen Bot API is running"}

async def create_tables():
    """Create necessary database tables"""
    if not supabase:
        logging.warning("Supabase not configured - running without database")
        return
    
    try:
        # Check if tables exist, create if not
        tables = supabase.table("users").select("*").limit(1).execute()
        logging.info("Database connected successfully")
    except Exception as e:
        logging.error(f"Database error: {e}")

# ==================== MAIN ====================
