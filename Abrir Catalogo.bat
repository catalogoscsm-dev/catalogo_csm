@echo off
echo.
echo  ================================================
echo   CSM Decor - Catalogo Digital
echo  ================================================
echo.
echo  Iniciando servidor...
echo  Acesse: http://localhost:5000
echo.
echo  Admin  : usuario "admin"   (ve fornecedores)
echo  Cliente: usuario "cliente" (so ve produtos)
echo.
echo  Pressione Ctrl+C para encerrar.
echo  ================================================
echo.
start "" "http://localhost:5000"
".venv\Scripts\python.exe" webapp\app.py
pause
