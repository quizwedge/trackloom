# Demo Data

Create small local demo libraries for `trackloom` commands.

## Generate

```bash
python3 scripts/make_demo_data.py --force
```

This creates:

- `demo_data/A`
- `demo_data/B`

Tagged `mp3`, `m4a`, and `flac` fixtures require `ffmpeg` to be installed.
If `ffmpeg` is unavailable, the script will skip those files and print why.

## Quick checks

```bash
trackloom parse demo_data/A
trackloom compare demo_data/A demo_data/B
trackloom compare demo_data/A demo_data/B --json > /tmp/trackloom-demo-compare.json
trackloom plan demo_data/A demo_data/B --json > /tmp/trackloom-demo-plan.json
trackloom parse demo_data/A --extensions .wav .mp3 .m4a .flac .m4p --json > /tmp/trackloom-demo-parse.json
trackloom plan demo_data/A demo_data/B --mode plex --extensions .wav .mp3 .m4a .flac .m4p --json > /tmp/trackloom-demo-plex-plan.json
```

Notes:

- The demo intentionally includes one `.m4p` placeholder to exercise Plex-mode
  skip behavior.
- When tagged compressed fixtures are generated, they exercise tag parsing
  precedence over path fields.
