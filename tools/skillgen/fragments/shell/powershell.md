```powershell
# Detect Python with graphify — uv/pipx-aware (fixes #831)
New-Item -ItemType Directory -Force -Path graphify-out | Out-Null
$GRAPHIFY_PYTHON = $null

function Find-GraphifyPython {
    # 1. uv tool install — 'uv tool dir' is authoritative, respects UV_TOOL_DIR automatically
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        $uvDir = (uv tool dir 2>$null).Trim()
        if ($uvDir) {
            $py = Join-Path $uvDir "graphifyy\Scripts\python.exe"
            if (Test-Path $py) {
                & $py -c "import graphify" 2>$null
                if ($LASTEXITCODE -eq 0) { return $py }
            }
        }
    }
    # 2. pipx install — 'pipx environment' respects PIPX_HOME automatically
    if (Get-Command pipx -ErrorAction SilentlyContinue) {
        $venvs = (pipx environment --value PIPX_LOCAL_VENVS 2>$null).Trim()
        if ($venvs) {
            $py = Join-Path $venvs "graphifyy\Scripts\python.exe"
            if (Test-Path $py) {
                & $py -c "import graphify" 2>$null
                if ($LASTEXITCODE -eq 0) { return $py }
            }
        }
    }
    # 3. Active venv / conda / pip-into-current-env
    $pyCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pyCmd) {
        & $pyCmd.Source -c "import graphify" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return (& $pyCmd.Source -c "import sys; print(sys.executable)").Trim()
        }
    }
    return $null
}

# Try to find the right Python (uv → pipx → active env)
$GRAPHIFY_PYTHON = Find-GraphifyPython

# Not found — never install from here (an unpinned install pulls whatever PyPI
# serves today into the user's environment): stop and hand the user the pinned command.
if (-not $GRAPHIFY_PYTHON) {
    Write-Error "graphify is not installed. Install the pinned release, then re-run /graphify:`n    uv tool install `"graphifyy==@@PINNED_VERSION@@`"`n  (without uv: python -m pip install `"graphifyy==@@PINNED_VERSION@@`")"
    exit 1
}

# Save interpreter path — all subsequent steps read this.
# `Out-File -Encoding utf8` always writes a BOM on Windows PowerShell 5.1 (utf8NoBOM
# only exists from PowerShell 6), and that BOM rides into the saved path, so the hook
# rebuild fails with WinError 123 (#3028). WriteAllText with an explicit BOM-less
# encoding writes the bytes POSIX writes, and adds no trailing newline.
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText((Join-Path $PWD 'graphify-out\.graphify_python'), [string]$GRAPHIFY_PYTHON, $Utf8NoBom)
# Save scan root so `graphify update` (no args) knows where to look next time.
# INPUT_PATH is captured through a single-quoted (literal) here-string, never
# substituted directly into the command line: an unquoted bareword argument
# substituted here would let a malicious path (a stray `;`, `|`, or `$(...)`)
# execute as script code the moment this line runs.
$InputPathRaw = @'
INPUT_PATH
'@
[System.IO.File]::WriteAllText((Join-Path $PWD 'graphify-out\.graphify_root'), (Resolve-Path $InputPathRaw.Trim()).Path, $Utf8NoBom)
```

If the import succeeds, print nothing and move straight to Step 2. If it prints the install message instead, **stop**: show the user that exact pinned command and wait for them to run it. Never run `uv tool install`, `pip install`, or any other install or upgrade command yourself, and never add `--upgrade` or `--break-system-packages`.

**Every later block starts with the same two `$GRAPHIFY_PYTHON` lines.** They read `graphify-out\.graphify_python` (a file in the repository, so data, never trusted as-is), reject it unless it is a plain path, an existing file, and an interpreter that can `import graphify`, and only then run it with the Python passed on stdin through a single-quoted here-string (`@' ... '@ | & $GRAPHIFY_PYTHON -`). Copy the two lines verbatim into every block, and never paste a path, label, answer or any other model- or repository-derived value into a command line: such values reach Python only through files or here-strings.
