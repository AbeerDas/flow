"""Native Mac windows, read across every running app.

The accessibility API answers for any app, not only the one in front, so the
registry spans apps. The menu bar is the exception: an inactive app reports its
menu items as disabled and lets their titles go stale, so menus are read only
for the app that is active.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from jarvis.registry import Entry, Reversibility, Tier, Verb, reversibility_of
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

DEEP_LIMIT = 250


class MacAdapter:
    """One bridge process, every app."""

    name = "mac"

    def __init__(self, deep_limit: int = DEEP_LIMIT):
        self.bridge = Bridge()
        self.deep_limit = deep_limit
        self._pages: dict[str, dict] = {}
        status = self.bridge.call("status")
        if not status["accessibility"]:
            self.close()
            raise PermissionError(
                "Accessibility permission is missing. System Settings > Privacy & Security > "
                "Accessibility: enable the app running this shell, then restart it."
            )

    def apps(self) -> list[dict]:
        return self.bridge.call("apps")["apps"]

    def targets(self) -> list[str]:
        return [a["name"] for a in self.apps()]

    def frontmost(self) -> str | None:
        for app in self.apps():
            if app["frontmost"]:
                return app["name"]
        return None

    def scan(self, target: str, tier: Tier = Tier.DEEP) -> list[Entry]:
        if tier is Tier.SHALLOW:
            return self._shallow(target)
        return self._deep(target)

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
            return self._shallow(app)
        page["observed_at"] = time.time()
        self._pages[app] = page

        entries: list[Entry] = []
        for element in page.get("elements", []):
            if not element.get("enabled", True):
                continue
            for operation in element.get("operations", []):
                verb = OPERATIONS.get(operation)
                if verb is None:
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
            return self.bridge.call("activate", app=handle["app"])
        request = {k: v for k, v in handle.items() if k not in ("kind", "fingerprint")}
        if text is not None:
            request["text"] = text
        return self.bridge.call("act", mutating=True, timeout=30, **request)

    def close(self) -> None:
        self.bridge.close()
