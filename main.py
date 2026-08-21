from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
import queue
import shutil
import sys
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:  # The program can still open for configuration without tray support.
    pystray = None
    Image = ImageDraw = None

APP_NAME = "Desktop Organizer"
CONFIG_PATH = Path.home() / ".desktop_organizer_config.json"
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DEFAULT_CONFIG = {
    "source_folder": str(Path.home() / "Desktop"),
    "archive_folder_name": "Desktop Archive",
    "date_format": "%d %B %Y",
    "exclude_extensions": [".lnk", ".url"],
    "exclude_names": [],
    "schedules": [
        {"time": "23:00", "repeat": "Daily", "days": WEEKDAYS},
    ],
    "run_missed": True,
    "start_with_windows": False,
    "start_hidden": True,
}

DATE_FORMATS = {
    "7 April 2026": "%d %B %Y",
    "07 April 2026": "%d %B %Y",
    "07-04-2026": "%d-%m-%Y",
    "2026-04-07": "%Y-%m-%d",
    "07.04.2026": "%d.%m.%Y",
}

COLORS = {
    "bg": "#0f172a",
    "panel": "#17233d",
    "panel2": "#1e2e4d",
    "input": "#243656",
    "text": "#e5edf8",
    "muted": "#9fb0c8",
    "accent": "#38bdf8",
    "accent2": "#2563eb",
    "file": "#60a5fa",
    "folder": "#c084fc",
    "skip": "#94a3b8",
    "error": "#f87171",
    "done": "#4ade80",
}


def deep_copy_default() -> dict:
    return json.loads(json.dumps(DEFAULT_CONFIG))


def load_config() -> dict:
    config = deep_copy_default()
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            saved = json.load(handle)
        if isinstance(saved, dict):
            config.update(saved)
    except (OSError, json.JSONDecodeError):
        pass

    # Migrate the former single run_time setting to the new schedule list.
    if not isinstance(config.get("schedules"), list) or not config["schedules"]:
        old_time = config.get("run_time", "23:00")
        config["schedules"] = [{"time": old_time, "repeat": "Daily", "days": WEEKDAYS}]
    normalized = []
    for slot in config["schedules"][:3]:
        if not isinstance(slot, dict):
            continue
        normalized.append({
            "time": str(slot.get("time", "23:00")),
            "repeat": str(slot.get("repeat", "Daily")),
            "days": [day for day in slot.get("days", WEEKDAYS) if day in WEEKDAYS] or WEEKDAYS[:],
        })
    config["schedules"] = normalized or deep_copy_default()["schedules"]
    config["exclude_extensions"] = [str(x).lower() for x in config.get("exclude_extensions", [])]
    config["exclude_names"] = [str(x) for x in config.get("exclude_names", [])]
    return config


def save_config(config: dict) -> None:
    payload = dict(config)
    payload["run_time"] = payload["schedules"][0]["time"] if payload.get("schedules") else "23:00"
    CONFIG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}" --hidden'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{executable.resolve()}" "{Path(__file__).resolve()}" --hidden'


def set_startup(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx("DesktopOrganizer", 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, "DesktopOrganizer")
            except FileNotFoundError:
                pass


def make_tray_image():
    if Image is None:
        return None
    image = Image.new("RGBA", (64, 64), (15, 23, 42, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((7, 7, 57, 57), radius=12, fill=(56, 189, 248, 255))
    draw.rectangle((17, 22, 47, 45), fill=(15, 23, 42, 255))
    draw.rectangle((21, 17, 43, 24), fill=(15, 23, 42, 255))
    draw.line((25, 29, 39, 29), fill=(56, 189, 248, 255), width=3)
    draw.line((25, 36, 36, 36), fill=(56, 189, 248, 255), width=3)
    return image


class Organizer:
    def __init__(self, app: "DesktopOrganizerApp"):
        self.app = app

    def destination_for(self, target: dt.date) -> Path:
        source = Path(self.app.config["source_folder"]).expanduser()
        archive = source / self.app.config.get("archive_folder_name", "Desktop Archive")
        return archive / target.strftime(self.app.config.get("date_format", "%d %B %Y"))

    def is_excluded(self, item: Path) -> bool:
        extension = item.suffix.lower()
        if extension in self.app.config.get("exclude_extensions", []):
            return True
        return any(fnmatch.fnmatch(item.name, pattern) or pattern.lower() in item.name.lower()
                   for pattern in self.app.config.get("exclude_names", []))

    def run(self, target: dt.date, dry_run: bool = False) -> dict:
        source = Path(self.app.config["source_folder"]).expanduser()
        destination = self.destination_for(target)
        result = {"files": 0, "folders": 0, "skipped": 0, "errors": 0, "items": [], "destination": str(destination)}
        if not source.exists() or not source.is_dir():
            raise FileNotFoundError(f"Source folder does not exist: {source}")
        if not dry_run:
            destination.mkdir(parents=True, exist_ok=True)

        archive_root = source / self.app.config.get("archive_folder_name", "Desktop Archive")
        for item in sorted(source.iterdir(), key=lambda path: path.name.lower()):
            if item == archive_root or self.is_excluded(item):
                result["skipped"] += 1
                self.app.log("SKIP", f"Skipped: {item.name}", COLORS["skip"])
                continue
            try:
                if item.is_dir():
                    # Folder handling intentionally uses creation time and only moves folders
                    # created on the selected date, leaving old date folders untouched.
                    created = dt.datetime.fromtimestamp(item.stat().st_ctime).date()
                    if created != target:
                        result["skipped"] += 1
                        self.app.log("SKIP", f"Old folder left in place: {item.name}", COLORS["skip"])
                        continue
                    result["folders"] += 1
                    label = f"Folder: {item.name}"
                else:
                    result["files"] += 1
                    label = f"File: {item.name}"
                result["items"].append(label)
                if item.is_dir():
                    color, kind = COLORS["folder"], "FOLDER"
                else:
                    color, kind = COLORS["file"], "FILE"
                if dry_run:
                    self.app.log("PREVIEW", f"Would move {label}", color)
                else:
                    destination.mkdir(parents=True, exist_ok=True)
                    target_path = destination / item.name
                    counter = 2
                    while target_path.exists():
                        target_path = destination / f"{item.stem} ({counter}){item.suffix}" if item.is_file() else destination / f"{item.name} ({counter})"
                        counter += 1
                    shutil.move(str(item), str(target_path))
                    self.app.log(kind, f"Moved {label}", color)
            except Exception as exc:  # A single locked item must not stop the whole run.
                result["errors"] += 1
                self.app.log("ERROR", f"Could not process {item.name}: {exc}", COLORS["error"])
        return result


class DesktopOrganizerApp:
    def __init__(self, root: tk.Tk, hidden: bool = False):
        self.root = root
        self.config = load_config()
        self.organizer = Organizer(self)
        self.log_queue: queue.Queue[tuple[str, str, str]] = queue.Queue()
        self.stop_event = threading.Event()
        self.scheduler_thread = threading.Thread(target=self.scheduler_loop, daemon=True)
        self.last_run_markers: set[str] = set()
        self.tray_icon = None
        self.tray_thread = None
        self.hidden_on_start = hidden
        self.schedule_rows = []
        self.status_var = tk.StringVar(value="Ready")
        self.preview_var = tk.BooleanVar(value=False)
        self.manual_date_var = tk.StringVar(value="Yesterday")
        self.custom_date_var = tk.StringVar(value=dt.date.today().isoformat())
        self.setup_theme()
        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.root.after(100, self.flush_logs)
        self.start_tray()
        self.scheduler_thread.start()
        if hidden:
            self.root.withdraw()
        else:
            self.root.deiconify()
        self.root.after(1200, self.check_missed_runs)

    def setup_theme(self):
        self.root.title(APP_NAME)
        self.root.geometry("870x620")
        self.root.minsize(760, 500)
        self.root.configure(bg=COLORS["bg"])
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=COLORS["panel"], foreground=COLORS["muted"], padding=(16, 8))
        style.map("TNotebook.Tab", background=[("selected", COLORS["accent2"])], foreground=[("selected", "white")])
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=COLORS["panel"], foreground=COLORS["text"])
        style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"])
        style.configure("PanelMuted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"])
        style.configure("Accent.TButton", background=COLORS["accent2"], foreground="white", padding=(14, 8), borderwidth=0)
        style.map("Accent.TButton", background=[("active", COLORS["accent"])])
        style.configure("TButton", background=COLORS["panel2"], foreground=COLORS["text"], padding=(10, 6), borderwidth=0)
        style.map("TButton", background=[("active", COLORS["accent2"])])
        style.configure("TEntry", fieldbackground=COLORS["input"], foreground=COLORS["text"], insertcolor="white")
        style.configure("TCombobox", fieldbackground=COLORS["input"], background=COLORS["input"], foreground=COLORS["text"])
        style.configure("TCheckbutton", background=COLORS["bg"], foreground=COLORS["text"])
        style.configure("Panel.TCheckbutton", background=COLORS["panel"], foreground=COLORS["text"])

    def build_ui(self):
        header = tk.Frame(self.root, bg=COLORS["bg"])
        header.pack(fill="x", padx=24, pady=(20, 10))
        tk.Label(header, text=APP_NAME, bg=COLORS["bg"], fg=COLORS["text"], font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(header, text="Automatically archive your desktop into dated folders", bg=COLORS["bg"], fg=COLORS["muted"], font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 0))

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        run_tab = ttk.Frame(notebook)
        settings_tab = ttk.Frame(notebook)
        log_tab = ttk.Frame(notebook)
        notebook.add(run_tab, text="Run")
        notebook.add(settings_tab, text="Settings")
        notebook.add(log_tab, text="Log")
        self.build_run_tab(run_tab)
        self.build_settings_tab(settings_tab)
        self.build_log_tab(log_tab)

        footer = tk.Frame(self.root, bg=COLORS["bg"])
        footer.pack(fill="x", padx=24, pady=(0, 14))
        tk.Label(footer, textvariable=self.status_var, bg=COLORS["bg"], fg=COLORS["muted"], font=("Segoe UI", 9)).pack(side="left")
        tk.Label(footer, text=f"Config: {CONFIG_PATH}", bg=COLORS["bg"], fg=COLORS["muted"], font=("Segoe UI", 8)).pack(side="right")

    def build_run_tab(self, tab):
        tab.columnconfigure(0, weight=1)
        card = ttk.Frame(tab, style="Panel.TFrame", padding=24)
        card.grid(row=0, column=0, sticky="new", padx=10, pady=16)
        ttk.Label(card, text="Manual organization", style="Panel.TLabel", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(card, text="Choose which date label should be used for the archive destination.", style="PanelMuted.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 20))
        ttk.Label(card, text="Date to archive:", style="Panel.TLabel").grid(row=2, column=0, sticky="w")
        date_combo = ttk.Combobox(card, textvariable=self.manual_date_var, values=["Yesterday", "Today", "Custom"], state="readonly", width=18)
        date_combo.grid(row=2, column=1, sticky="w", padx=(12, 8))
        ttk.Entry(card, textvariable=self.custom_date_var, width=16).grid(row=2, column=2, sticky="w")
        ttk.Checkbutton(card, text="Preview only (move nothing)", variable=self.preview_var, style="Panel.TCheckbutton").grid(row=3, column=0, columnspan=3, sticky="w", pady=(18, 14))
        ttk.Button(card, text="Run organizer", style="Accent.TButton", command=self.manual_run).grid(row=4, column=0, sticky="w")
        ttk.Label(card, text="Automatic runs archive yesterday's files and folders.", style="PanelMuted.TLabel").grid(row=4, column=1, columnspan=2, sticky="w", padx=(16, 0))

        info = ttk.Frame(tab, style="Panel.TFrame", padding=24)
        info.grid(row=1, column=0, sticky="new", padx=10, pady=(0, 16))
        ttk.Label(info, text="Current source", style="PanelMuted.TLabel").grid(row=0, column=0, sticky="w")
        self.source_summary = ttk.Label(info, text=self.config["source_folder"], style="Panel.TLabel")
        self.source_summary.grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(info, text="Next scheduled run", style="PanelMuted.TLabel").grid(row=0, column=1, sticky="w", padx=(80, 0))
        self.next_run_summary = ttk.Label(info, text=self.next_run_text(), style="Panel.TLabel")
        self.next_run_summary.grid(row=1, column=1, sticky="w", padx=(80, 0), pady=(4, 0))

    def build_settings_tab(self, tab):
        tab.columnconfigure(0, weight=1)
        source_card = ttk.Frame(tab, style="Panel.TFrame", padding=18)
        source_card.grid(row=0, column=0, sticky="ew", padx=10, pady=(14, 8))
        source_card.columnconfigure(1, weight=1)
        ttk.Label(source_card, text="Folders and archive format", style="Panel.TLabel", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
        ttk.Label(source_card, text="Source folder", style="Panel.TLabel").grid(row=1, column=0, sticky="w")
        self.source_var = tk.StringVar(value=self.config["source_folder"])
        ttk.Entry(source_card, textvariable=self.source_var).grid(row=1, column=1, sticky="ew", padx=12)
        ttk.Button(source_card, text="Browse", command=self.browse_source).grid(row=1, column=2)
        ttk.Label(source_card, text="Archive folder name", style="Panel.TLabel").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.archive_var = tk.StringVar(value=self.config.get("archive_folder_name", "Desktop Archive"))
        ttk.Entry(source_card, textvariable=self.archive_var).grid(row=2, column=1, sticky="ew", padx=12, pady=(10, 0))
        ttk.Label(source_card, text="Date format", style="Panel.TLabel").grid(row=3, column=0, sticky="w", pady=(10, 0))
        current_format = next((name for name, value in DATE_FORMATS.items() if value == self.config.get("date_format")), "7 April 2026")
        self.format_var = tk.StringVar(value=current_format)
        ttk.Combobox(source_card, textvariable=self.format_var, values=list(DATE_FORMATS), state="readonly", width=22).grid(row=3, column=1, sticky="w", padx=12, pady=(10, 0))

        schedule_card = ttk.Frame(tab, style="Panel.TFrame", padding=18)
        schedule_card.grid(row=1, column=0, sticky="ew", padx=10, pady=8)
        schedule_card.columnconfigure(0, weight=1)
        ttk.Label(schedule_card, text="Advanced schedule", style="Panel.TLabel", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(schedule_card, text="Up to three schedule slots can run independently.", style="PanelMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 10))
        self.schedule_rows_frame = tk.Frame(schedule_card, bg=COLORS["panel"])
        self.schedule_rows_frame.grid(row=2, column=0, sticky="ew")
        self.render_schedule_rows()
        ttk.Button(schedule_card, text="Add schedule slot", command=self.add_schedule_row).grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.missed_var = tk.BooleanVar(value=bool(self.config.get("run_missed", True)))
        ttk.Checkbutton(schedule_card, text="Run on startup if today's scheduled time was missed", variable=self.missed_var, style="Panel.TCheckbutton").grid(row=4, column=0, sticky="w", pady=(12, 0))

        exclusions_card = ttk.Frame(tab, style="Panel.TFrame", padding=18)
        exclusions_card.grid(row=2, column=0, sticky="ew", padx=10, pady=8)
        exclusions_card.columnconfigure(1, weight=1)
        ttk.Label(exclusions_card, text="Exclusions", style="Panel.TLabel", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(exclusions_card, text="Extensions (comma-separated)", style="Panel.TLabel").grid(row=1, column=0, sticky="w")
        self.extensions_var = tk.StringVar(value=", ".join(self.config.get("exclude_extensions", [])))
        ttk.Entry(exclusions_card, textvariable=self.extensions_var).grid(row=1, column=1, sticky="ew", padx=12)
        ttk.Label(exclusions_card, text="Names or patterns (comma-separated)", style="Panel.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.names_var = tk.StringVar(value=", ".join(self.config.get("exclude_names", [])))
        ttk.Entry(exclusions_card, textvariable=self.names_var).grid(row=2, column=1, sticky="ew", padx=12, pady=(8, 0))

        self.startup_var = tk.BooleanVar(value=bool(self.config.get("start_with_windows", False)))
        ttk.Checkbutton(tab, text="Start automatically with Windows (hidden in the system tray)", variable=self.startup_var).grid(row=3, column=0, sticky="w", padx=14, pady=(8, 2))
        ttk.Button(tab, text="Save settings", style="Accent.TButton", command=self.save_settings).grid(row=4, column=0, sticky="w", padx=14, pady=(6, 12))

    def build_log_tab(self, tab):
        tab.rowconfigure(0, weight=1)
        tab.columnconfigure(0, weight=1)
        self.log_text = tk.Text(tab, bg="#0b1220", fg=COLORS["text"], insertbackground="white", relief="flat", state="disabled", wrap="word", font=("Consolas", 9), padx=12, pady=12)
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=10, pady=14)
        scroll = ttk.Scrollbar(tab, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns", pady=14)
        self.log_text.configure(yscrollcommand=scroll.set)
        for tag, color in [("FILE", COLORS["file"]), ("FOLDER", COLORS["folder"]), ("SKIP", COLORS["skip"]), ("ERROR", COLORS["error"]), ("DONE", COLORS["done"]), ("PREVIEW", COLORS["accent"])]:
            self.log_text.tag_configure(tag, foreground=color)

    def render_schedule_rows(self):
        for child in self.schedule_rows_frame.winfo_children():
            child.destroy()
        self.schedule_rows = []
        for index, slot in enumerate(self.config.get("schedules", [])[:3]):
            row = tk.Frame(self.schedule_rows_frame, bg=COLORS["panel"])
            row.pack(fill="x", pady=3)
            enabled = tk.BooleanVar(value=True)
            time_var = tk.StringVar(value=slot.get("time", "23:00"))
            repeat_var = tk.StringVar(value=slot.get("repeat", "Daily"))
            days_vars = {day: tk.BooleanVar(value=day in slot.get("days", WEEKDAYS)) for day in WEEKDAYS}
            ttk.Label(row, text=f"Slot {index + 1}", style="Panel.TLabel", width=8).pack(side="left")
            ttk.Entry(row, textvariable=time_var, width=8).pack(side="left", padx=(0, 8))
            ttk.Combobox(row, textvariable=repeat_var, values=["Daily", "Weekdays only", "Custom days"], state="readonly", width=16).pack(side="left")
            days_frame = tk.Frame(row, bg=COLORS["panel"])
            days_frame.pack(side="left", padx=10)
            for day in WEEKDAYS:
                ttk.Checkbutton(days_frame, text=day, variable=days_vars[day], style="Panel.TCheckbutton").pack(side="left")
            if index > 0:
                ttk.Button(row, text="Remove", command=lambda i=index: self.remove_schedule_row(i)).pack(side="right")
            self.schedule_rows.append({"time": time_var, "repeat": repeat_var, "days": days_vars})

    def add_schedule_row(self):
        if len(self.schedule_rows) >= 3:
            messagebox.showinfo(APP_NAME, "You can add up to three schedule slots.")
            return
        self.config["schedules"].append({"time": "12:00", "repeat": "Daily", "days": WEEKDAYS[:]})
        self.render_schedule_rows()

    def remove_schedule_row(self, index):
        if 0 <= index < len(self.config["schedules"]):
            del self.config["schedules"][index]
        if not self.config["schedules"]:
            self.config["schedules"] = [{"time": "23:00", "repeat": "Daily", "days": WEEKDAYS[:] }]
        self.render_schedule_rows()

    def browse_source(self):
        selected = filedialog.askdirectory(initialdir=self.source_var.get() or str(Path.home()))
        if selected:
            self.source_var.set(selected)

    def collect_schedule_settings(self):
        schedules = []
        for row in self.schedule_rows:
            value = row["time"].get().strip()
            try:
                parsed = dt.datetime.strptime(value, "%H:%M")
                value = parsed.strftime("%H:%M")
            except ValueError:
                raise ValueError(f"Invalid schedule time: {value}. Use HH:MM, such as 23:00.")
            schedules.append({
                "time": value,
                "repeat": row["repeat"].get(),
                "days": [day for day, variable in row["days"].items() if variable.get()] or WEEKDAYS[:],
            })
        return schedules or [{"time": "23:00", "repeat": "Daily", "days": WEEKDAYS[:]}]

    def save_settings(self):
        try:
            schedules = self.collect_schedule_settings()
            extensions = [x.strip().lower() for x in self.extensions_var.get().split(",") if x.strip()]
            extensions = [x if x.startswith(".") else f".{x}" for x in extensions]
            names = [x.strip() for x in self.names_var.get().split(",") if x.strip()]
            self.config.update({
                "source_folder": self.source_var.get().strip(),
                "archive_folder_name": self.archive_var.get().strip() or "Desktop Archive",
                "date_format": DATE_FORMATS[self.format_var.get()],
                "exclude_extensions": extensions,
                "exclude_names": names,
                "schedules": schedules,
                "run_missed": self.missed_var.get(),
                "start_with_windows": self.startup_var.get(),
            })
            save_config(self.config)
            set_startup(self.startup_var.get())
            self.source_summary.configure(text=self.config["source_folder"])
            self.next_run_summary.configure(text=self.next_run_text())
            self.status_var.set("Settings saved")
            self.log("DONE", "Settings saved successfully", COLORS["done"])
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def selected_date(self) -> dt.date:
        choice = self.manual_date_var.get()
        if choice == "Today":
            return dt.date.today()
        if choice == "Yesterday":
            return dt.date.today() - dt.timedelta(days=1)
        return dt.date.fromisoformat(self.custom_date_var.get())

    def manual_run(self):
        try:
            target = self.selected_date()
        except ValueError:
            messagebox.showerror(APP_NAME, "Custom date must use YYYY-MM-DD format.")
            return
        self.run_async(target, self.preview_var.get(), automatic=False)

    def run_async(self, target: dt.date, dry_run: bool, automatic: bool):
        self.status_var.set("Running..." if not dry_run else "Preparing preview...")
        thread = threading.Thread(target=self.worker_run, args=(target, dry_run, automatic), daemon=True)
        thread.start()

    def worker_run(self, target: dt.date, dry_run: bool, automatic: bool):
        try:
            result = self.organizer.run(target, dry_run)
            summary = f"{'Preview' if dry_run else 'Run'} complete: {result['files']} files, {result['folders']} folders, {result['errors']} errors"
            self.log("DONE", summary, COLORS["done"])
            self.root.after(0, lambda: self.status_var.set(summary))
            if automatic and self.tray_icon and not dry_run:
                try:
                    self.tray_icon.notify(f"{result['files']} files and {result['folders']} folders moved", APP_NAME)
                except Exception:
                    pass
        except Exception as exc:
            self.log("ERROR", str(exc), COLORS["error"])
            self.root.after(0, lambda: self.status_var.set("Run failed"))

    def log(self, tag: str, text: str, color: str):
        timestamp = dt.datetime.now().strftime("%H:%M:%S")
        self.log_queue.put((tag, f"[{timestamp}] {text}\n", color))

    def flush_logs(self):
        try:
            while True:
                tag, text, _color = self.log_queue.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert("end", text, tag)
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(150, self.flush_logs)

    def eligible_today(self, slot: dict, today: dt.date) -> bool:
        repeat = slot.get("repeat", "Daily")
        day = WEEKDAYS[today.weekday()]
        if repeat == "Weekdays only":
            return today.weekday() < 5
        if repeat == "Custom days":
            return day in slot.get("days", WEEKDAYS)
        return True

    def next_run_text(self) -> str:
        now = dt.datetime.now()
        candidates = []
        for slot in self.config.get("schedules", []):
            try:
                hour, minute = map(int, slot.get("time", "23:00").split(":"))
            except ValueError:
                continue
            for offset in range(8):
                day = now.date() + dt.timedelta(days=offset)
                candidate = dt.datetime.combine(day, dt.time(hour, minute))
                if candidate > now and self.eligible_today(slot, day):
                    candidates.append(candidate)
                    break
        if not candidates:
            return "Not scheduled"
        return min(candidates).strftime("%a %d %b, %H:%M")

    def scheduler_loop(self):
        while not self.stop_event.is_set():
            now = dt.datetime.now().replace(second=0, microsecond=0)
            for index, slot in enumerate(self.config.get("schedules", [])):
                if not self.eligible_today(slot, now.date()):
                    continue
                if slot.get("time") == now.strftime("%H:%M"):
                    marker = f"{now.date().isoformat()}-{index}-{slot.get('time')}"
                    if marker not in self.last_run_markers:
                        self.last_run_markers.add(marker)
                        self.run_async(now.date() - dt.timedelta(days=1), False, True)
            self.root.after(0, lambda: self.next_run_summary.configure(text=self.next_run_text()))
            self.stop_event.wait(15)

    def check_missed_runs(self):
        if self.config.get("run_missed", True):
            now = dt.datetime.now()
            for index, slot in enumerate(self.config.get("schedules", [])):
                try:
                    scheduled = dt.datetime.strptime(slot.get("time", "23:00"), "%H:%M").time()
                except ValueError:
                    continue
                if self.eligible_today(slot, now.date()) and now.time() >= scheduled:
                    marker = f"{now.date().isoformat()}-{index}-{slot.get('time')}"
                    if marker not in self.last_run_markers:
                        self.last_run_markers.add(marker)
                        self.log("DONE", f"Missed schedule detected for {slot.get('time')}; running now", COLORS["done"])
                        self.run_async(now.date() - dt.timedelta(days=1), False, True)

    def start_tray(self):
        if pystray is None:
            self.log("ERROR", "Tray support is unavailable; install pystray and Pillow.", COLORS["error"])
            return
        try:
            image = make_tray_image()
            menu = pystray.Menu(
                pystray.MenuItem("Open", lambda icon, item: self.show_window()),
                pystray.MenuItem("Run Now", lambda icon, item: self.run_async(dt.date.today() - dt.timedelta(days=1), False, True)),
                pystray.MenuItem(lambda item: f"Next run: {self.next_run_text()}", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit", lambda icon, item: self.exit_app()),
            )
            self.tray_icon = pystray.Icon("desktop_organizer", image, APP_NAME, menu)
            self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            self.tray_thread.start()
        except Exception as exc:
            self.log("ERROR", f"Could not start system tray: {exc}", COLORS["error"])
            self.tray_icon = None

    def show_window(self):
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)
        self.root.after(0, self.root.focus_force)

    def hide_to_tray(self):
        if self.tray_icon:
            self.root.withdraw()
            self.status_var.set("Running in system tray")
        else:
            self.exit_app()

    def exit_app(self):
        self.stop_event.set()
        try:
            if self.tray_icon:
                self.tray_icon.stop()
        except Exception:
            pass
        self.root.after(0, self.root.destroy)


def main():
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--hidden", action="store_true", help="Start minimized to the system tray")
    args = parser.parse_args()
    root = tk.Tk()
    app = DesktopOrganizerApp(root, hidden=args.hidden)
    root.mainloop()


if __name__ == "__main__":
    main()
