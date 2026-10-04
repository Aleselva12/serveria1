"""Explicit public model preparation. Runtime transcription never uploads audio."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile


def digest(path):
    hasher=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):hasher.update(chunk)
    return hasher.hexdigest()


def verify(path):
    manifest=json.loads((path/'cora-model.json').read_text())
    if manifest.get('version')!=1 or not re.fullmatch('[0-9a-f]{40}',manifest.get('revision','')):
        raise ValueError('Invalid model manifest')
    files=manifest.get('sha256',{})
    if not {'model.bin','config.json','tokenizer.json'}.issubset(files):raise ValueError('Incomplete model manifest')
    for name,expected in files.items():
        target=(path/name).resolve()
        if not target.is_relative_to(path.resolve()):raise ValueError('Invalid model file path')
        if digest(target)!=expected:raise ValueError('Model checksum mismatch: '+name)
    return manifest


def prepare(model,destination,revision=None):
    from faster_whisper.utils import available_models,download_model,_MODELS
    from huggingface_hub import HfApi
    if model not in available_models():raise ValueError('Unknown public Whisper model')
    if destination.exists():raise ValueError('Model destination already exists; prepare a new directory instead')
    if revision is None:revision=HfApi(token=False).model_info(_MODELS[model]).sha
    if not re.fullmatch('[0-9a-f]{40}',revision or ''):raise ValueError('Use an immutable 40-character model revision')
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix='.whisper-prepare-',dir=destination.parent))
    try:
        download_model(model,output_dir=str(temporary),revision=revision,use_auth_token=False)
        files={p.name:digest(p) for p in temporary.iterdir() if p.is_file()}
        manifest={'version':1,'model':model,'repository':_MODELS[model],'revision':revision,'sha256':files}
        (temporary/'cora-model.json').write_text(json.dumps(manifest,indent=2)+'\n')
        verify(temporary)
        # Install without merging into a possibly partial or already configured model.
        temporary.rename(destination)
        return manifest
    finally:
        if temporary.exists():shutil.rmtree(temporary)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',default='small');parser.add_argument('--revision')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    destination=Path(os.getenv('CORA_WHISPER_MODEL','/state/models/whisper'))
    if args.check:
        manifest=verify(destination)
        from audio_agent.audio_tools import _load_whisper_model
        _load_whisper_model()
        print(json.dumps({'status':'ok','model':manifest['model'],'revision':manifest['revision'],'device':'cpu','privacy':'local_only'}))
    else:
        manifest=prepare(args.model,destination,args.revision)
        print(json.dumps({'status':'prepared','model':manifest['model'],'revision':manifest['revision']}))


if __name__=='__main__':main()
