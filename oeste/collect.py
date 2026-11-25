"""Coletor: lê as fontes configuradas e guarda as notícias novas em data/noticias/AAAA-MM-DD.json.

Uso:  python -m oeste.collect
"""
from __future__ import annotations

import hashlib
import logging
import re
import sys
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from urllib.parse import urljoin, urlsplit, urlunsplit

import feedparser
from bs4 import BeautifulSoup

from .classify import classificar_editoria, detectar_cidades, e_regional
from .fetch import Bloqueado, Navegador
from .util import (
    PASTA_DADOS, agora, config_fontes, config_site, encurtar, fuso, gravar_json, ler_json,
    limpar_html, normalizar,
)

log = logging.getLogger("coletor")

DIAS_PARA_DEDUPLICAR = 4
IDADE_MAXIMA_DIAS = 7  # notícias publicadas há mais tempo são ignoradas
MESES_ABREV = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
               "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}
LIMITE_SIMILARIDADE = 0.88  # títulos 88% iguais = mesma notícia


# ---------------------------------------------------------------- leitura das fontes

def ler_rss(fonte: dict, conteudo: bytes, fuso) -> list[dict]:
    feed = feedparser.parse(conteudo)
    itens = []
    for e in feed.entries:
        titulo = limpar_html(e.get("title", ""))
        link = e.get("link", "")
        if not titulo or not link:
            continue
        resumo = limpar_html(e.get("summary", "") or e.get("description", ""))
        publicado = None
        if e.get("published_parsed") or e.get("updated_parsed"):
            t = e.get("published_parsed") or e.get("updated_parsed")
            publicado = datetime(*t[:6], tzinfo=timezone.utc).astimezone(fuso)
        itens.append({"titulo": titulo, "link": link, "resumo": resumo, "publicado": publicado})
    return itens


def ler_wordpress(fonte: dict, conteudo: bytes, fuso) -> list[dict]:
    """Lê a API de posts de sites WordPress (mais leve que o RSS em alguns sites)."""
    import json

    itens = []
    for p in json.loads(conteudo):
        titulo = limpar_html(p.get("title", {}).get("rendered", ""))
        link = p.get("link", "")
        if not titulo or not link:
            continue
        publicado = None
        if p.get("date"):
            publicado = datetime.fromisoformat(p["date"]).replace(tzinfo=fuso)
        resumo = limpar_html(p.get("excerpt", {}).get("rendered", ""))
        itens.append({"titulo": titulo, "link": link, "resumo": resumo, "publicado": publicado})
    return itens


def _titulo_do_link(a, estrategia: str) -> str:
    if estrategia == "img_alt":
        img = a.find("img", alt=True)
        if img and img["alt"].strip():
            return img["alt"].strip()
    for tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        h = a.find(tag)
        if h and h.get_text(strip=True):
            return h.get_text(" ", strip=True)
    if a.get("title"):
        return a["title"].strip()
    return a.get_text(" ", strip=True)


def _titulo_da_url(url: str) -> str:
    slug = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"^\d{2}-\d{2}-\d{4}-", "", slug)
    return slug.replace("-", " ").strip().capitalize()


def ler_html(fonte: dict, html: str, fuso) -> list[dict]:
    sopa = BeautifulSoup(html, "html.parser")
    padrao = re.compile(fonte["padrao_link"])
    remover = re.compile(fonte["remover_do_titulo"]) if fonte.get("remover_do_titulo") else None
    data_url = re.compile(fonte["data_na_url"]) if fonte.get("data_na_url") else None
    data_texto = re.compile(fonte["data_no_texto"]) if fonte.get("data_no_texto") else None
    hoje = datetime.now(fuso)
    estrategia = fonte.get("titulo_de", "texto")

    por_link: dict[str, dict] = {}
    for a in sopa.find_all("a", href=True):
        href = a["href"].strip()
        caminho = urlsplit(urljoin(fonte["url"], href)).path
        if not padrao.search(caminho):
            continue
        link = urljoin(fonte["url"], href)
        titulo = re.sub(r"\s+", " ", _titulo_do_link(a, estrategia)).strip()
        if remover:
            titulo = remover.sub("", titulo).strip()
        atual = por_link.get(link)
        # o mesmo link costuma aparecer várias vezes (foto + título); fica o título mais completo
        if atual is None or len(titulo) > len(atual["titulo"]):
            publicado = None
            if data_url and (m := data_url.search(caminho)):
                publicado = datetime(int(m["ano"]), int(m["mes"]), int(m["dia"]), 12, tzinfo=fuso)
            elif data_texto and (m := data_texto.search(a.get_text(" ", strip=True).upper())):
                mes = MESES_ABREV.get(m["mes"][:3])
                if mes:
                    ano = int(m["ano"]) if m.groupdict().get("ano") else hoje.year
                    publicado = datetime(ano, mes, int(m["dia"]), 12, tzinfo=fuso)
                    if publicado > hoje + timedelta(days=1):  # "DEZ 30" lido em janeiro
                        publicado = publicado.replace(year=ano - 1)
            por_link[link] = {"titulo": titulo, "link": link, "resumo": "", "publicado": publicado}

    itens = []
    for item in por_link.values():
        if len(item["titulo"]) < 15:  # link de imagem sem texto: usa o endereço como título
            item["titulo"] = _titulo_da_url(item["link"])
        itens.append(item)
    return itens


# ---------------------------------------------------------------- tratamento

def normalizar_link(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), p.netloc.lower().removeprefix("www."), p.path.rstrip("/"), "", ""))


def id_da_noticia(link: str) -> str:
    return hashlib.sha1(normalizar_link(link).encode()).hexdigest()[:12]


def mesma_noticia(t1: str, t2: str) -> bool:
    return SequenceMatcher(None, normalizar(t1), normalizar(t2)).ratio() >= LIMITE_SIMILARIDADE


def enriquecer(item: dict, fonte: dict, site: dict, momento: datetime) -> dict | None:
    texto = f"{item['titulo']} {item['resumo']}"
    editoria = classificar_editoria(item["titulo"], item["resumo"])
    if fonte.get("so_editorias") and editoria not in fonte["so_editorias"]:
        return None  # fonte estadual: só aproveita cursos/vagas
    if fonte.get("exigir_termos"):
        alvo = normalizar(texto)
        if not any(normalizar(t) in alvo for t in fonte["exigir_termos"]):
            return None
    publicado = item.get("publicado")
    if publicado and publicado < momento - timedelta(days=IDADE_MAXIMA_DIAS):
        return None
    titulo_norm = normalizar(item["titulo"])
    if any(re.search(normalizar(p), titulo_norm) for p in site.get("ignorar_titulos", [])):
        return None
    cidades_cfg = site.get("cidades", {})
    if fonte.get("filtrar_regiao") and not fonte.get("so_editorias") and not e_regional(texto, cidades_cfg, site.get("termos_regiao", [])):
        return None
    cidades = detectar_cidades(texto, cidades_cfg)
    if fonte.get("cidade") and fonte["cidade"] not in cidades:
        cidades.insert(0, fonte["cidade"])
    if not cidades and fonte.get("abrangencia"):
        cidades = [fonte["abrangencia"]]
    return {
        "id": id_da_noticia(item["link"]),
        "titulo": item["titulo"],
        "link": item["link"],
        # guardamos só um trecho curto: o site nunca republica o texto completo
        "resumo": encurtar(item["resumo"], 400),
        "fonte": fonte["nome"],
        "fonte_id": fonte["id"],
        "cidades": cidades,
        "editoria": editoria,
        "publicado_em": publicado.isoformat() if publicado else None,
        "coletado_em": momento.isoformat(timespec="seconds"),
    }


def noticias_recentes(hoje: datetime) -> list[dict]:
    todas = []
    for d in range(DIAS_PARA_DEDUPLICAR):
        dia = (hoje - timedelta(days=d)).date().isoformat()
        todas.extend(ler_json(PASTA_DADOS / f"{dia}.json", []))
    return todas


def e_duplicada(nova: dict, existentes: list[dict]) -> bool:
    for n in existentes:
        if n["id"] == nova["id"]:
            return True
        if mesma_noticia(n["titulo"], nova["titulo"]):
            # mesma notícia em outra fonte: registra a fonte extra em vez de duplicar
            extras = n.setdefault("outras_fontes", [])
            if nova["link"] != n["link"] and all(e["link"] != nova["link"] for e in extras):
                extras.append({"fonte": nova["fonte"], "link": nova["link"]})
            return True
    return False


# ---------------------------------------------------------------- principal

def coletar(navegador: Navegador | None = None, momento: datetime | None = None) -> dict:
    site = config_site()
    fz = fuso(site)
    momento = momento or agora(site)
    navegador = navegador or Navegador()

    arquivo_hoje = PASTA_DADOS / f"{momento.date().isoformat()}.json"
    de_hoje = ler_json(arquivo_hoje, [])
    existentes = noticias_recentes(momento)
    # os itens de hoje precisam ser os mesmos objetos (para registrar "outras_fontes")
    ids_hoje = {n["id"] for n in de_hoje}
    existentes = de_hoje + [n for n in existentes if n["id"] not in ids_hoje]

    relatorio = {"novas": 0, "fontes": {}}
    for fonte in config_fontes():
        if not fonte.get("ativo", True):
            continue
        log.info("Lendo %s...", fonte["nome"])
        try:
            resposta = navegador.baixar(fonte["url"])
            if fonte["tipo"] == "rss":
                itens = ler_rss(fonte, resposta.content, fz)
            elif fonte["tipo"] == "wordpress":
                itens = ler_wordpress(fonte, resposta.content, fz)
            else:
                itens = ler_html(fonte, resposta.text, fz)
        except Bloqueado:
            relatorio["fontes"][fonte["id"]] = "bloqueada pelo robots.txt"
            log.warning("%s: bloqueada pelo robots.txt", fonte["nome"])
            continue
        except Exception as e:  # uma fonte com problema não derruba as outras
            relatorio["fontes"][fonte["id"]] = f"erro: {e}"
            log.warning("%s: erro %s", fonte["nome"], e)
            continue

        novas = 0
        for item in itens:
            noticia = enriquecer(item, fonte, site, momento)
            if noticia is None or e_duplicada(noticia, existentes):
                continue
            de_hoje.append(noticia)
            existentes.append(noticia)
            novas += 1
        relatorio["fontes"][fonte["id"]] = f"{len(itens)} lidas, {novas} novas"
        relatorio["novas"] += novas

    de_hoje.sort(key=lambda n: n["coletado_em"], reverse=True)
    gravar_json(arquivo_hoje, de_hoje)
    return relatorio


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rel = coletar()
    for fonte, status in rel["fontes"].items():
        print(f"  {fonte}: {status}")
    print(f"Total de notícias novas: {rel['novas']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
