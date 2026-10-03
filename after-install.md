# Google Antigravity Provider

Successfully installed the **antigravity** model provider plugin!

### 1. Authenticate
Authenticate with Google OAuth:
```bash
python3 ~/.hermes/plugins/antigravity-provider/login.py
```
*(or run `python3 login.py` inside the plugin directory)*

The login also registers a small `ANTIGRAVITY_OAUTH` marker in your Hermes `.env` so the model list shows up. Already logged in but the list is empty? Run `python3 ~/.hermes/plugins/antigravity-provider/login.py --setup-env`.

### 2. Select a Model
Once authenticated, select any supported Antigravity model:
```bash
hermes model antigravity/gemini-3.8-flash-tiered
```

Popular models:
- `antigravity/gemini-3.8-flash-tiered`
- `antigravity/gemini-2.5-pro`
- `antigravity/gemini-2.5-flash`
- `antigravity/claude-sonnet-4-5-20250929`
- `antigravity/claude-opus-4-5-20251101`
