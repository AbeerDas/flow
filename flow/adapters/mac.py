"""Native Mac windows, read across every running app.

The accessibility API answers for any app, not only the one in front, so the
registry spans apps. The menu bar is the exception: an inactive app reports its
menu items as disabled and lets their titles go stale, so menus are read only
for the app that is active.
"""

from __future__ import annotations

import subprocess
import sys
import urllib.parse
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flow.registry import Entry, Reversibility, Tier, Verb, reversibility_of
from vendor.bridge import Bridge, BridgeError, StaleWindow  # noqa: F401

# What the bridge reports against what the registry calls it. Anything outside
# this map is not offered, so an operation the executor cannot run cannot be
# chosen.
OPERATIONS = {
    "PRESS": Verb.PRESS,
    "CLICK": Verb.CLICK,
    "TYPE_TEXT": Verb.TYPE_TEXT,
    "SELECT": Verb.SELECT,
    "SCROLL_UP": Verb.SCROLL_UP,
    "SCROLL_DOWN": Verb.SCROLL_DOWN,
    "PRESS_RETURN": Verb.PRESS_RETURN,
    "PRESS_ESCAPE": Verb.PRESS_ESCAPE,
}

# An element reporting an operation is not the same as that operation being a
# thing a person would do. Static text accepts a click and is still text, and a
# container accepts a press and is still a container. Measured on one window,
# these two pairs were 45% of everything offered.
NOISE = {
    ("AXStaticText", "CLICK"),
    ("AXStaticText", "PRESS"),
    ("AXGroup", "PRESS"),
    ("AXGroup", "CLICK"),
    ("AXSplitter", "PRESS"),
    ("AXImage", "CLICK"),
    ("AXScrollArea", "PRESS"),
    ("AXUnknown", "PRESS"),
    ("AXUnknown", "CLICK"),
}

DEEP_LIMIT = 250

# Where a Mac keeps its applications. An app that is not running is not in the
# accessibility tree at all, so without this "open Notes" has no answer on a
# machine where Notes happens to be closed.
LAUNCHER = "mac.launch"
WEB = "mac.web"

APP_FOLDERS = (
    Path("/Applications"),
    Path("/Applications/Utilities"),
    Path("/System/Applications"),
    Path("/System/Applications/Utilities"),
    Path.home() / "Applications",
)


class MacAdapter:
    """One bridge process, every app."""

    name = "mac"

    def __init__(self, deep_limit: int = DEEP_LIMIT):
        self.bridge = Bridge()
        self.deep_limit = deep_limit
        self._pages: dict[str, dict] = {}
        self._installed: list[str] | None = None
        self._last_front: str | None = None
        status = self.bridge.call("status")
        if not status["accessibility"]:
            self.close()
            raise PermissionError(
                "Accessibility permission is missing. System Settings > Privacy & Security > "
                "Accessibility: enable the app running this shell, then restart it."
            )

    def apps(self) -> list[dict]:
        return self.bridge.call("apps")["apps"]

    def installed(self) -> list[str]:
        """Every app on the machine, running or not."""
        if self._installed is None:
            names = set()
            for folder in APP_FOLDERS:
                if folder.is_dir():
                    names.update(p.stem for p in folder.glob("*.app"))
            self._installed = sorted(names)
        return self._installed

    def targets(self) -> list[str]:
        return [a["name"] for a in self.apps()]

    def frontmost(self) -> str | None:
        """Whatever is in front, or whatever was last.

        Nothing reports as frontmost while focus sits on something the bridge
        does not list, and the answer is momentarily nobody. Taken at face
        value the registry collapses to the list of apps and every window on
        the screen stops existing, which reads as the request matching
        nothing. Remembering the last real answer costs one stale read and
        saves the whole window.
        """
        for app in self.apps():
            if app["frontmost"]:
                self._last_front = app["name"]
                return app["name"]
        return self._last_front

    def scan(self, target: str, tier: Tier = Tier.DEEP) -> list[Entry]:
        if tier is Tier.SHALLOW:
            return self._shallow(target)
        return self._deep(target)

    def launchable(self) -> list[Entry]:
        """Apps that are installed and not running. Starting one is free."""
        running = {a["name"] for a in self.apps()}
        now = time.time()
        return [
            Entry(
                index=-1,
                verb=Verb.LAUNCH_APP,
                label=f"Open {name}",
                app=name,
                owner=LAUNCHER,
                reversibility=reversibility_of(Verb.LAUNCH_APP, name),
                observed_at=now,
                tier=Tier.SHALLOW,
                handle={"kind": "launch", "app": name},
            )
            for name in self.installed()
            if name not in running
        ]

    def web(self) -> list[Entry]:
        """Searching and opening an address, without touching a browser window.

        Chrome publishes no editable field for its address bar, so typing into
        it is not possible through the accessibility tree. Both of these are
        real actions rather than a sequence of pokes at one, and they work
        whatever browser is default.
        """
        now = time.time()
        return [
            Entry(
                index=-1,
                verb=verb,
                label=label,
                app="Web",
                owner=WEB,
                reversibility=reversibility_of(verb, "Web"),
                observed_at=now,
                tier=Tier.SHALLOW,
                needs_text=True,
                handle={"kind": kind},
            )
            for verb, label, kind in (
                (Verb.SEARCH_WEB, "Search the web", "search"),
                (Verb.OPEN_URL, "Open a web address", "url"),
            )
        ]

    def scan_all(self, frontmost: str | None = None) -> list[Entry]:
        """Deep for the app in front, shallow for everything else."""
        front = frontmost or self.frontmost()
        out: list[Entry] = []
        for app in self.apps():
            name = app["name"]
            if name == front:
                out.extend(self._deep(name))
            else:
                out.extend(self._shallow(name))
        return out

    def _shallow(self, app: str) -> list[Entry]:
        """Reaching an app costs nothing to offer, so every app is always reachable.

        Reading one is what costs, and it happens once the app is in front.
        """
        return [
            Entry(
                index=-1,
                verb=Verb.FOCUS_APP,
                label=f"Switch to {app}",
                app=app,
                owner=self.name,
                reversibility=reversibility_of(Verb.FOCUS_APP, app),
                observed_at=time.time(),
                tier=Tier.SHALLOW,
                handle={"kind": "activate", "app": app},
            )
        ]

    def _deep(self, app: str) -> list[Entry]:
        try:
            page = self.bridge.call("snapshot", app=app, menus=True, limit=self.deep_limit)
        except BridgeError:
            # A covered window stops drawing and answers with nothing, so the
            # only thing offered for that app is reaching it.
            return self._shallow(app)
        page["observed_at"] = time.time()
        self._pages[app] = page

        entries: list[Entry] = []
        for element in page.get("elements", []):
            if not element.get("enabled", True):
                continue
            role = element.get("role", "")
            for operation in element.get("operations", []):
                verb = OPERATIONS.get(operation)
                if verb is None or (role, operation) in NOISE:
                    continue
                entries.append(
                    Entry(
                        index=-1,
                        verb=verb,
                        label=self._label(element),
                        app=app,
                        owner=self.name,
                        reversibility=reversibility_of(verb, app),
                        observed_at=page["observed_at"],
                        tier=Tier.DEEP,
                        needs_text=verb is Verb.TYPE_TEXT,
                        handle={
                            "kind": "element",
                            "app": app,
                            "op": operation,
                            "path": element["path"],
                            # Carried into execution: the element at that path
                            # must still be the one the decision was made about.
                            "expect": element.get("label", ""),
                            "expect_role": element.get("role", ""),
                            "fingerprint": page.get("fingerprint"),
                        },
                    )
                )

        # Menu commands are only trustworthy while the app validates them.
        if page.get("active"):
            for menu in page.get("menus", []):
                path = menu.get("menu") or menu.get("path") or ""
                if not path or menu.get("enabled") is False:
                    continue
                entries.append(
                    Entry(
                        index=-1,
                        verb=Verb.MENU,
                        label=path,
                        app=app,
                        owner=self.name,
                        reversibility=reversibility_of(Verb.MENU, app),
                        observed_at=page["observed_at"],
                        tier=Tier.DEEP,
                        handle={"kind": "menu", "app": app, "op": "MENU", "menu": path},
                    )
                )
        return entries

    @staticmethod
    def _label(element: dict) -> str:
        label = element.get("label") or element.get("value") or element.get("role", "")
        role = element.get("role", "")
        return f"{label} ({role})" if label and role else label or role

    def fresh(self, entry: Entry) -> bool:
        page = self._pages.get(entry.app)
        if page is None:
            return False
        try:
            now = self.bridge.call("fingerprint", app=entry.app, limit=self.deep_limit)
        except BridgeError:
            return False
        return now.get("fingerprint") == page.get("fingerprint")

    def execute(self, entry: Entry, text: str | None = None) -> dict:
        handle = entry.handle or {}
        if handle.get("kind") == "activate":
            result = self.bridge.call("activate", app=handle["app"])
            self.await_front(handle["app"])
            return result
        if handle.get("kind") == "search":
            query = urllib.parse.quote_plus((text or "").strip())
            subprocess.run(["open", f"https://www.google.com/search?q={query}"], check=True)
            return {"searched": text}
        if handle.get("kind") == "url":
            address = (text or "").strip().replace(" dot ", ".").replace(" ", "")
            if not address.startswith(("http://", "https://")):
                address = "https://" + address
            subprocess.run(["open", address], check=True)
            return {"opened": address}
        if handle.get("kind") == "launch":
            subprocess.run(["open", "-a", handle["app"]], check=True, capture_output=True)
            self.await_front(handle["app"], timeout=6.0)
            return {"launched": handle["app"]}
        request = {k: v for k, v in handle.items() if k not in ("kind", "fingerprint")}
        if text is not None:
            request["text"] = text
        return self.bridge.call("act", mutating=True, timeout=30, **request)

    def await_front(self, app: str, timeout: float = 3.0) -> bool:
        """Wait until the app really is in front before anything reads it.

        Activating returns as soon as the request is sent. Reading straight
        after still sees the window that was there, which is how "open notes
        and write pick up milk" ended up looking at the window it started in.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.frontmost() == app:
                # In front is not the same as finished drawing.
                time.sleep(0.35)
                return True
            time.sleep(0.1)
        return False

    def close(self) -> None:
        self.bridge.close()
