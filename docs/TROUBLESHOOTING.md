# Troubleshooting

## Common issues

- `mutagen` not found / missing metadata parsing:
  - install from PyPI: `python3 -m pip install trackloom`
  - for a source checkout: `python3 -m pip install -e .`
- Editable install issues on older pip:
  - `python3 -m pip install --upgrade pip setuptools wheel`
  - fallback: `python3 -m pip install -e . --no-use-pep517`
- Build/publish validation:
  - `python3 -m pip install --upgrade build twine setuptools wheel`
  - `python3 -m build`
  - `python3 -m twine check dist/*`
- `review` blocked by manual-item cap:
  - increase cap or disable with `--max-manual-items 0`
- `apply` cancelled unexpectedly with `--yes`:
  - expected safeguard; type `APPLY` when prompted or use `--force`
- Quarantine directory location:
  - default is `<dir_b>/.trackloom_quarantine`
  - override with `--quarantine-dir <path>` or disable with `--cleanup-mode none`
- Plex mode skipped too many files:
  - inspect `mode_skipped_operations` in JSON output/report for reasons
  - ensure source extensions/codecs are Plex-compatible (DRM-protected files are excluded)
