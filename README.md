# Hermes Antigravity Provider

[![Validation](https://img.shields.io/badge/hermes%20plugins-validated-brightgreen)](https://github.com/NousResearch/hermes-agent)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Standalone **Google Antigravity (Cloud Code Assist)** model provider plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

Allows Hermes to use your Google Antigravity subscription to access Gemini and Claude models through Google's unified Cloud Code Assist gateway without requiring modifications to the Hermes core codebase.

---

## Features

- **Gemini, Claude & GPT-OSS Models**: Access Claude Opus 5.5 and Sonnet 5.5, Gemini 3.x / 2.5 (Pro, Flash, Flash-Lite) and GPT-OSS 120B through your Antigravity subscription. The model list is discovered live from your account, so new models show up without a plugin update.
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

Once authenticated, switch to any Antigravity model from inside a session:

```text
/model gemini-3.8-flash-tiered --provider antigravity
```

Add `--global` to make it the default. For a one-off run from the shell:

```bash
hermes chat --provider antigravity -m claude-sonnet-5-5-high -q "hello"
```

Or set it as the default in `~/.hermes/config.yaml` (`hermes config set model.provider antigravity` and `hermes config set model.default <model-id>` do the same):

```yaml
model:
  default: gemini-3.8-flash-tiered
  provider: antigravity
```

The Desktop app and `hermes model` also list every model below under **Google Antigravity**.

### Available Models

Live catalog of this plugin as of 2026-10-03: 27 IDs, 26 of them chat models. Use the ID exactly as written, with `--provider antigravity`. What your account can actually call depends on your Antigravity plan and quota.

The suffixes (`-high`, `-medium`, `-low`, `-tiered`) are part of Google's model IDs and select a reasoning tier. The catalog does not document them any further.

**Claude**

| Model ID |
|---|
| `claude-opus-5-5-high` |
| `claude-opus-5-5-medium` |
| `claude-opus-5-5-low` |
| `claude-sonnet-5-5-high` |
| `claude-sonnet-5-5-medium` |
| `claude-sonnet-5-5-low` |

**Gemini 3.x**

| Model ID |
|---|
| `gemini-3.8-flash-tiered` |
| `gemini-3.7-flash-tiered` |
| `gemini-3.6-flash-tiered` |
| `gemini-3.6-flash-high` |
| `gemini-3.6-flash-medium` |
| `gemini-3.6-flash-low` |
| `gemini-3.5-flash-low` |
| `gemini-3.5-flash-extra-low` |
| `gemini-3.5-flash-lite` |
| `gemini-3.1-pro-high` |
| `gemini-3.1-pro-low` |
| `gemini-3.1-flash-lite` |
| `gemini-3-flash` |
| `gemini-3-flash-agent` |
| `gemini-pro-agent` |

**Gemini 2.5**

| Model ID |
|---|
| `gemini-2.5-pro` |
| `gemini-2.5-flash` |
| `gemini-2.5-flash-thinking` |
| `gemini-2.5-flash-lite` |

**Other**

| Model ID | Notes |
|---|---|
| `gpt-oss-120b-medium` | GPT-OSS 120B |
| `gemini-3.1-flash-image` | Image model. It is in the gateway catalog but is not a chat model, so Hermes hides it from the picker |

Models come and go on Google's side. To refresh the list in the Desktop picker and `hermes model`:

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
