"""Goals with the label that should win, as a substring.

Commands anyone would say to a Mac, biased to menu items that most apps carry
so the set survives a different frontmost app.
"""

GOALS = [
    ("go back", "Back"),
    ("open settings", "Settings"),
    ("quit claude", "Quit Claude"),
    ("hide claude", "Hide Claude"),
    ("check for updates", "Check for Updates"),
    ("switch to spotify", "Switch to Spotify"),
    ("go to google chrome", "Switch to Google Chrome"),
    ("bring up finder", "Switch to Finder"),
    ("open linear", "Switch to Linear"),
    ("close the window", "Close"),
    ("minimise the window", "Minimize"),
    ("zoom the window", "Zoom"),
    ("select all", "Select All"),
    ("copy that", "Copy"),
    ("paste it", "Paste"),
    ("undo that", "Undo"),
    ("cut this", "Cut"),
    ("find something", "Find"),
    ("show the artifacts panel", "Artifacts"),
    ("about claude", "About Claude"),
]


# Requests with no answer in the registry. The action's own confidence is what
# separates these, so a run that starts acting on them has regressed.
JUNK = [
    "tell me a joke",
    "order me a pizza",
    "yeah I think so too",
    "how tall is the eiffel tower",
    "remind me to call mum",
    "who won the match last night",
    "explain quantum computing to me",
]
