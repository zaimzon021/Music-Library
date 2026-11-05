#!/usr/bin/env python3
"""Minimal AI33 client used by every channel. Library first, generate second.

The API key is NOT in this repo. Each Hark keeps it in its vault and injects it
as the `xi-api-key` header for api.ai33.pro (in Hark: connect_service binds it).
If you run this elsewhere, set AI33_KEY in your environment.

  from tools.ai33 import tts, sfx, music
  tts("Full final script...", "voice.mp3", "words.json", voice_id="elevenlabs_...", model_id="eleven_v3", speed=1.15)
  sfx("giant kaiju roar, distorted", "roar.mp3", dur=2.5, check_prompt=True)   # refuses if the library has it
  music("dark horror trailer score ...", "out/horror_new", check_prompt=True)  # refuses if the library has it

Credit guide (approx., Nov 2026): TTS eleven_v3 ~1,200 credits per 60 s Short,
SFX ~100-300 each, Suno music 3,600 per call (returns 2 tracks), image gen ~2,574.
"""
import json, os, subprocess, sys, time
import requests

B = 'https://api.ai33.pro'
H = {'xi-api-key': os.environ.get('AI33_KEY', 'x')}  # 'x' is replaced on the wire inside Hark
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def post(path, **kw):
    for _ in range(400):
        r = requests.post(B + path, headers=H, timeout=120, **kw).json()
        if r.get('code') == 'active_task_limit' or (r.get('error') or {}).get('code') == 'queue_limit_exceeded':
            time.sleep(15); continue
        return r
    return r


def poll(tid, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = requests.get(f'{B}/v1/task/{tid}', headers=H, timeout=60).json()
        if r.get('status') == 'done':
            return r
        if r.get('status') in ('failed', 'error'):
            raise RuntimeError(json.dumps(r)[:800])
        time.sleep(5)
    raise TimeoutError(tid)


def credits():
    return requests.get(f'{B}/v1/credits', headers=H, timeout=60).json().get('credits')


def dl(url, path):
    r = requests.get(url, timeout=300); r.raise_for_status(); open(path, 'wb').write(r.content)


def _library_guard(prompt, typ):
    out = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'lib.py'), 'similar', '--prompt', prompt, '--type', typ],
                         capture_output=True, text=True).stdout
    print(out)
    if 'REUSE, DO NOT GENERATE' in out:
        raise SystemExit('Library already has a very similar ' + typ + '. Reuse it (see above). '
                         'If it truly does not fit the quality you need, call again with check_prompt=False and say why in the commit.')


def tts(text, out_mp3, out_json, voice_id, model_id='eleven_v3', speed=1.15, tries=3):
    """One job per FINAL script (or per patch segment). Never line by line."""
    for _ in range(tries):
        try:
            r = post('/v3/text-to-speech', data=dict(text=text, voice_id=voice_id, model_id=model_id,
                                                     speed=str(speed), with_transcript='true'))
            if not r.get('success'):
                raise RuntimeError(str(r))
            m = poll(r['task_id'])['metadata']
            dl(m['audio_url'], out_mp3); dl(m['json_url'], out_json); return
        except Exception as e:
            print('tts retry', e, file=sys.stderr); time.sleep(10)
    raise RuntimeError('tts failed')


def sfx(prompt, out, dur=None, check_prompt=True):
    if check_prompt:
        _library_guard(prompt, 'sfx')
    body = {'text': prompt, 'model_id': 'eleven_text_to_sound_v3'}
    if dur:
        body['duration_seconds'] = dur
    r = post('/v1/task/sound-effect', json=body)
    if not r.get('success'):
        raise RuntimeError(str(r))
    dl(poll(r['task_id'])['metadata']['audio_url'], out)
    print('Generated', out, '-> now: python3 tools/lib.py add ... and push (RULES.md rule 5)')


def music(prompt, outbase, check_prompt=True, tries=2):
    if check_prompt:
        _library_guard(prompt, 'music')
    for _ in range(tries):
        try:
            r = post('/v1s/task/music-generation', json={'create_mode': 'simple', 'gpt_description_prompt': prompt,
                                                         'make_instrumental': True})
            if not r.get('success'):
                raise RuntimeError(str(r))
            clips = poll(r['task_id'], 1500)['metadata']['suno_result']['clips']
            outs = []
            for i, c in enumerate(clips):
                if c.get('audio_url'):
                    p = f'{outbase}_{i}.mp3'; dl(c['audio_url'], p); outs.append(p)
            if outs:
                print('Generated', outs, '-> add BOTH to the library and push (RULES.md rule 5)')
                return outs
        except Exception as e:
            print('music retry', e, file=sys.stderr); time.sleep(15)
    raise RuntimeError('music failed')
