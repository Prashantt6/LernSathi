import os
import uuid
import streamlit as st

from ui.chat import render_chat, _local_css
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
    "messages": [],            # single source of truth for the chat
    "audio_history": {},       # assistant msg index -> tts wav path
    "voice_recording": None,   # raw bytes of a reviewed-but-unsent recording
    "show_recorder": False,    # mic panel open?
    "is_processing": False,    # global pipeline lock
    "processing_stage": "",
}
for key, val in _defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# Clear widget-bound keys BEFORE their widgets are instantiated this run
if st.session_state.pop("clear_chat_input", False):
    st.session_state.chat_text_input = ""
if st.session_state.pop("clear_chat_audio_input", False):
    st.session_state.chat_audio_input = None


# --------------------------------------------------
# Load AI models once (Whisper small / qwen3:1.7b / Piper)
# --------------------------------------------------

@st.cache_resource
def load_service():
    return ConversationService()


service = load_service()


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
        autoplay_idx=autoplay_idx,
    )


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
    st.session_state.voice_recording = None
    st.session_state.show_recorder = False
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

        # User bubble appears immediately (works for text AND voice)
        st.session_state.messages.append({"role": "user", "content": user_text})
        st.session_state.is_processing = False   # avoid banner during live redraws
        paint()
        st.session_state.is_processing = True

        # ---------- Stage 2: tutor responds (text prepared) ----------
        with st.spinner("🤔 LernSathi is responding…"):
            reply = service.generate_reply(st.session_state.messages)

        # ---------- Stage 3: voice response (prepared BEFORE showing either) ----------
        with st.spinner("🔊 Preparing the voice response…"):
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
        for k in ("messages", "audio_history"):
            st.session_state[k] = {} if k == "audio_history" else []
        st.session_state.voice_recording = None
        st.session_state.show_recorder = False
        st.session_state.is_processing = False
        st.session_state.processing_stage = ""
        st.session_state.chat_text_input = ""
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

paint()


# --------------------------------------------------
# Voice review card (record -> review -> Send / Cancel)
# --------------------------------------------------

if st.session_state.voice_recording is not None and not st.session_state.is_processing:
    with st.container(border=True):
        st.markdown("**🎤 Your recording**")
        st.caption("Listen back, then send it to LernSathi — or try again.")
        st.audio(st.session_state.voice_recording, format="audio/wav")

        c1, c2, spacer = st.columns([1, 1, 3])
        with c1:
            send_voice = st.button(
                "Send ➤", type="primary",
                use_container_width=True, key="btn_send_voice",
            )
        with c2:
            cancel_voice = st.button(
                "Cancel", use_container_width=True, key="btn_cancel_voice",
            )

    if cancel_voice:
        st.session_state.voice_recording = None
        st.rerun()

    if send_voice and not st.session_state.is_processing:
        run_pipeline(user_text=None, audio_bytes=st.session_state.voice_recording)


# --------------------------------------------------
# Recorder panel (opened by the mic button)
# --------------------------------------------------

if st.session_state.show_recorder and not st.session_state.is_processing \
        and st.session_state.voice_recording is None:

    with st.container(border=True):
        st.markdown("**🎙️ Record your German message**")
        st.caption("Press the record button, speak, then press stop.")
        recorded = st.audio_input("Recorder", key="chat_audio_input",
                                  label_visibility="collapsed")

    if recorded is not None:
        st.session_state.voice_recording = recorded.read()
        st.session_state.clear_chat_audio_input = True   # reset widget next run
        st.session_state.show_recorder = False
        st.rerun()


# --------------------------------------------------
# Composer  [ input ][ 🎤 ][ ➤ ]
# --------------------------------------------------

disabled = st.session_state.is_processing

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
    mic_clicked = st.button(
        "🎤", disabled=disabled,
        use_container_width=True, key="btn_mic",
    )

with col_c:
    send_clicked = st.button(
        "➤", type="primary",
        disabled=disabled or not typed,
        use_container_width=True, key="btn_send",
    )

if mic_clicked and not disabled:
    st.session_state.show_recorder = True
    st.rerun()

if send_clicked and typed and not disabled:
    run_pipeline(user_text=typed, audio_bytes=None)