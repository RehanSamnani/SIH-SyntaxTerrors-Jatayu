import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Record start time
        start_time = time.time()
        
        # Get request details
        path = request.url.path
        method = request.method
        client_ip = request.client.host if request.client else None

        # Log request
        logger.info(
            f"Request: {method} {path} from {client_ip}",
            extra={
                "request_id": request.state.request_id,
                "method": method,
                "path": path,
                "client_ip": client_ip,
                "headers": dict(request.headers)
            }
        )

        # Process request and get response
        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # Log response
            logger.info(
                f"Response: {response.status_code} for {method} {path} took {process_time:.3f}s",
                extra={
                    "request_id": request.state.request_id,
                    "status_code": response.status_code,
                    "process_time": process_time
                }
            )
            
            # Add processing time header
            response.headers["X-Process-Time"] = str(process_time)
            return response

        except Exception as e:
            # Log error
            logger.error(
                f"Error processing {method} {path}: {str(e)}",
                exc_info=True,
                extra={
                    "request_id": request.state.request_id,
                    "method": method,
                    "path": path,
                    "error": str(e)
                }
            )
            raise