"""
test_monitoring.py
==================
This file tests three things from app/monitoring.py:

1. RequestTimer  - Does it correctly measure how long something takes?
2. MetricsCollector - Does it correctly track request counts, errors,
                      latency, tokens, and cache stats?
3. JSON Logger   - Does it correctly output structured JSON logs?
"""

import time
import json
import logging
from io import StringIO

from app.monitoring import MetricsCollector, RequestTimer, JSONFormatter

# ─────────────────────────────────────────────
# Console Colors (just to make output pretty)
# ─────────────────────────────────────────────
GREEN  = '\033[92m'
RED    = '\033[91m'
YELLOW = '\033[93m'
BLUE   = '\033[94m'
CYAN   = '\033[96m'
RESET  = '\033[0m'
BOLD   = '\033[1m'

pass_count = 0
fail_count = 0

def check(label: str, condition: bool, expected: str, got: str):
    """
    A simple helper to print a test result.

    label     - What we are testing (e.g. "Timer measures 100ms")
    condition - True = PASS, False = FAIL
    expected  - What we expected to happen
    got       - What actually happened
    """
    global pass_count, fail_count

    status = f"{GREEN}PASS{RESET}" if condition else f"{RED}FAIL{RESET}"
    symbol = "v" if condition else "x"
    print(f"  {status} {symbol}  {BOLD}{label}{RESET}")
    print(f"       Expected : {YELLOW}{expected}{RESET}")
    print(f"       Got      : {CYAN}{got}{RESET}")

    if condition:
        pass_count += 1
    else:
        fail_count += 1

def section(title: str):
    """Print a section header."""
    print(f"\n{BLUE}{BOLD}{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}{RESET}")


# ══════════════════════════════════════════════
#  TEST 1 ─ Request Timer
#  
#  RequestTimer is a context manager that records
#  how long a block of code takes (in milliseconds).
#
#  Usage:
#     with RequestTimer() as timer:
#         do_something()
#     print(timer.elapsed_ms)   # time in ms
# ══════════════════════════════════════════════
section("1. Request Timer")

# We sleep 100ms and expect the timer to capture ≈100ms
with RequestTimer() as timer:
    time.sleep(0.1)   # 0.1 seconds = 100 milliseconds

elapsed = timer.elapsed_ms  # how many ms passed?

check(
    label     = "Timer measures ~100ms for a 0.1s sleep",
    condition = 100 <= elapsed < 200,       # allow some buffer
    expected  = "between 100ms and 200ms",
    got       = f"{elapsed:.1f}ms"
)


# ══════════════════════════════════════════════
#  TEST 2 ─ Metrics Collector
#
#  MetricsCollector keeps track of:
#  - How many requests were made
#  - How many resulted in errors
#  - Average response time (latency)
#  - Tokens sent/received to the LLM
#  - Cache hit rate (did we serve from cache or call LLM?)
#
#  We simulate 3 requests with known values, then check
#  that get_summary() returns the right numbers.
# ══════════════════════════════════════════════
section("2. Metrics Collector")

metrics = MetricsCollector()

# ── Request A: fast, successful, served from cache (no LLM call) ──
metrics.record_request(
    latency_ms=100,     # took 100ms
    input_tokens=50,    # we sent 50 tokens to the LLM
    output_tokens=80,   # LLM replied with 80 tokens
    error=False,        # it succeeded
    cache_hit=True      # answer came from cache
)

# ── Request B: slow, failed with an error, not in cache ──
metrics.record_request(
    latency_ms=500,     # took 500ms (slow)
    input_tokens=30,
    output_tokens=0,    # failed, so no output
    error=True,         # an error occurred
    cache_hit=False     # had to call LLM (missed cache)
)

# ── Request C: medium speed, successful, not in cache ──
metrics.record_request(
    latency_ms=200,
    input_tokens=20,
    output_tokens=60,
    error=False,
    cache_hit=False
)

# Now ask the collector for a summary
summary = metrics.get_summary()

print(f"\n  {YELLOW}Summary returned by get_summary():{RESET}")
for key, val in summary.items():
    print(f"    {key}: {CYAN}{val}{RESET}")
print()

# ── Check each metric individually ──

# 3 requests were made
check(
    label     = "Total requests = 3",
    condition = summary["total_requests"] == 3,
    expected  = "3",
    got       = str(summary["total_requests"])
)

# Only request B was an error
check(
    label     = "Total errors = 1",
    condition = summary["total_errors"] == 1,
    expected  = "1",
    got       = str(summary["total_errors"])
)

# 1 error out of 3 = 33.33%
check(
    label     = "Error rate = 33.33%",
    condition = summary["error_rate"] == "33.33%",
    expected  = "33.33%",
    got       = summary["error_rate"]
)

# (100 + 500 + 200) / 3 = 266.67ms
check(
    label     = "Average latency = 266.67ms",
    condition = summary["avg_latency_ms"] == 266.67,
    expected  = "266.67",
    got       = str(summary["avg_latency_ms"])
)

# 50 + 30 + 20 = 100 total input tokens
check(
    label     = "Total input tokens = 100",
    condition = summary["total_input_tokens"] == 100,
    expected  = "100",
    got       = str(summary["total_input_tokens"])
)

# 80 + 0 + 60 = 140 total output tokens
check(
    label     = "Total output tokens = 140",
    condition = summary["total_output_tokens"] == 140,
    expected  = "140",
    got       = str(summary["total_output_tokens"])
)

# 1 hit out of 3 total = 33.33%
check(
    label     = "Cache hit rate = 33.33%",
    condition = summary["cache_hit_rate"] == "33.33%",
    expected  = "33.33%",
    got       = summary["cache_hit_rate"]
)


# ══════════════════════════════════════════════
#  TEST 3 ─ JSON Logger
#
#  JSONFormatter formats every log line as a JSON
#  string instead of plain text, which makes it
#  easy to send logs to tools like Datadog or CloudWatch.
#
#  We capture what the logger writes, parse it as
#  JSON, and check that the right fields are present.
# ══════════════════════════════════════════════
section("3. JSON Logger")

# Set up a logger that writes to a string buffer
# (so we can read what it logged without printing to console)
log_buffer = StringIO()
handler = logging.StreamHandler(log_buffer)
handler.setFormatter(JSONFormatter())

logger = logging.getLogger("test-json-logger")
logger.setLevel(logging.INFO)
logger.handlers = []
logger.addHandler(handler)

# Log a message with extra metadata
logger.info("User logged in", extra={"extra_data": {"user_id": "u-42", "action": "login"}})

# Read and parse what was logged
raw_log = log_buffer.getvalue().strip()

print(f"\n  {YELLOW}Raw log output:{RESET}")
print(f"  {CYAN}{raw_log}{RESET}\n")

try:
    parsed = json.loads(raw_log)
    is_valid_json = True
except json.JSONDecodeError:
    parsed = {}
    is_valid_json = False

check(
    label     = "Log output is valid JSON",
    condition = is_valid_json,
    expected  = "valid JSON string",
    got       = "valid JSON" if is_valid_json else "INVALID JSON"
)

check(
    label     = "Log contains 'message' field",
    condition = parsed.get("message") == "User logged in",
    expected  = "User logged in",
    got       = str(parsed.get("message"))
)

check(
    label     = "Log contains 'timestamp' field",
    condition = "timestamp" in parsed,
    expected  = "timestamp key present",
    got       = "present" if "timestamp" in parsed else "MISSING"
)

check(
    label     = "Log contains 'level' = INFO",
    condition = parsed.get("level") == "INFO",
    expected  = "INFO",
    got       = str(parsed.get("level"))
)

check(
    label     = "Extra data (user_id) was merged into log",
    condition = parsed.get("user_id") == "u-42",
    expected  = "u-42",
    got       = str(parsed.get("user_id"))
)


# ══════════════════════════════════════════════
#  FINAL SCORE
# ══════════════════════════════════════════════
total = pass_count + fail_count
color = GREEN if fail_count == 0 else RED
print(f"\n{CYAN}{BOLD}{'='*55}")
print(f"  Final Results: {color}{pass_count}/{total} Tests Passed{RESET}{CYAN}{BOLD}")
print(f"{'='*55}{RESET}\n")
