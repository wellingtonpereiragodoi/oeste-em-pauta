"""Download de páginas respeitando o robots.txt de cada site."""
from __future__ import annotations

import logging
from urllib.parse import urlsplit

import requests

from .robots import Robots

AGENTE = "OesteEmPautaBot/1.0 (+https://wellingtonpereiragodoi.github.io/oeste-em-pauta/sobre.html)"
TEMPO_LIMITE = 25

log = logging.getLogger(__name__)


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
        r = self.sessao.get(url, timeout=TEMPO_LIMITE)
        r.raise_for_status()
        return r
