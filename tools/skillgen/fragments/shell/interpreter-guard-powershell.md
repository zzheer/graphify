```powershell
# graphify-out\.graphify_python is repository data: re-resolve it unless it is a
# plain path to an existing interpreter that can import graphify.
$GRAPHIFY_PYTHON = (Get-Content graphify-out\.graphify_python -Raw -ErrorAction SilentlyContinue)
if ($GRAPHIFY_PYTHON) { $GRAPHIFY_PYTHON = $GRAPHIFY_PYTHON.Trim() }
$valid = $GRAPHIFY_PYTHON -and ($GRAPHIFY_PYTHON -match '^[A-Za-z0-9_./+@:\\ -]+$') -and (Test-Path -PathType Leaf $GRAPHIFY_PYTHON)
if ($valid) { & $GRAPHIFY_PYTHON -c "import graphify" 2>$null; $valid = ($LASTEXITCODE -eq 0) }
if (-not $valid) {
    $GRAPHIFY_PYTHON = $null
    $graphifyCmd = Get-Command graphify -ErrorAction SilentlyContinue
    if ($graphifyCmd) {
        # The interpreter that owns the graphify entry point sits next to it
        # (<env>\Scripts\python.exe for uv tool, pipx, and venv installs).
        $py = Join-Path (Split-Path $graphifyCmd.Source) "python.exe"
        if (Test-Path $py) { $GRAPHIFY_PYTHON = $py }
    }
    if (-not $GRAPHIFY_PYTHON) { $GRAPHIFY_PYTHON = "python" }
    & $GRAPHIFY_PYTHON -c "import graphify" 2>$null
    if ($LASTEXITCODE -ne 0) { Write-Error "graphify is not importable: re-run Step 1"; exit 1 }
    New-Item -ItemType Directory -Force -Path graphify-out | Out-Null
    & $GRAPHIFY_PYTHON -c "import sys; open('graphify-out/.graphify_python', 'w', encoding='utf-8').write(sys.executable)"
}
```
