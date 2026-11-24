"""Classificação das notícias por editoria e por cidade, usando palavras-chave."""
from __future__ import annotations

import re

from .util import normalizar

# ordem de exibição no site
EDITORIAS = {
    "politica": "Política",
    "policial": "Segurança",
    "empregos": "Empregos",
    "cursos": "Cursos gratuitos",
    "eventos": "Eventos",
    "geral": "Geral",
}

# A ordem importa: a primeira editoria que bater é a escolhida.
PALAVRAS = {
    "empregos": [
        "vaga", "vagas", "emprego", "empregos", "pat", "casa do trabalhador", "contratacao",
        "contrata", "processo seletivo", "mutirao de emprego", "jovem aprendiz", "estagio",
        "estagiarios", "recrutamento", "oportunidades de trabalho", "emprega sp",
    ],
    "cursos": [
        "curso", "cursos", "capacitacao", "qualificacao", "qualifica sp", "oficina gratuita",
        "oficinas gratuitas", "senai", "senac", "etec", "fatec", "ifsp", "via rapida",
        "bolsa de estudo", "bolsas de estudo", "trampolim", "aulas gratuitas",
    ],
    "policial": [
        "policia", "policial", "pm", "gcm", "guarda civil", "preso", "presos", "presa", "prisao",
        "crime", "roubo", "furto", "homicidio", "assalto", "assaltante", "trafico", "apreensao",
        "apreendido", "apreendida", "suspeito", "suspeita de", "ocorrencia", "delegacia",
        "baleado", "baleada", "tiroteio", "sequestro", "golpe", "golpista", "investigacao",
        "boletim de ocorrencia", "flagrante", "mandado de prisao",
    ],
    "politica": [
        "prefeito", "prefeita", "vice-prefeito", "vereador", "vereadora", "vereadores",
        "camara municipal", "camara de", "eleicao", "eleicoes", "projeto de lei",
        "sessao ordinaria", "orcamento", "loa", "ldo", "ppa", "decreto", "licitacao",
        "tce", "tribunal de contas", "mandato", "cassacao", "audiencia publica",
        "deputado", "deputada", "governador", "secretario municipal", "secretaria municipal",
    ],
    # cultura e entretenimento: teatro, música, cinema, festas e artistas na região
    "eventos": [
        "show", "shows", "mostra de teatro", "peca de teatro", "teatro infantil", "espetaculo", "espetaculos", "peca teatral", "musical",
        "cinema", "cine", "filme", "filmes", "festival", "concerto", "orquestra", "coral",
        "cantor", "cantora", "banda", "dupla sertaneja", "artista", "artistas", "ator", "atriz",
        "celebridade", "humorista", "stand-up", "comedia", "exposicao", "mostra cultural",
        "virada cultural", "evento cultural", "eventos culturais", "programacao cultural",
        "natal de luz", "carnaval", "festa junina", "sarau", "danca", "bale", "ingressos",
        "apresentacao musical", "atracao", "atracoes",
    ],
}

_REGEX = {
    editoria: re.compile(r"\b(" + "|".join(re.escape(p) for p in palavras) + r")\b")
    for editoria, palavras in PALAVRAS.items()
}


# Palavras que só indicam o órgão (ex.: "promovida pela Guarda Civil"), não um crime.
# No resumo elas não bastam para classificar como policial.
POLICIAL_FRACAS = {"policia", "policial", "pm", "gcm", "guarda civil", "delegacia", "investigacao"}

# Competições esportivas ("festival de natação", "games") não são eventos culturais: ficam em "geral".
_ESPORTE = re.compile(
    r"\b(natacao|campeonato|competicao|torneio|atleta|atletas|medalha|games|futebol|corrida|"
    r"jogos|olimpiada|maratona|primeiro lugar|copa)\b"
)


def classificar_editoria(titulo: str, resumo: str = "") -> str:
    # o título pesa mais: se ele já define a editoria, o resumo não é consultado
    texto = normalizar(f"{titulo} {resumo}")
    esporte = bool(_ESPORTE.search(texto))
    for editoria, regex in _REGEX.items():
        if editoria == "eventos" and esporte:
            continue
        if regex.search(normalizar(titulo)):
            return editoria
    for editoria, regex in _REGEX.items():
        if editoria == "eventos" and esporte:
            continue
        achados = set(regex.findall(texto))
        if editoria == "policial":
            achados -= POLICIAL_FRACAS
        if achados:
            return editoria
    return "geral"


def detectar_cidades(texto: str, cidades: dict[str, list[str]]) -> list[str]:
    alvo = normalizar(texto)
    achadas = []
    for cidade, termos in cidades.items():
        if any(re.search(r"\b" + re.escape(normalizar(t)) + r"\b", alvo) for t in termos):
            achadas.append(cidade)
    return achadas


def e_regional(texto: str, cidades: dict[str, list[str]], termos_regiao: list[str]) -> bool:
    if detectar_cidades(texto, cidades):
        return True
    alvo = normalizar(texto)
    return any(normalizar(t) in alvo for t in termos_regiao)
