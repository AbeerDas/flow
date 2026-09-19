# Vendored code

`axbridge.swift` and `build.sh` come from
[open-computer-use](https://github.com/max1874/open-computer-use), MIT licensed.
The full licence is in `LICENSE-open-computer-use`.

The bridge walks the macOS accessibility tree and executes operations by path.
It is taken unmodified. Everything above it in this repository is ours, because
the upstream agent loop assumes a single focused window and this project spans
apps.
