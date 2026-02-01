# OpenClaw GitHub Enterprise Integration

This repository contains a proxy server and configuration to integrate [OpenClaw](https://github.com/openclaw/openclaw) with GitHub Models API (GitHub Copilot / Azure OpenAI).

## Overview

The GitHub Models Proxy allows OpenClaw to use GitHub's hosted AI models (GPT-4o, Claude, etc.) through an OpenAI-compatible API endpoint.

## Features

- 🔄 **OpenAI-compatible API** - Works with any OpenAI SDK client
- 🎯 **Model mapping** - Maps common model names to GitHub Models equivalents
- 📦 **Token truncation** - Automatically truncates large requests to fit GitHub's limits
- 🔐 **Secure** - Uses environment variables for API keys (no hardcoded secrets)

## Prerequisites

- Python 3.9+
- A GitHub account with access to GitHub Models
- A `GITHUB_TOKEN` with appropriate permissions

## Installation

1. Clone this repository:
   ```bash
   git clone git@github.com-personal:bhupenderkumar/openclaw-github-enterprise.git
   cd openclaw-github-enterprise
   ```

2. Install Python dependencies:
   ```bash
   pip install flask requests certifi
   ```

3. Set your GitHub token:
   ```bash
   export GITHUB_TOKEN="your_github_token_here"
   ```

## Usage

### Start the Proxy Server

```bash
python3 scripts/github_proxy.py
```

The proxy will start on `http://127.0.0.1:8000`.

### Configure OpenClaw

Copy the configuration files to your OpenClaw config directory:

```bash
# Merge github-proxy-models.json into your agent's models.json
# Merge openclaw-config-github-proxy.json into ~/.clawdbot/openclaw.json
```

### Run OpenClaw Agent

```bash
OPENCLAW_TS_COMPILER=tsc pnpm openclaw agent --agent main --message "hello" --local
```

## Configuration Files

| File | Description |
|------|-------------|
| `scripts/github_proxy.py` | Flask proxy server that routes requests to GitHub Models |
| `github-proxy-models.json` | Model definitions for the github-proxy provider |
| `openclaw-config-github-proxy.json` | Sample OpenClaw configuration with github-proxy |

## Supported Models

| Model ID | GitHub Model |
|----------|--------------|
| `gpt-4o` | `gpt-4o` |
| `gpt-4o-mini` | `gpt-4o-mini` |
| `gpt-4` | `gpt-4o` |
| `o1` | `o1` |
| `o1-mini` | `o1-mini` |
| `claude-3.5-sonnet` | `claude-3-5-sonnet` |

## Token Limits

GitHub Models has a token limit of ~8000 tokens per request. The proxy automatically:
- Truncates system prompts longer than ~3000 tokens
- Keeps only the last 5 messages in conversation history
- Limits tools to 10 per request

## Testing

Test the proxy with curl:
```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"hello"}],"stream":true}'
```

Or use the included test script:
```bash
node scripts/test-piai.mjs
```

## Security Notes

- Never commit your `GITHUB_TOKEN` to version control
- The proxy reads tokens from environment variables only
- API keys in config files are placeholders (e.g., `github-proxy-local`)

## License

MIT

## Contributing

Contributions are welcome! Please open an issue or PR.
