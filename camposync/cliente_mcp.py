"""
Cliente MCP do Consultor da Safra.

Sobe o servidor `camposync.servidor_mcp` como SUBPROCESSO e conversa com ele
pelo protocolo MCP (JSON-RPC sobre stdio), exatamente como o Claude Desktop,
o Cursor ou qualquer outro host MCP faria:

    agente ──(list_tools / call_tool)──► cliente_mcp ══stdio══► servidor_mcp

O fastmcp.Client é assíncrono, mas o Streamlit e o agente são síncronos.
Por isso a sessão MCP vive numa thread própria com o seu event loop, e as
chamadas síncronas são encaminhadas para ela. A conexão é aberta uma única
vez por processo e reutilizada (o subprocesso do servidor fica vivo).
"""
import asyncio, atexit, json, os, sys, threading

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from .config import ROOT

TIMEOUT_S = 600  # a 1ª busca no RAG pode esperar a indexação dos PDFs terminar


class ClienteMCP:
    def __init__(self):
        transporte = StdioTransport(
            command=sys.executable,
            args=["-m", "camposync.servidor_mcp"],
            cwd=str(ROOT),
            env=dict(os.environ),
            keep_alive=False,  # ao fechar o cliente, encerra o subprocesso
        )
        self._client = Client(transporte)
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True, name="mcp-loop").start()
        self._rodar(self._client.__aenter__())
        atexit.register(self.fechar)

    def _rodar(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(TIMEOUT_S)

    # ── API síncrona ────────────────────────────────────────────────────────
    def listar_ferramentas(self) -> list:
        """Ferramentas anunciadas pelo servidor (objetos mcp.types.Tool)."""
        return self._rodar(self._client.list_tools())

    def chamar(self, nome: str, args: dict | None = None):
        """Executa a ferramenta no servidor e devolve o resultado já como objeto Python."""
        res = self._rodar(self._client.call_tool(nome, args or {}, raise_on_error=False))
        if res.is_error:
            raise RuntimeError(_texto(res) or f"erro ao executar '{nome}'")
        if res.data is not None:
            return res.data
        if res.structured_content is not None:
            return res.structured_content.get("result", res.structured_content)
        txt = _texto(res)
        try:
            return json.loads(txt)
        except (json.JSONDecodeError, TypeError):
            return txt

    def fechar(self):
        try:
            # timeout curto: encerrar o app/testes nunca pode ficar preso no subprocesso
            asyncio.run_coroutine_threadsafe(
                self._client.__aexit__(None, None, None), self._loop
            ).result(10)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)


def _texto(res) -> str:
    return "\n".join(getattr(b, "text", "") for b in res.content or [])


_instancia: ClienteMCP | None = None
_lock = threading.Lock()


def get_cliente() -> ClienteMCP:
    """Conexão única por processo (o Streamlit reexecuta o script a cada interação)."""
    global _instancia
    with _lock:
        if _instancia is None:
            _instancia = ClienteMCP()
        return _instancia


def chamar(nome: str, args: dict | None = None):
    return get_cliente().chamar(nome, args)


if __name__ == "__main__":
    # Diagnóstico rápido:  python -m camposync.cliente_mcp
    c = get_cliente()
    for t in c.listar_ferramentas():
        print(f"- {t.name}: {(t.description or '').strip().splitlines()[0]}")
