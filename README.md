# Shared Sound Library

One shared library of **music and sound effects** for every channel and every Hark that uses our AI33 API key.
It's built once and reused by everyone. Only new sounds cost credits, and every new sound is added here for everyone.

**Read [RULES.md](RULES.md) first. The rules are mandatory for every person and every AI using the API.**

## What's inside
| Path | What |
|---|---|
| `music/<mood>/` | Instrumental cues (full length, with build and climax), named `<slug>-a.mp3` / `-b.mp3` |
| `sfx/<category>/` | Single clean sound effects |
| `library.json` | One entry per file: tags, mood, length, exact prompt, who added it, where it was used |
| `CATALOG.md` | Readable list of everything (auto-generated) |
| `tools/lib.py` | `search`, `similar` (duplicate check), `add`, `validate` |
| `tools/ai33.py` | AI33 client: `tts`, `sfx`, `music` (sfx and music check the library first) |
| `tools/voice_patch.py` | Replace only one part of a voiceover (e.g. the hook) instead of re-voicing everything |
| `HARK_SPECIALTY.md` | The text every person pastes into their Hark as a specialty |

## Quick start
```bash
git clone <this repo> sound-library && cd sound-library
pip install requests numpy          # ffmpeg must be installed
python3 tools/lib.py search "epic battle drums" --type music
python3 tools/lib.py search "explosion" --type sfx
```

## Typical flow for one video
1. `git pull`
2. Pick music and SFX from the library (`search`).
3. Need something new? Run `similar` first. Generate only if it says `OK TO GENERATE` (Rule 2).
4. Add every new file with `lib.py add`, then `catalog.py`, `validate`, commit, push (Rule 5).
5. Voice the **final** script once. If one part needs redoing, use `voice_patch.py` (Rule 6).

## Access
- Everyone who adds sounds needs **write access** (the owner adds them as collaborators), and their Hark needs their GitHub account connected.
- Max file size on GitHub is 100 MB. Keep files as MP3 (192 kbps is plenty).
- The AI33 API key is **never** committed here. Each Hark keeps it in its vault.
