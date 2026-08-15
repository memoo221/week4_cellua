import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import tempfile
from pathlib import Path
from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")


def transcribe_audio(audio_bytes: bytes) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as f:
        f.write(audio_bytes)
        path = Path(f.name)

    segments, info = model.transcribe(str(path))
    text = " ".join(segment.text.strip() for segment in segments)

    path.unlink(missing_ok=True)

    return {"text": text.strip(), "language": info.language}
