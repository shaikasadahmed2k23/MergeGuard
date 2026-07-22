from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from webhook.github import router as webhook_router
from logs.logger import get_logger
from api.demo import router as demo_router
from api.repos import router as repos_router
from auth.github_oauth import router as auth_router
from config import FRONTEND_URL

logger = get_logger("main")

app = FastAPI(
    title="MergeGuard",
    description="Autonomous Semantic Code Review Agent",
    version="1.0.0"
)

app.include_router(demo_router, prefix="/api", tags=["Demo"])
app.include_router(repos_router, prefix="/api", tags=["Repos"])
app.include_router(auth_router, prefix="/auth", tags=["Auth"])

# CORS — now that login exists, we scope this to the actual frontend origin(s)
# instead of "*". Local dev ports included so the frontend works during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(webhook_router, prefix="/webhook", tags=["Webhook"])

@app.get("/")
async def root():
    logger.info("MergeGuard is running ✅")
    return {"status": "MergeGuard is running ✅"}

@app.get("/health")
async def health():
    return {"status": "healthy"}


from database.models import get_all_reviews, get_review_by_pr, get_stats

@app.get("/api/reviews")
async def list_reviews(repo: str = None):
    data = await get_all_reviews(repo)
    return {"reviews": data}

@app.get("/api/reviews/{pr_number}")
async def get_review(pr_number: int, repo: str):
    data = await get_review_by_pr(repo, pr_number)
    if not data:
        return {"error": "Not found"}
    return data

@app.get("/api/stats")
async def stats(repo: str = None):
    data = await get_stats(repo)
    return data