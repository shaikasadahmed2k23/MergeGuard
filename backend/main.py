from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from webhook.github import router as webhook_router
from logs.logger import get_logger

logger = get_logger("main")

app = FastAPI(
    title="MergeGuard",
    description="Autonomous Semantic Code Review Agent",
    version="1.0.0"
)

# CORS - Frontend se baat karne ke liye
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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