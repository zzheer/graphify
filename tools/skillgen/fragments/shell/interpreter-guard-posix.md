```bash
# graphify-out/.graphify_python is repository data: re-resolve it unless it is a
# plain path to an executable interpreter that can import graphify.
GRAPHIFY_PYTHON=""; read -r GRAPHIFY_PYTHON 2>/dev/null < graphify-out/.graphify_python || true
case "$GRAPHIFY_PYTHON" in ""|*[!A-Za-z0-9_./+@:\\-]*) GRAPHIFY_PYTHON="";; esac
if [ -z "$GRAPHIFY_PYTHON" ] || [ ! -x "$GRAPHIFY_PYTHON" ] || ! "$GRAPHIFY_PYTHON" -c "import graphify" 2>/dev/null; then
    PYTHON="python3"
    GRAPHIFY_BIN=$(which graphify 2>/dev/null)
    if [ -n "$GRAPHIFY_BIN" ]; then
        _SHEBANG=$(head -1 "$GRAPHIFY_BIN" | tr -d '#!')
        case "$_SHEBANG" in *[!A-Za-z0-9_./+@:\\-]*) ;; *) "$_SHEBANG" -c "import graphify" 2>/dev/null && PYTHON="$_SHEBANG" ;; esac
    fi
    "$PYTHON" -c "import graphify" 2>/dev/null || { echo "graphify is not importable: re-run Step 1" >&2; exit 1; }
    mkdir -p graphify-out
    "$PYTHON" -c "import sys; open('graphify-out/.graphify_python', 'w', encoding='utf-8').write(sys.executable)"
fi
```
