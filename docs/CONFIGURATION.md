# Configuration reference

Desktop Organizer stores its settings in `~/.desktop_organizer_config.json`. On Windows this normally resolves beneath the current user's profile directory. The file is created or updated when **Save settings** is selected.

## Example

```json
{
  "source_folder": "C:\\Users\\Noor\\Desktop",
  "archive_folder_name": "Desktop Archive",
  "date_format": "%d %B %Y",
  "exclude_extensions": [
    ".lnk",
    ".url",
    ".tmp"
  ],
  "exclude_names": [
    "keep-*",
    "important.txt"
  ],
  "schedules": [
    {
      "time": "23:00",
      "repeat": "Daily",
      "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    },
    {
      "time": "12:00",
      "repeat": "Weekdays only",
      "days": ["Mon", "Tue", "Wed", "Thu", "Fri"]
    }
  ],
  "run_missed": true,
  "start_with_windows": false,
  "start_hidden": true,
  "run_time": "23:00"
}
```

The `run_time` key is retained for backward compatibility with older versions. The application uses the first entry in `schedules` for current settings and writes the compatibility value when saving.

## Date formats

The interface exposes common date formats including `7 April 2026`, `07-04-2026`, `2026-04-07`, and `07.04.2026`. Internally these map to Python `strftime` directives. Avoid changing `date_format` manually unless the resulting folder names are understood by everyone using the computer.

## Exclusions

Extensions are compared case-insensitively and may be entered with or without a leading period in the Settings interface. Name exclusions are compared against the item name; wildcard patterns such as `keep-*` are supported. The archive directory itself is always skipped to prevent recursive movement.

## Schedule objects

There can be no more than three schedule objects. `time` uses 24-hour `HH:MM` notation. `repeat` accepts `Daily`, `Weekdays only`, or `Custom days`. For custom schedules, `days` should contain one or more of `Mon`, `Tue`, `Wed`, `Thu`, `Fri`, `Sat`, and `Sun`.

Automatic schedules archive the previous calendar day's files. Folder movement is stricter than file movement: a folder is moved only when its creation date matches the selected archive date. This protects older work folders from being moved unexpectedly.

## Backup and reset

To back up settings, copy `.desktop_organizer_config.json` to a safe location while the application is closed. To reset the application, exit it, rename or remove the configuration file, and start the application again. The next launch recreates safe defaults.
