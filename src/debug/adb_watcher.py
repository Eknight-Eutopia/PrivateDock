import os
import subprocess
import sys
import threading
import time
from datetime import datetime

from typing import Callable

from src.logger.logger import log_event, log_raw, LOG_LEVEL_INFO, LOG_LEVEL_ERROR

AZUR_LANE_PACKAGE = "com.YoStarEN.AzurLane"
GREP_REGEX = r"(azurlane|blhx|manjuu|yostar)"
# adb logcat -e takes a plain regex matched against the whole line.  The crash
# report itself must be included: the "FATAL EXCEPTION" header and the exception
# class line live under the AndroidRuntime tag, so a filter of just
# (System|Unity) hides the cause and leaves only the UnityPlayer stack frames.
DEFAULT_LOGCAT_FILTER = "(System|Unity|AndroidRuntime|FATAL|libc|tombstone|beginning of crash)"
PS_DELAY_DEFAULT = 3.0

_handlers: dict[str, Callable] = {}
_logcat_process: subprocess.Popen | None = None
_azur_lane_pid: int = 0
_ps_delay: float = PS_DELAY_DEFAULT
_running = False


def _restart_game():
    log_event("ADB", "Restart", "Restarting game...", LOG_LEVEL_INFO)
    try:
        subprocess.run(["adb", "shell", "am", "force-stop", AZUR_LANE_PACKAGE], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        log_event("ADB", "Restart", f"Failed to force-stop: {e}", LOG_LEVEL_ERROR)
        return
    time.sleep(3)
    try:
        subprocess.run(
            ["adb", "shell", "monkey", "-p", AZUR_LANE_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"],
            check=True, capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        log_event("ADB", "Restart", f"Failed to launch: {e}", LOG_LEVEL_ERROR)
        return
    log_event("ADB", "Restart", "Game restarted successfully", LOG_LEVEL_INFO)


def _help():
    print("src -- adb watcher help")
    print("?: print this help")
    print("l: list connected devices")
    print("c: clear terminal")
    print("s: start/stop logcat parsing")
    print("f: flush logcat")
    print("d: dump logcat buffer to a file")
    print("r: restart game")
    print("+: increase delay between ps commands (default: 3s)")
    print("-: decrease delay between ps commands (default: 3s)")
    print("=: print current delay between ps commands")
    print("x: exit adb watcher")


def _clear():
    subprocess.run(["cmd", "/c", "cls"] if sys.platform == "win32" else ["clear"])


def _list_devices():
    try:
        out = subprocess.check_output(["adb", "devices"], text=True)
        print(out, end="")
    except subprocess.CalledProcessError:
        log_event("ADB", "ListDevices", "Failed to list devices", LOG_LEVEL_ERROR)


def _flush_logcat():
    try:
        subprocess.run(["adb", "logcat", "-c"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        log_event("ADB", "Flush", "Failed to flush logcat", LOG_LEVEL_ERROR)
        return
    log_event("ADB", "FlushLogcat", "Logcat flushed", LOG_LEVEL_INFO)


def _echo_log(line: str):
    # Also lands in the session log file (see logger.log_raw) so a crash trace
    # survives the terminal scrolling.
    log_raw(line)


def _stop_logcat():
    global _logcat_process
    if _logcat_process is None:
        return
    pid = _logcat_process.pid
    _logcat_process.kill()
    _logcat_process = None
    log_event("ADB", "Logcat", f"Logcat stopped (PID: {pid})", LOG_LEVEL_INFO)


def _toggle_logcat():
    global _logcat_process
    if _logcat_process is not None:
        _stop_logcat()
        return
    if _azur_lane_pid == 0:
        log_event("ADB", "Logcat", f"Azur Lane PID not found, waiting {_ps_delay}s to retry", LOG_LEVEL_INFO)
        return

    def _run_logcat():
        global _logcat_process
        proc = _logcat_process
        if proc is not None:
            _stop_logcat()
        args = ["adb", "logcat", "--pid", str(_azur_lane_pid), "-e", DEFAULT_LOGCAT_FILTER]
        try:
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
            _logcat_process = proc
        except FileNotFoundError:
            log_event("ADB", "Logcat", "Failed to start logcat", LOG_LEVEL_ERROR)
            return
        log_event("ADB", "Logcat", f"Logcat started (PID: {proc.pid})", LOG_LEVEL_INFO)
        for line in proc.stdout:
            _echo_log(line.rstrip("\n"))
        exit_code = proc.poll()
        if exit_code and exit_code != 0:
            log_event("ADB", "Logcat", f"Logcat process (PID: {proc.pid}) exited with code {exit_code}", LOG_LEVEL_ERROR)
        if _logcat_process is proc:
            _logcat_process = None

    t = threading.Thread(target=_run_logcat, daemon=True)
    t.start()


def _increase_sleep():
    global _ps_delay
    _ps_delay += 1.0
    log_event("Watcher", "Delay", f"Delay increased to {_ps_delay}s", LOG_LEVEL_INFO)


def _decrease_sleep():
    global _ps_delay
    if _ps_delay > 1.0:
        _ps_delay -= 1.0
        log_event("Watcher", "Delay", f"Delay decreased to {_ps_delay}s", LOG_LEVEL_INFO)
    else:
        log_event("Watcher", "Delay", "Delay cannot be decreased further, minimum is 1s", LOG_LEVEL_INFO)


def _print_delay():
    log_event("ADB", "PrintDelay", f"Current delay: {_ps_delay}s", LOG_LEVEL_INFO)


def _logcat_dir() -> str:
    # src/debug/adb_watcher.py -> project root/logs
    root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    return os.path.join(root, "logs")


def _dump_logcat():
    # Dumps the FULL buffer unfiltered, so the AndroidRuntime crash block is
    # included even though the live filter may not match it.
    try:
        out = subprocess.check_output(["adb", "logcat", "-d"])
    except (subprocess.CalledProcessError, OSError):
        log_event("ADB", "DumpLogcat", "Failed to dump logcat", LOG_LEVEL_ERROR)
        return
    directory = _logcat_dir()
    filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_privatedock_logcat.log"
    path = os.path.join(directory, filename)
    try:
        os.makedirs(directory, exist_ok=True)
        with open(path, "wb") as f:
            f.write(out)
    except OSError:
        log_event("ADB", "DumpLogcat", "Failed to create file", LOG_LEVEL_ERROR)
        return
    log_event("ADB", "DumpLogcat", f"Logcat dumped to {path}", LOG_LEVEL_INFO)


_handlers = {
    "?": _help,
    "c": _clear,
    "l": _list_devices,
    "s": _toggle_logcat,
    "f": _flush_logcat,
    "d": _dump_logcat,
    "+": _increase_sleep,
    "-": _decrease_sleep,
    "=": _print_delay,
    "r": _restart_game,
}


def _pid_watcher():
    global _azur_lane_pid
    while _running:
        try:
            out = subprocess.check_output(
                ["adb", "shell", "ps", "-A", "-o", "PID,NAME"],
                text=True, stderr=subprocess.DEVNULL,
            )
            for line in out.split("\n"):
                line = line.strip().lower()
                for keyword in GREP_REGEX.strip("()").split("|"):
                    if keyword in line:
                        parts = line.split(None, 1)
                        if parts and parts[0].isdigit():
                            new_pid = int(parts[0])
                            if new_pid != 0 and new_pid != _azur_lane_pid:
                                _azur_lane_pid = new_pid
                                log_event("ADB", "Shell", f"Azur Lane PID: {_azur_lane_pid}", LOG_LEVEL_INFO)
                                _stop_logcat()
                                _toggle_logcat()
        except subprocess.CalledProcessError:
            pass
        time.sleep(_ps_delay)


def ADBRoutine(flush: bool = False, restart: bool = False) -> None:
    global _running
    try:
        subprocess.run(["adb", "version"], check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        log_event("ADB", "Init", "ADB not found in PATH", LOG_LEVEL_ERROR)
        return
    log_event("ADB", "Init", "ADB watcher started", LOG_LEVEL_INFO)
    if flush:
        _flush_logcat()
    if restart:
        _restart_game()
    _help()

    _running = True
    watcher_thread = threading.Thread(target=_pid_watcher, daemon=True)
    watcher_thread.start()

    try:
        import msvcrt
        while _running:
            ch = msvcrt.getwch()
            if ch == "x":
                log_event("ADB", "Exit", "ADB watcher exited", LOG_LEVEL_INFO)
                break
            handler = _handlers.get(ch)
            if handler:
                handler()
    except (ImportError, KeyboardInterrupt):
        _running = False
