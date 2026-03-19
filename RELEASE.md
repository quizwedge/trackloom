# Release Checklist

Use this checklist for versioned releases.

## Pre-release

1. Verify clean working tree.
2. Run tests:
   - `python3 -m pytest -q`
3. Build and validate distributions:
   - `python3 -m pip install --upgrade build twine setuptools wheel`
   - `python3 -m build`
   - `python3 -m twine check dist/*`
   - `python3 -m pip install --force-reinstall dist/*.whl`
   - `trackloom help`
4. (Optional) Regenerate demo fixtures:
   - `python3 scripts/make_demo_data.py --force`
5. Review docs for changed flags/behavior:
   - `README.md`
   - `AGENTS.md`
   - relevant ADRs in `adr/`

## Version update

1. Bump version in `pyproject.toml`.
2. Commit version bump and documentation updates.
3. Create a git tag:
   - `git tag vX.Y.Z`

## Publish

1. Optional TestPyPI dry run:
   - `python3 -m twine upload --repository testpypi dist/*`
2. Upload to PyPI:
   - `python3 -m twine upload dist/*`

## Post-release

1. Push commits and tags:
   - `git push origin main`
   - `git push origin vX.Y.Z`
2. Create GitHub release notes from the tag.

## Release notes template

- Summary:
  - <one-line overview>
- Behavior changes:
  - `apply`/`review` prompts now cancel cleanly on EOF while still emitting reports/decisions, which keeps automation from crashing when stdin closes.
  - `apply` destination validation now uses `os.path.lexists` so broken symlinks/racing files are treated as existing and quarantined files are restored on failure.
- Compatibility:
  - <python version changes, config changes>
