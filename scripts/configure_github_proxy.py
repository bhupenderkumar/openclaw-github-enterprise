#!/usr/bin/env python3
"""One-off helper to inject the GitHub proxy provider into ~/.openclaw/openclaw.json."""
from __future__ import annotations

import json
import pathlib

CONFIG_PATH = pathlib.Path.home() / ".openclaw" / "openclaw.json"
PROVIDER_NAME = "github-proxy"
DEFAULT_MODEL = "claude-4.5-opus"
MODEL_FALLBACK = "anthropic/claude-opus-4-5"


def load_config() -> dict:
    with CONFIG_PATH.open() as fh:
        return json.load(fh)


def write_config(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def ensure_agent_defaults(cfg: dict) -> None:
    agents = cfg.setdefault("agents", {}).setdefault("defaults", {})
    model_cfg = agents.setdefault("model", {})
    model_cfg["primary"] = f"{PROVIDER_NAME}/{DEFAULT_MODEL}"
    fallbacks = model_cfg.setdefault("fallbacks", [])
    if MODEL_FALLBACK not in fallbacks:
        fallbacks.append(MODEL_FALLBACK)

    allowed = agents.setdefault("models", {})
    allowed.setdefault(MODEL_FALLBACK, {"alias": "opus"})
    allowed[f"{PROVIDER_NAME}/{DEFAULT_MODEL}"] = {"alias": "gh-opus"}


def ensure_provider(cfg: dict) -> None:
    models_block = cfg.setdefault("models", {})
    models_block.setdefault("mode", "merge")
    providers = models_block.setdefault("providers", {})
    providers[PROVIDER_NAME] = {
        "api": "openai-completions",
        "baseUrl": "http://127.0.0.1:8000/v1",
        "apiKey": "github-proxy-local",
        "defaultHeaders": {
            "HTTP-Referer": "https://openclaw.local",
            "X-Title": "GitHub Proxy via OpenClaw",
        },
        "models": [
            {
                "id": DEFAULT_MODEL,
                "name": "Claude 4.5 Opus (GitHub)",
                "reasoning": True,
                "input": ["text"],
                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                "contextWindow": 200_000,
                "maxTokens": 8192,
            },
            {
                "id": "gpt-4o",
                "name": "GPT-4o (GitHub)",
                "reasoning": True,
                "input": ["text"],
                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                "contextWindow": 128_000,
                "maxTokens": 8192,
            },
        ],
    }


def main() -> None:
    cfg = load_config()
    ensure_agent_defaults(cfg)
    ensure_provider(cfg)
    write_config(cfg)
    print(f"Updated {CONFIG_PATH} with {PROVIDER_NAME} provider.")


if __name__ == "__main__":
    main()
