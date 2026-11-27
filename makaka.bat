@echo off
py -3 -X utf8 "%~dp0makaka.py" %*
exit /b %ERRORLEVEL%
