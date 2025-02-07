uv venv
.\.venv\Scripts\activate
uv pip install -r requirements.txt
uv pip install pyinstaller
pyinstaller .\IsaacMM-Windows.spec