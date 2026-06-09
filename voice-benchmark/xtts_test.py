from TTS.api import TTS

print("Loading model...")

tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

print("Generating audio...")

tts.tts_to_file(
    text="नमस्ते राहुल, मेरा नाम सारा है। मैं आपकी सहायता के लिए यहाँ हूँ।",
    file_path="output.wav",
    language="hi"
)

print("Done!")