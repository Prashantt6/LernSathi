import base64
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

        /* Unified composer container */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 16px !important;
            padding: 12px 14px !important;
            background: rgba(128, 128, 128, 0.04);
        }
        div[data-testid="stVerticalBlockBorderWrapper"] > div {
            gap: 0.35rem !important;
        }

        /* Composer row: input, mic and send share one height & center line.
           Scoped via :has() to the one row containing the text input, so
           welcome chips, level cards and sidebar buttons are untouched.
           NOTE: v1.62 nests the real <button> below a tooltip wrapper, so
           descendant selectors are required (direct-child never matches). */
        div[data-testid="stHorizontalBlock"]:has([data-testid="stTextInput"]) {
            align-items: center;
        }
        [data-testid="stTextInput"] > label {
            display: none;
        }
        [data-testid="stTextInputRootElement"] {
            height: 42px;
        }
        div[data-testid="stHorizontalBlock"]:has([data-testid="stTextInput"]) div.stButton button {
            height: 42px !important;
            min-height: 42px !important;
            max-height: 42px;
            width: 100%;
            max-width: 100%;
            box-sizing: border-box;
            padding: 0 !important;
            margin: 0 auto;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            overflow: hidden;
        }
        div[data-testid="stHorizontalBlock"]:has([data-testid="stTextInput"]) div.stButton button > p {
            margin: 0 !important;
            padding: 0 !important;
            line-height: 1;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        /* Composer buttons round & tidy */
        div.stButton button {
            border-radius: 12px;
            font-size: 1.05rem;
        }
        div.stButton button[kind="primary"] {
            background: #10a37f;
            border-color: #10a37f;
        }
        div.stButton button[kind="primary"]:hover {
            background: #0d8c6d;
            border-color: #0d8c6d;
        }
        div.stButton button[kind="primary"]:disabled {
            opacity: 0.45;
        }
        div.stButton button[kind="secondary"]:hover {
            border-color: #10a37f;
            color: #10a37f;
        }

        /* Example chips on welcome screen */
        .chip-row {display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 10px;}
    </style>
    """, unsafe_allow_html=True)


# --------------------------------------------------
# Single message
# --------------------------------------------------

def _autoplay_audio(path: str):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    st.markdown(
        '<audio controls autoplay style="width:100%;">'
        f'<source src="data:audio/wav;base64,{b64}" type="audio/wav">'
        "</audio>",
        unsafe_allow_html=True,
    )


def _render_message(message: dict, idx: int, audio_history: dict, autoplay: bool = False):
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
                if autoplay:
                    _autoplay_audio(audio_path)
                else:
                    with open(audio_path, "rb") as f:
                        st.audio(f.read(), format="audio/wav")


# --------------------------------------------------
# Levels (CEFR)
# --------------------------------------------------

LEVELS = {
    "A1": {"name": "Beginner", "desc": "First words & very simple sentences"},
    "A2": {"name": "Elementary", "desc": "Everyday small talk, simple past"},
    "B1": {"name": "Intermediate", "desc": "Opinions, plans & experiences"},
    "B2": {"name": "Upper-Intermediate", "desc": "Debates & abstract topics"},
    "C1": {"name": "Advanced", "desc": "Fluent, nuanced discussion"},
    "C2": {"name": "Proficient", "desc": "Near-native sophistication"},
}

EXAMPLES = {
    "A1": ["Hallo! Wie geht es dir?", "Ich heiße Anna.", "Ich lerne Deutsch."],
    "A2": ["Was machst du gern am Wochenende?", "Gestern war ich einkaufen.", "Wie ist das Wetter bei dir?"],
    "B1": ["Erzähl mir von deiner Stadt.", "Ich möchte meine Meinung üben.", "Was hast du letztes Jahr gemacht?"],
    "B2": ["Lass uns über soziale Medien diskutieren.", "Ist Fernsehen noch zeitgemäß?", "Welche Rolle spielt Kunst in deinem Leben?"],
    "C1": ["Wie beeinflusst KI die Arbeitswelt?", "Diskutieren wir über Bildungssysteme.", "Erkläre mir ein deutsches Idiom."],
    "C2": ["Ironie im Alltag – Fluch oder Segen?", "Deine Sicht auf moderne Literatur?", "Führe ein Bewerbungsgespräch mit mir."],
}


def render_level_select():
    st.markdown(
        """
        <div style="text-align:center; padding:56px 12px 8px;">
            <div style="font-size:3rem; line-height:1;">🇩🇪</div>
            <h1 style="font-size:1.9rem; font-weight:700; margin:14px 0 4px;">LernSathi</h1>
            <p style="color:#57606a; font-size:1.05rem; margin:0 0 6px;">
                Your German AI Tutor
            </p>
            <p style="color:#57606a; margin:0;">
                Choose your German level to begin.<br>
                The conversation adapts to what you pick.
            </p>
            <hr style="border:none; border-top:1px solid #e6e8eb; width:220px; margin:26px auto;">
        </div>
        """,
        unsafe_allow_html=True,
    )

    rows = [list(LEVELS.items())[i:i + 3] for i in range(0, len(LEVELS), 3)]
    for r, row in enumerate(rows):
        cols = st.columns(3)
        for c, (code, meta) in enumerate(row):
            with cols[c]:
                st.markdown(
                    f"""
                    <div style="text-align:center; padding:14px 6px 4px;">
                        <div style="font-size:1.5rem; font-weight:800;">{code}</div>
                        <div style="font-size:0.9rem; font-weight:600; margin-top:2px;">{meta['name']}</div>
                        <div style="color:#57606a; font-size:0.78rem; margin-top:4px; min-height:2.4em;">
                            {meta['desc']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("Start", key=f"level_{code}", use_container_width=True,
                             type="primary" if (r * 3 + c) == 0 else "secondary"):
                    st.session_state.pending_level = code
                    st.rerun()


# --------------------------------------------------
# Welcome screen (English UI, level-aware examples)
# --------------------------------------------------

def _welcome_state(level: str):
    meta = LEVELS[level]
    phrases = EXAMPLES.get(level, [])

    st.markdown(
        f"""
        <div style="text-align:center; padding:56px 12px 8px;">
            <div style="font-size:3rem; line-height:1;">🇩🇪</div>
            <h1 style="font-size:1.9rem; font-weight:700; margin:14px 0 4px;">LernSathi</h1>
            <p style="color:#57606a; font-size:1.05rem; margin:0 0 10px;">
                Your German AI Tutor
            </p>
            <p style="margin:0;">
                <span style="display:inline-block; background:#e7f7f1; color:#0d8c6d;
                border-radius:999px; padding:4px 14px; font-weight:700; font-size:0.85rem;">
                    Level {level} · {meta["name"]}
                </span>
            </p>
            <p style="color:#57606a; margin:16px 0 0;">
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

    cols = st.columns(len(phrases))
    for i, phrase in enumerate(phrases):
        with cols[i]:
            if st.button(phrase, key=f"phrase_{i}", use_container_width=True):
                st.session_state.chat_text_input = phrase
                st.rerun()


# --------------------------------------------------
# Public entry point
# --------------------------------------------------

def render_chat(messages: list, is_processing: bool, audio_history: dict,
                level: str, autoplay_idx: int | None = None,
                stage_status: str | None = None):
    _local_css()

    if not messages and not is_processing:
        _welcome_state(level)
        return

    for idx, msg in enumerate(messages):
        _render_message(msg, idx, audio_history, autoplay=(idx == autoplay_idx))

    # Live pipeline status, rendered inline after the messages so previous
    # chat stays visible while a stage is running.
    if is_processing:
        st.caption(stage_status or "⏳ Working on your message…")