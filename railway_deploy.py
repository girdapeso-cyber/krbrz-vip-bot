#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Railway Deployment Checker for KRBRZ VIP Bot
Bu script deployment öncesi kontrolları yapar
"""

import os
import sys
import json
from pathlib import Path

def check_file_exists(filepath, description):
    """Check if required file exists"""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description} eksik: {filepath}")
        return False

def check_requirements():
    """Check requirements.txt content"""
    if not os.path.exists('requirements.txt'):
        return False
    
    with open('requirements.txt', 'r') as f:
        content = f.read()
        required_packages = [
            'python-telegram-bot',
            'httpx',
            'Pillow',
            'Flask',
            'google-generativeai'
        ]
        
        missing = []
        for package in required_packages:
            if package not in content:
                missing.append(package)
        
        if missing:
            print(f"❌ requirements.txt'de eksik paketler: {missing}")
            return False
        else:
            print("✅ requirements.txt tamam")
            return True

def check_main_py():
    """Check main.py for Railway compatibility"""
    if not os.path.exists('main.py'):
        return False
    
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()
        
        checks = [
            ('Flask app tanımı', 'app = flask_app'),
            ('PORT environment variable', 'os.environ.get(\'PORT\''),
            ('Flask run config', 'flask_app.run(host=\'0.0.0.0\''),
            ('Threading import', 'from threading import Thread')
        ]
        
        all_good = True
        for check_name, check_pattern in checks:
            if check_pattern in content:
                print(f"✅ {check_name} bulundu")
            else:
                print(f"❌ {check_name} eksik: {check_pattern}")
                all_good = False
        
        return all_good

def create_gitignore():
    """Create .gitignore file"""
    gitignore_content = """# Bot files
bot_config.json
bot_data.db
bot.log
.env

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual env
venv/
ENV/
env/
.venv/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db
"""
    
    with open('.gitignore', 'w', encoding='utf-8') as f:
        f.write(gitignore_content)
    
    print("✅ .gitignore oluşturuldu")

def main():
    """Main deployment checker"""
    print("🚀 KRBRZ VIP Bot - Railway Deployment Checker")
    print("=" * 50)
    
    required_files = [
        ('main.py', 'Ana bot dosyası'),
        ('requirements.txt', 'Python dependencies'),
        ('Procfile', 'Railway process tanımı'),
        ('railway.json', 'Railway yapılandırması'),
        ('runtime.txt', 'Python version'),
        ('.env.example', 'Environment variables template')
    ]
    
    all_files_ok = True
    for filepath, description in required_files:
        if not check_file_exists(filepath, description):
            all_files_ok = False
    
    print("\n📋 İçerik Kontrolleri:")
    print("-" * 30)
    
    requirements_ok = check_requirements()
    main_py_ok = check_main_py()
    
    # Create .gitignore if not exists
    if not os.path.exists('.gitignore'):
        create_gitignore()
    
    print("\n🌍 Environment Variables Rehberi:")
    print("-" * 40)
    print("Railway dashboard'da şu değişkenleri ekleyin:")
    print("• BOT_TOKEN=your_telegram_bot_token")
    print("• ADMIN_USER_ID=your_telegram_user_id") 
    print("• GEMINI_API_KEY=your_gemini_api_key")
    
    print("\n📊 Sonuç:")
    print("-" * 20)
    
    if all_files_ok and requirements_ok and main_py_ok:
        print("✅ Tüm kontroller başarılı! Railway'e deploy etmeye hazır.")
        print("\n🔄 Sonraki adımlar:")
        print("1. GitHub'a push edin")
        print("2. Railway'de 'New Project' → 'Deploy from GitHub'")
        print("3. Environment variables'ları ekleyin")
        print("4. Deploy'u bekleyin")
        return True
    else:
        print("❌ Bazı kontroller başarısız. Lütfen düzeltin.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)