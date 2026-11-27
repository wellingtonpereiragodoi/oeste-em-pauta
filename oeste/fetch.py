"""Download de páginas respeitando o robots.txt de cada site."""
from __future__ import annotations

import logging
import time
from urllib.parse import urlsplit

import requests

from .robots import Robots

AGENTE = "OesteEmPautaBot/1.0 (+https://oesteempauta.com/sobre.html)"
TEMPO_LIMITE = (10, 20)   # (conectar, esperar cada pedaço da resposta)
TEMPO_TOTAL = 45          # segundos no máximo por página, mesmo se o site responder devagar
TAMANHO_MAXIMO = 8_000_000

log = logging.getLogger(__name__)


class LentoDemais(Exception):
    """O site demorou demais para responder."""


class Bloqueado(Exception):
    """O robots.txt do site não permite ler este endereço."""


class Navegador:
    def __init__(self, sessao: requests.Session | None = None):
        self.sessao = sessao or requests.Session()
        self.sessao.headers.update({"User-Agent": AGENTE, "Accept-Language": "pt-BR,pt;q=0.9"})
        self._robots: dict[str, Robots] = {}

    def robots_de(self, url: str) -> Robots:
        partes = urlsplit(url)
        origem = f"{partes.scheme}://{partes.netloc}"
        if origem not in self._robots:
            texto = None
            try:
                r = self.sessao.get(origem + "/robots.txt", timeout=TEMPO_LIMITE)
                # 4xx = sem robots.txt = tudo liberado. 5xx = na dúvida, não ler.
                if r.status_code >= 500:
                    texto = "User-agent: *\nDisallow: /"
                elif r.ok and "text/html" not in r.headers.get("content-type", ""):
                    texto = r.text
            except requests.RequestException as e:
                log.warning("robots.txt indisponível em %s (%s); site ignorado nesta rodada", origem, e)
                texto = "User-agent: *\nDisallow: /"
            self._robots[origem] = Robots(texto, AGENTE)
        return self._robots[origem]

    def baixar(self, url: str) -> requests.Response:
        if not self.robots_de(url).permite(url):
            raise Bloqueado(url)
        inicio = time.monotonic()
        r = self.sessao.get(url, timeout=TEMPO_LIMITE, stream=True)
        r.raise_for_status()
        pedacos, total = [], 0
        for pedaco in r.iter_content(64 * 1024):
            pedacos.append(pedaco)
            total += len(pedaco)
            if time.monotonic() - inicio > TEMPO_TOTAL:
                r.close()
                raise LentoDemais(f"mais de {TEMPO_TOTAL}s para baixar {url}")
            if total > TAMANHO_MAXIMO:
                r.close()
                raise LentoDemais(f"página grande demais: {url}")
        r._content = b"".join(pedacos)
        return r
