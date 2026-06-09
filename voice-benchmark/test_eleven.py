from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv
import os

load_dotenv()

client = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY")
)

audio_stream = client.text_to_speech.convert(
    voice_id="FGY2WhTYpPnrIDTdsKH5",
    text="नमस्ते राहुल, मेरा नाम सारा है। मैं एक कृत्रिम बुद्धिमत्ता आधारित सहायक हूँ और आपकी सहायता के लिए यहाँ हूँ।",
    model_id="eleven_multilingual_v2"
)

with open("output4.mp3", "wb") as f:
    for chunk in audio_stream:
        if chunk:
            f.write(chunk)

print("Saved!")