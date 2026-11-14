"""Tiny wrapper around the Claude API.

The app works without it (offline mode). If you put ANTHROPIC_API_KEY in a .env
file and install the `anthropic` package, answers and quizzes get much better.
"""
import importlib.util
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")


def llm_available():
    return bool(os.getenv("ANTHROPIC_API_KEY")) and importlib.util.find_spec("anthropic") is not None


def ask_llm(prompt, system="", max_tokens=1200):
    import anthropic

    client = anthropic.Anthropic()
    kwargs = dict(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    if system:
        kwargs["system"] = system
    response = client.messages.create(**kwargs)
    return "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
