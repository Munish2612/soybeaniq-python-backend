import os
import secrets
from fastapi import FastAPI, Header, HTTPException
from .schemas import OptimizeRequest, OptimizeResponse
from .optimizer import optimize

app = FastAPI(title="SoybeanIQ Optimization API", version="1.0.0")
SERVICE_KEY = os.getenv("SOYBEANIQ_SERVICE_KEY", "")

@app.middleware("http")
async def protect_api(request, call_next):
    if request.url.path not in ("/health", "/docs", "/openapi.json", "/redoc"):
        supplied = request.headers.get("x-soybeaniq-service-key", "")
        if not SERVICE_KEY or not secrets.compare_digest(supplied, SERVICE_KEY):
            return __import__("starlette.responses", fromlist=["JSONResponse"]).JSONResponse({"detail":"Unauthorized"}, status_code=401)
    return await call_next(request)

@app.get("/health")
def health():
    return {"ok": True, "service": "soybeaniq-python-optimizer", "solver": "OR-Tools CP-SAT"}

@app.post("/v1/optimize", response_model=OptimizeResponse)
def optimize_procurement(payload: OptimizeRequest):
    try:
        return optimize(payload)
    except Exception as exc:
        # Keep internals out of client responses; platform logs retain exception details.
        raise HTTPException(status_code=500, detail="Optimization failed. Check service logs and input data.") from exc
