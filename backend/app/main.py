from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging import RequestLogMiddleware, configure_logging
from app.routers import materials, moments, studies

configure_logging(settings.log_level)

app = FastAPI(title="Stimulated Assistant API")
app.add_middleware(RequestLogMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(studies.router)
app.include_router(materials.router)
app.include_router(moments.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
