# Cria o venv (se preciso), instala dependencias e sobe o Streamlit.
# Uso (de qualquer pasta): .\scripts\rodar.ps1
# Requer a variavel de ambiente OPENROUTER_API_KEY definida.

$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

if (-not $env:OPENROUTER_API_KEY) {
    Write-Warning "OPENROUTER_API_KEY nao definida - o agente nao vai conseguir chamar o LLM."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Criando venv em .venv ..."
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
}

Write-Host "Subindo Consultor da Safra em http://localhost:8501 ..."
.venv\Scripts\streamlit run app.py --server.port 8501
