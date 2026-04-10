from fastapi import FastAPI

from fastapi.responses import JSONResponse

app = FastAPI(
    title="ShareTrip API",
    description="Enterprise-grade settlement engine with Clean Architecture",
    version="0.1.0",
)

@app.get("/health", tags=["Monitoring"])
async def health_check():
    """
    Vérifie que l'API est en ligne. 
    Plus tard, on ajoutera ici les tests de connexion à Redis et Vault.
    """
    return JSONResponse(
        content={
            "status": "healthy",
            "version": "0.1.0",
            "services": {
                "api": "up",
                "vault": "pending",  # À implémenter
                "redis": "pending"   # À implémenter
            }
        },
        status_code=200
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)