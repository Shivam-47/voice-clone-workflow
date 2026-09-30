# voices/

One file per voice, named after it. Everything here except this README is gitignored.

```
voices/gilfoyle.wav      -> voice "gilfoyle"  (wav, mp3, m4a, flac, mp4, ... anything ffmpeg reads)
voices/gilfoyle.txt      -> exact transcript (created with Whisper on first use; fix misheard words)
voices/raw/              -> untrimmed source recordings (ignored)
voices/.cache/           -> prepared clips: mono, 24 kHz, loudness-normalized, first 20 s (auto)
```

Good sample: **10-20 s, only that person speaking, no music / laugh track / other voices**, natural delivery,
ending on a pause. If the good part is in the middle of a recording:

```bash
python scripts/make_ref.py erlich voices/raw/scene.mp4 --start 42 --duration 14
```

From a movie or show, isolate the voice first if there's background music:

```bash
uv pip install demucs
demucs --two-stems=vocals -o voices/raw/separated voices/raw/scene.mp4
```

The transcript must match the clip word for word. Qwen3-TTS only clones with both; without it the output is
short, broken and not in the voice.

Only clone voices you have the right to use, and keep clones of real people private.
