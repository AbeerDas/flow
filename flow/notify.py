"""Telling you what it is doing, without a window.

Sound for the moments that need no words, notifications for the ones that do.
Both are system tools rather than dependencies, so nothing here can fail to
install.
"""

from __future__ import annotations

import shutil
import subprocess

SOUNDS = {
    "listening": "/System/Library/Sounds/Pop.aiff",
    "heard": "/System/Library/Sounds/Tink.aiff",
    "done": "/System/Library/Sounds/Glass.aiff",
    "nothing": "/System/Library/Sounds/Funk.aiff",
}


def sound(name: str) -> None:
    path = SOUNDS.get(name)
    if path and shutil.which("afplay"):
        subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def banner(title: str, message: str) -> None:
    if not shutil.which("osascript"):
        return
    # Quotes in what was said would otherwise end the script's own string.
    safe = message.replace('"', "'")[:180]
    head = title.replace('"', "'")[:60]
    subprocess.Popen(
        ["osascript", "-e", f'display notification "{safe}" with title "{head}"'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def ask(title: str, message: str, timeout: int = 25) -> bool:
    """A dialog, because a background process has no keyboard to read.

    Asking on stdin killed the listener outright the first time something
    needed confirming: detached there is no stdin, and the read raised.
    """
    if not shutil.which("osascript"):
        return False
    safe = message.replace('"', "'")[:200]
    head = title.replace('"', "'")[:60]
    script = (
        'tell application "System Events" to display dialog '
        f'"{safe}" with title "{head}" '
        'buttons {"Cancel", "Run"} default button "Run" '
        f"with icon caution giving up after {timeout}"
    )
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, timeout=timeout + 10
    )
    # Giving up counts as no. Silence should never be taken for consent.
    return "button returned:Run" in result.stdout and "gave up:true" not in result.stdout
