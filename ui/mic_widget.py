import base64
import os

import streamlit.components.v1 as components

_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "mic_frontend")

_voice_component = components.declare_component("lernsathi_voice", path=_FRONTEND_DIR)


def voice_recorder(action: str | None, cmd_n: int, height: int = 0,
                   key: str = "lernsathi_voice"):
    """
    Inline microphone recorder used by the unified composer.

    action : one-shot command "start" | "send" | "cancel" (None = no command).
             Deduplicated browser-side via cmd_n, so reruns replaying the same
             args never re-trigger a command.
    height : iframe height in px (0 hides the recorder while idle).
    cmd_n  : monotonic counter identifying the current command.

    Returns when the frontend emits:
      {"bytes": wav_bytes, "id": int, "duration_ms": int, "sample_rate": int}
      {"error": str, "id": int}
    Otherwise None.
    """
    val = _voice_component(
        action=action,
        cmd_n=cmd_n,
        height=height,
        key=key,
        default=None,
    )
    if not val:
        return None
    if "error" in val:
        return {"error": str(val["error"]), "id": val.get("id")}
    if "b64" in val:
        return {
            "bytes": base64.b64decode(val["b64"]),
            "id": val["id"],
            "duration_ms": int(val.get("duration_ms", 0)),
            "sample_rate": int(val.get("sample_rate", 48000)),
        }
    return None
