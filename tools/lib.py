#!/usr/bin/env python3
"""Shared sound library: search it, check for near-duplicates, add new files.

Usage:
  python3 tools/lib.py search "horror music box dread" [--type music|sfx] [--top 8]
  python3 tools/lib.py similar --prompt "dark horror trailer, creepy music box" [--file new.mp3] [--type music]
  python3 tools/lib.py add new.mp3 --type music --category horror --slug creepy-lullaby \
        --tags horror,music-box,lullaby --prompt "..." --generator "Suno via AI33" --by "your-channel" [--energy high]
  python3 tools/lib.py validate

Run everything from the repo root. Needs: python3, numpy, ffmpeg/ffprobe.
"""
import argparse, datetime, json, os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, 'library.json')
STOP = set('a an the and or of to with then into in on for by from very big huge score track music sound effect sfx'.split())

# Similarity thresholds. "Too similar" means: do NOT generate, reuse the existing file.
TEXT_TOO_SIMILAR = 0.55   # word/tag overlap of description vs existing item
AUDIO_TOO_SIMILAR = 0.97  # cosine of coarse audio fingerprints (only when --file given)


def load():
    return json.load(open(LIB))


def save(d):
    d['updated'] = datetime.date.today().isoformat()
    json.dump(d, open(LIB, 'w'), indent=2)


def words(s):
    return {w for w in re.findall(r'[a-z0-9]+', s.lower().replace('-', ' ')) if w not in STOP and len(w) > 1}


def item_words(it):
    return words(' '.join(it.get('tags', [])) + ' ' + it.get('prompt', '') + ' ' + it.get('category', '') + ' ' + it['id'])


def text_score(q, it):
    a, b = words(q), item_words(it)
    if not a or not b:
        return 0.0
    common = len(a & b)
    score = common / min(len(a), len(b))
    return score if common >= 3 else min(score, 0.4)  # 1-2 shared words is never "too similar"


def fingerprint(path):
    """Coarse, mood-level fingerprint: band energies + their movement over time."""
    import numpy as np
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', '11025', '-f', 's16le', '-'],
                         capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    if len(x) < 4096:
        x = np.pad(x, (0, 4096 - len(x)))
    n = 2048
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[::n]
    spec = np.abs(np.fft.rfft(frames * np.hanning(n), axis=1)) + 1e-9
    edges = np.geomspace(1, spec.shape[1] - 1, 25).astype(int)
    bands = np.stack([spec[:, edges[i]:max(edges[i] + 1, edges[i + 1])].mean(1) for i in range(24)], 1)
    lb = np.log(bands)
    v = np.concatenate([lb.mean(0), lb.std(0), np.abs(np.diff(lb, axis=0)).mean(0)])
    v = v - v.mean()
    return v / (np.linalg.norm(v) + 1e-9)


def cmd_search(a):
    d = load()
    rows = [(text_score(a.query, it), it) for it in d['items'] if not a.type or it['type'] == a.type]
    rows.sort(key=lambda r: -r[0])
    for s, it in rows[:a.top]:
        print(f"{s:.2f}  {it['file']}  [{', '.join(it.get('tags', []))}]  {it.get('duration_s', '?')}s")


def cmd_similar(a):
    d = load()
    pool = [it for it in d['items'] if not a.type or it['type'] == a.type]
    rows = sorted(((text_score(a.prompt, it), it) for it in pool), key=lambda r: -r[0])[:5]
    verdict = 'OK TO GENERATE (nothing too similar by description)'
    print('Closest by description:')
    for s, it in rows:
        flag = '  <-- TOO SIMILAR' if s >= TEXT_TOO_SIMILAR else ''
        print(f"  {s:.2f}  {it['file']}{flag}")
        if s >= TEXT_TOO_SIMILAR:
            verdict = 'REUSE, DO NOT GENERATE: ' + it['file']
            break
    if a.file:
        fq = fingerprint(a.file)
        best = []
        for it in pool:
            p = os.path.join(ROOT, it['file'])
            if os.path.exists(p):
                best.append((float(fq @ fingerprint(p)), it))
        best.sort(key=lambda r: -r[0])
        print('Closest by sound:')
        for s, it in best[:5]:
            flag = '  <-- TOO SIMILAR' if s >= AUDIO_TOO_SIMILAR else ''
            print(f"  {s:.3f}  {it['file']}{flag}")
        if best and best[0][0] >= AUDIO_TOO_SIMILAR:
            verdict = 'TOO SIMILAR TO ' + best[0][1]['file'] + ': do not add, reuse it'
    print('VERDICT:', verdict)
    print('(The numbers are a guide. Listen/read the closest items before deciding.)')


def cmd_add(a):
    d = load()
    if a.type == 'music' and not a.category:
        sys.exit('music needs --category (a mood folder, e.g. horror, epic-cinematic)')
    folder = os.path.join(a.type if a.type == 'music' else 'sfx', a.category)
    os.makedirs(os.path.join(ROOT, folder), exist_ok=True)
    ext = os.path.splitext(a.src)[1].lower() or '.mp3'
    rel = os.path.join(folder, a.slug + ext)
    if os.path.exists(os.path.join(ROOT, rel)):
        sys.exit('A file with that name already exists: ' + rel)
    shutil.copy(a.src, os.path.join(ROOT, rel))
    dur = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0',
                          os.path.join(ROOT, rel)], capture_output=True, text=True).stdout.strip()
    it = dict(id=os.path.splitext(rel)[0], type=a.type, file=rel, category=a.category,
              tags=[t.strip() for t in a.tags.split(',') if t.strip()],
              duration_s=round(float(dur or 0), 1), prompt=a.prompt, generator=a.generator,
              added_by=a.by, added=datetime.date.today().isoformat(), used_in=[a.used_in] if a.used_in else [],
              notes=a.notes or '')
    if a.type == 'music':
        it['energy'] = a.energy
        it['instrumental'] = True
    d['items'].append(it)
    save(d)
    print('Added', rel, '- now commit and push (see RULES.md, rule 5).')


def cmd_validate(a):
    d = load()
    bad = 0
    ids = set()
    for it in d['items']:
        if it['id'] in ids:
            print('duplicate id', it['id']); bad += 1
        ids.add(it['id'])
        if not os.path.exists(os.path.join(ROOT, it['file'])):
            print('missing file', it['file']); bad += 1
    print(f"{len(d['items'])} items, {bad} problems")
    sys.exit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    s = sp.add_parser('search'); s.add_argument('query'); s.add_argument('--type'); s.add_argument('--top', type=int, default=8)
    s = sp.add_parser('similar'); s.add_argument('--prompt', required=True); s.add_argument('--file'); s.add_argument('--type')
    s = sp.add_parser('add'); s.add_argument('src'); s.add_argument('--type', choices=['music', 'sfx'], required=True)
    s.add_argument('--category', required=True); s.add_argument('--slug', required=True); s.add_argument('--tags', required=True)
    s.add_argument('--prompt', required=True); s.add_argument('--generator', required=True); s.add_argument('--by', required=True)
    s.add_argument('--energy', default='medium'); s.add_argument('--used-in', dest='used_in'); s.add_argument('--notes')
    sp.add_parser('validate')
    a = ap.parse_args()
    dict(search=cmd_search, similar=cmd_similar, add=cmd_add, validate=cmd_validate)[a.cmd](a)


if __name__ == '__main__':
    main()
