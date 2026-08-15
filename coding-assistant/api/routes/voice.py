from fastapi import APIRouter, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from services.speech_to_text import transcribe_audio
from api.routes.query import answer_question

router = APIRouter()


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    result = await run_in_threadpool(transcribe_audio, audio_bytes)
    return result


@router.post("/ask-voice")
async def ask_voice(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    transcription = await run_in_threadpool(transcribe_audio, audio_bytes)

    answer = answer_question(transcription["text"])
    answer["question"] = transcription["text"]
    answer["language"] = transcription["language"]
    return answer
