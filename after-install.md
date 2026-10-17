# Google Antigravity Provider

Successfully installed the **antigravity** model provider plugin!

### 1. Authenticate
Authenticate with Google OAuth:
```bash
# POSIX / WSL
python3 ~/.hermes/plugins/antigravity-provider/login.py

# Native Windows (PowerShell)
python "$env:LOCALAPPDATA\hermes\plugins\antigravity-provider\login.py"
```
*(or run `python3 login.py` inside the plugin directory)*

The login also registers a small `ANTIGRAVITY_OAUTH` marker in your Hermes `.env` so the model list shows up. Already logged in but the list is empty? Run the same script with `--setup-env`.

### 2. Select a Model
Once authenticated, switch to any supported Antigravity model inside a session:
```text
/model gemini-3.8-flash-tiered --provider antigravity
```
(add `--global` to make it the default; the Desktop picker and `hermes model` list them too)

Popular models (exact IDs depend on your plan):
- `gemini-3.8-flash-tiered`
- `gemini-4-argon-high`
- `gemini-pro-agent`
- `claude-sonnet-4-6`
- `claude-sonnet-5-5-high`
- `claude-opus-5-5-high`

See the README for the full model list.
