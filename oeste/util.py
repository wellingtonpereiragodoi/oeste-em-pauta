"""Funções auxiliares: configuração, datas, texto."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "data" / "noticias"
PASTA_POSTS = RAIZ / "conteudo" / "posts"
PASTA_RASCUNHOS = RAIZ / "rascunhos"


def carregar_yaml(caminho: Path) -> dict:
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def config_site() -> dict:
    return carregar_yaml(RAIZ / "config" / "site.yaml")


def config_fontes() -> list[dict]:
    return carregar_yaml(RAIZ / "config" / "sources.yaml").get("fontes", [])


def fuso(cfg: dict | None = None) -> ZoneInfo:
    return ZoneInfo((cfg or config_site()).get("fuso", "America/Sao_Paulo"))


def agora(cfg: dict | None = None) -> datetime:
    return datetime.now(fuso(cfg))


def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos e com espaços simples - para comparar textos."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto.lower()).strip()


def limpar_html(texto: str) -> str:
    """Remove tags HTML e espaços extras de um trecho de texto."""
    from bs4 import BeautifulSoup

    if not texto:
        return ""
    limpo = BeautifulSoup(texto, "html.parser").get_text(" ")
    limpo = re.sub(r"\s+", " ", limpo).strip()
    # rodapé padrão do WordPress
    limpo = re.sub(r"\s*O post .+ apareceu primeiro em .+$", "", limpo)
    limpo = re.sub(r"\s*\[(…|\.\.\.)\]\s*$", "…", limpo)
    return limpo


def encurtar(texto: str, limite: int = 280) -> str:
    texto = (texto or "").strip()
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(" ", 1)[0]
    return corte.rstrip(",.;:") + "…"


def ler_json(caminho: Path, padrao):
    if not caminho.exists():
        return padrao
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def gravar_json(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
        f.write("\n")
