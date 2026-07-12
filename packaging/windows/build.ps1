if (Get-Command uv -ErrorAction SilentlyContinue) {
    if (!(Test-Path .venv)) {
        uv venv
    }
    . .\.venv\Scripts\activate
    uv pip install -r requirements.txt pyinstaller
} else {
    pip install -r requirements.txt pyinstaller
}

pyinstaller .\packaging\windows\IsaacMM-Windows.spec

Write-Output "Created dist\IsaacMM-Windows.exe"
