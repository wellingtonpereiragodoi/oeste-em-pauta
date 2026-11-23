"""Leitura do robots.txt seguindo a regra do Google (vale a regra mais específica).

O módulo urllib.robotparser do Python usa a PRIMEIRA regra que bate, o que dá
resultado errado em sites como o da Prefeitura de Barueri, que têm
"Disallow: /" seguido de "Allow: /Noticia". Aqui vale a regra mais longa,
e em empate o Allow vence - como fazem Google e Bing.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit


class Robots:
    def __init__(self, texto: str | None, agente: str = "*"):
        self.regras: list[tuple[bool, str]] = []  # (permitido, caminho)
        if texto:
            self._interpretar(texto, agente.lower())

    def _interpretar(self, texto: str, agente: str) -> None:
        grupos: dict[str, list[tuple[bool, str]]] = {}
        agentes_atuais: list[str] = []
        lendo_regras = False
        for linha in texto.splitlines():
            linha = linha.split("#", 1)[0].strip()
            if ":" not in linha:
                continue
            campo, valor = (p.strip() for p in linha.split(":", 1))
            campo = campo.lower()
            if campo == "user-agent":
                if lendo_regras:
                    agentes_atuais = []
                    lendo_regras = False
                agentes_atuais.append(valor.lower())
                for a in agentes_atuais:
                    grupos.setdefault(a, [])
            elif campo in ("allow", "disallow"):
                lendo_regras = True
                if campo == "disallow" and not valor:
                    continue  # "Disallow:" vazio = tudo liberado
                for a in agentes_atuais:
                    grupos.setdefault(a, []).append((campo == "allow", valor))
        # grupo específico do nosso robô, senão o grupo "*"
        for nome, regras in grupos.items():
            if nome != "*" and nome in agente:
                self.regras = regras
                return
        self.regras = grupos.get("*", [])

    @staticmethod
    def _bate(padrao: str, caminho: str) -> bool:
        regex = re.escape(padrao).replace(r"\*", ".*")
        if regex.endswith(r"\$"):
            regex = regex[:-2] + "$"
        return re.match(regex, caminho) is not None

    def permite(self, url: str) -> bool:
        partes = urlsplit(url)
        caminho = (partes.path or "/") + (f"?{partes.query}" if partes.query else "")
        melhor: tuple[int, bool] | None = None
        for permitido, padrao in self.regras:
            # robots.txt diferencia maiúsculas de minúsculas: /Noticia != /noticia
            if self._bate(padrao, caminho):
                chave = (len(padrao), permitido)
                if melhor is None or chave > melhor:
                    melhor = chave
        return True if melhor is None else melhor[1]
