# Desktop Organizer

[![Build Windows executable](https://github.com/noorcollo/desktop-organizer-windows/actions/workflows/build-windows.yml/badge.svg)](https://github.com/noorcollo/desktop-organizer-windows/actions/workflows/build-windows.yml)

Desktop Organizer is a small Windows utility that keeps a cluttered Desktop organized by moving files into dated archive folders. It is built with Python 3.12, Tkinter, PyStray, Pillow, and PyInstaller. The application is designed for Windows 10 and Windows 11 and runs quietly in the system tray when configured for automatic startup.

## Features

The application provides a dark graphical interface with three tabs: **Run**, **Settings**, and **Log**. Manual runs support yesterday, today, or a custom date. A preview mode reports the files and folders that would be moved without changing anything. Automatic runs archive yesterday's desktop content and place it in a date-labeled folder under the configured archive directory.

Folder handling is deliberately conservative. A folder is moved only when its creation date matches the selected archive date, so older date folders and long-lived working folders are left in place. Existing destination names are never overwritten; a numbered suffix is added instead. Files can be excluded by extension or by name pattern.

The scheduler supports up to three independent time slots. Each slot may run every day, on weekdays only, or on selected custom days. If enabled, the missed-run option starts an eligible run when the application launches after a scheduled time has already passed that day.

The Windows startup option registers the application for the current Windows user. When launched from startup, the application starts hidden in the system tray. The tray menu provides **Open**, **Run Now**, the next-run display, and **Exit**. Automatic runs can show a tray notification with the number of files and folders moved.

## Download and install

The simplest installation method is to download `DesktopOrganizer.exe` from the [latest GitHub release](https://github.com/noorcollo/desktop-organizer-windows/releases/latest). The executable is a self-contained, one-file Windows application and does not require Python to be installed.

Save the executable to a permanent location, such as a folder under your user profile. Start it, open **Settings**, confirm the source folder, archive folder name, date format, exclusions, and schedules, and select **Save settings**. The default source is the current user's Desktop, and the default archive folder is `Desktop Archive`.

For a first-time setup, use the **Run** tab with **Preview only** enabled. Review the Log tab before running a real organization operation.

## Configuration reference

Settings are stored in `~/.desktop_organizer_config.json`, which resolves to the current user's home directory. Existing configuration files from earlier versions are accepted; the former single `run_time` value is migrated into the first schedule slot.

| Setting | Description | Default |
|---|---|---|
| `source_folder` | Folder whose direct contents are organized. | Current user's Desktop |
| `archive_folder_name` | Archive directory created under the source folder. | `Desktop Archive` |
| `date_format` | Python date format used for destination folders. | `%d %B %Y` |
| `exclude_extensions` | File extensions skipped during a run. | `.lnk`, `.url` |
| `exclude_names` | Names or simple wildcard patterns skipped during a run. | Empty |
| `schedules` | Up to three schedule objects containing time, repeat mode, and days. | `23:00` daily |
| `run_missed` | Runs an eligible schedule after startup when its time was missed today. | Enabled |
| `start_with_windows` | Registers the application in the current user's Windows startup key. | Disabled |

A detailed example configuration is available in [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md).

## Scheduling behavior

Automatic runs organize the previous calendar day's files and qualifying folders. A schedule is considered eligible only when its repeat mode includes the current weekday. The scheduler checks every few seconds, but each schedule slot is protected against duplicate execution within the same minute. When the application starts, the missed-run check runs once and prevents a duplicate run for the same slot and date.

The **Close** button does not exit the program when tray support is available. It hides the main window instead. To stop the scheduler and close the process, select **Exit** from the tray menu.

## Building from source

The repository contains a reproducible Windows build script. On Windows with Python 3.12 installed, open PowerShell in the project directory and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
```

The generated file is `dist\DesktopOrganizer.exe`. The build uses PyInstaller's one-file and windowed options and explicitly collects PyStray and Pillow resources.

A GitHub Actions workflow in [`.github/workflows/build-windows.yml`](.github/workflows/build-windows.yml) builds the executable on `windows-latest` whenever it is manually dispatched or when a version tag is pushed.

## Project layout

| Path | Purpose |
|---|---|
| `main.py` | Complete Tkinter application implementation. |
| `requirements.txt` | Runtime and build dependencies. |
| `build_windows.ps1` | Local Windows build command. |
| `.github/workflows/build-windows.yml` | Automated Windows packaging workflow. |
| `docs/CONFIGURATION.md` | Configuration keys and examples. |
| `docs/TROUBLESHOOTING.md` | Common setup and runtime issues. |
| `LICENSE` | MIT license terms. |
| `CONTRIBUTING.md` | Contribution and pull-request guidance. |
| `SECURITY.md` | Security-reporting process. |

## Safety and limitations

Desktop Organizer moves files. It should be tested in preview mode and configured with exclusions before the first real run. It does not upload, delete, or overwrite files, but a move can still change their location and may be affected by Windows file locks or permissions. Keep normal backups of important files.

The current release targets Windows 10 and Windows 11. The source is not intended to provide a fully supported Linux or macOS tray experience because Windows startup registration and the packaging target are Windows-specific.

## Contributing and support

Bug reports, feature requests, and pull requests are welcome. Please include the Windows version, application version, reproduction steps, relevant Log tab output, and whether the issue occurs in preview mode. Do not attach personal files or configuration files containing private paths unless they have been sanitized.

See [`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md), and [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) for project procedures.

## License

Desktop Organizer is released under the [MIT License](LICENSE).
