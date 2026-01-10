# ===================================================
# FILE: ping.py
# AUTO-PING SERVICE TO PREVENT RENDER FROM SLEEPING
# ===================================================

import asyncio
import aiohttp
import logging
import os
import socket
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ping_service")

class RenderPinger:
    """Service to ping Render URL periodically to prevent sleep"""
    
    def __init__(self, ping_url=None, interval_minutes=8):
        """
        Initialize the pinger
        
        Args:
            ping_url: URL to ping (if None, tries to auto-detect)
            interval_minutes: How often to ping (default: 8 minutes)
        """
        self.ping_url = ping_url or self._get_service_url()
        self.interval_seconds = interval_minutes * 60
        self.is_running = False
        self.ping_count = 0
        logger.info(f"Initialized pinger for: {self.ping_url}")
        logger.info(f"Interval: {interval_minutes} minutes ({self.interval_seconds} seconds)")
    
    def _get_service_url(self):
        """Get the service URL for pinging"""
        # Priority 1: Use explicitly set PING_URL
        ping_url = os.environ.get("PING_URL", "")
        if ping_url:
            return ping_url.rstrip('/')
        
        # Priority 2: Use WEBHOOK_URL without /webhook
        webhook_url = os.environ.get("WEBHOOK_URL", "")
        if webhook_url:
            return webhook_url.replace("/webhook", "").rstrip('/')
        
        # Priority 3: Use RENDER_EXTERNAL_URL
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
        if render_url:
            return render_url.rstrip('/')
        
        # Priority 4: Construct from service name
        service_name = os.environ.get("RENDER_SERVICE_NAME", "")
        if service_name:
            return f"https://{service_name}.onrender.com"
        
        # Priority 5: Try to get hostname (for local testing)
        try:
            hostname = socket.gethostname()
            if 'localhost' in hostname or '127.0.0.1' in hostname:
                return "http://localhost:8000"
        except:
            pass
        
        # Final fallback
        return "https://personal-api-generator.onrender.com"
    
    async def ping(self):
        """Send a ping request to keep the service awake"""
        self.ping_count += 1
        ping_num = self.ping_count
        
        # Try multiple endpoints
        endpoints = [
            f"{self.ping_url}/health",
            f"{self.ping_url}/",
            f"{self.ping_url}"
        ]
        
        success = False
        last_error = ""
        
        for endpoint in endpoints:
            try:
                logger.debug(f"Ping #{ping_num}: Trying {endpoint}")
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                    async with session.get(endpoint, timeout=10) as response:
                        status = response.status
                        if 200 <= status < 300:
                            logger.info(f"✅ Ping #{ping_num} successful to {endpoint} - Status: {status}")
                            success = True
                            break
                        else:
                            logger.warning(f"⚠️ Ping #{ping_num} to {endpoint} returned status: {status}")
            except asyncio.TimeoutError:
                last_error = f"Timeout connecting to {endpoint}"
                logger.warning(f"⏰ Ping #{ping_num} timeout for {endpoint}")
                continue
            except Exception as e:
                last_error = str(e)
                logger.warning(f"⚠️ Ping #{ping_num} failed for {endpoint}: {e}")
                continue
        
        if not success:
            logger.error(f"❌ All ping attempts failed for ping #{ping_num}. Last error: {last_error}")
        
        return success
    
    async def start(self):
        """Start the periodic pinging service"""
        self.is_running = True
        logger.info(f"🚀 Starting auto-ping service...")
        logger.info(f"🔗 URL: {self.ping_url}")
        logger.info(f"⏰ Interval: {self.interval_seconds} seconds")
        
        # Initial ping
        await self.ping()
        
        # Start periodic pinging
        while self.is_running:
            try:
                await asyncio.sleep(self.interval_seconds)
                await self.ping()
                
                # Log every 10th ping for monitoring
                if self.ping_count % 10 == 0:
                    logger.info(f"📊 Pinger status: {self.ping_count} pings sent, still running")
                    
            except asyncio.CancelledError:
                logger.info("Pinger service cancelled")
                break
            except Exception as e:
                logger.error(f"Error in ping loop: {e}")
                # Wait a bit before retrying, but don't stop
                await asyncio.sleep(60)
    
    async def stop(self):
        """Stop the pinging service"""
        self.is_running = False
        logger.info("🛑 Stopping auto-ping service")
        logger.info(f"📊 Total pings sent: {self.ping_count}")

if __name__ == "__main__":
    # Run as standalone script for testing
    async def test_pinger():
        pinger = RenderPinger()
        await pinger.start()
    
    asyncio.run(test_pinger())
