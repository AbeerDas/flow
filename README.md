# Jarvis

Voice-first control of a Mac. Hold a key, say what you want, and it happens
before you finish the sentence.

## The idea

Do not show a model a picture of the screen and ask where to click. Build a
numbered list of everything that is genuinely possible right now, and ask it for
a line number.

A disabled button never reaches the list. An element with no real action never
reaches the list. So clicking something that does not exist stops being a bug to
prompt away and becomes a sentence the system cannot form.

That list is the registry, and it is the whole project. Every surface is an
adapter that fills it. Speech picks from it. Adapters carry it out.

## Where it spans

The registry covers the machine, not one window. macOS answers accessibility
queries for any running app, so every app is readable at once. Cost is managed
by depth rather than by scope.

| Tier | Covers | Read |
| --- | --- | --- |
| Deep | The app in front | Every actionable element, plus its menu commands |
| Shallow | Every other running app | Reachable, nothing read until it comes forward |

Menus are read only for the active app. An inactive app reports its menu items
as disabled and lets their titles go stale.

## Safety

Reversibility is a property of the verb and the app, decided in code. It is
never read off a label, because labels are written by whoever wrote the window.

- **Free** may fire on a half-finished sentence
- **Undoable** waits for the sentence to end
- **Permanent** never fires on its own

A press is only as safe as the app it lands in, and nothing about the button
tells you which. So apps earn a lower floor by being named in `registry.py`, and
anything unnamed treats a press as permanent.

## Status

Working. The registry, the reversibility rules, and the Mac adapter reading
every running app.

Not built yet. Speech, speculation on partial sentences, the overlay, undo, and
the browser, work tools and Claude Code adapters.

## Running it

Accessibility permission goes to the application that owns your shell, not to
the shell. Running from Terminal means ticking Terminal. Running inside another
app's built-in terminal means ticking that app, which is easy to get wrong and
gives no error worth reading.

To check which one that is

```bash
ps -o comm= -p $(ps -o ppid= -p $PPID)
```

Tick it under System Settings, then Privacy and Security, then Accessibility.
Then quit that application fully and reopen it, because the switch does not
reach a process that is already running.

```bash
python3 scripts/scan.py
```

prints what your machine can currently do.

## Layout

```
jarvis/registry.py        the list, the seven fields, the reversibility rules
jarvis/adapters/base.py   what a surface has to provide
jarvis/adapters/mac.py    native Mac windows, across every app
vendor/                   the accessibility bridge, MIT, see NOTICE.md
scripts/scan.py           print the registry and exit
```

## Credit

The Swift accessibility bridge and its pipe client come from
[open-computer-use](https://github.com/max1874/open-computer-use) under MIT, and
the indexed-action-space idea comes from
[jev-ultrafast](https://github.com/browser-use/jev-ultrafast). The upstream
agent loop is not used, because it assumes a single focused window.
