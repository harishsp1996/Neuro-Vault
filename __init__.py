"""
HelperGPT Application Package
AI-powered internal documentation system
"""

__version__ = "1.0.0"
__author__ = "HelperGPT Team"
__description__ = "AI-powered internal documentation and Q&A system"

# Package imports
from .main import app
from .models import *
from .database import init_db

__all__ = [
    "app",
    "init_db"
]
