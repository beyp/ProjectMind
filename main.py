"""ProjectMind — Point d entree principal."""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

from core.database import init_db
from api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise la base de donnees au demarrage."""
    await init_db()
    yield


app = FastAPI(
    title="ProjectMind",
    description="Gestionnaire de projets intelligent — Premier Tech",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/health")
async def health():
    return {"status": "ok", "app": "ProjectMind", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8766))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
