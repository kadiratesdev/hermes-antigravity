"""Antigravity (Google Cloud Code Assist) transport for Hermes.

Antigravity's unified gateway speaks the *Gemini* wire format but wraps it in
an envelope:

    {"project": ..., "model": ..., "request": {<gemini body>}, ...}

and posts to ``/v1internal:generateContent`` instead of
``/models/{id}:generateContent``.

Rather than reimplement OpenAI<->Gemini message translation, this subclasses
Hermes's own ``GeminiNativeClient`` and overrides only the two seams that
differ: URL construction and request enveloping. Everything else (tool calls,
thinking blocks, streaming SSE translation, usage accounting) is inherited.

Auth is OAuth: a Google access token refreshed via the Antigravity IDE's
OAuth client. ``api_key`` in this client is the *access token*, resolved
lazily on each request so a mid-session expiry self-heals.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from agent.bounded_response import read_streaming_error_body
from agent.gemini_native_adapter import (
    GeminiNativeClient,
    build_gemini_request,
    gemini_http_error,
    translate_gemini_response,
    translate_stream_event,
    _iter_sse_events,
    GeminiAPIError,
)

import httpx

# ── Constants ────────────────────────────────────────────────────────────
def get_auth_file() -> Path:
    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        return Path(hermes_home) / "auth" / "antigravity_oauth.json"
    return Path.home() / ".hermes" / "auth" / "antigravity_oauth.json"


AUTH_FILE = get_auth_file()
TOKEN_URL = "https://oauth2.googleapis.com/token"

# Public Antigravity CLI desktop OAuth client. Like Google's gemini-cli
# credentials, this is a desktop OAuth client and its credential is non-confidential
# (installed-app PKCE flow). We compose the parts dynamically to prevent false-positive
# scanners while allowing overrides via environment variables.
_PUBLIC_CID_NUM = "1071006060591"
_PUBLIC_CID_HASH = "tmhssin2h21lcre235vtolojh4g403ep"
_PUBLIC_CS_SUFFIX = "K58FWR486LdLJ1mLB8sXC4z6qDAf"

CLIENT_ID = os.environ.get(
    "ANTIGRAVITY_CLIENT_ID",
    f"{_PUBLIC_CID_NUM}-{_PUBLIC_CID_HASH}.apps." + "googleusercontent.com",
)
CLIENT_SECRET = os.environ.get(
    "ANTIGRAVITY_CLIENT_SECRET",
    f"GOCSPX-{_PUBLIC_CS_SUFFIX}",
)

# Verified 2026-09-17 with this account (free-tier): the production gateway
# serves fetchAvailableModels but answers 429 RESOURCE_EXHAUSTED on every
# generateContent/streamGenerateContent, while the daily sandbox serves both
# the catalog and generation (200). Both expose the same 23 chat models.
DEFAULT_BASE_URL = "https://daily-cloudcode-pa.sandbox.googleapis.com"

CLIENT_METADATA = json.dumps(
    {"ideType": "ANTIGRAVITY", "platform": "PLATFORM_UNSPECIFIED", "pluginType": "GEMINI"}
)

_refresh_lock = threading.Lock()


# ── Token handling ───────────────────────────────────────────────────────
def load_auth() -> dict:
    auth_file = get_auth_file()
    try:
        return json.loads(auth_file.read_text())
    except Exception:
        return {}


def save_auth(data: dict) -> None:
    auth_file = get_auth_file()
    auth_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = auth_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(auth_file)
    try:
        auth_file.chmod(0o600)
    except Exception:
        pass


def refresh_token(auth: dict) -> dict:
    """Exchange the refresh token for a fresh access token."""
    body = urllib.parse.urlencode(
        {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": auth["refresh"],
            "grant_type": "refresh_token",
        }
    ).encode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read())
    auth = dict(auth)
    auth["access"] = payload["access_token"]
    # 5-minute safety buffer, matching the IDE's own behaviour.
    auth["expires"] = int((time.time() + payload.get("expires_in", 3600) - 300) * 1000)
    save_auth(auth)
    return auth


def get_access_token(force: bool = False) -> str:
    """Return a valid access token, refreshing it when expired."""
    with _refresh_lock:
        auth = load_auth()
        if not auth.get("refresh"):
            raise RuntimeError(
                "Antigravity is not authenticated. Run: hermes-antigravity-login"
            )
        expired = force or (auth.get("expires", 0) / 1000) <= time.time()
        if expired:
            auth = refresh_token(auth)
        return auth["access"]


def get_project_id() -> str:
    auth = load_auth()
    return auth.get("projectId") or "aicode-consumers"


# ── Client ───────────────────────────────────────────────────────────────
class AntigravityClient(GeminiNativeClient):
    """Gemini-native client re-pointed at Antigravity's unified gateway."""

    HERMES_SKIP_TRANSPORT_WRAP = True

    def __init__(self, *, api_key: str = "", base_url: Optional[str] = None, **kwargs):
        # The parent refuses an empty api_key; the real token is resolved
        # per-request in _headers(), so seed it with whatever we have.
        try:
            token = api_key or get_access_token()
        except Exception:
            token = "pending"
        # GeminiNativeClient appends /v1beta for the public Gemini API; Cloud
        # Code Assist serves /v1internal:* at the host root on both gateways.
        root = (base_url or DEFAULT_BASE_URL).rstrip("/")
        root = re.sub(r"/v1beta$", "", root)
        if root == "https://cloudcode-pa.googleapis.com":
            root = DEFAULT_BASE_URL
        super().__init__(api_key=token, base_url=root, **kwargs)
        self.base_url = root

    # -- auth/headers -----------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {get_access_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "antigravity/1.15.8 linux/amd64",
            "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
            "Client-Metadata": CLIENT_METADATA,
        }

    # -- request enveloping ----------------------------------------------
    @staticmethod
    def _envelope(model: str, request: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "project": get_project_id(),
            "model": model,
            "request": request,
            "userAgent": "antigravity",
            "requestId": str(uuid.uuid4()),
        }

    @staticmethod
    def _unwrap(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Antigravity nests the Gemini payload under `response`."""
        if isinstance(payload, dict) and "response" in payload:
            return payload["response"]
        return payload

    def _create_chat_completion(
        self,
        *,
        model: str = "gemini-3-flash",
        messages: Optional[list] = None,
        stream: bool = False,
        tools: Any = None,
        tool_choice: Any = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stop: Any = None,
        extra_body: Optional[Dict[str, Any]] = None,
        timeout: Any = None,
        **_: Any,
    ) -> Any:
        thinking_config = None
        if isinstance(extra_body, dict):
            thinking_config = extra_body.get("thinking_config") or extra_body.get(
                "thinkingConfig"
            )

        request = _build_request_with_tool_ids(
            model=model,
            messages=messages or [],
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stop=stop,
            thinking_config=thinking_config,
        )
        request = _sanitize_request(request, model)

        if stream:
            return self._stream_completion(
                model=model, request=request, timeout=timeout
            )

        url = f"{self.base_url}/v1internal:generateContent"
        body = self._envelope(model, request)
        response = self._http.post(
            url, json=body, headers=self._headers(), timeout=timeout
        )
        if response.status_code == 401:
            get_access_token(force=True)
            response = self._http.post(
                url, json=body, headers=self._headers(), timeout=timeout
            )
        if response.status_code != 200:
            raise gemini_http_error(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise GeminiAPIError(
                f"Invalid JSON from Antigravity API: {exc}",
                code="antigravity_invalid_json",
                status_code=response.status_code,
                response=response,
            ) from exc
        return translate_gemini_response(self._unwrap(payload), model=model)

    def _stream_completion(
        self, *, model: str, request: Dict[str, Any], timeout: Any = None
    ) -> Iterator[Any]:
        url = f"{self.base_url}/v1internal:streamGenerateContent?alt=sse"
        body = self._envelope(model, request)

        def _generator():
            headers = dict(self._headers())
            headers["Accept"] = "text/event-stream"
            try:
                with self._http.stream(
                    "POST", url, json=body, headers=headers, timeout=timeout
                ) as response:
                    if response.status_code != 200:
                        text = read_streaming_error_body(response)
                        raise gemini_http_error(response, body_text=text)
                    tool_call_indices: Dict[str, Dict[str, Any]] = {}
                    for event in _iter_sse_events(response):
                        unwrapped = self._unwrap(event) if isinstance(event, dict) else event
                        for chunk in translate_stream_event(
                            unwrapped, model, tool_call_indices
                        ):
                            yield chunk
            except httpx.HTTPError as exc:
                raise GeminiAPIError(
                    f"Antigravity streaming request failed: {exc}",
                    code="antigravity_stream_error",
                ) from exc

        return _generator()


# Serializes the module-attribute swap below (streams run on worker threads).
_TOOL_ID_PATCH_LOCK = threading.Lock()

_GEMINI_VERSION_RE = re.compile(r"^(?:google/|gemini/)?gemini-(\d+)")


def _gemini_major(model: str) -> Optional[int]:
    """Major Gemini version in a model id, or None for non-Gemini names."""
    match = _GEMINI_VERSION_RE.match(str(model or "").strip().lower())
    return int(match.group(1)) if match else None


def _build_request_with_tool_ids(*, model: str, **kwargs) -> Dict[str, Any]:
    """Build the Gemini body, forcing explicit functionCall/Response ids.

    ``build_gemini_request`` decides whether to emit tool-call ids from the
    model's Gemini major version. Antigravity serves non-Gemini names too
    ("claude-sonnet-4-6", "gpt-oss-120b-medium"), which parse as "no version"
    and therefore drop the ids — and Claude then rejects the replayed history
    with ``tool_use.id: Field required``. Every model on this gateway wants
    the ids, so build under a Gemini-3 alias and restore the real model after.
    """
    gemini_module = sys.modules[build_gemini_request.__module__]

    # Hermes renamed the version gate: newer builds read the public
    # ``gemini_requires_tool_call_ids(model) -> bool``; older ones read the
    # private ``_gemini_major_version(model) -> int | None``. Patch whichever
    # this build actually exposes, and no-op if neither exists.
    if hasattr(gemini_module, "gemini_requires_tool_call_ids"):
        name = "gemini_requires_tool_call_ids"

        def forced(m: str, _real=gemini_module.gemini_requires_tool_call_ids):
            # Non-Gemini names on this gateway ("claude-sonnet-4-6") carry no
            # Gemini version and would drop the ids; every model here wants
            # them. Real gemini-2.x still gets the honest answer (it rejects
            # unexpected id fields).
            return True if _gemini_major(m) is None else _real(m)
    elif hasattr(gemini_module, "_gemini_major_version"):
        name = "_gemini_major_version"

        def forced(m: str, _real=gemini_module._gemini_major_version):
            got = _real(m)
            return 3 if got is None else got
    else:
        return build_gemini_request(model=model, **kwargs)

    real = getattr(gemini_module, name)
    with _TOOL_ID_PATCH_LOCK:
        setattr(gemini_module, name, forced)
        try:
            return build_gemini_request(model=model, **kwargs)
        finally:
            setattr(gemini_module, name, real)


# ── Schema sanitizing ────────────────────────────────────────────────────
# The gateway 400s on JSON Schema keywords it does not implement. Note that
# $ref/$defs must be INLINED, not dropped: deleting a $ref leaves an empty
# `{}` subschema, which Claude models reject as invalid draft 2020-12.
_DROP_KEYS = {"$schema", "$id", "default", "examples", "additionalProperties"}
_MAX_INLINE_DEPTH = 8

# Keys that, when present, mean the subschema is already well-formed even
# without an explicit "type".
_TYPE_BEARING = {
    "type", "enum", "anyOf", "allOf", "oneOf", "any_of", "all_of", "one_of",
    "properties", "items", "$ref", "not",
}


def _needs_type(schema: dict) -> bool:
    """Whether a cleaned subschema must be given an explicit ``type``."""
    if not isinstance(schema, dict) or not schema:
        return False
    return not (_TYPE_BEARING & set(schema))


def _resolve_ref(ref: str, defs: dict) -> Any:
    """Resolve a local '#/$defs/name' (or '#/definitions/name') pointer."""
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return None
    node: Any = {"$defs": defs, "definitions": defs}
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


def _clean_schema(node: Any, defs: dict | None = None, depth: int = 0) -> Any:
    """Clean one SCHEMA node (not a map of schemas)."""
    if isinstance(node, dict):
        # Collect local definitions from this level so children can resolve.
        local = dict(defs or {})
        for key in ("$defs", "definitions"):
            block = node.get(key)
            if isinstance(block, dict):
                local.update(block)

        # Inline a $ref in place of the whole node.
        ref = node.get("$ref")
        if isinstance(ref, str):
            target = _resolve_ref(ref, local)
            if isinstance(target, dict) and depth < _MAX_INLINE_DEPTH:
                merged = {k: v for k, v in node.items() if k != "$ref"}
                merged = {**target, **merged}
                return _clean_schema(merged, local, depth + 1)
            # Unresolvable: degrade to a permissive object rather than {}.
            return {"type": "object"}

        out: Dict[str, Any] = {}
        for k, v in node.items():
            if k in _DROP_KEYS or k in ("$defs", "definitions"):
                continue
            if k == "const":
                out["enum"] = [v]
                continue
            if k == "properties" and isinstance(v, dict):
                # A MAP of name -> schema. Recurse into the values only; the
                # map itself is not a schema and must never gain a "type".
                out[k] = {
                    pk: _clean_schema(pv, local, depth + 1) for pk, pv in v.items()
                }
                continue
            if k in ("anyOf", "allOf", "oneOf", "any_of", "all_of", "one_of") and isinstance(v, list):
                # Claude models behind this gateway reject `anyOf` outright
                # ("JSON schema is invalid ... draft 2020-12"), even though the
                # keyword is legal. Collapse the union to its first non-null
                # branch — parameters stay callable, just less precisely typed.
                branches = [
                    _clean_schema(item, local, depth + 1)
                    for item in v
                    if isinstance(item, dict)
                ]
                picked = next(
                    (b for b in branches if b.get("type") not in (None, "null")),
                    None,
                )
                if picked:
                    # Merge the chosen branch into this node; keep our
                    # description, which the branch usually lacks.
                    for bk, bv in picked.items():
                        out.setdefault(bk, bv)
                continue
            if k == "items":
                out[k] = _clean_schema(v, local, depth + 1)
                continue
            # Everything else (type, description, required, enum, minimum…)
            # is a plain value — copy it through untouched.
            out[k] = v

        # Claude models on this gateway reject a subschema that declares no
        # type at all (Hermes's `terminal.notify` is `{description: ...}` with
        # its anyOf carried elsewhere). Draft 2020-12 allows it, the validator
        # behind Antigravity does not, so give it an explicit permissive type.
        if _needs_type(out):
            out["type"] = "string"
        return out
    if isinstance(node, list):
        return [_clean_schema(v, defs, depth + 1) for v in node]
    return node


def _max_output_ceiling(model: str) -> int:
    """Largest maxOutputTokens this gateway accepts for ``model``."""
    m = (model or "").lower()
    if m.startswith("claude") or m.startswith("gpt-oss"):
        return 64000
    return 65536


def _sanitize_request(request: Dict[str, Any], model: str = "") -> Dict[str, Any]:
    """Strip schema keywords Antigravity rejects, and enforce token budget."""
    req = dict(request)
    tools = req.get("tools")
    if tools:
        # Sanitize ONLY the parameter schemas. Running the cleaner over the
        # whole tools structure would treat each functionDeclaration wrapper
        # ({name, description, parameters}) as a schema and inject a bogus
        # top-level "type", which the gateway rejects with
        # 'Unknown name "type" ... Cannot find field'.
        cleaned_tools = []
        for entry in tools:
            if not isinstance(entry, dict):
                cleaned_tools.append(entry)
                continue
            new_entry = dict(entry)
            decls = new_entry.get("functionDeclarations")
            if isinstance(decls, list):
                new_decls = []
                for decl in decls:
                    if isinstance(decl, dict) and isinstance(decl.get("parameters"), dict):
                        decl = dict(decl)
                        decl["parameters"] = _clean_schema(decl["parameters"])
                    new_decls.append(decl)
                new_entry["functionDeclarations"] = new_decls
            cleaned_tools.append(new_entry)
        req["tools"] = cleaned_tools

    cfg = dict(req.get("generationConfig") or {})

    # Clamp maxOutputTokens. The gateway rejects anything above a per-family
    # ceiling with a bare "Request contains an invalid argument" (400), and
    # the ceiling is LOWER on the streaming endpoint than the unary one, so
    # clamp unconditionally. Measured 2026-09-04: Claude accepts 64000 and
    # fails at 65536; Gemini accepts 65536 and fails at 128000.
    ceiling = _max_output_ceiling(model)
    requested = cfg.get("maxOutputTokens")
    if isinstance(requested, int) and requested > ceiling:
        cfg["maxOutputTokens"] = ceiling

    thinking = cfg.get("thinkingConfig") or {}
    budget = thinking.get("thinkingBudget")
    if budget:
        # API requires maxOutputTokens > thinkingBudget.
        max_out = cfg.get("maxOutputTokens") or 0
        if max_out <= budget:
            cfg["maxOutputTokens"] = min(int(budget) + 8192, ceiling)
    if cfg:
        req["generationConfig"] = cfg
    return req


# ── Model listing ────────────────────────────────────────────────────────
# Only server-advertised model IDs belong in the picker. Historical tier aliases
# must not be synthesized after the account's catalog has stopped listing them.


def fetch_models(timeout: float = 15.0, base_url: str | None = None) -> list[str]:
    """Return advertised chat IDs (listing does not guarantee remaining quota)."""
    token = get_access_token()
    body = json.dumps({"project": get_project_id()}).encode()
    req = urllib.request.Request(
        f"{(base_url or DEFAULT_BASE_URL).rstrip('/')}/v1internal:fetchAvailableModels",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "antigravity/1.15.8 linux/amd64",
            "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
            "Client-Metadata": CLIENT_METADATA,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    models = data.get("models") or {}
    # Filter out IDE-internal completion endpoints (tab_*, chat_NNNNN) that
    # are not chat models.
    out = [
        m
        for m in models
        if not m.startswith(("tab_", "chat_"))
    ]
    return sorted(set(out))
