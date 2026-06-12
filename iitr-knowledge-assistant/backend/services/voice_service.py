import os
import logging
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# Singleton — only Whisper needs preloading; gTTS is stateless
_whisper_model = None


def init_voice_models():
    """Preload Whisper at startup. gTTS requires no preloading."""
    global _whisper_model
    if _whisper_model is None:
        logger.info("Initializing Whisper 'base' model on CPU...")
        try:
            _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
            logger.info("Whisper model initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Whisper model: {e}")


def get_whisper_model() -> WhisperModel:
    global _whisper_model
    if _whisper_model is None:
        init_voice_models()
    return _whisper_model


def transcribe_audio(audio_path: str) -> str:
    model = get_whisper_model()
    if model is None:
        raise RuntimeError("Whisper model not initialized")

    segments, _info = model.transcribe(
        audio_path,
        beam_size=5,
        language="en",          # force English — avoids mis-detection
        condition_on_previous_text=False,
    )
    return " ".join(seg.text for seg in segments).strip()


def synthesize_text(text: str, output_path: str) -> None:
    """
    Synthesise text to a WAV file using Google TTS with an Indian English
    accent (tld='co.in').  The result is an MP3 internally but we save it
    to whatever path is given (callers rename to .mp3 or convert as needed).
    """
    from gtts import gTTS
    import subprocess
    import shutil

    # gTTS produces MP3; save as .mp3 first, then convert to WAV if ffmpeg is present
    mp3_path = output_path.replace(".wav", ".mp3")
    tts = gTTS(text=text, lang="en", tld="co.in", slow=False)
    tts.save(mp3_path)

    # Try to convert to WAV so the browser Audio element plays it natively
    if shutil.which("ffmpeg"):
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", mp3_path, output_path],
                capture_output=True,
                check=True,
            )
            os.remove(mp3_path)
        except subprocess.CalledProcessError:
            # ffmpeg conversion failed — just serve the MP3 directly
            os.rename(mp3_path, output_path)
    else:
        # No ffmpeg — rename MP3 to the expected path; caller sends as audio/mpeg
        os.rename(mp3_path, output_path)
