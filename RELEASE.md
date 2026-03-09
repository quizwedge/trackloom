# Release Checklist

Use this checklist for versioned releases.

## Pre-release

1. Verify clean working tree.
2. Run tests:
   - `python3 -m pytest -q`
3. (Optional) Regenerate demo fixtures:
   - `python3 scripts/make_demo_data.py --force`
4. Review docs for changed flags/behavior:
   - `README.md`
   - `AGENTS.md`
   - relevant ADRs in `adr/`

## Version update

1. Bump version in `pyproject.toml`.
2. Commit version bump and documentation updates.
3. Create a git tag:
   - `git tag vX.Y.Z`

## Build and publish (optional)

1. Build distributions:
   - `python3 -m pip install --upgrade build twine`
   - `python3 -m build`
2. Verify package metadata:
   - `python3 -m twine check dist/*`
3. Upload to PyPI:
   - `python3 -m twine upload dist/*`

## Post-release

1. Push commits and tags:
   - `git push origin main`
   - `git push origin vX.Y.Z`
2. Create GitHub release notes from the tag.
