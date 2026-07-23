# Contributing

Thank you for helping improve Hyundai Kia Developers.

## Before opening an issue

- Search existing issues and update to the latest release.
- Use the bug or feature issue form.
- For bugs, attach Home Assistant diagnostics only after checking that they are
  redacted.
- Never submit credentials, tokens, complete OAuth redirect URLs or codes, car
  IDs, or other account-identifying data.

## Development

Use Python 3.14 and Home Assistant 2026.7 or newer.

```bash
python -m pip install -e .[test]
ruff format .
ruff check .
python -m compileall custom_components tests
pytest
```

Keep runtime changes covered by tests and update both English and Korean flow
translations when user-facing strings change. Do not include captured production
payloads; create redacted fixtures with synthetic vehicle and credential data.

Pull requests should be focused, explain compatibility impact, and keep config
entry `VERSION`/`MINOR_VERSION` unchanged unless a migration is implemented and
tested. By contributing, you agree that your contribution is licensed under the
repository's MIT license.
