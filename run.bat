@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON_EXE="

where py >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"
    if not defined PYTHON_EXE (
        for /f "delims=" %%P in ('py -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"
    )
)

if not defined PYTHON_EXE (
    if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
        set "PYTHON_EXE=%LOCALAPPDATA%\Python\bin\python.exe"
    )
)

if not defined PYTHON_EXE (
    echo.
    echo Python nao encontrado.
    echo Instale em https://www.python.org/downloads/ e marque "Add python.exe to PATH".
    echo Ou desative o alias da Microsoft Store em Configuracoes ^> Aplicativos ^> Aliases de execucao.
    exit /b 1
)

echo Usando Python: %PYTHON_EXE%

if exist ".venv" if not exist ".venv\Scripts\activate.bat" (
    echo Removendo .venv incompleto ...
    rmdir /s /q ".venv"
)

if not exist ".venv" (
    echo Criando ambiente virtual .venv ...
    "%PYTHON_EXE%" -m venv .venv
    if errorlevel 1 (
        echo Falha ao criar o ambiente virtual.
        exit /b 1
    )
)

echo Ativando .venv ...
call .venv\Scripts\activate.bat

echo Sincronizando dependencias ...
pip install -r requirements.txt --disable-pip-version-check
if errorlevel 1 (
    echo Falha ao instalar dependencias.
    exit /b 1
)

echo Iniciando SIGEN em http://127.0.0.1:8000 ...
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
