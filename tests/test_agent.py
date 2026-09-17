"""
test_agent.py
=============
Tests for app/agent.py - ProductionAgent

Covers:
1. Happy path  - primary LLM succeeds -> response returned with model_used="primary"
2. Fallback    - primary fails, fallback succeeds -> model_used="fallback"
3. Full error  - both LLMs fail -> graceful error message, model_used="error_handler"
4. Retry count - primary_llm called once, fallback_llm called once on primary failure
5. Short-circuit - fallback never called when primary succeeds
6. Return shape - invoke() always contains required keys

All tests use unittest.mock to patch ChatLiteLLM so no real API calls are made.
"""

import sys
import os

# Ensure the project root is on sys.path so `app.*` imports resolve
# when the script is run directly (e.g. `python tests/test_agent.py`)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage

# ─────────────────────────────────────────────
# Console Colors
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
    """Simple test assertion helper with coloured output."""
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


# ─────────────────────────────────────────────
# Shared mock settings fixture
# ─────────────────────────────────────────────
def _mock_settings():
    settings = MagicMock()
    settings.LITELLM_PRIMARY_CHAT_MODEL  = "gpt-4o"
    settings.LITELLM_FALLBACK_CHAT_MODEL = "gpt-3.5-turbo"
    settings.LITELLM_CHAT_API_KEY        = "test-key"
    settings.MAX_RETRIES                 = 3
    return settings


def _make_agent(primary_side_effect=None, fallback_side_effect=None,
                primary_return=None, fallback_return=None):
    """
    Build a ProductionAgent with mocked LLMs and settings.

    primary_side_effect  - exception to raise on primary_llm.invoke (or None)
    fallback_side_effect - exception to raise on fallback_llm.invoke (or None)
    primary_return       - AIMessage returned by primary_llm (if no exception)
    fallback_return      - AIMessage returned by fallback_llm (if no exception)
    """
    with patch("app.agent.get_settings", return_value=_mock_settings()), \
         patch("app.agent.ChatLiteLLM") as MockChatLiteLLM:

        primary_mock  = MagicMock()
        fallback_mock = MagicMock()
        MockChatLiteLLM.side_effect = [primary_mock, fallback_mock]

        if primary_side_effect:
            primary_mock.invoke.side_effect = primary_side_effect
        else:
            primary_mock.invoke.return_value = primary_return or AIMessage(content="Hello from primary")

        if fallback_side_effect:
            fallback_mock.invoke.side_effect = fallback_side_effect
        else:
            fallback_mock.invoke.return_value = fallback_return or AIMessage(content="Hello from fallback")

        from app.agent import ProductionAgent
        agent = ProductionAgent()
        # Replace the real LLM references so invoke() uses our mocks
        agent.primary_llm  = primary_mock
        agent.fallback_llm = fallback_mock
        return agent


# ══════════════════════════════════════════════
#  TEST 1 - Happy Path (primary LLM succeeds)
# ══════════════════════════════════════════════
section("1. Happy Path - Primary LLM Succeeds")

agent = _make_agent(
    primary_return=AIMessage(content="The capital of France is Paris.")
)
# pyrefly: ignore [missing-argument]
result = agent.invoke(message="What is the capital of France?")

check(
    label     = "Response content is returned",
    condition = result["response"] == "The capital of France is Paris.",
    expected  = "The capital of France is Paris.",
    got       = result["response"]
)
check(
    label     = "model_used is 'primary'",
    condition = result["model_used"] == "primary",
    expected  = "primary",
    got       = result["model_used"]
)
check(
    label     = "error is None on success",
    condition = result["error"] is None,
    expected  = "None",
    got       = str(result["error"])
)


# ══════════════════════════════════════════════
#  TEST 2 - Fallback Path
# ══════════════════════════════════════════════
section("2. Fallback Path - Primary Fails, Fallback Succeeds")

agent = _make_agent(
    primary_side_effect=Exception("Primary timeout"),
    fallback_return=AIMessage(content="Fallback answer here.")
)
# pyrefly: ignore [missing-argument]
result = agent.invoke(message="Tell me something.")

check(
    label     = "Fallback response content is returned",
    condition = result["response"] == "Fallback answer here.",
    expected  = "Fallback answer here.",
    got       = result["response"]
)
check(
    label     = "model_used is 'fallback'",
    condition = result["model_used"] == "fallback",
    expected  = "fallback",
    got       = result["model_used"]
)
check(
    label     = "error is None after successful fallback",
    condition = result["error"] is None,
    expected  = "None",
    got       = str(result["error"])
)


# ══════════════════════════════════════════════
#  TEST 3 - Full Failure (both LLMs fail)
# ══════════════════════════════════════════════
section("3. Full Failure - Both LLMs Fail -> Graceful Error")

agent = _make_agent(
    primary_side_effect=Exception("Primary error"),
    fallback_side_effect=Exception("Fallback error")
)
# pyrefly: ignore [missing-argument]
result = agent.invoke(message="This will fail.")

check(
    label     = "Response contains apology message",
    condition = "sorry" in result["response"].lower() or "trouble" in result["response"].lower(),
    expected  = "a graceful apology string",
    got       = result["response"]
)
check(
    label     = "model_used is 'error_handler'",
    condition = result["model_used"] == "error_handler",
    expected  = "error_handler",
    got       = result["model_used"]
)


# ══════════════════════════════════════════════
#  TEST 4 - Retry Count (call counts)
# ══════════════════════════════════════════════
section("4. Retry Count - Primary Failure Increments Counter")

agent = _make_agent(
    primary_side_effect=Exception("Timeout"),
    fallback_return=AIMessage(content="Fallback worked.")
)
# pyrefly: ignore [missing-argument]
result = agent.invoke(message="Test retry count.")

check(
    label     = "primary_llm.invoke was called exactly once",
    # pyrefly: ignore [missing-attribute]
    condition = agent.primary_llm.invoke.call_count == 1,
    expected  = "1",
    # pyrefly: ignore [missing-attribute]
    got       = str(agent.primary_llm.invoke.call_count)
)
check(
    label     = "fallback_llm.invoke was called exactly once",
    # pyrefly: ignore [missing-attribute]
    condition = agent.fallback_llm.invoke.call_count == 1,
    expected  = "1",
    # pyrefly: ignore [missing-attribute]
    got       = str(agent.fallback_llm.invoke.call_count)
)
check(
    label     = "Result came from fallback after primary retry",
    condition = result["model_used"] == "fallback",
    expected  = "fallback",
    got       = result["model_used"]
)


# ══════════════════════════════════════════════
#  TEST 5 - Short-Circuit (no fallback on primary success)
# ══════════════════════════════════════════════
section("5. Short-Circuit - Fallback Not Called on Primary Success")

agent = _make_agent(
    primary_return=AIMessage(content="Quick answer.")
)
    # pyrefly: ignore [missing-argument]
result = agent.invoke(message="Short circuit test.")

check(
    label     = "primary_llm.invoke was called once",
    # pyrefly: ignore [missing-attribute]
    condition = agent.primary_llm.invoke.call_count == 1,
    expected  = "1",
    # pyrefly: ignore [missing-attribute]
    got       = str(agent.primary_llm.invoke.call_count)
)
check(
    label     = "fallback_llm.invoke was NOT called",
    # pyrefly: ignore [missing-attribute]
    condition = agent.fallback_llm.invoke.call_count == 0,
    expected  = "0",
    # pyrefly: ignore [missing-attribute]
    got       = str(agent.fallback_llm.invoke.call_count)
)
check(
    label     = "model_used is 'primary'",
    condition = result["model_used"] == "primary",
    expected  = "primary",
    got       = result["model_used"]
)


# ══════════════════════════════════════════════
#  TEST 6 - Return shape
# ══════════════════════════════════════════════
section("6. Return Shape - invoke() Always Has Required Keys")

scenarios = [
    ("primary success",  {"primary_return": AIMessage(content="ok")}),
    ("fallback success", {"primary_side_effect": Exception("err"), "fallback_return": AIMessage(content="ok2")}),
    ("full failure",     {"primary_side_effect": Exception("err"), "fallback_side_effect": Exception("err2")}),
]

for scenario, kwargs in scenarios:
    agent  = _make_agent(**kwargs)
    # pyrefly: ignore [missing-argument]
    result = agent.invoke(message="check shape")
    has_all_keys = all(k in result for k in ("response", "model_used", "error"))
    check(
        label     = f"All keys present ({scenario})",
        condition = has_all_keys,
        expected  = "response, model_used, error",
        got       = ", ".join(result.keys())
    )


# ══════════════════════════════════════════════
#  FINAL SCORE
# ══════════════════════════════════════════════
total = pass_count + fail_count
color = GREEN if fail_count == 0 else RED
print(f"\n{CYAN}{BOLD}{'='*55}")
print(f"  Final Results: {color}{pass_count}/{total} Tests Passed{RESET}{CYAN}{BOLD}")
print(f"{'='*55}{RESET}\n")

if fail_count > 0:
    sys.exit(1)
