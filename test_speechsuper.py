import streamlit as st
import requests
import subprocess
import tempfile
import hashlib
import json
from pathlib import Path

# Static authentication credentials
STATIC_USER_ID = "ldm"
STATIC_PASSWORD = "PmAenB$Mf$$2YjTr"

APP_KEY = "1768202371000642"
SECRET_KEY = "41fbb04cf60a0d55d49dc6e581bff0f6"
BASE_URL = "https://api.speechsuper.com/"

TESTS = {
    "Words": {
        "perro": ("perro", "word.eval.sp"),
        "pero": ("pero", "word.eval.sp"),
        "pollo": ("pollo", "word.eval.sp"),
        "bajo": ("bajo", "word.eval.sp"),
        "universidad": ("universidad", "word.eval.sp"),
    },
    "Sentences": {
        "Quiero pero no puedo": ("Quiero pero no puedo", "sent.eval.sp"),
        "Mi perro corre rápido": ("Mi perro corre rápido", "sent.eval.sp"),
        "Yo llamo a mi mamá": ("Yo llamo a mi mamá", "sent.eval.sp"),
        "La ciudad es grande": ("La ciudad es grande", "sent.eval.sp"),
    },
}


def check_authentication():
    """Check if user is authenticated"""
    return st.session_state.get("authenticated", False)


def login_page():
    """Display login page"""
    st.title("🔐 Spanish Pronunciation Test - Login")
    st.markdown("### Access Required")
    
    with st.form("login_form"):
        user_id = st.text_input("User ID")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login", type="primary")
        
        if submit:
            if user_id == STATIC_USER_ID and password == STATIC_PASSWORD:
                st.session_state["authenticated"] = True
                st.session_state["user_id"] = user_id
                st.rerun()
            else:
                st.error("❌ Invalid credentials")


def logout():
    """Logout function"""
    st.session_state["authenticated"] = False
    st.session_state.pop("user_id", None)
    st.rerun()


def convert_to_wav(audio_bytes):
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.webm"
        output_file = Path(tmpdir) / "output.wav"

        input_file.write_bytes(audio_bytes.read())

        subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(input_file),
                "-acodec",
                "pcm_s16le",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-y",
                str(output_file),
            ],
            capture_output=True,
            check=True,
        )

        return output_file.read_bytes()


def call_api(audio_bytes, ref_text, core_type):
    timestamp = str(int(time.time()))

    # Signature for connect
    connect_sig_str = APP_KEY + timestamp + SECRET_KEY
    connect_sig = hashlib.sha1(connect_sig_str.encode()).hexdigest()

    # Signature for start
    user_id = "guest"
    start_sig_str = APP_KEY + timestamp + user_id + SECRET_KEY
    start_sig = hashlib.sha1(start_sig_str.encode()).hexdigest()

    # Build text payload
    text_payload = {
        "connect": {
            "cmd": "connect",
            "param": {
                "sdk": {"version": 16777472, "source": 9, "protocol": 2},
                "app": {
                    "applicationId": APP_KEY,
                    "timestamp": timestamp,
                    "sig": connect_sig,
                },
            },
        },
        "start": {
            "cmd": "start",
            "param": {
                "app": {
                    "userId": user_id,
                    "applicationId": APP_KEY,
                    "timestamp": timestamp,
                    "sig": start_sig,
                },
                "audio": {
                    "audioType": "wav",
                    "channel": 1,
                    "sampleBytes": 2,
                    "sampleRate": 16000,
                },
                "request": {
                    "coreType": core_type,
                    "refText": ref_text,
                    "tokenId": "streamlit-test",
                },
            },
        },
    }

    url = BASE_URL + core_type

    files = {
        "text": (None, json.dumps(text_payload)),
        "audio": ("audio.wav", audio_bytes, "application/octet-stream"),
    }

    headers = {"Request-Index": "0"}

    response = requests.post(url, files=files, headers=headers, timeout=30)
    return response.json()


import time

st.set_page_config(page_title="Spanish Pronunciation", layout="wide")

# Authentication check
if not check_authentication():
    login_page()
    st.stop()

# Main app (only shown when authenticated)
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🎤 Spanish Pronunciation Test")
    st.markdown(f"**Welcome, {st.session_state.get('user_id', 'User')}!**")

with col2:
    if st.button("Logout", type="secondary"):
        logout()

test_type = st.sidebar.radio("Type", ["Words", "Sentences", "Custom Text"])

if test_type == "Custom Text":
    st.sidebar.markdown("---")
    custom_text = st.sidebar.text_area(
        "Enter Spanish text to practice:",
        placeholder="Type your Spanish text here...",
        help="Enter any Spanish word or sentence you want to practice"
    )
    
    # Determine if it's a word or sentence based on spaces
    if custom_text.strip():
        word_count = len(custom_text.strip().split())
        if word_count == 1:
            core_type = "word.eval.sp"
            st.sidebar.info("📝 Single word detected - using word evaluation")
        else:
            core_type = "sent.eval.sp"
            st.sidebar.info("📝 Multiple words detected - using sentence evaluation")
        
        ref_text = custom_text.strip()
    else:
        ref_text = None
        core_type = None
else:
    selected = st.sidebar.selectbox("Select", list(TESTS[test_type].keys()))
    ref_text, core_type = TESTS[test_type][selected]

if ref_text:
    st.code(ref_text)
    audio = st.audio_input("Record")

    if audio and st.button("Analyze", type="primary"):
        with st.spinner("Processing..."):
            wav = convert_to_wav(audio)
            result = call_api(wav, ref_text, core_type)

        st.json(result)

        if result.get("result"):
            data = result["result"]
            cols = st.columns(4)
            for i, metric in enumerate(["overall", "fluency", "accuracy", "integrity"]):
                if metric in data:
                    cols[i].metric(metric.title(), f"{data[metric]}")
else:
    st.info("👆 Please enter some Spanish text in the sidebar to get started")
