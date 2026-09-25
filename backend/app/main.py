"""FastAPI application entrypoint. Routers are mounted under /api/v1."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.domains.api_performer.router import router as api_performer_router
from app.domains.automation.router import router as automation_router
from app.domains.environments.router import router as environments_router
from app.domains.executions.router import router as executions_router
from app.domains.identity.router import router as identity_router
from app.domains.performance.router import router as performance_router
from app.domains.projects.router import router as projects_router
from app.domains.reporting.router import router as reporting_router
from app.domains.requirements.router import router as requirements_router
from app.domains.schedules.router import router as schedules_router
from app.domains.testcases.router import router as testcases_router

settings = get_settings()

app = FastAPI(title=settings.project_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_V1_PREFIX = "/api/v1"

app.include_router(identity_router, prefix=API_V1_PREFIX)
app.include_router(projects_router, prefix=API_V1_PREFIX)
app.include_router(requirements_router, prefix=API_V1_PREFIX)
app.include_router(testcases_router, prefix=API_V1_PREFIX)
app.include_router(environments_router, prefix=API_V1_PREFIX)
app.include_router(automation_router, prefix=API_V1_PREFIX)
app.include_router(executions_router, prefix=API_V1_PREFIX)
app.include_router(reporting_router, prefix=API_V1_PREFIX)
app.include_router(schedules_router, prefix=API_V1_PREFIX)
app.include_router(api_performer_router, prefix=API_V1_PREFIX)
app.include_router(performance_router, prefix=API_V1_PREFIX)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
