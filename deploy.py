# File: deploy.py
import subprocess
import sys

def setup_deployment():
    """One-click setup script"""
    print("🔧 Setting up deployment...")
    
    # Create requirements.txt
    requirements = """aiogram==3.0.0b7
fastapi==0.104.1
uvicorn[standard]==0.24.0
supabase==1.0.3
python-jose[cryptography]==3.3.0
pydantic==2.5.0
httpx==0.25.1
"""
    
    with open("requirements.txt", "w") as f:
        f.write(requirements)
    
    # Create render.yaml
    render_config = """services:
  - type: web
    name: telegram-token-bot
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python -m uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PORT
        value: 10000
      - key: BOT_TOKEN
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_KEY
        sync: false
      - key: ADMIN_ID
        sync: false
    autoDeploy: true
"""
    
    with open("render.yaml", "w") as f:
        f.write(render_config)
    
    print("✅ Files created!")
    print("\nNext steps:")
    print("1. Push to GitHub")
    print("2. Go to render.com")
    print("3. Connect repository")
    print("4. Add environment variables")
    print("5. Deploy!")

if __name__ == "__main__":
    setup_deployment()
