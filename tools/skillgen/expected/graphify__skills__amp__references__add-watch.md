# graphify reference: add a URL and watch a folder

Load this when the user ran `/graphify add <url>` or passed `--watch`. Neither is part of the default build.

## For /graphify add

Fetch a URL and add it to the corpus, then update the graph.

```bash
GRAPHIFY_PYTHON=""; read -r GRAPHIFY_PYTHON 2>/dev/null < graphify-out/.graphify_python || true
case "$GRAPHIFY_PYTHON" in ""|*[!A-Za-z0-9_./+@:\ \\-]*|*/../*|*/./*|/proc/*|/dev/*|/sys/*) GRAPHIFY_PYTHON="";; /*|[A-Za-z]:/*|[A-Za-z]:\\*) ;; *) GRAPHIFY_PYTHON="";; esac; [ -n "$GRAPHIFY_PYTHON" ] && [ -x "$GRAPHIFY_PYTHON" ] && "$GRAPHIFY_PYTHON" -c "import graphify" 2>/dev/null || { echo "graphify-out/.graphify_python is missing, not an absolute plain executable path, or cannot import graphify: re-run Step 1" >&2; exit 1; }
"$GRAPHIFY_PYTHON" - <<'PY'
import sys
from graphify.ingest import ingest
from pathlib import Path

try:
    out = ingest('URL', Path('./raw'), author='AUTHOR', contributor='CONTRIBUTOR')
    print(f'Saved to {out}')
except ValueError as e:
    print(f'error: {e}', file=sys.stderr)
    sys.exit(1)
except RuntimeError as e:
    print(f'error: {e}', file=sys.stderr)
    sys.exit(1)
PY
```

Replace `URL` with the actual URL, `AUTHOR` with the user's name if provided, `CONTRIBUTOR` likewise. If the command exits with an error, tell the user what went wrong - do not silently continue. After a successful save, automatically run the `--update` pipeline on `./raw` to merge the new file into the existing graph.

Supported URL types (auto-detected):
- YouTube / any video URL → audio downloaded via yt-dlp, transcribed to `.txt` on next run (requires `pip install 'graphifyy[video]'`)
- Twitter/X → fetched via oEmbed, saved as `.md` with tweet text and author
- arXiv → abstract + metadata saved as `.md`
- PDF → downloaded as `.pdf`
- Images (.png/.jpg/.webp) → downloaded, Claude vision extracts on next run
- Any webpage → converted to markdown via html2text

---

## For --watch

Start a background watcher that monitors a folder and auto-updates the graph when files change.

```bash
GRAPHIFY_PYTHON=""; read -r GRAPHIFY_PYTHON 2>/dev/null < graphify-out/.graphify_python || true
case "$GRAPHIFY_PYTHON" in ""|*[!A-Za-z0-9_./+@:\ \\-]*|*/../*|*/./*|/proc/*|/dev/*|/sys/*) GRAPHIFY_PYTHON="";; /*|[A-Za-z]:/*|[A-Za-z]:\\*) ;; *) GRAPHIFY_PYTHON="";; esac; [ -n "$GRAPHIFY_PYTHON" ] && [ -x "$GRAPHIFY_PYTHON" ] && "$GRAPHIFY_PYTHON" -c "import graphify" 2>/dev/null || { echo "graphify-out/.graphify_python is missing, not an absolute plain executable path, or cannot import graphify: re-run Step 1" >&2; exit 1; }
"$GRAPHIFY_PYTHON" -m graphify.watch "$(cat graphify-out/.graphify_root)" --debounce 3
```

This watches the same folder graphify extracted, read from the trusted `graphify-out/.graphify_root` that Step 1 resolved - there is no path to substitute, so a scan root containing shell metacharacters can never be re-interpreted here. Behavior depends on what changed:

- **Code files only (.py, .ts, .go, etc.):** re-runs AST extraction + rebuild + cluster immediately, no LLM needed. `graph.json` and `GRAPH_REPORT.md` are updated automatically.
- **Docs, papers, or images:** writes a `graphify-out/needs_update` flag and prints a notification to run `/graphify --update` (LLM semantic re-extraction required).

Debounce (default 3s): waits until file activity stops before triggering, so a wave of parallel agent writes doesn't trigger a rebuild per file.

Press Ctrl+C to stop.

For agentic workflows: run `--watch` in a background terminal. Code changes from agent waves are picked up automatically between waves. If agents are also writing docs or notes, you'll need a manual `/graphify --update` after those waves.
