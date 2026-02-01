#!/usr/bin/env python3
"""OpenRouter-compatible proxy that forwards to GitHub Enterprise models.

Usage:
    1. Export GITHUB_TOKEN (PAT with "copilot" scope).
    2. Optionally set GITHUB_ENTERPRISE_URL, GITHUB_MODELS_URL, DEFAULT_MODEL, PORT.
    3. Run: python scripts/openrouter_to_github.py
    4. Point OpenAI/OpenRouter clients to http://localhost:8000/v1/chat/completions
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Generator

import requests
from flask import Flask, Response, jsonify, request, stream_with_context

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("openrouter-to-github")

app = Flask(__name__)


@dataclass
class Config:
    github_token: str
    github_api_url: str
    github_models_url: str
    default_model: str
    port: int


def load_config() -> Config:
    """Load configuration from environment variables."""
    return Config(
        github_token=os.getenv("GITHUB_TOKEN", ""),
        github_api_url=os.getenv("GITHUB_ENTERPRISE_URL", "https://api.github.com"),
        github_models_url=os.getenv("GITHUB_MODELS_URL", "https://models.inference.ai.azure.com"),
        default_model=os.getenv("DEFAULT_MODEL", "claude-4.5-opus"),
        port=int(os.getenv("PORT", "8000")),
    )


def model_mapping() -> Dict[str, str]:
    """Map OpenRouter/OpenAI ids to the GitHub Models ids."""
    return {
        "gpt-4": "gpt-4o",
        "gpt-4-turbo": "gpt-4o",
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
        "gpt-3.5-turbo": "gpt-4o-mini",
        "o1": "o1",
        "o1-mini": "o1-mini",
        "o1-preview": "o1-preview",
        "claude-3-opus": "claude-3-opus",
        "claude-3-sonnet": "claude-3-sonnet",
        "claude-3-haiku": "claude-3-haiku",
        "claude-3.5-sonnet": "claude-3.5-sonnet",
        "opus-4.5": "claude-4.5-opus",
        "claude-4.5-opus": "claude-4.5-opus",
        "llama-3": "meta-llama-3-70b-instruct",
        "llama-3-70b": "meta-llama-3-70b-instruct",
        "llama-3.1-405b": "meta-llama-3.1-405b-instruct",
        "mistral-large": "mistral-large",
        "mistral-small": "mistral-small",
        "command-r": "cohere-command-r",
        "command-r-plus": "cohere-command-r-plus",
    }


MODEL_MAPPING = model_mapping()


def get_github_model(requested_model: str, config: Config) -> str:
    """Resolve the GitHub model id from an incoming request."""
    if requested_model in MODEL_MAPPING:
        return MODEL_MAPPING[requested_model]

    requested_lower = requested_model.lower()
    for key, value in MODEL_MAPPING.items():
        if key.lower() in requested_lower or requested_lower in key.lower():
            return value

    return requested_model or config.default_model


def transform_request(openai_request: Dict[str, Any], config: Config) -> Dict[str, Any]:
    """Translate an OpenAI/OpenRouter payload to GitHub's schema."""
    github_request: Dict[str, Any] = {
        "messages": openai_request.get("messages", []),
        "model": get_github_model(openai_request.get("model", config.default_model), config),
    }

    passthrough_keys = (
        "temperature",
        "max_tokens",
        "top_p",
        "stream",
        "stop",
        "presence_penalty",
        "frequency_penalty",
    )
    for key in passthrough_keys:
        if key in openai_request:
            github_request[key] = openai_request[key]

    return github_request


def call_github_models(config: Config, github_request: Dict[str, Any], stream: bool) -> requests.Response:
    headers = {
        "Authorization": f"Bearer {config.github_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    url = f"{config.github_models_url}/chat/completions"
    logger.info("Forwarding %s to %s", github_request.get("model"), url)

    return requests.post(url, headers=headers, json=github_request, stream=stream, timeout=120)


def stream_response(github_response: requests.Response) -> Generator[str, None, None]:
    for line in github_response.iter_lines():
        if not line:
            continue
        decoded = line.decode("utf-8")
        if decoded.startswith("data: "):
            yield decoded + "\n\n"


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions() -> Response:
    config = load_config()
    if not config.github_token:
        return jsonify({"error": {"message": "GITHUB_TOKEN not set", "type": "configuration_error"}}), 500

    openai_request = request.get_json(silent=True)
    if not openai_request:
        return jsonify({"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}}), 400

    logger.info("Incoming request model=%s", openai_request.get("model"))

    github_request = transform_request(openai_request, config)
    is_stream = bool(github_request.get("stream"))
    github_response = call_github_models(config, github_request, stream=is_stream)

    if github_response.status_code != 200:
        logger.error("GitHub Models API error %s: %s", github_response.status_code, github_response.text)
        return (
            jsonify(
                {
                    "error": {
                        "message": f"GitHub Models API error: {github_response.text}",
                        "type": "api_error",
                        "code": github_response.status_code,
                    }
                }
            ),
            github_response.status_code,
        )

    if is_stream:
        return Response(
            stream_with_context(stream_response(github_response)),
            content_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    return jsonify(github_response.json())


@app.route("/v1/models", methods=["GET"])
def list_models() -> Response:
    models = [{"id": model_id, "object": "model", "owned_by": "github"} for model_id in set(MODEL_MAPPING.values())]
    return jsonify({"object": "list", "data": models})


@app.route("/health", methods=["GET"])
def health() -> Response:
    cfg = load_config()
    return jsonify({"status": "healthy", "github_token_set": bool(cfg.github_token), "github_models_url": cfg.github_models_url})


@app.route("/", methods=["GET"])
def index() -> Response:
    cfg = load_config()
    return jsonify(
        {
            "name": "OpenRouter to GitHub Models Router",
            "version": "1.0.0",
            "base_url": f"http://localhost:{cfg.port}/v1",
            "requires": "GITHUB_TOKEN",
        }
    )


def main() -> None:
    cfg = load_config()
    banner = r"""
╔══════════════════════════════════════════════════════════════╗
║       OpenRouter to GitHub Enterprise Model Router           ║
╠══════════════════════════════════════════════════════════════╣
║  This proxy accepts OpenAI-compatible API requests and       ║
║  routes them to GitHub Enterprise/GitHub Models.             ║
╠══════════════════════════════════════════════════════════════╣
║  Base URL: http://localhost:{port}/v1                        ║
║  API Key: any value (GITHUB_TOKEN used internally)           ║
╚══════════════════════════════════════════════════════════════╝
""".format(port=cfg.port)
    print(banner)

    if not cfg.github_token:
        logger.warning("GITHUB_TOKEN not set! Set it before making requests.")
    else:
        logger.info("GitHub token detected; proxy ready")

    logger.info("Listening on port %s", cfg.port)
    logger.info("GitHub Models URL: %s", cfg.github_models_url)

    app.run(host="0.0.0.0", port=cfg.port, debug=True)


if __name__ == "__main__":
    main()
