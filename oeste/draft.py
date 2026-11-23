"""Gera os rascunhos do dia: post do site, newsletter, roteiro de TikTok e carrossel de Instagram.

Uso:  python -m oeste.draft            (usa o Gemini se houver GEMINI_API_KEY)
      python -m oeste.draft --sem-ia   (só organiza as manchetes, sem IA)

Nada aqui é publicado direto: os arquivos vão para um Pull Request no GitHub
e só entram no site depois que o editor aprova (Merge).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta

from .classify import EDITORIAS
from .gemini import ErroGemini, gerar_json
from .util import (
    PASTA_DADOS, PASTA_POSTS, PASTA_RASCUNHOS, agora, config_site, encurtar, ler_json,
)

log = logging.getLogger("rascunho")

ORDEM_EDITORIAS = ["politica", "policial", "empregos", "cursos", "geral"]
MAX_NOTICIAS = 45
MAX_GERAL = 12           # notícias "gerais" (cultura, esporte, serviços) no máximo por dia
IDADE_MAXIMA_HORAS = 72  # não resumir notícia publicada há mais de 3 dias

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]

REGRAS = """
Você é editor do site "{nome}", que resume as notícias da Região Oeste da Grande São Paulo.
Escreva em português do Brasil, tom jornalístico, claro e neutro, para o morador comum.

REGRAS OBRIGATÓRIAS
1. Escreva SEMPRE com suas próprias palavras. Nunca copie frases das fontes. Cada notícia
   vira 1 ou 2 frases curtas (no máximo 45 palavras).
2. Use SOMENTE as informações fornecidas abaixo. Não invente números, datas, nomes, horários
   ou locais. Se a informação for vaga, seja vago também.
3. Segurança/policial: use "suspeito", "investigado", "preso por suspeita de". Nunca chame
   ninguém de criminoso. NÃO escreva nomes de suspeitos, vítimas ou de qualquer menor de idade.
   Sem detalhes violentos.
4. Política: neutralidade total. Descreva o fato, sem opinião, sem adjetivos de valor e sem
   favorecer partido ou político.
5. Empregos e cursos: destaque quantidade de vagas, prazos e como se inscrever, se informado.
6. Ignore notícias que não sejam de interesse da região ou que sejam só propaganda.
7. Refira-se às notícias pelo campo "id" exatamente como fornecido. NÃO escreva links.
8. Em "alertas", liste o que o editor humano deve conferir antes de publicar (ex.: notícia
   policial sensível, informação que pode estar desatualizada, possível duplicidade).

Responda APENAS com um JSON neste formato:
{{
  "titulo": "título do resumo do dia (até 80 caracteres)",
  "descricao": "uma frase de até 160 caracteres para o Google e redes sociais",
  "abertura": "2 ou 3 frases apresentando os destaques do dia",
  "secoes": [
    {{"editoria": "politica|policial|empregos|cursos|geral",
      "itens": [{{"id": "id da notícia", "titulo": "título reescrito", "texto": "1-2 frases"}}]}}
  ],
  "newsletter_assunto": "assunto do e-mail (até 60 caracteres, sem emoji)",
  "newsletter_abertura": "2 frases de abertura da newsletter, tom próximo",
  "tiktok_roteiro": "roteiro de vídeo de 45 a 60 segundos: gancho inicial, 3 a 5 notícias, chamada final para seguir o perfil",
  "instagram_slides": ["texto curto do slide 1 (capa)", "slide 2", "..."],
  "instagram_legenda": "legenda com as fontes citadas pelo nome e 5 a 8 hashtags regionais",
  "alertas": ["..."]
}}
Use de 5 a 8 slides no Instagram. Coloque as editorias na ordem: politica, policial,
empregos, cursos, geral, e só inclua editorias que tenham notícias.
"""


def data_por_extenso(d: datetime) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def selecionar(momento: datetime) -> list[dict]:
    """Notícias coletadas nas últimas 24 horas."""
    limite = momento - timedelta(hours=24)
    antiga = momento - timedelta(hours=IDADE_MAXIMA_HORAS)
    noticias = []
    for d in (momento, momento - timedelta(days=1)):
        for n in ler_json(PASTA_DADOS / f"{d.date().isoformat()}.json", []):
            if datetime.fromisoformat(n["coletado_em"]) < limite:
                continue
            if n.get("publicado_em") and datetime.fromisoformat(n["publicado_em"]) < antiga:
                continue
            noticias.append(n)
    vistos, unicas = set(), []
    for n in noticias:
        if n["id"] not in vistos:
            vistos.add(n["id"])
            unicas.append(n)
    # mais recentes primeiro dentro de cada editoria; "geral" limitada
    unicas.sort(key=lambda n: n.get("publicado_em") or n["coletado_em"], reverse=True)
    gerais = [n for n in unicas if n["editoria"] == "geral"][:MAX_GERAL]
    principais = [n for n in unicas if n["editoria"] != "geral"]
    selecionadas = principais + gerais
    selecionadas.sort(key=lambda n: ORDEM_EDITORIAS.index(n["editoria"]))
    return selecionadas[:MAX_NOTICIAS]


def montar_prompt(noticias: list[dict], site: dict, momento: datetime) -> str:
    entrada = [
        {
            "id": n["id"],
            "editoria_sugerida": n["editoria"],
            "cidades": n["cidades"],
            "fonte": n["fonte"],
            "titulo_original": n["titulo"],
            "trecho": encurtar(n["resumo"], 300),
        }
        for n in noticias
    ]
    return (
        REGRAS.format(nome=site["nome"])
        + f"\nData de hoje: {data_por_extenso(momento)}.\n\nNOTÍCIAS COLETADAS:\n"
        + json.dumps(entrada, ensure_ascii=False, indent=1)
    )


def rascunho_sem_ia(noticias: list[dict], site: dict, momento: datetime) -> dict:
    secoes = []
    for ed in ORDEM_EDITORIAS:
        itens = [
            {"id": n["id"], "titulo": n["titulo"], "texto": encurtar(n["resumo"], 220)}
            for n in noticias if n["editoria"] == ed
        ]
        if itens:
            secoes.append({"editoria": ed, "itens": itens})
    return {
        "titulo": f"Resumo do dia — {momento.strftime('%d/%m')}",
        "descricao": f"As principais notícias da Região Oeste em {data_por_extenso(momento)}.",
        "abertura": "[ESCREVER] Rascunho gerado sem IA: reescreva os títulos e textos com suas palavras.",
        "secoes": secoes,
        "newsletter_assunto": f"Região Oeste hoje — {momento.strftime('%d/%m')}",
        "newsletter_abertura": "[ESCREVER]",
        "tiktok_roteiro": "[ESCREVER]",
        "instagram_slides": ["[ESCREVER]"],
        "instagram_legenda": "[ESCREVER]",
        "alertas": ["Rascunho gerado SEM IA: os textos abaixo são os originais das fontes e precisam ser reescritos."],
    }


def _secoes_markdown(resp: dict, por_id: dict) -> tuple[str, list[str]]:
    """Monta as seções em Markdown. Os links vêm dos nossos dados, nunca da IA."""
    linhas, problemas = [], []
    usados = set()
    for secao in sorted(resp.get("secoes", []),
                        key=lambda s: ORDEM_EDITORIAS.index(s.get("editoria", "geral"))
                        if s.get("editoria") in ORDEM_EDITORIAS else 99):
        itens_ok = []
        for item in secao.get("itens", []):
            n = por_id.get(item.get("id"))
            if n is None:
                problemas.append(f"A IA citou uma notícia inexistente (id {item.get('id')}); item descartado.")
                continue
            if n["id"] in usados:
                continue
            usados.add(n["id"])
            fontes = [f"[{n['fonte']}]({n['link']})"] + [
                f"[{o['fonte']}]({o['link']})" for o in n.get("outras_fontes", [])
            ]
            cidades = f" ({', '.join(n['cidades'])})" if n["cidades"] else ""
            itens_ok.append(
                f"- **{item.get('titulo', n['titulo']).strip()}**{cidades} — {item.get('texto', '').strip()} "
                f"*Fonte: {' · '.join(fontes)}*"
            )
        if itens_ok:
            nome = EDITORIAS.get(secao.get("editoria"), "Geral")
            linhas.append(f"## {nome}\n\n" + "\n".join(itens_ok))
    return "\n\n".join(linhas), problemas


def _aspas(texto: str) -> str:
    return json.dumps(texto, ensure_ascii=False)  # string YAML válida


def escrever_arquivos(resp: dict, noticias: list[dict], site: dict, momento: datetime, com_ia: bool) -> dict:
    dia = momento.date().isoformat()
    por_id = {n["id"]: n for n in noticias}
    corpo, problemas = _secoes_markdown(resp, por_id)
    alertas = list(resp.get("alertas", [])) + problemas

    post = (
        "---\n"
        f"titulo: {_aspas(resp.get('titulo') or 'Resumo do dia')}\n"
        f"data: {dia}\n"
        f"descricao: {_aspas(resp.get('descricao', ''))}\n"
        f"gerado_por: {'gemini' if com_ia else 'sem-ia'}\n"
        "---\n\n"
        f"{resp.get('abertura', '').strip()}\n\n{corpo}\n"
    )
    PASTA_POSTS.mkdir(parents=True, exist_ok=True)
    (PASTA_POSTS / f"{dia}.md").write_text(post, encoding="utf-8")

    pasta = PASTA_RASCUNHOS / dia
    pasta.mkdir(parents=True, exist_ok=True)
    url_post = f"{site['url'].rstrip('/')}/posts/{dia}.html"
    (pasta / "newsletter.md").write_text(
        f"**Assunto:** {resp.get('newsletter_assunto', '')}\n\n"
        f"{resp.get('newsletter_abertura', '').strip()}\n\n{corpo}\n\n"
        f"---\nLeia no site: {url_post}\n",
        encoding="utf-8",
    )
    (pasta / "tiktok.md").write_text(
        f"# Roteiro TikTok/Reels — {momento.strftime('%d/%m/%Y')}\n\n{resp.get('tiktok_roteiro', '').strip()}\n\n"
        "> Lembrete: cite as fontes na legenda e não use imagens das matérias originais.\n",
        encoding="utf-8",
    )
    slides = "\n".join(f"{i}. {s}" for i, s in enumerate(resp.get("instagram_slides", []), 1))
    (pasta / "instagram.md").write_text(
        f"# Carrossel Instagram — {momento.strftime('%d/%m/%Y')}\n\n## Slides\n\n{slides}\n\n"
        f"## Legenda\n\n{resp.get('instagram_legenda', '').strip()}\n",
        encoding="utf-8",
    )
    policiais = [n for n in noticias if n["editoria"] == "policial"]
    revisao = ["## O que conferir antes de aprovar", ""]
    revisao += [f"- [ ] {a}" for a in alertas] or ["- [ ] Nenhum alerta automático."]
    if policiais:
        revisao += ["", "### Notícias policiais incluídas (revisar com atenção)", ""]
        revisao += [f"- [ ] {n['titulo']} — {n['fonte']}: {n['link']}" for n in policiais]
    revisao += [
        "", "### Checklist geral", "",
        "- [ ] Nenhum nome de suspeito, vítima ou menor de idade",
        "- [ ] Textos com palavras próprias (nada copiado das fontes)",
        "- [ ] Números de vagas, datas e prazos conferem com a fonte",
        "- [ ] Política descrita de forma neutra",
    ]
    (pasta / "revisao.md").write_text("\n".join(revisao) + "\n", encoding="utf-8")
    return {"post": str(PASTA_POSTS / f"{dia}.md"), "pasta": str(pasta), "alertas": alertas}


def gerar(momento: datetime | None = None, usar_ia: bool = True) -> dict:
    site = config_site()
    momento = momento or agora(site)
    noticias = selecionar(momento)
    if not noticias:
        log.warning("Nenhuma notícia nas últimas 24 horas; nada a fazer.")
        return {"post": None, "noticias": 0}

    resp, com_ia = None, False
    if usar_ia:
        try:
            resp = gerar_json(montar_prompt(noticias, site, momento), site.get("gemini", {}).get("modelo", "gemini-3.5-flash"))
            com_ia = True
        except ErroGemini as e:
            log.warning("Gemini indisponível (%s); gerando rascunho sem IA.", e)
    if resp is None:
        resp = rascunho_sem_ia(noticias, site, momento)
    resultado = escrever_arquivos(resp, noticias, site, momento, com_ia)
    resultado["noticias"] = len(noticias)
    resultado["com_ia"] = com_ia
    return resultado


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--sem-ia", action="store_true")
    args = p.parse_args()
    r = gerar(usar_ia=not args.sem_ia)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
