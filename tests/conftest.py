"""
Configuração dos testes.

Os testes NUNCA tocam no banco versionado (data/camposync_demo.db): antes de
qualquer import do pacote, copiamos o banco para uma pasta temporária e
apontamos a variável CAMPOSYNC_DB para a cópia. Como o cliente MCP repassa o
ambiente ao subprocesso do servidor, o servidor também usa a cópia.
"""
import os, shutil, sys, tempfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

_tmp = Path(tempfile.mkdtemp(prefix="camposync_testes_"))
DB_TESTE = _tmp / "camposync_teste.db"
shutil.copy(RAIZ / "data" / "camposync_demo.db", DB_TESTE)
os.environ["CAMPOSYNC_DB"] = str(DB_TESTE)


@pytest.fixture(scope="session")
def db_teste() -> Path:
    return DB_TESTE


def pytest_sessionfinish(session, exitstatus):
    try:
        from camposync.cliente_mcp import _instancia
        if _instancia is not None:
            _instancia.fechar()
    except Exception:
        pass
    shutil.rmtree(_tmp, ignore_errors=True)
