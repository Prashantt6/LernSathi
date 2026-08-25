import os
import uuid
import streamlit as st

from ui.chat import render_chat, render_level_select, _local_css, LEVELS
from ui.mic_widget import record_mic
from services.conversation_service import ConversationService


# --------------------------------------------------
# Page configuration
# --------------------------------------------------

st.set_page_config(
    page_title="LernSathi",
    page_icon="🇩🇪",
    layout="wide",
)

_local_css()


# --------------------------------------------------
# Session state (deterministic across reruns)
# --------------------------------------------------

_defaults = {
    "level": None,             # selected CEFR level (A1–C2); None = not chosen yet
    "messages": [],            # single source of truth for the chat
    "audio_history": {},       # assistant msg index -> tts wav path
    "is_recording": False,     # mic capture in progress
    "mic_action": "idle",      # pending command for the mic component
    "last_mic_id": 0,          # dedupe guard for emitted recordings
    "is_processing": False,    # global pipeline lock
    "processing_stage": "",
}
for key, val in _defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# Clear widget-bound keys BEFORE their widgets are instantiated this run
if st.session_state.pop("clear_chat_input", False):
    st.session_state.chat_text_input = ""


# --------------------------------------------------
# Load AI models once (Whisper small / qwen3:1.7b / Piper)
# --------------------------------------------------

@st.cache_resource
def load_service():
    return ConversationService()


service = load_service()

# Keep the cached service in sync with the selected level
if st.session_state.level is not None:
    service.set_level(st.session_state.level)


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def paint():
    """Redraw the conversation from session state."""
    autoplay_idx = st.session_state.pop("autoplay_idx", None)
    render_chat(
        messages=st.session_state.messages,
        is_processing=st.session_state.is_processing,
        audio_history=st.session_state.audio_history,
        level=st.session_state.level,
        autoplay_idx=autoplay_idx,
    )


def reset_conversation():
    """Clear the chat history (keeps the selected level)."""
    st.session_state.messages = []
    st.session_state.audio_history = {}
    st.session_state.is_recording = False
    st.session_state.mic_action = "idle"
    st.session_state.is_processing = False
    st.session_state.processing_stage = ""
    st.session_state.chat_text_input = ""


def _fail(message: str, exc: Exception):
    st.error(f"{message} Please try again.")
    print(f"[LernSathi] {type(exc).__name__}: {exc}")


def _rollback_unpaired_user():
    """If a user message was added but no reply followed, remove it."""
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        st.session_state.messages.pop()


def _finish():
    st.session_state.is_processing = False
    st.session_state.processing_stage = ""
    st.session_state.is_recording = False
    st.session_state.mic_action = "idle"
    st.session_state.clear_chat_input = True


def run_pipeline(user_text: str | None, audio_bytes: bytes | None):
    """
    One request -> one full pipeline run.

    TEXT :  LLM -> TTS                     (Whisper skipped entirely)
    VOICE:  Whisper -> LLM -> TTS          (transcription shown as the user bubble)
    """
    if st.session_state.is_processing:
        return

    st.session_state.is_processing = True

    try:
        # ---------- Stage 1a: transcription (voice only) ----------
        if audio_bytes is not None:
            rec_dir = os.path.join("audio", "input")
            os.makedirs(rec_dir, exist_ok=True)
            rec_path = os.path.join(rec_dir, f"user_recording_{uuid.uuid4().hex}.wav")
            with open(rec_path, "wb") as f:
                f.write(audio_bytes)

            with st.spinner("🎤 Transcribing your message…"):
                user_text = service.transcribe(rec_path)

            if not user_text or not user_text.strip():
                raise ValueError("The recording could not be understood.")

        if not user_text or not user_text.strip():
            raise ValueError("Empty message.")

        # User bubble is appended now but drawn on the post-rerun paint,
        # so the conversation never renders twice in one run.
        st.session_state.messages.append({"role": "user", "content": user_text})

        # ---------- Stage 2: tutor responds (text prepared) ----------
        with st.spinner("LernSathi is responding…"):
            reply = service.generate_reply(st.session_state.messages)

        # ---------- Stage 3: voice response (prepared BEFORE showing either) ----------
        with st.spinner("Preparing the voice response…"):
            audio_path = service.speak(reply)

        # Both ready -> shown together on the post-rerun paint (with autoplay)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        last_idx = len(st.session_state.messages) - 1
        st.session_state.audio_history[last_idx] = audio_path
        st.session_state.autoplay_idx = last_idx

    except Exception as e:
        _rollback_unpaired_user()
        if isinstance(e, ValueError):
            _fail(str(e) + ".", e)
        elif "piper" in str(e).lower():
            _fail("I couldn't generate the voice response.", e)
        else:
            _fail("The tutor is temporarily unavailable.", e)

    finally:
        _finish()
        st.rerun()


# --------------------------------------------------
# Sidebar
# --------------------------------------------------

with st.sidebar:
    st.markdown("### 🇩🇪 LernSathi")
    st.caption("German AI Conversation Tutor")

    if st.button("＋ New conversation", use_container_width=True):
        reset_conversation()
        st.rerun()

    st.divider()

    st.markdown("**Current level**")
    if st.session_state.level is None:
        st.caption("Not selected yet")
    else:
        meta = LEVELS[st.session_state.level]
        st.markdown(
            f"<span style='display:inline-block; background:#e7f7f1; color:#0d8c6d;"
            f"border-radius:999px; padding:3px 12px; font-weight:700; font-size:0.85rem;'>"
            f"{st.session_state.level} · {meta['name']}</span>",
            unsafe_allow_html=True,
        )
        if st.button("🎚 Change level", use_container_width=True):
            reset_conversation()
            st.session_state.level = None
            st.rerun()

    st.divider()

    st.markdown("**Current session**")
    st.caption("German practice · not saved anywhere")
    st.markdown(f"**{len(st.session_state.messages)} messages** in this conversation")

    st.divider()

    st.markdown("**About**")
    st.caption(
        "Practice German through AI-powered "
        "conversation. Everything runs locally."
    )


# --------------------------------------------------
# Main area
# --------------------------------------------------

if st.session_state.level is None:
    # Level-first flow: no level chosen -> show picker, hide chat
    render_level_select()

    pending = st.session_state.pop("pending_level", None)
    if pending:
        st.session_state.level = pending
        service.set_level(pending)
        reset_conversation()
        st.rerun()
else:
    paint()


# --------------------------------------------------
# Composer  [ input ][ 🎤 / ✕ ][ ➤ ]
# idle      : [ input ][ 🎤 ][ ➤ ]   (➤ sends text)
# recording : [ input ][ ✕  ][ ➤ ]   (➤ stops & sends audio, ✕ discards)
# --------------------------------------------------

if st.session_state.level is not None:

    disabled = st.session_state.is_processing
    recording = st.session_state.is_recording and not disabled

    col_a, col_b, col_c = st.columns([8, 0.7, 0.7])

    with col_a:
        typed = st.text_input(
            "Message",
            placeholder="Write in German...",
            key="chat_text_input",
            label_visibility="collapsed",
            disabled=disabled,
        )

    with col_b:
        if recording:
            if st.button("✕", use_container_width=True, key="btn_cancel_rec"):
                st.session_state.is_recording = False
                st.session_state.mic_action = "idle"
                st.rerun()
        elif st.button("🎤", disabled=disabled, use_container_width=True, key="btn_mic"):
            st.session_state.is_recording = True
            st.rerun()

    with col_c:
        if recording:
            if st.button("➤", type="primary", use_container_width=True,
                         key="btn_send_rec"):
                st.session_state.mic_action = "stop"
                st.rerun()
        else:
            text_send_clicked = st.button(
                "➤", type="primary",
                disabled=disabled or not typed,
                use_container_width=True, key="btn_send",
            )

    # Pipeline runs OUTSIDE any column context so its spinners/errors
    # render full-width instead of squeezed under the send button.
    if not recording and text_send_clicked and typed and not disabled:
        run_pipeline(user_text=typed, audio_bytes=None)

    if recording:
        st.caption("🔴 Recording… press **➤** to send or **✕** to discard")

        result = record_mic(action=st.session_state.mic_action)
        st.session_state.mic_action = "idle"

        if isinstance(result, dict) and "error" in result:
            st.session_state.is_recording = False
            _fail(f"Microphone unavailable ({result['error']}).", Exception(result["error"]))
            st.rerun()
        elif isinstance(result, dict) and result.get("id") \
                and result["id"] != st.session_state.last_mic_id:
            st.session_state.last_mic_id = result["id"]
            st.session_state.is_recording = False
            run_pipeline(user_text=None, audio_bytes=result["bytes"])