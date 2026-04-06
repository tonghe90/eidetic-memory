from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.routers import connectors, ingest, settings_router, search

app = FastAPI(title="LLM Wiki", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(connectors.router)
app.include_router(ingest.router)
app.include_router(settings_router.router)
app.include_router(search.router)


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve frontend build if it exists
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")
