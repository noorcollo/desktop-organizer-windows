# Contributing

Thank you for considering a contribution to Desktop Organizer. The project values small, focused changes that preserve the application's safety-first behavior and its Windows 10/11 target.

## Before opening an issue

Search existing issues first. For a bug, include the Windows version, release version, exact reproduction steps, expected behavior, actual behavior, and sanitized Log tab output. Do not upload personal documents, private paths, or complete configuration files containing identifying information.

## Development setup

Use Windows with Python 3.12 for the closest match to the supported runtime. Create a virtual environment and install the dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the source application with:

```powershell
.\.venv\Scripts\python.exe main.py
```

The tray integration and Windows startup registry behavior are Windows-specific. Use Preview mode when testing file movement and use a temporary test directory rather than a real Desktop containing important files.

## Pull requests

Keep each pull request focused. Update the README or the relevant documentation when behavior, configuration keys, packaging, or user-visible features change. Preserve backward compatibility for `~/.desktop_organizer_config.json` whenever possible.

Before submitting, run a syntax check, test Preview mode, test a real run against a disposable directory, and run the Windows packaging script if the change affects imports or resources. Explain the tests performed in the pull-request description.

## Code style

Use clear names, type annotations where practical, small functions, and comments for behavior that protects user files. Avoid silently deleting or overwriting files. Errors for individual items should be logged while allowing the rest of a run to continue.

## Release changes

Versioned releases are built through the GitHub Actions workflow on a Windows runner. Release assets should include the packaged executable and a checksum. Update `CHANGELOG.md` with user-visible changes.
