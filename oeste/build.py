"""Gera o site estático em _site/ a partir dos posts aprovados em conteudo/posts/.

Uso:  python -m oeste.build
"""
from __future__ import annotations

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
from .util import PASTA_POSTS, RAIZ, config_fontes, config_site, fuso

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


def construir() -> int:
    site = config_site()
    env = Environment(
        loader=FileSystemLoader(RAIZ / "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    posts = sorted(
        (ler_post(p) for p in PASTA_POSTS.glob("*.md")) if PASTA_POSTS.exists() else [],
        key=lambda p: p["data"], reverse=True,
    )
    fontes = [f for f in config_fontes() if f.get("ativo", True)]

    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    (SAIDA / "posts").mkdir(parents=True)
    shutil.copytree(RAIZ / "static", SAIDA / "static")

    comum = {"site": site, "ano": datetime.now(fuso(site)).year}
    (SAIDA / "index.html").write_text(
        env.get_template("index.html").render(**comum, raiz="", posts=posts), encoding="utf-8")
    for p in posts:
        (SAIDA / "posts" / f"{p['slug']}.html").write_text(
            env.get_template("post.html").render(**comum, raiz="../", post=p), encoding="utf-8")
    (SAIDA / "sobre.html").write_text(
        env.get_template("sobre.html").render(**comum, raiz="", fontes=fontes), encoding="utf-8")

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
