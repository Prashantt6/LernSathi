import streamlit as st
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------
# Global styles
# --------------------------------------------------

def _local_css():
    st.markdown("""
    <style>
        /* Centered, spacious content column */
        .block-container {
            max-width: 820px;
            padding-top: 1.2rem;
            padding-bottom: 7rem;
        }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header[data-testid="stHeader"] {background: transparent;}

        /* Message typography */
        .stChatMessage {
            padding: 6px 4px !important;
            background: transparent !important;
        }
        .stChatMessage [data-testid="stMarkdownContainer"] p {
            font-size: 1rem;
            line-height: 1.55;
        }
        .msg-label {
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: #8a8f98;
            margin: 0 0 2px 0;
        }

        /* Compact recorder widget */
        div[data-testid="stAudioInput"] > div {
            min-height: unset;
        }
        section[data-testid="stAudioInput"] {
            border: none !important;
        }

        /* Composer buttons round & tidy */
        div.stButton > button {
            border-radius: 12px;
            font-size: 1.05rem;
        }
        div.stButton > button[kind="primary"] {
            background: #10a37f;
            border-color: #10a37f;
        }
        div.stButton > button[kind="primary"]:hover {
            background: #0d8c6d;
            border-color: #0d8c6d;
        }
        div.stButton > button[kind="primary"]:disabled {
            opacity: 0.45;
        }

        /* Example chips on welcome screen */
        .chip-row {display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 10px;}
    </style>
    """, unsafe_allow_html=True)


# --------------------------------------------------
# Single message
# --------------------------------------------------

def _render_message(message: dict, idx: int, audio_history: dict):
    role = message["role"]

    if role == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown('<p class="msg-label">You</p>', unsafe_allow_html=True)
            st.markdown(message["content"])
    else:
        with st.chat_message("assistant", avatar="🇩🇪"):
            st.markdown('<p class="msg-label">LernSathi</p>', unsafe_allow_html=True)
            st.markdown(message["content"])
            audio_path = audio_history.get(idx)
            if audio_path and Path(audio_path).exists():
                with open(audio_path, "rb") as f:
                    st.audio(f.read(), format="audio/wav")


# --------------------------------------------------
# Welcome screen (English UI, German examples)
# --------------------------------------------------

EXAMPLES = [
    "Hallo, wie geht es dir?",
    "Ich möchte Deutsch lernen.",
    "Erzähl mir etwas über deine Hobbys.",
]


def _welcome_state():
    st.markdown(
        """
        <div style="text-align:center; padding:56px 12px 8px;">
            <div style="font-size:3rem; line-height:1;">🇩🇪</div>
            <h1 style="font-size:1.9rem; font-weight:700; margin:14px 0 4px;">LernSathi</h1>
            <p style="color:#57606a; font-size:1.05rem; margin:0 0 18px;">
                Your German AI Tutor
            </p>
            <p style="color:#57606a; margin:0;">
                Practice German through natural conversation.<br>
                You can type or speak in German.<br>
                Don't worry about mistakes — LernSathi will help you.
            </p>
            <hr style="border:none; border-top:1px solid #e6e8eb; width:220px; margin:26px auto;">
            <p style="color:#8a8f98; font-size:0.85rem; margin:0 0 4px;">Try saying</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(len(EXAMPLES))
    for i, phrase in enumerate(EXAMPLES):
        with cols[i]:
            if st.button(phrase, key=f"phrase_{i}", use_container_width=True):
                st.session_state.chat_text_input = phrase
                st.rerun()


# --------------------------------------------------
# Public entry point
# --------------------------------------------------

def render_chat(messages: list, is_processing: bool, audio_history: dict):
    _local_css()

    if not messages:
        _welcome_state()
        return

    for idx, msg in enumerate(messages):
        _render_message(msg, idx, audio_history)

    if is_processing:
        st.caption("⏳ Working on your message…")