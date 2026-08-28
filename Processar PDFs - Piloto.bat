@echo off
echo.
echo  ================================================
echo   CSM Decor - Processar PDFs (Piloto - 5 PDFs)
echo  ================================================
echo.
echo  Coloque os PDFs em: data\pdfs\piloto\
echo  Resultados em: data\output\piloto\
echo.
".venv\Scripts\python.exe" scripts\run_pilot.py
echo.
pause
