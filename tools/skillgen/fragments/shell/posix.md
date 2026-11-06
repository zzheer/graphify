```bash
# Detect the correct Python interpreter (handles uv tool, pipx, venv, system installs)
PYTHON=""
GRAPHIFY_BIN=$(which graphify 2>/dev/null)
# 1. uv tool installs — look in the tool dir; never `uv tool run --from graphifyy`,
#    which fetches the package from PyPI when it is not installed.
if [ -z "$PYTHON" ] && command -v uv >/dev/null 2>&1; then
    _UV_DIR=$(uv tool dir 2>/dev/null)
    if [ -n "$_UV_DIR" ] && [ -x "$_UV_DIR/graphifyy/bin/python" ]; then PYTHON="$_UV_DIR/graphifyy/bin/python"; fi
fi
# 2. Read shebang from graphify binary (pipx and direct pip installs)
if [ -z "$PYTHON" ] && [ -n "$GRAPHIFY_BIN" ]; then
    _SHEBANG=$(head -1 "$GRAPHIFY_BIN" | tr -d '#!')
    case "$_SHEBANG" in
        *[!a-zA-Z0-9/_.@-]*) ;;
        *) "$_SHEBANG" -c "import graphify" 2>/dev/null && PYTHON="$_SHEBANG" ;;
    esac
fi
# 3. Fall back to python3
if [ -z "$PYTHON" ]; then PYTHON="python3"; fi
if ! "$PYTHON" -c "import graphify" 2>/dev/null; then
    # Not installed. Never install from here: an unpinned upgrade or a pip install
    # into the system site-packages pulls whatever PyPI serves today into the
    # user's environment. Stop and hand the user the pinned command instead.
    echo "graphify is not installed: 'graphify --version' is unavailable and '$PYTHON' cannot import graphify." >&2
    echo "Install the pinned release, then re-run /graphify:" >&2
    echo "    uv tool install \"graphifyy==@@PINNED_VERSION@@\"" >&2
    echo "  (without uv: python3 -m pip install \"graphifyy==@@PINNED_VERSION@@\")" >&2
    exit 1
fi
# Write interpreter path for all subsequent steps (persists across invocations)
mkdir -p graphify-out
"$PYTHON" -c "import sys; open('graphify-out/.graphify_python', 'w', encoding='utf-8').write(sys.executable)"
# Save scan root so `graphify update` (no args) knows where to look next time.
# The scan path is passed through a quoted heredoc, never substituted into the
# command line itself: a bare `cd <path>` (or an unquoted heredoc, which
# still expands $()/backticks in its body) would let a malicious path execute
# as shell code the moment this line runs.
"$PYTHON" -c "import os, sys; out_path = os.path.abspath('graphify-out/.graphify_root'); os.chdir(sys.stdin.readline().rstrip('\n')); open(out_path, 'w', encoding='utf-8').write(os.getcwd())" <<'GRAPHIFY_ROOT_EOF'
INPUT_PATH
GRAPHIFY_ROOT_EOF
```

If the import succeeds, print nothing and move straight to Step 2. If it prints the install message instead, **stop**: show the user that exact pinned command and wait for them to run it. Never run `uv tool install`, `pip install`, or any other install or upgrade command yourself, and never add `--upgrade` or the pip flag that overrides the system site-packages protection.

**Every later bash block starts with the same two `GRAPHIFY_PYTHON` lines.** They read `graphify-out/.graphify_python` (a file in the repository, so data, never trusted as-is), reject it unless it is an absolute plain path (`A-Za-z0-9_./+@:\-` and spaces only; a relative path such as a committed `./tools/py`, a `..` or `.` segment, and a `/proc`, `/dev` or `/sys` path are refused), an executable file, and an interpreter that can `import graphify`, and only then run it, always quoted, with the Python passed on stdin through a quoted heredoc (`- <<'PY' ... PY`). Copy the two lines verbatim into every block; never expand the file into a command line with `$(cat ...)`, never use `-c "..."` with substituted text, and never paste a path, label, answer or any other model- or repository-derived value into a command line: such values reach Python only through files or quoted heredocs. When the `graphify` CLI is on PATH, prefer its subcommands (`graphify query`, `graphify path`, `graphify explain`, `graphify save-result`, `graphify update`) over an inline block that does the same thing.
