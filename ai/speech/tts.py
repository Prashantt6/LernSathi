import re

from pathlib import Path
import subprocess
import sys
import uuid

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags (iOS)
    "\U00002500-\U00002BEF"  # various symbols
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]",
    flags=re.UNICODE,
)


def strip_emoji(text: str) -> str:
    return EMOJI_PATTERN.sub("", text)


class TextToSpeech:
    def __init__(self, model_path=None):
        project_root = Path(__file__).resolve().parents[2]

        self.project_root = project_root

        if model_path is None:
            model_path = (
                project_root
                / "models"
                / "tts"
                / "de_DE-thorsten-medium.onnx"
            )

        self.model_path = Path(model_path)

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"TTS model not found: {self.model_path}"
            )

    def synthesize(
        self,
        text: str,
        output_path=None,
    ) -> str:

        text = strip_emoji(text)

        if output_path is None:
            filename = f"response_{uuid.uuid4().hex}.wav"
            output = (
                self.project_root
                / "audio"
                / "output"
                / filename
            )
        else:
            output = Path(output_path)

            # If a relative path is supplied, make it relative
            # to the project root rather than tests/
            if not output.is_absolute():
                output = self.project_root / output

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "piper",
                "--model",
                str(self.model_path),
                "--output_file",
                str(output),
            ],
            input=text.encode("utf-8"),
            capture_output=True,
        )

        if result.returncode != 0:
            error = result.stderr.decode(
                "utf-8",
                errors="replace",
            )

            raise RuntimeError(
                f"Piper TTS failed:\n{error}"
            )

        return str(output)