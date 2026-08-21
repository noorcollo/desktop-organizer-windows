# Troubleshooting

## The application does not appear after double-clicking

Windows may be blocking an executable downloaded from the internet. Open the file's Properties dialog and, if present, select **Unblock** before applying the change. If Windows Defender or another security product reports a warning, verify that the executable came from the official GitHub release page and compare its SHA-256 checksum with the release notes.

The application is a windowed executable, so it does not open a console window. If it was configured to start hidden, check the notification area near the clock and use the Desktop Organizer tray icon's **Open** command.

## The tray icon is not visible

Windows may hide newly installed notification icons. Open the taskbar's notification-area settings and allow the Desktop Organizer icon. If tray support is unavailable, the application records an error in the Log tab and closing the main window exits instead of hiding it.

## Startup does not work

The startup option is registered for the current Windows user only. Open Settings, enable **Start automatically with Windows**, and select **Save settings**. If the application was moved after enabling startup, save the setting again so the registry points to the new executable path. The registration uses the current user's `HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run` key and does not require administrator privileges.

## Files were not moved

Use the Preview mode first and inspect the Log tab. Files may be skipped because their extension or name matches an exclusion. Folders are intentionally skipped when their creation date does not match the selected archive date. The archive directory itself is always skipped. A file may also be locked by another program or unavailable because of Windows permissions.

## A run reports errors

Close programs that may be using the affected files, such as document editors, media players, archive tools, or synchronization clients. Confirm that the source folder exists and that the account running Desktop Organizer has permission to read and move its contents. The application continues processing other items after an individual error.

## The automatic run happened immediately after startup

When the missed-run setting is enabled, the application checks whether an eligible scheduled time has already passed today. It then performs one automatic run and records an in-memory marker to avoid repeating that slot during the current process session. This is expected behavior.

## I need to reset all settings

Exit Desktop Organizer from the tray menu, then rename `~/.desktop_organizer_config.json` to a backup filename. Start the application again to recreate default settings. This does not undo files that have already been moved; restore those files manually from their archive folders if necessary.

## Support information to include in an issue

Please include the application version or release name, Windows version, the exact steps that reproduce the issue, whether Preview mode is affected, and a sanitized copy of the relevant Log tab lines. Remove usernames, personal paths, document names, and other private information before posting.
