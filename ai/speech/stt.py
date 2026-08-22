import torch
import whisper

class SpeechToText:
    def __init__(self, model_name: str = "small"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self.model = whisper.load_model(
            model_name,
            device=self.device
        )

    def transcribe(self, audio_path:str ) -> str:
        result = self.model.transcribe(
            audio_path,
            language="de",
            fp16=self.device == "cuda"
        )  

        text = result["text"]
        return text.strip()