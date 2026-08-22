import ollama


class GermanChatbot:
    def __init__(self, model_name: str = "qwen3:4b"):
        self.model_name = model_name

        self.system_prompt = """
Du bist ein freundlicher und geduldiger deutscher Sprachlehrer.

Deine Aufgabe ist es, mit dem Benutzer auf Deutsch zu sprechen
und ihm dabei zu helfen, sein Deutsch zu verbessern.

Regeln:
- Sprich hauptsächlich auf Deutsch.
- Passe die Sprache an das Niveau des Benutzers an.
- Halte deine Antworten natürlich und nicht unnötig lang.
- Stelle gelegentlich Fragen, damit das Gespräch weitergeht.
- Wenn der Benutzer einen grammatikalischen Fehler macht,
  korrigiere ihn freundlich.
- Vermeide komplizierte Wörter, wenn sie nicht notwendig sind.
"""

    def generate_response(self, messages: list[dict]) -> str:

        conversation = [
            {
                "role": "system",
                "content": self.system_prompt
            }
        ]

        conversation.extend(messages)

        response = ollama.chat(
            model=self.model_name,
            messages=conversation
        )

        return response["message"]["content"].strip()