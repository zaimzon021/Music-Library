# Paste this into your Hark as a specialty

In Hark, say: **"Save this as a specialty called shared-sound-library and follow it for every video"**, then paste everything between the lines.

Then send the push token in its own message and say: **"Save this to my vault as the Music-Library push token"**. Never paste the token inside the specialty, a file, or this repo.

---

SHARED SOUND LIBRARY + AI33 RULES (mandatory for every video)

Repo: https://github.com/zaimzon021/Music-Library  (clone it into the workspace, run `git pull` before each video)
Full rules: RULES.md in the repo. Read it on first use.
PUSH ACCESS: no GitHub login is needed. Use the Music-Library push token saved in my vault. Connect it once as a service for host github.com with Basic auth, username "x-access-token" and the token as the password (identity URL: https://github.com/zaimzon021/Music-Library.git/info/refs?service=git-receive-pack). Then plain git pull/push over HTTPS works. Never print, echo, log or commit the token. If a push is rejected, ask me; never force-push, and never delete or rename other people's files.

1. LIBRARY FIRST. Before generating any music or sound effect, search the repo:
   python3 tools/lib.py search "<mood/sound words>" --type music|sfx
   Use a library file whenever one fits. That costs zero credits.
2. GENERATE ONLY WHEN NEEDED. Generate new music or SFX only when nothing in the library fits, or what's there is clearly different from what the video needs. Before every generation, run:
   python3 tools/lib.py similar --prompt "<planned prompt>" --type music|sfx
   If it says REUSE, DO NOT GENERATE, use that file. Never generate something too similar to an existing file. Similar genre with a clearly different mood, tempo or instruments is fine.
3. MAKE IT REUSABLE. Prompts describe moods and styles, not one video. Music is instrumental and full-length with intro, build and climax. SFX are single clean sounds.
4. QUALITY FIRST, NO WASTE. Spend credits whenever it clearly improves the video. Never spend on duplicates, repeats, or "just to see" full generations.
5. PUSH EVERYTHING NEW. Every music track (both Suno outputs) and every SFX you generate gets added the same day:
   python3 tools/lib.py add <file> --type ... --category ... --slug ... --tags ... --prompt "<exact prompt>" --generator ... --by "<channel>"
   python3 tools/catalog.py && python3 tools/lib.py validate
   git add -A && git commit -m "add <type>: <category>/<slug> (<channel>)" && git push
6. VOICE. Lock and fact-check the script before TTS. Use one TTS job per full script, never line by line. If only one part is wrong (for example, the hook), DON'T re-voice everything. Voice only that part and splice it with tools/voice_patch.py (same voice, model, speed), then listen to the join. Re-voice the full script only if the tool prints FULL REGEN ADVISED or the join audibly doesn't match.
7. IMAGES. Use free real images first. Use AI image generation only when no real image works.
8. CREDITS. Check the balance before a batch and log what each video spent.

---
