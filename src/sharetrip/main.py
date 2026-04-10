from fastapi import Depends, FastAPI

from sharetrip.api.routers import auth, expenses, settlements, trips
from sharetrip.config import Settings, get_settings

app = FastAPI(
    title="ShareTrip API",
    description="Enterprise-grade settlement engine with Clean Architecture",
    version="0.1.0",
)

app.include_router(auth.router)
app.include_router(trips.router)
app.include_router(expenses.router)
app.include_router(settlements.router)


@app.get("/health", tags=["Monitoring"])
def health_check(settings: Settings = Depends(get_settings)):
    return {"status": "healthy", "version": "0.1.0", "env": settings.app_env}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
