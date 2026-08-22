from pathlib import Path
import subprocess
import sys


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

        if output_path is None:
            output = (
                self.project_root
                / "audio"
                / "output"
                / "response.wav"
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