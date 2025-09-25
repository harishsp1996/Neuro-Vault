#!/usr/bin/env python3
"""
HelperGPT Setup Script
Automated installation and configuration
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(command, description=""):
    """Run shell command and handle errors"""
    print(f"🔧 {description}")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Error: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"❌ Error running command: {str(e)}")
        return False

def check_python_version():
    """Check Python version compatibility"""
    print("🐍 Checking Python version...")
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True

def create_virtual_environment():
    """Create virtual environment"""
    if Path("venv").exists():
        print("📦 Virtual environment already exists")
        return True

    print("📦 Creating virtual environment...")
    return run_command(f"{sys.executable} -m venv venv", "Creating virtual environment")

def install_dependencies():
    """Install Python dependencies"""
    print("📚 Installing dependencies...")
    venv_python = "venv/Scripts/python" if os.name == "nt" else "venv/bin/python"
    venv_pip = "venv/Scripts/pip" if os.name == "nt" else "venv/bin/pip"

    commands = [
        f"{venv_pip} install --upgrade pip",
        f"{venv_pip} install -r requirements.txt"
    ]

    for cmd in commands:
        if not run_command(cmd):
            return False

    return True

def setup_environment():
    """Set up environment configuration"""
    print("⚙️ Setting up environment configuration...")

    if not Path(".env").exists():
        shutil.copy(".env.example", ".env")
        print("✅ Created .env file from template")
        print("⚠️  Please edit .env with your Azure OpenAI credentials before running!")
        return False
    else:
        print("✅ .env file already exists")
        return True

def create_directories():
    """Create necessary directories"""
    print("📁 Creating directories...")
    directories = ["uploads", "backups"]

    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Created {directory}/ directory")

    return True

def test_installation():
    """Test the installation"""
    print("🧪 Testing installation...")
    venv_python = "venv/Scripts/python" if os.name == "nt" else "venv/bin/python"

    test_command = f"{venv_python} -c \"import fastapi, openai, faiss, sqlalchemy; print('All packages imported successfully')\"

    return run_command(test_command, "Testing package imports")

def main():
    """Main setup function"""
    print("🤖 HelperGPT Setup Script")
    print("=" * 50)

    # Step 1: Check Python version
    if not check_python_version():
        sys.exit(1)

    # Step 2: Create virtual environment
    if not create_virtual_environment():
        print("❌ Failed to create virtual environment")
        sys.exit(1)

    # Step 3: Install dependencies
    if not install_dependencies():
        print("❌ Failed to install dependencies")
        sys.exit(1)

    # Step 4: Set up environment
    env_configured = setup_environment()

    # Step 5: Create directories
    if not create_directories():
        print("❌ Failed to create directories")
        sys.exit(1)

    # Step 6: Test installation
    if not test_installation():
        print("❌ Installation test failed")
        sys.exit(1)

    print("\n🎉 Setup completed successfully!")
    print("\n📋 Next Steps:")

    if not env_configured:
        print("1. ⚠️  Edit .env file with your Azure OpenAI credentials")
        print("2. 🚀 Run: ./start.sh (Linux/Mac) or start.bat (Windows)")
    else:
        print("1. 🚀 Run: ./start.sh (Linux/Mac) or start.bat (Windows)")

    print("3. 🌐 Open http://localhost:8000 in your browser")
    print("4. 📖 Check API docs at http://localhost:8000/docs")
    print("\n👨‍💼 Admin Login: admin / password123")

if __name__ == "__main__":
    main()
