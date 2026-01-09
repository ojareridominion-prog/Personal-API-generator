# ===================================================
# FILE: ping.py
# AUTO-PING SERVICE TO PREVENT RENDER FROM SLEEPING
# ===================================================

import asyncio
import aiohttp
import logging
import os
from datetime import datetime
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ping_service")

class RenderPinger:
    """Service to ping Render URL periodically to prevent sleep"""
    
    def __init__(self, ping_url=None, interval_minutes=5):
        """
        Initialize the pinger
        
        Args:
            ping_url: URL to ping (if None, tries to auto-detect)
            interval_minutes: How often to ping (default: 5 minutes)
        """
        self.ping_url = ping_url or self._get_render_url()
        self.interval_seconds = interval_minutes * 60
        self.is_running = False
        logger.info(f"Initialized pinger for: {self.ping_url}")
        logger.info(f"Interval: {interval_minutes} minutes ({self.interval_seconds} seconds)")
    
    def _get_render_url(self):
        """Try to get Render URL from environment or construct it"""
        # Try environment variables first
        webhook_url = os.environ.get("WEBHOOK_URL", "")
        if webhook_url:
            # Convert webhook to base URL
            base_url = webhook_url.replace("/webhook", "")
            return base_url
        
        # Try Render external URL
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
        if render_url:
            return render_url
        
        # Try from service name
        service_name = os.environ.get("RENDER_SERVICE_NAME", "")
        if service_name:
            return f"https://{service_name}.onrender.com"
        
        # Default fallback (from main.py)
        return "https://personal-api-generator.onrender.com"
    
    async def ping(self):
        """Send a ping request to keep the service awake"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.ping_url, timeout=10) as response:
                    status = response.status
                    if status == 200:
                        logger.info(f"✅ Ping successful to {self.ping_url} - Status: {status}")
                        return True
                    else:
                        logger.warning(f"⚠️ Ping to {self.ping_url} returned status: {status}")
                        return False
        except Exception as e:
            logger.error(f"❌ Ping failed to {self.ping_url}: {str(e)}")
            return False
    
    async def start(self):
        """Start the periodic pinging service"""
        self.is_running = True
        logger.info(f"🚀 Starting auto-ping service...")
        logger.info(f"🔗 URL: {self.ping_url}")
        logger.info(f"⏰ Interval: {self.interval_seconds} seconds")
        
        # Send immediate ping on startup
        await self.ping()
        
        # Start periodic pinging
        while self.is_running:
            try:
                await asyncio.sleep(self.interval_seconds)
                await self.ping()
            except asyncio.CancelledError:
                logger.info("Pinger service cancelled")
                break
            except Exception as e:
                logger.error(f"Error in ping loop: {e}")
                # Wait a bit before retrying
                await asyncio.sleep(60)
    
    async def stop(self):
        """Stop the pinging service"""
        self.is_running = False
        logger.info("🛑 Stopping auto-ping service")

# Global pinger instance
_pinger = None

def start_pinger_as_background_task(app):
    """
    Start pinger as a background task in FastAPI app
    
    Usage in main.py:
        from ping import start_pinger_as_background_task
        start_pinger_as_background_task(app)
    """
    global _pinger
    
    @app.on_event("startup")
    async def startup_pinger():
        """Start pinger on app startup"""
        global _pinger
        
        # Don't run pinger in development mode or if disabled
        if os.environ.get("DISABLE_PINGER", "").lower() == "true":
            logger.info("Pinger disabled by DISABLE_PINGER environment variable")
            return
        
        # Create and start pinger
        _pinger = RenderPinger()
        asyncio.create_task(_pinger.start())
        logger.info("✅ Auto-pinger started as background task")
    
    @app.on_event("shutdown")
    async def shutdown_pinger():
        """Stop pinger on app shutdown"""
        global _pinger
        if _pinger:
            await _pinger.stop()

def start_pinger_standalone():
    """
    Start pinger as a standalone script
    
    Usage: python ping.py
    """
    global _pinger
    
    async def main():
        """Main async function for standalone mode"""
        global _pinger
        logger.info("🚀 Starting standalone ping service...")
        
        _pinger = RenderPinger()
        
        try:
            await _pinger.start()
        except KeyboardInterrupt:
            logger.info("👋 Received keyboard interrupt, shutting down...")
            await _pinger.stop()
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            await _pinger.stop()
    
    # Run the async main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Ping service stopped")

if __name__ == "__main__":
    # Run as standalone script
    start_pinger_standalone()
