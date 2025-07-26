import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.config import settings
from app.routers import auth, conversations, tools
from app.db.session import engine
from app.db.session import Base
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

fastapi_app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

fastapi_app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origin,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
fastapi_app.include_router(auth.router)
fastapi_app.include_router(conversations.router)
fastapi_app.include_router(tools.router)

@fastapi_app.get("/")
async def root():
    return {
        "message": "Welcome to meAI Backend",
        "version": settings.app_version,
        "status": "running"
    }

@fastapi_app.get("/health")
async def health_check():
    return {"status": "healthy"}

sio = socketio.AsyncServer(
    cors_allowed_origins='*', 
    async_mode='asgi',
    ping_timeout=90000,
    ping_interval=25,
    max_http_buffer_size=1e8,
)

import app.routers.conversation_sockets

app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)