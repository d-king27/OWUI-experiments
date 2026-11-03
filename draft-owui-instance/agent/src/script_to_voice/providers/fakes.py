"""Deterministic, explicitly labelled fixtures. Never substitutes for live inference."""
import base64
import io
import math
import struct
import wave
from script_to_voice.contracts import *


def tone_wav(frequency=440, seconds=0.25):
    out = io.BytesIO()
    with wave.open(out, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(22050)
        audio.writeframes(b''.join(struct.pack('<h', int(3000*math.sin(2*math.pi*frequency*i/22050)))
                                  for i in range(int(seconds*22050))))
    return out.getvalue()


class FakePlanners:
    def __init__(self, intent=None):
        self.intent = intent or IntentProposal()

    async def interpret(self, request, revision, prior=None):
        return self.intent

    async def propose(self, request):
        return CastingProposal(assignments=())

    async def annotate(self, request):
        return DirectionProposal(annotations=())


class FakeVoiceProvider:
    def __init__(self):
        self.calls = []
        self.voices = {f'mock-{i}': Voice(voice_id=f'mock-{i}', name=f'Mock voice {i}') for i in range(1, 13)}

    async def list_voices(self, cursor=None):
        return VoicePage(voices=tuple(self.voices.values()))

    async def get_voice(self, voice_id):
        if voice_id.startswith('mock-designed-'):
            return Voice(voice_id=voice_id, name='Mock designed voice')
        if voice_id not in self.voices:
            raise ValueError('Voice unavailable; select a replacement')
        return self.voices[voice_id]

    async def design_previews(self, request):
        self.calls.append('design')
        key = request.semantic_hash()[:12]
        return tuple(VoicePreview(generated_voice_id=f'preview-{key}-{i}',
                     audio_base64=base64.b64encode(tone_wav(330+i*110)).decode(), mime='audio/wav') for i in range(3))

    async def save_preview(self, generated_voice_id, name, description):
        if not generated_voice_id.startswith('preview-'):
            raise ValueError('Unknown preview')
        self.calls.append('save')
        v = Voice(voice_id='mock-designed-'+digest(generated_voice_id)[:16], name=name)
        self.voices[v.voice_id] = v
        return v

    async def render(self, chunk):
        self.calls.append(chunk.id)
        return ProviderAudioResult(audio=tone_wav(seconds=max(0.25,len(chunk.request.inputs)*0.2)),
                                   mime='audio/wav', request_id='mock-'+chunk.id,
                                   timing={'mock':True, 'alignment':None, 'voice_segments':[]})
