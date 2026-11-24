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
}

_REGEX = {
    editoria: re.compile(r"\b(" + "|".join(re.escape(p) for p in palavras) + r")\b")
    for editoria, palavras in PALAVRAS.items()
}


# Palavras que só indicam o órgão (ex.: "promovida pela Guarda Civil"), não um crime.
# No resumo elas não bastam para classificar como policial.
POLICIAL_FRACAS = {"policia", "policial", "pm", "gcm", "guarda civil", "delegacia", "investigacao"}


def classificar_editoria(titulo: str, resumo: str = "") -> str:
    # o título pesa mais: se ele já define a editoria, o resumo não é consultado
    for editoria, regex in _REGEX.items():
        if regex.search(normalizar(titulo)):
            return editoria
    texto = normalizar(f"{titulo} {resumo}")
    for editoria, regex in _REGEX.items():
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
