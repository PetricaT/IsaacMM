if (Get-Command uv -ErrorAction SilentlyContinue) {
    if (!(Test-Path .venv)) {
        uv venv
    }
    . .\.venv\Scripts\activate
    uv pip install -r requirements.txt pyinstaller
} else {
    pip install -r requirements.txt pyinstaller
}

$version = Select-String -Path "pyproject.toml" -Pattern '^version = "(.*)"' | ForEach-Object { $_.Matches.Groups[1].Value }

pyinstaller .\packaging\windows\IsaacMM-Windows.spec

Move-Item "dist\IsaacMM-Windows.exe" "dist\IsaacMM-$version-Windows.exe" -Force
Write-Output "Created dist\IsaacMM-$version-Windows.exe"
