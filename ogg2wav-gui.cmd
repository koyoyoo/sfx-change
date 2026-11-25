@echo off
setlocal
set "ROOT=%~dp0"
if defined PYTHONPATH (
  set "PYTHONPATH=%ROOT%src;%PYTHONPATH%"
) else (
  set "PYTHONPATH=%ROOT%src"
)
python -m sfx_change.gui %*
endlocal
