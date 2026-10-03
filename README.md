# Hermes Antigravity Provider

[![Validation](https://img.shields.io/badge/hermes%20plugins-validated-brightgreen)](https://github.com/NousResearch/hermes-agent)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Standalone **Google Antigravity (Cloud Code Assist)** model provider plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

Allows Hermes to use your Google Antigravity subscription to access Gemini and Claude models through Google's unified Cloud Code Assist gateway without requiring modifications to the Hermes core codebase.

---

## Features

- **Gemini & Claude Models**: Access Gemini (3.8 Flash, 2.5 Pro, 2.5 Flash) and Claude (Sonnet 3.7/4.5, Opus 4.5) through your Antigravity subscription.
- **Native Gemini Protocol**: Full support for tool calling, reasoning/thinking blocks, streaming SSE events, and usage accounting.
- **Automated OAuth Refresh**: Performs PKCE authentication against Google OAuth and automatically refreshes expiring access tokens in the background.
- **Profile-Aware**: Fully respects `HERMES_HOME` for multi-profile Hermes setups.
- **Safe & Clean**: Passes `hermes plugins validate` and the Hermes static security scanner with zero warnings.

---

## Installation

### Method 1: Hermes Plugin Installer (Recommended)

Install directly from GitHub via the Hermes CLI:

```bash
hermes plugins install kadiratesdev/hermes-antigravity --enable
```

### Method 2: Manual Clone

Clone into your user plugins directory:

```bash
git clone https://github.com/kadiratesdev/hermes-antigravity.git ~/.hermes/plugins/antigravity-provider
```

### Method 3: Pip / Editable Install

If running inside Hermes Agent's virtualenv:

```bash
pip install git+https://github.com/kadiratesdev/hermes-antigravity.git
```

---

## Authentication

Run the PKCE OAuth login script to authenticate your Google account:

```bash
# If installed as a plugin:
python3 ~/.hermes/plugins/antigravity-provider/login.py

# Or if pip-installed:
hermes-antigravity-login
```

This opens your default browser for Google sign-in and captures the OAuth callback locally. Credentials are saved securely to `~/.hermes/auth/antigravity_oauth.json` (mode `0600`).

The login also adds `ANTIGRAVITY_OAUTH=oauth-file` to the `.env` of the same Hermes home (profile-aware). It is a marker, not a secret: Hermes only lists a provider's models once it finds a credential for it, and the real token lives in the OAuth file. Without it the Antigravity model list stays empty in the Desktop picker and `hermes model`.

Already logged in, but the model list is empty? Register the marker without logging in again:

```bash
python3 ~/.hermes/plugins/antigravity-provider/login.py --setup-env
```

### Headless / SSH Environments

For remote or headless setups where a browser cannot be opened automatically:

```bash
python3 ~/.hermes/plugins/antigravity-provider/login.py --manual
```
Open the printed URL in your local browser, sign in, and paste the redirect URL back into the terminal.

---

## Usage

Once authenticated, select any Antigravity model:

```bash
hermes model antigravity/gemini-3.8-flash-tiered
```

Or configure it in `~/.hermes/config.yaml`:

```yaml
model:
  default: gemini-3.8-flash-tiered
  provider: antigravity
```

### Popular Models

| Model ID | Notes |
|---|---|
| `antigravity/gemini-3.8-flash-tiered` | Fast and capable default model with deep reasoning |
| `antigravity/gemini-2.5-pro` | Flagship Gemini reasoning model |
| `antigravity/gemini-2.5-flash` | Ultra-fast lightweight model |
| `antigravity/claude-sonnet-4-5-20250929` | Claude 3.5/4.5 Sonnet via Cloud Code Assist |
| `antigravity/claude-opus-4-5-20251101` | Claude 3.5/4.5 Opus via Cloud Code Assist |

To fetch live models available on your account:
```bash
hermes models antigravity
```

---

## Development & Testing

Run unit tests using `pytest`:

```bash
pytest tests/ -v
```

Validate catalog admission:

```bash
hermes plugins validate .
```

---

## License

MIT © [Abdulkadir Ateş](https://github.com/kadiratesdev)
