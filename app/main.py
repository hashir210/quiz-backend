from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import auth, quizzes, sessions
from app.ws.router import router as ws_router

app = FastAPI(
    title="Quiz App API",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,     prefix="/api/auth",     tags=["Auth"])
app.include_router(quizzes.router,  prefix="/api/quizzes",  tags=["Quizzes"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])
app.include_router(ws_router,       tags=["WebSocket"])


@app.get("/")
def root():
    return {"status": "Quiz App API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}