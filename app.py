import os
import uuid
import streamlit as st

from ui.chat import render_chat, render_level_select, _local_css, LEVELS
from ui.mic_widget import voice_recorder
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
    "last_audio_id": None,     # dedupe guard for processed voice messages
    "composer_mode": "text",   # "text" | "recording"
    "mic_cmd": "",             # last one-shot command for the recorder
    "mic_cmd_n": 0,            # monotonic counter -> browser-side dedupe
    "send_in_flight": False,   # recording sent, waiting for the audio bytes
    "is_processing": False,    # global pipeline lock
    "processing_stage": "",    # "" | "transcribe" | "respond"
    "pending_audio_path": "",  # saved recording awaiting Whisper
    "pipeline_error": "",      # friendly error shown once on next paint
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

STAGE_STATUS = {
    "transcribe": "🎤 Transcribing your message…",
    "respond": "🤔 LernSathi is responding…",
}


def paint():
    """Redraw the conversation from session state."""
    autoplay_idx = st.session_state.pop("autoplay_idx", None)
    render_chat(
        messages=st.session_state.messages,
        is_processing=st.session_state.is_processing,
        audio_history=st.session_state.audio_history,
        level=st.session_state.level,
        autoplay_idx=autoplay_idx,
        stage_status=STAGE_STATUS.get(st.session_state.processing_stage),
    )


def reset_conversation():
    """Clear the chat history (keeps the selected level)."""
    st.session_state.messages = []
    st.session_state.audio_history = {}
    st.session_state.last_audio_id = None
    st.session_state.composer_mode = "text"
    st.session_state.mic_cmd = ""
    st.session_state.send_in_flight = False
    st.session_state.is_processing = False
    st.session_state.processing_stage = ""
    st.session_state.pending_audio_path = ""
    st.session_state.pipeline_error = ""
    st.session_state.chat_text_input = ""


def _mic_command(name: str):
    """Issue a one-shot command to the recorder component."""
    st.session_state.mic_cmd_n += 1
    st.session_state.mic_cmd = name


def _handle_recorder(recorder):
    """Consume an emitted recording / error from the recorder component."""
    if not recorder:
        return
    st.session_state.send_in_flight = False
    st.session_state.composer_mode = "text"

    rid = recorder.get("id")
    if "error" in recorder:
        if rid is not None and rid != st.session_state.last_audio_id:
            st.session_state.last_audio_id = rid
            _fail(f"Microphone error ({recorder['error']}).",
                  Exception(recorder["error"]))
        st.rerun()

    if rid is not None and rid != st.session_state.last_audio_id:
        st.session_state.last_audio_id = rid
        rec_dir = os.path.join("audio", "input")
        os.makedirs(rec_dir, exist_ok=True)
        rec_path = os.path.join(rec_dir, f"user_recording_{uuid.uuid4().hex}.wav")
        with open(rec_path, "wb") as f:
            f.write(recorder["bytes"])
        st.session_state.pending_audio_path = rec_path
        _start_pipeline("transcribe")


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
    st.session_state.pending_audio_path = ""
    st.session_state.clear_chat_input = True


def _friendly_error(e: Exception) -> str:
    print(f"[LernSathi] {type(e).__name__}: {e}")
    if isinstance(e, ValueError):
        return f"{e} Please try again."
    if "piper" in str(e).lower():
        return "I couldn't generate the voice response. Please try again."
    return "The tutor is temporarily unavailable. Please try again."


def _start_pipeline(stage: str):
    """Accept a new request and lock the UI until the pipeline completes."""
    st.session_state.processing_stage = stage
    st.session_state.is_processing = True
    st.rerun()


def _drive_pipeline():
    """
    Run the next pending pipeline stage.

    Called AFTER this run's UI has been drawn, so each finished stage becomes
    visible (via st.rerun at the end of every run) before the next one starts:

    TEXT :  Qwen + Piper together            (Whisper skipped entirely)
    VOICE:  Whisper, then Qwen + Piper       (transcription shown as user bubble)

    The reply text and its audio are always shown as ONE unit once both are
    ready — only Whisper is split out so the transcription appears instantly.
    """
    stage = st.session_state.processing_stage
    if not stage or not st.session_state.is_processing:
        return

    try:
        if stage == "transcribe":
            # Stage 1: Whisper -> immediately show the transcription.
            user_text = service.transcribe(st.session_state.pending_audio_path)
            if not user_text or not user_text.strip():
                raise ValueError("The recording could not be understood.")
            st.session_state.messages.append({"role": "user", "content": user_text})
            st.session_state.processing_stage = "respond"

        elif stage == "respond":
            # Stage 2: Qwen reply + Piper voice prepared together and shown
            # as one message (text + audio) when both are ready.
            reply = service.generate_reply(st.session_state.messages)
            audio_path = service.speak(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            last_idx = len(st.session_state.messages) - 1
            st.session_state.audio_history[last_idx] = audio_path
            st.session_state.autoplay_idx = last_idx
            st.session_state.processing_stage = ""

    except Exception as e:
        if stage == "respond":
            _rollback_unpaired_user()
        st.session_state.pipeline_error = _friendly_error(e)
        st.session_state.processing_stage = ""

    finally:
        if not st.session_state.processing_stage:
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

# Friendly pipeline error from the previous stage run (shown once).
pipeline_error = st.session_state.pop("pipeline_error", None)
if pipeline_error:
    st.error(pipeline_error)


# --------------------------------------------------
# Unified composer — ONE component, two states
#
# TEXT      : [ Write in German...        ][ 🎤 ][ ➤ ]
# RECORDING : [ 00:07  ~~~live waveform~~~ ][ ✕  ][ ➤ ]
#             Send stops the recording AND submits it.
# --------------------------------------------------

if st.session_state.level is not None:

    processing = st.session_state.is_processing
    recording_mode = st.session_state.composer_mode == "recording"

    with st.container(border=True):

        if not recording_mode:
            col_a, col_b, col_c = st.columns([8, 0.55, 0.55])

            with col_a:
                typed = st.text_input(
                    "Message",
                    placeholder="Write in German...",
                    key="chat_text_input",
                    label_visibility="collapsed",
                    disabled=processing,
                )

            with col_b:
                if st.button("🎤", disabled=processing, use_container_width=True,
                             key="btn_mic", help="Record a voice message"):
                    _mic_command("start")
                    st.session_state.composer_mode = "recording"
                    st.rerun()

            with col_c:
                text_send_clicked = st.button(
                    "➤", type="primary",
                    disabled=processing or not typed,
                    use_container_width=True, key="btn_send",
                    help="Send message",
                )

            # Accept the message and hand over to the stage driver:
            # the user bubble paints on the next rerun, before Qwen runs.
            if text_send_clicked and typed and not processing:
                st.session_state.messages.append({"role": "user", "content": typed})
                _start_pipeline("respond")

        else:
            col_a, col_b, col_c = st.columns([8, 0.55, 0.55])

            with col_a:
                st.caption("🔴 Recording")

            with col_b:
                if st.button("✕", disabled=processing or st.session_state.send_in_flight,
                             use_container_width=True, key="btn_cancel_rec",
                             help="Discard recording"):
                    _mic_command("cancel")
                    st.session_state.composer_mode = "text"
                    st.session_state.send_in_flight = False
                    st.rerun()

            with col_c:
                if st.button("➤", type="primary", disabled=processing,
                             use_container_width=True, key="btn_send_rec",
                             help="Stop and send"):
                    _mic_command("send")
                    st.session_state.send_in_flight = True
                    st.rerun()

            # Live timer + waveform live inside this iframe; on "send" it
            # stops capturing and emits the WAV bytes back to Python.
            recorder_result = voice_recorder(
                action=st.session_state.mic_cmd or None,
                cmd_n=st.session_state.mic_cmd_n,
                height=64,
            )
            _handle_recorder(recorder_result)

    # Run the next pending pipeline stage (Whisper / Qwen / Piper) AFTER the
    # UI above has been drawn, so each finished stage is painted before the
    # next one blocks this run. No global spinner — stages stay visible.
    _drive_pipeline()