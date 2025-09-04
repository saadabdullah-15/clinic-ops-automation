@echo off
set ROOT=%~dp0..
call "%ROOT%\.venv\Scripts\activate"
python -m 01_kpi_dashboard.etl.refresh_daily
