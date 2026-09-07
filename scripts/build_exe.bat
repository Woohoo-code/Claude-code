@echo off
REM Build pcba-builder.exe on Windows.
cd /d "%~dp0\.."
python -m pip install --quiet -r requirements-build.txt
pyinstaller --onefile --name pcba-builder --noconfirm ^
  --distpath dist --workpath build\pyinstaller --specpath build\pyinstaller ^
  pcba_builder_entry.py
echo Built: dist\pcba-builder.exe
