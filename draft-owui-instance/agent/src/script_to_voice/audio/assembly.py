import io
from pathlib import Path
import subprocess
import tempfile
import wave
import imageio_ffmpeg


def assemble(data):
    """Decode each clip to consistent PCM, then encode exactly once."""
    if not data: raise ValueError('No audio to assemble')
    executable=imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory); pcm=[]; durations=[]
        for index,clip in enumerate(data):
            source=root/f'input-{index}.audio'; output=root/f'clip-{index}.wav'
            source.write_bytes(clip)
            result=subprocess.run([executable,'-v','error','-nostdin','-y','-i',str(source),'-t','600',
                '-ac','1','-ar','44100','-c:a','pcm_s16le',str(output)],capture_output=True,timeout=90)
            if result.returncode: raise ValueError('Audio could not be decoded')
            with wave.open(str(output),'rb') as wav:
                duration=wav.getnframes()/wav.getframerate()
                if not 0<duration<600: raise ValueError('Audio duration is empty or exceeds the clip limit')
                frames=wav.readframes(wav.getnframes()); pcm.append(frames); durations.append(duration)
            if sum(len(x) for x in pcm)>512*1024*1024: raise ValueError('Decoded assembly exceeds its size limit')
        combined=root/'combined.wav'; final=root/'combined.mp3'
        with wave.open(str(combined),'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(44100)
            for frames in pcm: wav.writeframes(frames)
        result=subprocess.run([executable,'-v','error','-nostdin','-y','-i',str(combined),'-c:a','libmp3lame','-b:a','128k',str(final)],
                              capture_output=True,timeout=90)
        if result.returncode: raise ValueError('Audio encoding failed')
        return final.read_bytes(),durations
