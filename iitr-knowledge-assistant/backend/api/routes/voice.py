import os
import uuid
import shutil
import logging
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from backend.services.voice_service import transcribe_audio, synthesize_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])


class SynthesizeRequest(BaseModel):
    text: str


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    temp_dir = tempfile.gettempdir()
    suffix = os.path.splitext(file.filename)[1] if file.filename else ".webm"
    temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}{suffix}")

    try:
        with open(temp_path, "wb") as f:
            f.write(await file.read())

        transcript = transcribe_audio(temp_path)
        return {"text": transcript}
    except Exception as e:
        logger.exception("Error during transcription")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@router.post("/synthesize")
async def synthesize(body: SynthesizeRequest):
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    temp_dir = tempfile.gettempdir()
    base = os.path.join(temp_dir, str(uuid.uuid4()))
    wav_path = base + ".wav"
    mp3_path = base + ".mp3"

    try:
        synthesize_text(text, wav_path)

        # Determine which file was actually produced
        if os.path.exists(wav_path):
            with open(wav_path, "rb") as f:
                audio_bytes = f.read()
            media_type = "audio/wav"
        elif os.path.exists(mp3_path):
            with open(mp3_path, "rb") as f:
                audio_bytes = f.read()
            media_type = "audio/mpeg"
        else:
            raise RuntimeError("No audio file produced by TTS")

        return Response(
            content=audio_bytes,
            media_type=media_type,
            headers={"Content-Disposition": "attachment; filename=response.wav"},
        )
    except Exception as e:
        logger.exception("Error during synthesis")
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {str(e)}")
    finally:
        for p in (wav_path, mp3_path):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
