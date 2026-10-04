"""Real native CPU decoder smoke; no model download or personal recording."""
from pathlib import Path
import tempfile
import wave
from faster_whisper.audio import decode_audio

with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'silence.wav'
    with wave.open(str(path),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(16000)
        stream.writeframes(b'\x00\x00'*16000)
    samples=decode_audio(str(path),sampling_rate=16000)
    assert len(samples)==16000
    assert float(abs(samples).max())==0
print('NATIVE CPU AUDIO DECODE: OK')
