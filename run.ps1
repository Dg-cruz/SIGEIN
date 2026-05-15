$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Get-PythonExecutable {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($flag in @("-3", "")) {
            $args = @()
            if ($flag) { $args += $flag }
            $args += @("-c", "import sys; print(sys.executable)")
            $exe = & py @args 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe -and (Test-Path $exe.Trim())) {
                return $exe.Trim()
            }
        }
    }

    $localPython = Join-Path $env:LOCALAPPDATA "Python\bin\python.exe"
    if (Test-Path $localPython) {
        return $localPython
    }

    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike "*WindowsApps*") {
        return $cmd.Source
    }

    Write-Host ""
    Write-Host "Python nao encontrado." -ForegroundColor Red
    Write-Host "Instale em https://www.python.org/downloads/ e marque 'Add python.exe to PATH'."
    Write-Host "Ou desative o alias da Microsoft Store em:"
    Write-Host "  Configuracoes > Aplicativos > Aliases de execucao do aplicativo"
    Write-Host "  (desligue python.exe e python3.exe)"
    exit 1
}

$python = Get-PythonExecutable
Write-Host "Usando Python: $python"

$activateScript = ".\.venv\Scripts\Activate.ps1"
if ((Test-Path ".venv") -and -not (Test-Path $activateScript)) {
    Write-Host "Removendo .venv incompleto ..."
    Remove-Item -Recurse -Force ".venv"
}

if (-not (Test-Path ".venv")) {
    Write-Host "Criando ambiente virtual .venv ..."
    & $python -m venv .venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $activateScript)) {
        Write-Host "Falha ao criar o ambiente virtual." -ForegroundColor Red
        exit 1
    }
}

Write-Host "Ativando .venv ..."
. $activateScript

Write-Host "Sincronizando dependencias ..."
pip install -r requirements.txt --disable-pip-version-check
if ($LASTEXITCODE -ne 0) {
    Write-Host "Falha ao instalar dependencias." -ForegroundColor Red
    exit 1
}

Write-Host "Iniciando SIGEN em http://127.0.0.1:8000 ..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
