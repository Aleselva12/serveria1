import json
import os
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
AUDIO_ROOT = Path(
    os.getenv("CORA_AUDIO_ROOT", str(DEFAULT_ROOT))
).expanduser().resolve()

SUPPORTED_AUDIO_EXTENSIONS = {
    ".wav", ".mp3", ".m4a", ".mp4", ".aac",
    ".flac", ".ogg", ".opus", ".webm",
}

BLOCKED_PARTS = {".git", ".venv", "__pycache__", "node_modules"}


def _safe_path(relative_path: str) -> Path:
    candidate = (AUDIO_ROOT / relative_path).resolve()

    if candidate != AUDIO_ROOT and AUDIO_ROOT not in candidate.parents:
        raise ValueError("Accesso esterno alla cartella audio vietato.")

    relative = candidate.relative_to(AUDIO_ROOT)
    if any(part in BLOCKED_PARTS for part in relative.parts):
        raise ValueError("Cartella protetta.")

    return candidate


def _format_timestamp(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _load_whisper_model():
    try:
        from faster_whisper import WhisperModel
    except ImportError as error:
        raise RuntimeError(
            "faster-whisper non è installato. Esegui: pip install faster-whisper"
        ) from error

    model_name = os.getenv("CORA_WHISPER_MODEL", "small")
    device = os.getenv("CORA_WHISPER_DEVICE", "cpu")
    compute_type = os.getenv(
        "CORA_WHISPER_COMPUTE_TYPE",
        "int8" if device == "cpu" else "float16",
    )

    return WhisperModel(
        model_name,
        device=device,
        compute_type=compute_type,
    )


def _extract_diarization_tracks(diarization_result):
    diarization = getattr(
        diarization_result,
        "speaker_diarization",
        diarization_result,
    )

    tracks = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        tracks.append({
            "start": float(turn.start),
            "end": float(turn.end),
            "speaker": str(speaker),
        })

    return tracks


def _run_local_diarization(
    audio_path: Path,
    expected_speakers: int,
):
    model_path = os.getenv("CORA_DIARIZATION_MODEL")

    if not model_path:
        return None, (
            "Diarizzazione non configurata. Imposta CORA_DIARIZATION_MODEL "
            "su un modello pyannote locale."
        )

    local_model = Path(model_path).expanduser().resolve()
    if not local_model.exists():
        return None, (
            f"Modello di diarizzazione locale non trovato: {local_model}"
        )

    try:
        from pyannote.audio import Pipeline
    except ImportError:
        return None, (
            "pyannote.audio non è installato; impossibile distinguere gli speaker."
        )

    try:
        pipeline = Pipeline.from_pretrained(str(local_model))
        result = pipeline(
            str(audio_path),
            num_speakers=max(1, expected_speakers),
        )
        return _extract_diarization_tracks(result), None
    except Exception as error:
        return None, f"Diarizzazione fallita: {error}"


def _speaker_for_segment(
    segment_start: float,
    segment_end: float,
    tracks: list[dict],
) -> Optional[str]:
    best_speaker = None
    best_overlap = 0.0

    for track in tracks:
        overlap = max(
            0.0,
            min(segment_end, track["end"])
            - max(segment_start, track["start"]),
        )
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = track["speaker"]

    return best_speaker


@tool
def list_audio_files(
    directory: str = ".",
    recursive: bool = True,
) -> str:
    """Elenca i file audio locali accessibili all'Audio Agent."""
    try:
        base = _safe_path(directory)

        if not base.exists() or not base.is_dir():
            return "La cartella audio richiesta non esiste."

        iterator = base.rglob("*") if recursive else base.glob("*")
        results = []

        for path in iterator:
            if not path.is_file():
                continue
            if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
                continue

            relative = path.relative_to(AUDIO_ROOT)
            if any(part in BLOCKED_PARTS for part in relative.parts):
                continue

            stat = path.stat()
            results.append({
                "path": str(relative),
                "type": path.suffix.lower(),
                "size_bytes": stat.st_size,
                "modified_timestamp": stat.st_mtime,
            })

            if len(results) >= 200:
                break

        return json.dumps({
            "audio_root": str(AUDIO_ROOT),
            "count": len(results),
            "files": results,
        }, ensure_ascii=False, indent=2)
    except Exception as error:
        return f"Errore durante l'elenco audio: {error}"


@tool
def transcribe_audio_file(
    relative_path: str,
    language: str = "it",
    diarize: bool = False,
    expected_speakers: int = 2,
) -> str:
    """
    Trascrive un file audio locale con faster-whisper.
    Se diarize=True prova a distinguere gli speaker usando un modello
    pyannote configurato localmente.
    """
    try:
        path = _safe_path(relative_path)

        if not path.exists() or not path.is_file():
            return "Il file audio richiesto non esiste."

        if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
            return "Formato audio non supportato."

        model = _load_whisper_model()
        segments_iter, info = model.transcribe(
            str(path),
            language=language or None,
            beam_size=5,
            vad_filter=True,
            word_timestamps=False,
        )

        segments = []
        for segment in segments_iter:
            text = segment.text.strip()
            if not text:
                continue
            segments.append({
                "start": float(segment.start),
                "end": float(segment.end),
                "text": text,
            })

        diarization_tracks = None
        diarization_warning = None

        if diarize:
            diarization_tracks, diarization_warning = _run_local_diarization(
                path,
                expected_speakers,
            )

        speaker_map = {}
        next_speaker_number = 1
        transcript_lines = []
        structured_segments = []

        for segment in segments:
            speaker_label = None

            if diarization_tracks:
                raw_speaker = _speaker_for_segment(
                    segment["start"],
                    segment["end"],
                    diarization_tracks,
                )

                if raw_speaker is not None:
                    if raw_speaker not in speaker_map:
                        speaker_map[raw_speaker] = (
                            f"Interlocutore {next_speaker_number}"
                        )
                        next_speaker_number += 1
                    speaker_label = speaker_map[raw_speaker]

            timestamp = _format_timestamp(segment["start"])
            prefix = (
                f"[{timestamp}] {speaker_label}: "
                if speaker_label
                else f"[{timestamp}] "
            )
            transcript_lines.append(prefix + segment["text"])

            structured_segments.append({
                "start": segment["start"],
                "end": segment["end"],
                "speaker": speaker_label,
                "text": segment["text"],
            })

        response = {
            "source_path": str(path.relative_to(AUDIO_ROOT)),
            "detected_language": getattr(info, "language", None),
            "language_probability": getattr(
                info,
                "language_probability",
                None,
            ),
            "diarization_requested": diarize,
            "diarization_applied": bool(diarization_tracks),
            "diarization_warning": diarization_warning,
            "transcript": "\n".join(transcript_lines),
            "segments": structured_segments,
        }

        return json.dumps(response, ensure_ascii=False, indent=2)

    except Exception as error:
        return f"Errore durante la trascrizione audio: {error}"


AUDIO_TOOLS = [
    list_audio_files,
    transcribe_audio_file,
]
