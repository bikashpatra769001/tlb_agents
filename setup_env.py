#!/usr/bin/env python3
"""
Setup script for configuring environment variables for the agents-with-strands project.
"""

import os
import sys

def setup_anthropic_key():
    """Setup Anthropic API key"""
    print("🤖 Setting up Anthropic Claude API")
    print("=" * 50)
    
    current_key = os.getenv("ANTHROPIC_API_KEY")
    if current_key:
        print(f"✅ ANTHROPIC_API_KEY is already set (ends with: ...{current_key[-8:]})")
        update = input("Do you want to update it? (y/N): ").lower().strip()
        if update != 'y':
            return
    
    print("\n📝 To get your Anthropic API key:")
    print("1. Go to https://console.anthropic.com/")
    print("2. Sign up or log in")
    print("3. Go to API Keys section")
    print("4. Create a new API key")
    print()
    
    api_key = input("Enter your Anthropic API key: ").strip()
    
    if not api_key:
        print("❌ No API key provided. Skipping setup.")
        return
    
    if not api_key.startswith("sk-ant-"):
        print("⚠️  Warning: API key doesn't look like a valid Anthropic key (should start with 'sk-ant-')")
        confirm = input("Continue anyway? (y/N): ").lower().strip()
        if confirm != 'y':
            return
    
    # Create .env file
    env_content = f"ANTHROPIC_API_KEY={api_key}\n"
    
    with open(".env", "w") as f:
        f.write(env_content)
    
    print("✅ API key saved to .env file")
    print("🔒 Make sure .env is in your .gitignore to keep your key secure!")
    
    # Check if .gitignore exists and add .env if needed
    gitignore_path = ".gitignore"
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r") as f:
            gitignore_content = f.read()
        
        if ".env" not in gitignore_content:
            with open(gitignore_path, "a") as f:
                f.write("\n# Environment variables\n.env\n")
            print("✅ Added .env to .gitignore")
    else:
        with open(gitignore_path, "w") as f:
            f.write("# Environment variables\n.env\n")
        print("✅ Created .gitignore with .env")

def main():
    print("🚀 agents-with-strands Environment Setup")
    print("=" * 50)
    
    setup_anthropic_key()
    
    print("\n🎉 Setup complete!")
    print("\n📋 Next steps:")
    print("1. Run: python api_server.py")
    print("2. Load the Chrome extension")
    print("3. Navigate to https://bhulekh.ori.nic.in/SRoRFront_Uni.aspx")
    print("4. Click 'Help me understand' to start chatting!")

if __name__ == "__main__":
    main()