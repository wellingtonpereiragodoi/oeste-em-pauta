@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo ============================================
echo   Oeste em Pauta - instalar, testar e coletar
echo ============================================
echo.
where python >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Python nao encontrado. Instale o Python 3.12 em python.org
  echo        marcando "Add python.exe to PATH" e rode este arquivo de novo.
  echo [ERRO] Python nao encontrado > resultado-teste.log
  pause
  exit /b 1
)
if not exist .venv (
  echo Criando ambiente Python...
  python -m venv .venv
)
echo Instalando dependencias (pode levar 1 minuto)...
.venv\Scripts\python -m pip install -q -r requirements.txt pytest > resultado-teste.log 2>&1
echo.
echo ----- TESTES -----
.venv\Scripts\python -m pytest -q >> resultado-teste.log 2>&1
echo.
echo ----- COLETA NOS SITES REAIS -----
.venv\Scripts\python -m oeste.collect >> resultado-teste.log 2>&1
echo.
echo ----- GERANDO O SITE -----
.venv\Scripts\python -m oeste.build >> resultado-teste.log 2>&1
type resultado-teste.log
echo.
echo ============================================
echo  Pronto! O resultado foi salvo em resultado-teste.log
echo ============================================
start "" "_site\index.html"
pause
