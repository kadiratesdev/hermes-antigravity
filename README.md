# Hermes Antigravity Provider

[![Validation](https://img.shields.io/badge/hermes%20plugins-validated-brightgreen)](https://github.com/NousResearch/hermes-agent)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Standalone **Google Antigravity (Cloud Code Assist)** model provider plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

Allows Hermes to use your Google Antigravity subscription to access Gemini and Claude models through Google's unified Cloud Code Assist gateway without requiring modifications to the Hermes core codebase.

---

## Features

- **Gemini, Claude & GPT-OSS Models**: Access Gemini 4 Argon, Gemini 3.x Flash/Pro, Claude Opus/Sonnet 5.5 (and 4.6 on Free/Plus), and GPT-OSS 120B through your Antigravity subscription. The model list is discovered live from your account, so new models show up without a plugin update.
- **Native Gemini Protocol**: Full support for tool calling, reasoning/thinking blocks, streaming SSE events, and usage accounting.
- **Automated OAuth Refresh**: Performs PKCE authentication against Google OAuth and automatically refreshes expiring access tokens in the background.
- **Profile-Aware**: Fully respects `HERMES_HOME` for multi-profile Hermes setups. On native Windows the default home is `%LOCALAPPDATA%\hermes` (not `~/.hermes`).
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
# POSIX / WSL
git clone https://github.com/kadiratesdev/hermes-antigravity.git ~/.hermes/plugins/antigravity-provider

# Native Windows (PowerShell)
git clone https://github.com/kadiratesdev/hermes-antigravity.git "$env:LOCALAPPDATA\hermes\plugins\antigravity-provider"
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
# If installed as a plugin (POSIX / WSL):
python3 ~/.hermes/plugins/antigravity-provider/login.py

# Native Windows:
python "$env:LOCALAPPDATA\hermes\plugins\antigravity-provider\login.py"

# Or if pip-installed:
hermes-antigravity-login
```

This opens your default browser for Google sign-in and captures the OAuth callback locally. Credentials are saved securely to `$HERMES_HOME/auth/antigravity_oauth.json` (mode `0600`) — `%LOCALAPPDATA%\hermes\auth\` on native Windows, `~/.hermes/auth/` on POSIX.

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

Once authenticated, switch to any Antigravity model from inside a session:

```text
/model gemini-3.8-flash-tiered --provider antigravity
```

Add `--global` to make it the default. For a one-off run from the shell:

```bash
hermes chat --provider antigravity -m claude-sonnet-4-6 -q "hello"
```

Or set it as the default in `$HERMES_HOME/config.yaml` (`hermes config set model.provider antigravity` and `hermes config set model.default <model-id>` do the same):

```yaml
model:
  default: gemini-3.8-flash-tiered
  provider: antigravity
```

The Desktop app and `hermes model` also list every model below under **Google Antigravity**.

### Available Models

Reference catalog as of 2026-10-17. **Live discovery is authoritative** — `hermes model --refresh` shows exactly what your account advertises. Availability depends on plan (Free / Google AI Plus / Pro / Ultra / Enterprise) and quota. Claude 4.6 and GPT-OSS are scheduled for removal from Antigravity on 2026-11-02.

The suffixes (`-high`, `-medium`, `-low`, `-tiered`, `-thinking`) are part of Google's wire IDs. Send them exactly as discovered; do not strip Claude 5.5 effort suffixes.

**Claude 5.5** (Google AI Pro / Ultra)

| Model ID |
|---|
| `claude-opus-5-5-high` |
| `claude-opus-5-5-medium` |
| `claude-opus-5-5-low` |
| `claude-sonnet-5-5-high` |
| `claude-sonnet-5-5-medium` |
| `claude-sonnet-5-5-low` |

**Claude 4.6** (Free / Plus — retiring 2026-11-02)

| Model ID |
|---|
| `claude-opus-4-6-thinking` |
| `claude-sonnet-4-6` |

**Gemini 4**

| Model ID |
|---|
| `gemini-4-argon` |
| `gemini-4-argon-high` |
| `gemini-4-argon-medium` |
| `gemini-4-argon-low` |

**Gemini 3.x**

| Model ID |
|---|
| `gemini-3.8-flash-tiered` |
| `gemini-3.8-flash-high` |
| `gemini-3.8-flash-medium` |
| `gemini-3.8-flash-low` |
| `gemini-3.7-flash-tiered` |
| `gemini-3.7-flash-high` |
| `gemini-3.7-flash-medium` |
| `gemini-3.7-flash-low` |
| `gemini-3.6-flash-tiered` |
| `gemini-3.6-flash-high` |
| `gemini-3.6-flash-medium` |
| `gemini-3.6-flash-low` |
| `gemini-3.5-flash-high` |
| `gemini-3.5-flash-medium` |
| `gemini-3.5-flash-low` |
| `gemini-3.5-flash-extra-low` |
| `gemini-3-flash-agent` |
| `gemini-3.1-pro-high` |
| `gemini-3.1-pro-low` |
| `gemini-pro-agent` |
| `gemini-3.1-flash-lite` |

**Other**

| Model ID | Notes |
|---|---|
| `gpt-oss-120b-medium` | GPT-OSS 120B (retiring 2026-11-02) |
| `gemini-3.1-flash-image` | Image model. In the gateway catalog but not a chat model; Hermes hides it from the picker |

Older Gemini 2.5 IDs (`gemini-2.5-flash`, `gemini-2.5-flash-thinking`, `gemini-2.5-flash-lite`, …) may still appear on some accounts until Google retires them from the live catalog.

To refresh the list in the Desktop picker and `hermes model`:

```bash
hermes model --refresh
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
