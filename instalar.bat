@echo off
REM Instalador do SGP-UNIFEI para avaliacao (Windows).
REM Requer Docker Desktop instalado e em execucao.
cd /d "%~dp0"

echo === SGP-UNIFEI - Instalacao para avaliacao ===

echo 1/3 Carregando a imagem do sistema...
docker load -i sgp-unifei-imagem.tar.gz
if errorlevel 1 goto erro

echo 2/3 Subindo o sistema (migracoes + dados de demonstracao)...
docker compose -f docker-compose.prod.yml up -d
if errorlevel 1 goto erro

echo 3/3 Aguardando o sistema ficar disponivel...
timeout /t 15 /nobreak >nul

echo.
echo === Pronto! ===
echo   Sistema:  http://localhost:8000/
echo   Admin:    http://localhost:8000/admin/          (admin / admin123)
echo   Login:    http://localhost:8000/contas/entrar/  (aluno1, docente1,
echo             tecnico1, diretor1, proreitor1 - senha demo123)
echo.
echo   Logs:   docker compose -f docker-compose.prod.yml logs --tail=100 app
echo   Parar:  docker compose -f docker-compose.prod.yml stop
echo   Checklist e relato de problemas: README-AVALIACAO.md
echo.
pause
goto fim

:erro
echo.
echo ERRO: verifique se o Docker Desktop esta instalado e em execucao
echo       https://www.docker.com/products/docker-desktop/
pause
:fim
