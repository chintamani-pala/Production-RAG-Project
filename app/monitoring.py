import logging
import json
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable

class JSONFormatter(logging.Formatter):
    """Format logs as JSON for log aggregation."""

    def format(self, record):
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }

        # Merge any extra data attached to the record.
        if hasattr(record, "extra_data"):
            log_obj.update(record.extra_data)

        return json.dumps(log_obj)

def get_logger(name: str="production-api") -> logging.Logger:
    """
    Create a structured JSON logger.
    """

    logger = logging.getLogger(name)

    if not logger.handlers:
        handlers = logging.StreamHandler()
        handlers.setFormatter(JSONFormatter())
        logger.addHandler(handlers)
        logger.setLevel(logging.INFO)

    return logger


# === Metrics Collection ===
class MetricsCollector:
    """Collect and aggregate metrics."""
    #NOTE: In production use promithious for monitoring. This is just for educational purposes.
    def __init__(self):
        self._requests_total=0
        self._errors_total=0
        self._latency_sum=0.0
        self._latency_count=0
        self._tokens_input=0
        self._tokens_output=0
        self._cache_hits=0
        self._cache_misses=0


    def record_request(
        self,
        latency_ms: float=0,
        input_tokens: int=0,
        output_tokens: int=0,
        error: bool = False,
        cache_hit: bool = False,
    ):
        self._requests_total += 1
        self._latency_sum += latency_ms
        self._latency_count += 1
        self._tokens_input += input_tokens
        self._tokens_output += output_tokens

        if error:
            self._errors_total += 1

        if cache_hit:
            self._cache_hits += 1
        else:
            self._cache_misses += 1

    def get_summary(self) -> dict:
        avg_latency = (
            self._latency_sum / self._latency_count
            if self._latency_count > 0
            else 0
        )
        error_rate = (
            self._errors_total / self._requests_total
            if self._requests_total > 0
            else 0
        )
        cache_hit_rate = (
            self._cache_hits
            / (self._cache_hits + self._cache_misses)
            if (self._cache_hits + self._cache_misses) > 0
            else 0
        )

        return {
            "total_requests": self._requests_total,
            "total_errors": self._errors_total,
            "error_rate": f"{error_rate:.2%}",
            "avg_latency_ms": round(avg_latency, 2),
            "total_input_tokens": self._tokens_input,
            "total_output_tokens": self._tokens_output,
            "cache_hit_rate": f"{cache_hit_rate:.2%}",
        }

class RequestTimer:
    """Context m,anager for timing requests"""

    def __enter__(self):
        self.start = time.time()
        return self
    
    def __exit__(self, *args):
        self.elapsed_ms = (time.time()-self.start) * 1000

    
