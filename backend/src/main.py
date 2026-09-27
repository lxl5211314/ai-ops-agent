from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import (
    routes_analyses,
    routes_analysis_stream,
    routes_chat_stream,
    routes_conversations,
    routes_folders,
    routes_health,
    routes_kb,
    routes_projects,
)
from core.config import get_settings
from core.db import init_db
from core.errors import install_error_handlers

app = FastAPI(title="智能运维助手「小龙」", version="0.1.0")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_error_handlers(app)

API_PREFIX = "/api/v1"
for router in (
    routes_health.router,
    routes_conversations.router,
    routes_chat_stream.router,
    routes_kb.router,
    routes_folders.router,
    routes_projects.router,
    routes_analyses.router,
    routes_analysis_stream.router,
):
    app.include_router(router, prefix=API_PREFIX)


@app.on_event("startup")
def on_startup():
    init_db()
