import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


FIXTURE_TRANSCRIPT = "a glass phoenix that reflects spells but shatters under thunder"
DEFAULT_TIMEOUT_SECONDS = 12
SLNG_TRANSCRIBE_URL = "https://api.slng.ai/v1/bridges/unmute/stt/deepgram/nova:3"
SLNG_TTS_URL = "https://api.slng.ai/v1/bridges/unmute/tts/deepgram/aura:2"
SLNG_TTS_URL_ES = "https://api.slng.ai/v1/bridges/unmute/tts/deepgram/aura:2:es"
GRADIUM_TTS_URL = "https://api.gradium.ai/api/post/speech/tts"


@dataclass
class VoiceProviderStatus:
    provider: str
    mode: str
    fallback: bool
    status: str = "ready"
    latencyMs: int = 0
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "provider": self.provider,
            "mode": self.mode,
            "fallback": self.fallback,
            "status": self.status,
            "latencyMs": self.latencyMs,
        }
        if self.detail:
            payload["detail"] = self.detail
        return payload


def _elapsed_ms(start: float) -> int:
    return max(0, round((time.perf_counter() - start) * 1000))


def _with_top_level_status(payload: dict[str, Any], provider_status: VoiceProviderStatus) -> dict[str, Any]:
    status = provider_status.as_dict()
    return {
        **payload,
        "providerStatus": status,
        "latencyMs": status["latencyMs"],
        "fallback": status["fallback"],
    }


def _provider_headers(provider: str, api_key: str, content_type: str, accept: str = "application/json") -> dict[str, str]:
    headers = {
        "Content-Type": content_type,
        "Accept": accept,
    }
    if provider == "gradium":
        headers["x-api-key"] = api_key
    else:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _post_bytes(url: str, payload: bytes, headers: dict[str, str]) -> tuple[bytes, str]:
    request = Request(
        url,
        data=payload,
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
        return response.read(), response.headers.get("Content-Type", "")


def _json_from_bytes(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def _http_error_detail(error: HTTPError) -> str:
    try:
        body = error.read().decode("utf-8", errors="ignore").strip()
    except Exception:
        body = ""
    snippet = f" {body[:160]}" if body else ""
    return f"HTTP {error.code}{snippet}"


def _extract_transcript(response: dict[str, Any]) -> str | None:
    for key in ("transcript", "text", "output_text"):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    result = response.get("result")
    if isinstance(result, dict):
        return _extract_transcript(result)
    return None


def _extract_audio(response: dict[str, Any]) -> dict[str, str] | None:
    for key in ("audioUrl", "audio_url", "url"):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return {"audioUrl": value.strip()}

    for key in ("audioBase64", "audio_base64", "audio"):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return {"audioBase64": value.strip()}

    result = response.get("result")
    if isinstance(result, dict):
        return _extract_audio(result)
    return None


def _provider_candidates(kind: str) -> list[tuple[str, str | None, str | None]]:
    if kind == "transcribe":
        return [
            ("slng", os.getenv("SLNG_API_KEY"), os.getenv("SLNG_TRANSCRIBE_URL") or SLNG_TRANSCRIBE_URL),
            ("gradium", os.getenv("GRADIUM_API_KEY"), os.getenv("GRADIUM_TRANSCRIBE_URL")),
        ]
    return [
        ("slng", os.getenv("SLNG_API_KEY"), os.getenv("SLNG_TTS_URL") or SLNG_TTS_URL),
        ("gradium", os.getenv("GRADIUM_API_KEY"), os.getenv("GRADIUM_TTS_URL") or GRADIUM_TTS_URL),
    ]


def _tts_payload(provider: str, text: str) -> bytes:
    payload: dict[str, Any] = {"text": text}
    if provider == "slng":
        payload["model"] = os.getenv("SLNG_TTS_MODEL", "aura-2-thalia-en")
    elif provider == "gradium":
        payload = {
            **payload,
            "voice_id": os.getenv("GRADIUM_VOICE_ID", "YTpq7expH9539ERJ"),
            "output_format": os.getenv("GRADIUM_OUTPUT_FORMAT", "wav"),
            "only_audio": True,
        }
    return json.dumps(payload).encode("utf-8")


def _parse_gradium_transcript(body: bytes) -> str | None:
    text = body.decode("utf-8", errors="ignore").strip()
    if not text:
        return None
    try:
        return _extract_transcript(json.loads(text))
    except json.JSONDecodeError:
        return text


async def transcribe_audio(audio: bytes | None, content_type: str | None) -> dict[str, Any]:
    start = time.perf_counter()
    if not audio:
        return _with_top_level_status(
            {"transcript": FIXTURE_TRANSCRIPT},
            VoiceProviderStatus(
                provider="voice-fixture",
                mode="transcript",
                fallback=True,
                status="missing-audio",
                latencyMs=_elapsed_ms(start),
                detail="No audio body was supplied; using demo-safe fixture transcript.",
            ),
        )

    content_type = content_type or "application/octet-stream"
    last_detail = "No voice provider key configured."
    for provider, api_key, endpoint in _provider_candidates("transcribe"):
        if not api_key:
            continue
        if not endpoint:
            last_detail = f"{provider.upper()}_API_KEY is configured but no transcribe endpoint URL is set."
            continue
        if provider == "gradium":
            last_detail = "Gradium STT is documented as WebSocket/PCM-first; browser multipart is using SLNG or fixture fallback."
            continue
        try:
            body, _response_type = _post_bytes(
                endpoint,
                audio,
                _provider_headers(provider, api_key, content_type),
            )
            transcript = _parse_gradium_transcript(body) if provider == "gradium" else _extract_transcript(_json_from_bytes(body))
            if transcript:
                return _with_top_level_status(
                    {"transcript": transcript},
                    VoiceProviderStatus(
                        provider=provider,
                        mode="transcript",
                        fallback=False,
                        status="live",
                        latencyMs=_elapsed_ms(start),
                    ),
                )
            last_detail = f"{provider} returned no transcript."
        except HTTPError as error:
            last_detail = f"{provider} transcribe failed: {_http_error_detail(error)}"
        except (URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
            last_detail = f"{provider} transcribe failed: {error.__class__.__name__}"

    return _with_top_level_status(
        {"transcript": FIXTURE_TRANSCRIPT},
        VoiceProviderStatus(
            provider="voice-fixture",
            mode="transcript",
            fallback=True,
            status="fallback",
            latencyMs=_elapsed_ms(start),
            detail=last_detail,
        ),
    )


async def synthesize_speech(text: str | None) -> dict[str, Any]:
    start = time.perf_counter()
    display_text = (text or "").strip() or "The arena awaits a challenger."
    last_detail = "No voice provider key configured."

    for provider, api_key, endpoint in _provider_candidates("speak"):
        if not api_key:
            continue
        if not endpoint:
            last_detail = f"{provider.upper()}_API_KEY is configured but no TTS endpoint URL is set."
            continue
        try:
            body, response_type = _post_bytes(
                endpoint,
                _tts_payload(provider, display_text),
                _provider_headers(provider, api_key, "application/json", accept="audio/*, application/json"),
            )
            if "application/json" in response_type:
                audio = _extract_audio(_json_from_bytes(body))
            else:
                audio = {"audioBase64": base64.b64encode(body).decode("ascii")} if body else None
            if audio:
                return _with_top_level_status(
                    {**audio, "displayText": display_text},
                    VoiceProviderStatus(
                        provider=provider,
                        mode="tts",
                        fallback=False,
                        status="live",
                        latencyMs=_elapsed_ms(start),
                    ),
                )
            last_detail = f"{provider} returned no playable audio."
        except HTTPError as error:
            last_detail = f"{provider} TTS failed: {_http_error_detail(error)}"
        except (URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
            last_detail = f"{provider} TTS failed: {error.__class__.__name__}"

    return _with_top_level_status(
        {"displayText": display_text},
        VoiceProviderStatus(
            provider="text-only",
            mode="tts",
            fallback=True,
            status="fallback",
            latencyMs=_elapsed_ms(start),
            detail=last_detail,
        ),
    )


def audio_data_url(audio_base64: str, mime_type: str = "audio/mpeg") -> str:
    try:
        base64.b64decode(audio_base64, validate=True)
    except Exception:
        return ""
    return f"data:{mime_type};base64,{audio_base64}"
