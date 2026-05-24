# TODO: implement src/agent/core/settings.py
# src/agent/core/settings.py
from pathlib import Path
from dotenv import load_dotenv

# Get the project root (two levels up from this file)
# This file is at: src/agent/core/settings.py
# Project root is: linkedin-ai-agent/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Always load THIS project's .env — never search parent folders
load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=True)

# Now import settings
import os

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_MODEL_FAST = os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")

# LinkedIn
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
LINKEDIN_PUBLISHER_CLIENT_ID = os.getenv("LINKEDIN_PUBLISHER_CLIENT_ID")
LINKEDIN_PUBLISHER_CLIENT_SECRET = os.getenv("LINKEDIN_PUBLISHER_CLIENT_SECRET")
LINKEDIN_REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI")
LINKEDIN_ORG_URN = os.getenv("LINKEDIN_ORG_URN")

# Database
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

# Langfuse
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

# Tavily
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
