# ===================================================
# FILE: utils.py
# UTILITY FUNCTIONS
# ===================================================

import logging
from typing import Dict, Any

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('token_bot.log'),
            logging.StreamHandler()
        ]
    )

def format_token_for_display(token: str, token_type: str) -> str:
    """Format token for display"""
    if token_type == "jwt":
        # Pretty print JWT
        parts = token.split('.')
        if len(parts) == 3:
            return f"Header: {parts[0]}\nPayload: {parts[1]}\nSignature: {parts[2][:20]}..."
    return token

def validate_token_params(params: Dict[str, Any]) -> bool:
    """Validate token generation parameters"""
    # Add validation logic
    return True

def calculate_credits_required(token_type: str, params: Dict[str, Any]) -> int:
    """Calculate credits required for token generation"""
    base_price = {
        "api": 5,
        "jwt": 10,
        "uuid": 3,
        "custom": 8,
        "bulk": 20
    }.get(token_type, 5)
    
    # Add modifiers for customizations
    if token_type == "custom":
        length = params.get("length", 32)
        if length > 64:
            base_price += 5
        if params.get("include_special", False):
            base_price += 2
    
    return base_price
