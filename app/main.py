from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, disaster, inventory, order, drone, telemetry
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
import os

app = FastAPI(
    title="Disaster Relief Drone API",
    description="Backend API for disaster relief drone system",
    version="1.0.0")

# Include routers
app.include_router(auth.router)
app.include_router(disaster.router)
app.include_router(inventory.router)
app.include_router(order.router)
app.include_router(drone.router)
app.include_router(telemetry.router)

# Configure CORS for Flutter app
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("FRONTEND_URL", "http://localhost:3000"),  # Flutter web
        "app://disaster-relief-drone",  # Flutter desktop/mobile app scheme
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Request-ID",
    ],
    expose_headers=["X-Process-Time"],
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Add rate limiting middleware (60 requests per minute for auth endpoints)
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)