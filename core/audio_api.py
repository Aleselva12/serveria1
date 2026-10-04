"""Owner UI for existing recordings, sharing the single runtime with chat."""
import json
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb
from core.database import db_connection
from core.server_files import operation, upload_to, resolve, exists
from core.runtime import runtime, checkpoint

from core.access import owner_dependency
router = APIRouter(prefix='/api/v1/audio', tags=['Audio'], dependencies=[Depends(owner_dependency('files'))])


def engine():
    from audio_agent import audio_tools
    return audio_tools


def get_record(ident):
    with db_connection() as conn:
        row = conn.execute('SELECT * FROM audio_records WHERE id=%s AND archived=FALSE', (ident,)).fetchone()
    if not row: raise HTTPException(404, 'Registrazione non trovata.')
    return row


def public(row):
    from core.run_lifecycle import get_run, persisted_snapshot
    state = None
    if row['run_id']:
        live = runtime.get(str(row['run_id']))
        if live: state = live.snapshot()
        else:
            try: state = persisted_snapshot(get_run(str(row['run_id'])))
            except KeyError: pass
    return {'id': str(row['id']), 'title': row['title'], 'name': row['name'], 'recordedAt': row['recorded_at'],
            'speakerNames': row['speaker_names'], 'createdAt': row['created_at'].isoformat(), 'version': row['version'],
            'transcript': row['transcript'], 'result': row['machine_result'], 'run': state}


@router.get('/status')
def audio_status():
    import importlib.util
    import os
    model = os.getenv('CORA_WHISPER_MODEL', 'small')
    local_only = os.getenv('CORA_WHISPER_LOCAL_ONLY', 'false').lower() == 'true'
    installed = importlib.util.find_spec('faster_whisper') is not None
    model_ready = not local_only or (Path(model).is_dir() and all((Path(model)/name).is_file() for name in ('model.bin','config.json','tokenizer.json')))
    diarization = os.getenv('CORA_DIARIZATION_MODEL', '')
    return {'ready': installed and model_ready, 'engineInstalled': installed, 'localModelReady': model_ready,
            'localOnly': local_only, 'diarizationReady': bool(diarization and Path(diarization).exists() and importlib.util.find_spec('pyannote') is not None)}


@router.get('')
def records():
    with db_connection() as conn:
        rows = conn.execute('SELECT id,title,name,source_path,recorded_at,speaker_names,created_at,run_id,version,NULL AS transcript,NULL AS machine_result FROM audio_records WHERE archived=FALSE ORDER BY created_at DESC LIMIT 200').fetchall()
    # List metadata only; fetch text/details on selection.
    return {'items': [{k: v for k,v in public(r).items() if k not in {'transcript','result'}} for r in rows]}


@router.post('', status_code=201)
def upload(file: UploadFile = File(...), title: str = Form(''), recorded_at: str = Form(''), speaker_one: str = Form(''), speaker_two: str = Form('')):
    tools = engine()
    name = file.filename or ''
    if Path(name).suffix.lower() not in tools.SUPPORTED_AUDIO_EXTENSIONS:
        file.file.close()
        raise HTTPException(415, 'Formato audio non supportato.')
    if any(len(s)>200 for s in [title,recorded_at,speaker_one,speaker_two]):
        file.file.close()
        raise HTTPException(422, 'Metadati troppo lunghi.')
    ident = uuid.uuid4()
    base = tools.AUDIO_ROOT
    base.mkdir(parents=True, exist_ok=True)
    with operation():
        inbox = resolve(base, 'ui_uploads')
        inbox.mkdir(exist_ok=True)
        folder = resolve(base, 'ui_uploads/'+ident.hex)
        folder.mkdir()
    try:
        item = upload_to({'writable': True}, base, 'ui_uploads/'+ident.hex, file)
        with db_connection() as conn:
            row = conn.execute('''INSERT INTO audio_records(id,title,name,source_path,recorded_at,speaker_names)
                VALUES(%s,%s,%s,%s,%s,%s) RETURNING *''', (ident,title.strip() or name,name,item['path'],recorded_at,Jsonb([speaker_one.strip(),speaker_two.strip()]))).fetchone()
        return public(row)
    except Exception:
        import shutil
        shutil.rmtree(folder, ignore_errors=True)
        raise


@router.get('/{ident}')
def record(ident: uuid.UUID):
    return public(get_record(ident))


@router.get('/{ident}/source')
def source(ident: uuid.UUID):
    row = get_record(ident)
    target = resolve(engine().AUDIO_ROOT, row['source_path'])
    exists(target)
    return FileResponse(target, filename=row['name'], headers={'Cache-Control': 'private, no-store'})


class TranscriptionRequest(BaseModel):
    language: str = Field(default='it', max_length=10)
    diarize: bool = False
    expected_speakers: int = Field(default=2, ge=1, le=10)
    expected_version: int = Field(ge=1)


@router.post('/{ident}/transcribe', status_code=202)
def transcribe(ident: uuid.UUID, body: TranscriptionRequest):
    row = get_record(ident)
    if row['version'] != body.expected_version: raise HTTPException(409, 'Registrazione aggiornata: ricarica i dettagli.')
    if row['transcript'] is not None: raise HTTPException(409, 'Trascrizione già disponibile; puoi correggerla ed esportarla.')
    if not audio_status()['ready']: raise HTTPException(503, 'Trascrizione non disponibile: installa le dipendenze Audio e prepara il modello Whisper locale.')
    def work(run):
        with db_connection() as conn:
            conn.execute('UPDATE audio_records SET run_id=%s WHERE id=%s', (uuid.UUID(run.id),ident))
        tools = engine()
        target = resolve(tools.AUDIO_ROOT, row['source_path'])
        exists(target)
        result = tools.transcribe_path(target, body.language, body.diarize, body.expected_speakers)
        checkpoint()
        transcript = result['transcript']
        for number, name in enumerate(row['speaker_names'], 1):
            if name:
                import re
                transcript = re.sub(r'(^\[[0-9:]+\] )Interlocutore '+str(number)+':', lambda match: match.group(1)+name+':', transcript, flags=re.MULTILINE)
        with db_connection() as conn:
            saved = conn.execute('''UPDATE audio_records SET transcript=%s,machine_result=%s,version=version+1
                WHERE id=%s AND version=%s AND archived=FALSE AND transcript IS NULL RETURNING id''',
                (transcript,Jsonb(result),ident,body.expected_version)).fetchone()
            if not saved: raise RuntimeError('Trascrizione non salvata: registrazione modificata.')
        return {'audio_id': str(ident), 'transcript_saved': True}
    try:
        run = runtime.submit('audio:'+str(ident), work, graph_version='audio-upload-v1', kind='audio', target='audio_agent')
    except ValueError as error: raise HTTPException(409, str(error)) from error
    except RuntimeError as error: raise HTTPException(503, 'Runtime non disponibile. Verifica Attività.') from error
    with db_connection() as conn:
        conn.execute('UPDATE audio_records SET run_id=%s WHERE id=%s', (uuid.UUID(run.id),ident))
    return run.snapshot()


class TranscriptEdit(BaseModel):
    transcript: str = Field(max_length=1_000_000)
    expected_version: int = Field(ge=1)


@router.put('/{ident}/transcript')
def edit(ident: uuid.UUID, body: TranscriptEdit):
    with db_connection() as conn:
        row = conn.execute('''UPDATE audio_records SET transcript=%s,version=version+1
            WHERE id=%s AND version=%s AND archived=FALSE AND transcript IS NOT NULL RETURNING *''',
            (body.transcript,ident,body.expected_version)).fetchone()
    if not row: raise HTTPException(409, 'Trascrizione non disponibile o versione cambiata. Ricarica i dettagli.')
    return public(row)


@router.get('/{ident}/transcript/download')
def export(ident: uuid.UUID):
    row = get_record(ident)
    if row['transcript'] is None: raise HTTPException(409, 'Trascrizione non ancora disponibile.')
    return Response(row['transcript'], media_type='text/plain; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="trascrizione-'+str(ident)+'.txt"','Cache-Control':'private, no-store'})


@router.post('/{ident}/library', status_code=201)
def copy_to_library(ident: uuid.UUID):
    from io import BytesIO
    from core.ia_library import upload_copy
    row = get_record(ident)
    if row['transcript'] is None: raise HTTPException(409, 'Trascrizione non ancora disponibile.')
    # Version in the filename avoids overwriting an earlier imported transcript.
    name = 'trascrizione-'+str(ident)+'-v'+str(row['version'])+'.txt'
    return upload_copy('', UploadFile(filename=name, file=BytesIO(row['transcript'].encode('utf-8'))))
