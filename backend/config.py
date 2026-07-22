import os
from dotenv import load_dotenv

load_dotenv()

# GitHub (also used as the fallback single-tenant identity for repos that
# haven't been onboarded through the new multi-tenant flow yet)
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# GitHub OAuth App — used for "Sign in with GitHub" (multi-tenant login).
# Create this at github.com/settings/developers -> OAuth Apps -> New OAuth App
GITHUB_OAUTH_CLIENT_ID = os.getenv("GITHUB_OAUTH_CLIENT_ID")
GITHUB_OAUTH_CLIENT_SECRET = os.getenv("GITHUB_OAUTH_CLIENT_SECRET")

# Groq (legacy — unused by the live pipeline, kept for backend/agents/*.py)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Gemini — the live pipeline's default/trial key. Per-user BYOK keys are
# stored encrypted per repo_config and used instead of this when present.
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Discord (fallback single-tenant webhook — same idea as GITHUB_TOKEN above)
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Session + encryption
JWT_SECRET = os.getenv("JWT_SECRET")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")  # Fernet key — encrypts stored user tokens/API keys

# Frontend (for OAuth redirect after login)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Backend's own public URL (for registering GitHub webhooks pointing back at us)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Trial limits (BYOK-free trial requests per repo before a user must add their own key)
FREE_TRIAL_REQUESTS = int(os.getenv("FREE_TRIAL_REQUESTS", "5"))

# App
APP_ENV = os.getenv("APP_ENV", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
