"""Gera o site estático em _site/ a partir dos posts aprovados em conteudo/posts/.

Uso:  python -m oeste.build
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import date, datetime
from email.utils import format_datetime
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .classify import EDITORIAS
from .util import PASTA_POSTS, RAIZ, config_fontes, config_site, fuso, normalizar

SAIDA = RAIZ / "_site"
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def ler_post(caminho: Path) -> dict:
    texto = caminho.read_text(encoding="utf-8")
    meta, corpo = {}, texto
    if texto.startswith("---"):
        _, bruto, corpo = texto.split("---", 2)
        meta = yaml.safe_load(bruto) or {}
    data = meta.get("data")
    if isinstance(data, str):
        data = date.fromisoformat(data)
    data = data or date.fromisoformat(caminho.stem)
    html = markdown.markdown(corpo, extensions=["extra", "sane_lists"])
    # links externos abrem em nova aba
    html = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noopener"', html)
    editorias = [ed for ed in EDITORIAS.values() if f"<h2>{ed}</h2>" in html]
    return {
        "slug": caminho.stem,
        "titulo": meta.get("titulo") or f"Resumo de {data.strftime('%d/%m/%Y')}",
        "descricao": meta.get("descricao", ""),
        "data": data,
        "data_curta": f"{data.day} {MESES[data.month - 1]} {data.year}",
        "html": html,
        "editorias": editorias,
    }


def slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalizar(texto)).strip("-")


ITEM = re.compile(
    r"^- \*\*(?P<titulo>.+?)\*\*(?: \((?P<cidades>[^)]*)\))?\s*[—-]\s*(?P<texto>.*?)\s*\*Fonte: (?P<fontes>.+)\*\s*$"
)
LINK_MD = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def extrair_noticias(caminho: Path, post: dict) -> list[dict]:
    """Lê as notícias de um post (uma por linha '- **Título** (Cidade) — texto *Fonte: ...*')."""
    noticias, editoria = [], "Geral"
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if linha.startswith("## "):
            editoria = linha[3:].strip()
            continue
        m = ITEM.match(linha.strip())
        if not m:
            continue
        noticias.append({
            "titulo": m["titulo"].strip(),
            "cidades": [c.strip() for c in (m["cidades"] or "").split(",") if c.strip()],
            "texto": m["texto"].strip(),
            "fontes": [{"nome": n, "url": u} for n, u in LINK_MD.findall(m["fontes"])],
            "editoria": editoria,
            "data": post["data"],
            "data_curta": post["data_curta"],
            "post": post["slug"],
            "post_titulo": post["titulo"],
        })
    return noticias


def agrupar_por_dia(noticias: list[dict]) -> list[dict]:
    dias: dict = {}
    for n in noticias:
        dias.setdefault(n["post"], {"data_curta": n["data_curta"], "post": n["post"], "data": n["data"], "itens": []})
        dias[n["post"]]["itens"].append(n)
    return sorted(dias.values(), key=lambda d: d["data"], reverse=True)


def construir() -> int:
    site = config_site()
    env = Environment(
        loader=FileSystemLoader(RAIZ / "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    arquivos = sorted(PASTA_POSTS.glob("*.md")) if PASTA_POSTS.exists() else []
    posts, noticias = [], []
    for arq in arquivos:
        p = ler_post(arq)
        p["noticias"] = extrair_noticias(arq, p)
        posts.append(p)
        noticias.extend(p["noticias"])
    posts.sort(key=lambda p: p["data"], reverse=True)
    noticias.sort(key=lambda n: n["data"], reverse=True)
    for p in posts:
        p["cidades"] = sorted({c for n in p["noticias"] for c in n["cidades"]})
    fontes = [f for f in config_fontes() if f.get("ativo", True)]

    editorias = [{"nome": e, "slug": slug(e)} for e in EDITORIAS.values()]
    cidades = [{"nome": c, "slug": slug(c)} for c in site.get("cidades", {})]
    for e in editorias:
        e["total"] = sum(n["editoria"] == e["nome"] for n in noticias)
    for c in cidades:
        c["total"] = sum(c["nome"] in n["cidades"] for n in noticias)

    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    for pasta in ("posts", "editoria", "cidade"):
        (SAIDA / pasta).mkdir(parents=True)
    shutil.copytree(RAIZ / "static", SAIDA / "static")

    comum = {"site": site, "ano": datetime.now(fuso(site)).year, "editorias": editorias, "cidades": cidades,
             "slug": slug}

    def gravar(destino: str, modelo: str, raiz: str = "", **extra) -> None:
        (SAIDA / destino).write_text(env.get_template(modelo).render(**comum, raiz=raiz, **extra), encoding="utf-8")

    gravar("index.html", "index.html", posts=posts, ultimas=noticias[:6])
    for p in posts:
        gravar(f"posts/{p['slug']}.html", "post.html", "../", post=p)
    gravar("sobre.html", "sobre.html", fontes=fontes)
    gravar("anuncie.html", "anuncie.html")
    gravar("busca.html", "busca.html")

    meses: dict = {}
    for p in posts:
        meses.setdefault((p["data"].year, p["data"].month), []).append(p)
    nomes_meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                   "setembro", "outubro", "novembro", "dezembro"]
    arquivo = [{"nome": f"{nomes_meses[m - 1].capitalize()} de {a}", "posts": ps} for (a, m), ps in meses.items()]
    gravar("arquivo.html", "arquivo.html", meses=arquivo)

    for e in editorias:
        gravar(f"editoria/{e['slug']}.html", "lista.html", "../", tipo="Editoria", nome=e["nome"], atual=e["slug"],
               dias=agrupar_por_dia([n for n in noticias if n["editoria"] == e["nome"]]))
    for c in cidades:
        gravar(f"cidade/{c['slug']}.html", "lista.html", "../", tipo="Cidade", nome=c["nome"], atual=c["slug"],
               dias=agrupar_por_dia([n for n in noticias if c["nome"] in n["cidades"]]))

    # índice para a busca (feita no navegador, sem servidor)
    indice = [{"t": n["titulo"], "x": n["texto"], "c": n["cidades"], "e": n["editoria"], "d": n["data_curta"],
               "p": n["post"], "f": n["fontes"][0]["nome"] if n["fontes"] else ""} for n in noticias]
    (SAIDA / "busca.json").write_text(json.dumps(indice, ensure_ascii=False), encoding="utf-8")

    # Feed RSS do próprio site: serve para ferramentas de newsletter (Beehiiv, Substack,
    # Mailchimp) que enviam e-mail automaticamente a cada post novo.
    for p in posts:
        p["data_rss"] = format_datetime(datetime.combine(p["data"], datetime.min.time(), fuso(site)).replace(hour=7))
    (SAIDA / "feed.xml").write_text(
        env.get_template("feed.xml").render(**comum, posts=posts[:20]), encoding="utf-8")
    (SAIDA / ".nojekyll").write_text("")
    print(f"Site gerado em {SAIDA} com {len(posts)} post(s).")
    return 0


if __name__ == "__main__":
    sys.exit(construir())
