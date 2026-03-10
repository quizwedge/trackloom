# Troubleshooting

## Common issues

- `mutagen` not found / missing metadata parsing:
  - install dependencies: `python3 -m pip install -e .`
- Editable install issues on older pip:
  - `python3 -m pip install --upgrade pip setuptools wheel`
  - fallback: `python3 -m pip install -e . --no-use-pep517`
- `review` blocked by manual-item cap:
  - increase cap or disable with `--max-manual-items 0`
- `apply` cancelled unexpectedly with `--yes`:
  - expected safeguard; type `APPLY` when prompted or use `--force`
- Quarantine mode error:
  - provide `--quarantine-dir` with `--cleanup-mode move-to-quarantine`
- Plex mode skipped too many files:
  - inspect `mode_skipped_operations` in JSON output/report for reasons
  - ensure source extensions/codecs are Plex-compatible (DRM-protected files are excluded)
