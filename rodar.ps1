# Ativa o venv e sobe o Streamlit
# Uso: .\rodar.ps1

$env:ANTHROPIC_API_KEY = $env:ANTHROPIC_API_KEY  # já deve estar definida no sistema

if (-not (Test-Path "C:\v\Scripts\python.exe")) {
    Write-Host "Criando venv em C:\v ..."
    python -m venv C:\v
    C:\v\Scripts\pip install anthropic fastmcp streamlit chromadb pypdf onnxruntime pandas requests
}

Write-Host "Subindo Consultor da Safra em http://localhost:8501 ..."
C:\v\Scripts\streamlit run app.py --server.port 8501
