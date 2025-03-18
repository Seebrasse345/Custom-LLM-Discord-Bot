# cogs/tts_engine.py

import uuid
import asyncio
from TTS.api import TTS

class CoquiTTS:
    """
    Simple wrapper around Coqui TTS.
    """
    def __init__(self, model_name="tts_models/en/ljspeech/tacotron2-DDC"):
        print(f"[DEBUG] Loading TTS model: {model_name}")
        try:
            self.tts = TTS(model_name=model_name)
            print("[DEBUG] TTS model loaded successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to load TTS model: {e}")

    def generate_wav(self, text: str, output_file: str):
        try:
            self.tts.tts_to_file(text=text, file_path=output_file)
            print(f"[DEBUG] Generated TTS audio: {output_file}")
        except Exception as e:
            print(f"[ERROR] TTS generation error: {e}")

# Create a global TTS engine instance
tts_engine = CoquiTTS()

async def setup(bot):
    pass
