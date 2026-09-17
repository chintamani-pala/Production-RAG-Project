import time
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from langsmith import traceable
from dotenv import load_dotenv

from app.config import get_settings
from app.models import (
    ChatRequest, 
    ChatResponse,
    HealthResponse,
    MetricsResponse,
    ErrorResponse
)

from app.security import SecurityPipeline
from app.cache import ResponseCache
from app.monitoring import get_logger, MetricsCollector, RequestTimer
from app.agent import ProductionAgent

load_dotenv()


security: SecurityPipeline | None = None
cache: ResponseCache | None = None
metrics: MetricsCollector | None = None
agent: ProductionAgent | None = None
logger = get_logger()


# ==== Lifespan (startup/shotdown)]

async def lifespan(app: FastAPI):
    """
    Initialize all components on startup, clean on shutdown
    This is the modern FastAPI pattern(replaces @app.on_event)
    """

    global security, cache, metrics, agent

    settings = get_settings()

    logger.info("Starting production API...", extra={"extra_data": {
        "environment": settings.APP_ENV,
        "primary_model": settings.LITELLM_PRIMARY_CHAT_MODEL,
        "tracing_enabled": settings.LANGCHAIN_TRACING_V2
    }})

    # Initialize components
    security = SecurityPipeline()
    cache = ResponseCache(ttl_seconds=settings.CACHE_TTL_SECONDS)
    metrics = MetricsCollector()
    agent=ProductionAgent()

    logger.info("All components initialized. Ready to serve requests.")

    yield # App is running

    # Shutdown
    logger.info("Shutting down server...", extra={"extra_data": metrics.get_summary()})

# ==== Rate Limiter ====
limiter = Limiter(key_func=get_remote_address)

# ==== FastAPI app ====
app = FastAPI(
    title="Production AI Chat API",
    description="A production-ready chat API with security, caching, and observability.",
    version="1.0.0",
    lifespan=lifespan
)

app.state.limiter = limiter

# ==== Error Handlers ====
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors."""
    logger.warning("Rate limit exceeded", extra={"extra_data": {
        "ip_address": request.client.host if request.client else "unknown"
    }})
    return JSONResponse(
        status_code=429,
        content=ErrorResponse(
            error_type="RATE_LIMIT_EXCEEDED",
            error_message="Too many requests. Please slow down.",
            request_id=request.state.request_id
        ).model_dump()
    )




# ================================================
# ENDPOINTS
# ================================================

@app.post("/chat", response_model=ChatResponse)
@limiter.limit(get_settings().RATE_LIMIT)
@traceable(name="chat_endpoint")
async def chat(request: Request, body: ChatRequest):
    """
    Main chat endpoint

    Flow:
    1. Security check(Injection, PII masking)
    2. Cache lookup
    3. Langgraph agent invoke(if cache miss)
    4. Output validation
    5. Cache store
    6. Return response
    """

    with RequestTimer() as timer:
        security_notes = []
        is_allowed, cleaned_message, notes = security.check_input(body.message)
        security_notes.extend(notes)

        # if not allowed
        if not is_allowed:
            logger.warning("Request blocked by security", extra={
                "extra_data": {
                    "reason": notes,
                    "thread_id": body.thread_id
                }
            })
            metrics.record_request(latency_ms=0, error=True)
            raise HTTPException(
                status_code=400,
                detail="Your message was blocked by our security filters."
            )

        # ---- Step 2: Cache Lookup ----
        cached_response = cache.get(cleaned_message)
        if cached_response is not None:
            metrics.record_request(latency_ms=0, cache_hit=True)
            logger.info("Cache hit", extra={"extra_data":{
                "thread_id": body.thread_id
            }})

            return ChatResponse(
                response=cached_response,
                thread_id=body.thread_id,
                model_used="cache",
                cached=True,
                processing_time_ms=0,
                security_notes=security_notes
            )

        # ---- Step 3: Langgraph Agent Invoke ----
        try:
            result = agent.invoke(cleaned_message)
        except Exception as e:
            logger.error(f"Agent invocation failed: {e}", extra={"extra_data":{
                "thread_id": body.thread_id,
                "error": str(e) 
            }})
            metrics.record_request(latency_ms=0, error=True)
            raise HTTPException(
                status_code=500,
                detail="An error occured while processing your request."
            )
        response_text = result['response']
        
        model_used=result['model_used']
        
        # ---- Step 4: Output Validation ----
        valid_response, output_warnings =  security.check_output(response_text)
        security_notes.extend(output_warnings)

        # ---- Step 5 : Cache Store ----
        cache.set(cleaned_message, valid_response)
    
    # ---- Step 6: Log and Record Metrics ---- 
    input_tokens = int(len(cleaned_message.split()) * 1.3)
    output_tokens = int(len(valid_response.split()) * 1.3)

    metrics.record_request(
        latency_ms=timer.elapsed_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_hit=False
    )

    if security_notes:
        logger.info("Security notes", extra={"extra_data": {
            "notes": security_notes,
            "thread_id": body.thread_id
        }})
    
    logger.info("Request Completed", extra={"extra_data":{
        "thread_id": body.thread_id,
        "model_used": model_used,
        "latency_ms": round(timer.elapsed_ms, 2)
    }})

    return ChatResponse(
        response=valid_response,
        thread_id=body.thread_id,
        model_used=model_used,
        cached=False,
        processing_time_ms=round(timer.elapsed_ms, 2),
        security_notes=security_notes
    )
    

        
        

@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check for Docker/Kubernetes"""
    settings = get_settings()

    checks={
        "agent": agent is not None,
        "security": security is not None,
        "cache": cache is not None
    }
    
    all_healthy = all(checks.values())

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        environment=settings.APP_ENV,
        checks=checks
    )


@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Metrics for monitoring dashboard"""
    summary = metrics.get_summary()
    return MetricsResponse(**summary)

@app.get("/cache/stats")
async def cache_stats():
    """Cache performance statistics"""
    return cache.stats