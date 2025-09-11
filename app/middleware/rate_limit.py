from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
import time
from collections import defaultdict
import asyncio

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute=60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = defaultdict(list)
        self.lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next):
        # Only apply rate limiting to auth endpoints
        if "/auth/" in request.url.path:
            client_ip = request.client.host if request.client else "unknown"
            
            async with self.lock:
                # Remove requests older than 1 minute
                current_time = time.time()
                self.request_counts[client_ip] = [
                    req_time for req_time in self.request_counts[client_ip]
                    if current_time - req_time < 60
                ]
                
                # Check if rate limit is exceeded
                if len(self.request_counts[client_ip]) >= self.requests_per_minute:
                    raise HTTPException(
                        status_code=429,
                        detail="Rate limit exceeded. Please try again later."
                    )
                
                # Add current request
                self.request_counts[client_ip].append(current_time)

        response = await call_next(request)
        return response