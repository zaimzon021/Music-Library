#!/usr/bin/env python3
"""Replace ONE part of a finished voiceover (e.g. the hook) instead of re-voicing everything.

  python3 tools/voice_patch.py --voice voice.mp3 --words words.json \
      --replace-until "first sentence(s) to replace, last words of the part" \
      --new-text "The new hook text." --voice-id elevenlabs_XXXX --model eleven_v3 --speed 1.15 \
      --out voice_patched.mp3 --out-words words_patched.json

  Replace a middle part instead: add --replace-from "first words of the part".

How it works
  1. Finds the part in words.json and snaps both cut points to sentence ends,
     cutting in the middle of the natural pause (no clipped words).
  2. Voices ONLY --new-text (same voice, model and speed as the original).
  3. Trims the new clip, matches its loudness to the original part, keeps the
     original pause lengths, joins with 30 ms crossfades.
  4. Writes a new words.json with every timing shifted, so captions stay synced.
  5. Prints a QC report. If it says FULL REGEN ADVISED, or the join sounds off when
     you listen, re-voice the whole script instead (that is the fallback, not the default).
Re-render the video afterwards (rendering is local and free).
"""
import argparse, json, os, re, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.ai33 import tts  # noqa: E402

SR = 44100


def words_of(path):
    d = json.load(open(path))
    d = d[0] if isinstance(d, list) else d
    return d, [w for w in d['words'] if w['type'] == 'word']


def norm(s):
    return re.findall(r"[a-z0-9']+", s.lower())


def find(ws, phrase, last=False):
    p = norm(phrase)
    toks = [norm(w['text'])[0] if norm(w['text']) else '' for w in ws]
    hits = [i for i in range(len(toks) - len(p) + 1) if toks[i:i + len(p)] == p]
    if not hits:
        sys.exit('Could not find in transcript: ' + phrase)
    return (hits[-1] + len(p) - 1) if last else hits[0]


def sentence_end(ws, i):
    while i < len(ws) - 1 and not re.search(r'[.!?]["\')]*$', ws[i]['text']):
        i += 1
    return i


def run(*a):
    return subprocess.run(a, capture_output=True, text=True)


def lufs(path, start=None, end=None):
    args = ['ffmpeg', '-hide_banner', '-nostats']
    if start is not None:
        args += ['-ss', str(start), '-to', str(end)]
    args += ['-i', path, '-af', 'loudnorm=print_format=json', '-f', 'null', '-']
    err = run(*args).stderr
    return float(json.loads(re.findall(r'\{[^{}]*\}', err)[-1])['input_i'])


def dur(path):
    return float(run('ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path).stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--voice', required=True); ap.add_argument('--words', required=True)
    ap.add_argument('--replace-from'); ap.add_argument('--replace-until', required=True)
    ap.add_argument('--new-text', required=True); ap.add_argument('--voice-id', required=True)
    ap.add_argument('--model', default='eleven_v3'); ap.add_argument('--speed', type=float, default=1.15)
    ap.add_argument('--out', required=True); ap.add_argument('--out-words', required=True)
    a = ap.parse_args()

    meta, ws = words_of(a.words)
    i0 = find(ws, a.replace_from) if a.replace_from else 0
    if i0 > 0:  # snap start back to the beginning of its sentence
        while i0 > 0 and not re.search(r'[.!?]["\')]*$', ws[i0 - 1]['text']):
            i0 -= 1
    i1 = sentence_end(ws, find(ws, a.replace_until, last=True))
    total = dur(a.voice)
    cut_a = 0.0 if i0 == 0 else (ws[i0 - 1]['end'] + ws[i0]['start']) / 2
    cut_b = total if i1 == len(ws) - 1 else (ws[i1]['end'] + ws[i1 + 1]['start']) / 2
    lead = ws[i0]['start'] - cut_a                       # silence before the part
    tail = cut_b - ws[i1]['end']                         # silence after the part
    old_lufs = lufs(a.voice, ws[i0]['start'], ws[i1]['end'])

    CH = run('ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=channels', '-of', 'csv=p=0', a.voice).stdout.strip() or '1'
    t = tempfile.mkdtemp()
    seg, segw = f'{t}/seg.mp3', f'{t}/seg.json'
    tts(a.new_text, seg, segw, voice_id=a.voice_id, model_id=a.model, speed=a.speed)
    _, nws = words_of(segw)
    s0, s1 = max(0, nws[0]['start'] - 0.02), nws[-1]['end'] + 0.06
    new_lufs = lufs(seg, s0, s1)
    gain = old_lufs - new_lufs
    core = f'{t}/core.wav'
    run('ffmpeg', '-y', '-v', 'error', '-ss', str(s0), '-to', str(s1), '-i', seg,
        '-af', f'volume={gain:.2f}dB,aresample={SR}', '-ac', CH, core)
    part = f'{t}/part.wav'
    run('ffmpeg', '-y', '-v', 'error', '-i', core, '-af',
        f'adelay={int(lead * 1000)},apad=pad_dur={tail:.3f},afade=t=in:d=0.01', '-ar', str(SR), '-ac', CH, part)

    pieces = []
    if cut_a > 0:
        run('ffmpeg', '-y', '-v', 'error', '-to', str(cut_a), '-i', a.voice, '-ar', str(SR), '-ac', CH, f'{t}/pre.wav')
        pieces.append(f'{t}/pre.wav')
    pieces.append(part)
    if cut_b < total:
        run('ffmpeg', '-y', '-v', 'error', '-ss', str(cut_b), '-i', a.voice, '-ar', str(SR), '-ac', CH, f'{t}/post.wav')
        pieces.append(f'{t}/post.wav')
    if len(pieces) == 1:
        run('ffmpeg', '-y', '-v', 'error', '-i', pieces[0], '-b:a', '192k', a.out)
    else:
        ins = sum([['-i', p] for p in pieces], [])
        chain, prev = [], '[0]'
        for k in range(1, len(pieces)):
            lab = f'[x{k}]'
            chain.append(f'{prev}[{k}]acrossfade=d=0.03:c1=tri:c2=tri{lab}')
            prev = lab
        run('ffmpeg', '-y', '-v', 'error', *ins, '-filter_complex', ';'.join(chain), '-map', prev, '-b:a', '192k', a.out)

    # rebuild timings
    new_len = lead + (s1 - s0) + tail
    shift_new = cut_a + lead - s0
    delta = new_len - (cut_b - cut_a)
    out = []
    for w in meta['words']:
        if w['end'] <= cut_a + 1e-6:
            out.append(w)
    segmeta, _ = words_of(segw)
    for w in segmeta['words']:
        if s0 - 1e-6 <= w['start'] and w['end'] <= s1 + 1e-6:
            out.append(dict(w, start=round(w['start'] + shift_new, 3), end=round(w['end'] + shift_new, 3)))
    for w in meta['words']:
        if w['start'] >= cut_b - 1e-6:
            out.append(dict(w, start=round(w['start'] + delta, 3), end=round(w['end'] + delta, 3)))
    meta2 = dict(meta, words=out, audio_duration_secs=round(total + delta, 3),
                 text=' '.join(w['text'] for w in out if w['type'] == 'word'))
    json.dump([meta2], open(a.out_words, 'w'), indent=1)

    # QC
    after = lufs(a.out)
    before = lufs(a.voice)
    old_part = ws[i1]['end'] - ws[i0]['start']
    print(f'Replaced words {i0}-{i1} ({old_part:.1f}s) with {s1 - s0:.1f}s of new audio; total {total:.1f}s -> {total + delta:.1f}s')
    print(f'Loudness: original part {old_lufs:.1f} LUFS, new part adjusted by {gain:+.1f} dB; file {before:.1f} -> {after:.1f} LUFS')
    issues = []
    if abs(after - before) > 1.5:
        issues.append('overall loudness moved >1.5 LU')
    if abs(gain) > 6:
        issues.append('new take was very different in level (>6 dB), tone may not match')
    print('QC:', 'FULL REGEN ADVISED: ' + '; '.join(issues) if issues else 'OK. Listen to the join before using it.')


if __name__ == '__main__':
    main()
