import base64
import os

import streamlit.components.v1 as components

_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "mic_frontend")

_mic_component = components.declare_component("lernsathi_mic", path=_FRONTEND_DIR)


def record_mic(action: str = "idle", key: str = "lernsathi_mic"):
    """
    Custom mic component. Starts recording as soon as it is rendered.

    action="stop" -> stops recording and returns {"bytes": wav, "id": int}
    Mic errors    -> returns {"error": str, "id": int}
    Otherwise     -> None (still recording)
    """
    val = _mic_component(action=action, key=key, default=None)
    if not val:
        return None
    if "b64" in val:
        return {"bytes": base64.b64decode(val["b64"]), "id": val["id"]}
    return val
