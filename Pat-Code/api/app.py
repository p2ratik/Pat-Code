import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from redis.asyncio import Redis

from api.cache.conv_context import ConversationContextRepository
from api.db.database import CloudDatabase
from api.auth.service import AuthService
from api.pat_service import PATService
from api.routes import users, chat
from config.config import Config, ModelConfig, ApprovalPolicy
from tools.registry import create_default_registry

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required")

    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        raise RuntimeError("REDIS_URL environment variable is required")

    logger.info("Validating database schema before starting API")
    db = CloudDatabase(database_url)
    await db.initialize()
    redis = Redis.from_url(redis_url, decode_responses=True)
    conversation_context_repo = ConversationContextRepository(db, redis)

    app.state.db = db
    app.state.redis = redis
    app.state.auth_service = AuthService(db)
    app.state.conversation_context_repo = conversation_context_repo

    # Build the base tool registry ONCE at startup.
    # Per-request runtimes filter this instead of re-scanning builtins.
    # Phase 4: add event_bus=EventBus() here.
    # Phase 5: add qdrant=AsyncQdrantClient() here.
    base_config = Config(
        model=ModelConfig(name="gpt-4.1-mini"),
        cwd=Path.cwd(),
        approval=ApprovalPolicy.AUTO,
    )
    app.state.base_tool_registry = create_default_registry(base_config)

    app.state.pat_service = PATService(
        db=db,
        conversation_context_repo=conversation_context_repo,
        base_tool_registry=app.state.base_tool_registry,
    )

    logger.info("PAT API started")
    yield

    # ── Shutdown ──
    await redis.aclose()
    await db.shutdown()
    logger.info("PAT API shut down")


app = FastAPI(
    title="PAT API",
    description="""PAT — Personal Agent Terminal Cloud API

## Quick start
1. `POST /users` — create a user, copy the `id`
2. `POST /users/{id}/token` — get a JWT, copy `access_token`
3. Click **Authorize** above, paste `Bearer <token>`
4. `POST /chat` — start chatting
""",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router, prefix="/users")
app.include_router(chat.router, prefix="/chat")


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Add Bearer security scheme so the Authorize button appears in /docs
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    for path in schema["paths"].values():
        for operation in path.values():
            operation.setdefault("security", [{"BearerAuth": []}])
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi
