from fastapi import APIRouter

from app.api.v1.routes import (
    agent_runs,
    documents,
    evaluations,
    experiences,
    health,
    jobs,
    prep_packages,
    resumes,
)


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(documents.router, tags=["documents"])
api_router.include_router(resumes.router, tags=["resumes"])
api_router.include_router(jobs.router, tags=["jobs"])
api_router.include_router(experiences.router, tags=["experiences"])
api_router.include_router(prep_packages.router, tags=["prep-packages"])
api_router.include_router(evaluations.router, tags=["evaluations"])
api_router.include_router(agent_runs.router, tags=["agent-runs"])
