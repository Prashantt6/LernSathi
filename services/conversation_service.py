from pathlib import Path

from ai.speech.stt import SpeechToText
from ai.speech.tts import TextToSpeech
from ai.llm.model import GermanChatbot


class ConversationService:

    def __init__(self, level: str = "A1"):
        print("Loading AI models...")

        self.stt = SpeechToText("small")
        self.chatbot = GermanChatbot(model_name="qwen3:1.7b", level=level)
        self.tts = TextToSpeech()

        print("All AI models loaded.")

    @property
    def level(self) -> str:
        return self.chatbot.level

    def set_level(self, level: str):
        """Switch tutor level without reloading any models."""
        self.chatbot.set_level(level)

    def process_text(
        self,
        user_text: str,
        conversation_history: list[dict],
    ) -> dict:

        if not user_text.strip():
            raise ValueError("Please enter some text.")

        # Generate AI response using conversation_history as context
        # (read-only; service does not modify session state)
        ai_response = self.chatbot.generate_response(conversation_history)

        # Synthesize TTS
        audio_output = self.tts.synthesize(ai_response)

        return {
            "ai_response": ai_response,
            "audio_path": str(audio_output),
        }

    def process_audio(
        self,
        audio_path: str,
        conversation_history: list[dict],
    ) -> dict:

        # 1. Speech → Text
        user_text = self.stt.transcribe(audio_path)

        if not user_text:
            raise ValueError("Could not understand the audio.")

        # 2. Generate AI response using conversation_history as context
        ai_response = self.chatbot.generate_response(conversation_history)

        # 3. Text → Speech
        audio_output = self.tts.synthesize(ai_response)

        # 4. Return everything
        return {
            "user_text": user_text,
            "ai_response": ai_response,
            "audio_path": str(audio_output),
        }

    # --------------------------------------------------
    # Staged methods (used by the UI for step-by-step feedback)
    # TEXT never touches STT; VOICE always goes through Whisper.
    # --------------------------------------------------

    def transcribe(self, audio_path: str) -> str:
        """Stage 1 (voice only): Whisper speech-to-text."""
        return self.stt.transcribe(audio_path)

    def generate_reply(self, conversation_history: list[dict]) -> str:
        """Stage 2: Qwen3 response. History must already include the latest user message."""
        return self.chatbot.generate_response(conversation_history)

    def speak(self, text: str) -> str:
        """Stage 3: Piper text-to-speech."""
        return str(self.tts.synthesize(text))