"""Testes com dados de exemplo (não acessam a internet)."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from oeste import build, collect, draft, util
from oeste.classify import classificar_editoria, detectar_cidades, e_regional
from oeste.robots import Robots

FUSO = ZoneInfo("America/Sao_Paulo")
SITE = util.config_site()

ROBOTS_BARUERI = """User-agent: *
Disallow: /
Allow: /cidadao
Allow: /noticia
Allow: /Noticia
"""

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Jornal</title>
<item><title>Barueri abre 300 vagas de emprego na Casa do Trabalhador</title>
<link>https://jornal.exemplo/barueri-vagas</link>
<description>&lt;p&gt;A prefeitura de Barueri anunciou...&lt;/p&gt; O post X apareceu primeiro em Jornal.</description>
<pubDate>Mon, 23 Nov 2026 12:00:00 +0000</pubDate></item>
<item><title>Lenovo recebe pr\xc3\xaamio internacional de tecnologia</title>
<link>https://jornal.exemplo/lenovo</link><description>Empresa chinesa...</description></item>
<item><title>PM prende suspeito de roubo em Alphaville</title>
<link>https://jornal.exemplo/pm-alphaville</link><description>Ocorr\xc3\xaancia...</description></item>
</channel></rss>"""

HTML_BARUERI = """<html><body>
<div class="card"><a href="/Noticia/23-11-2026-semurb-promove-acoes"><img src="x.jpg"></a></div>
<div class="card"><a href="/Noticia/23-11-2026-semurb-promove-acoes">23.11 Semurb promove ações de educação para o trânsito</a></div>
<div class="card"><a href="/Noticia/21-11-2026-barueri-disponibiliza-53-vagas">21.11.2026 Barueri disponibiliza 53 vagas de emprego a partir de terça</a></div>
<a href="/Noticia/VerTodas">Ver todas</a>
</body></html>"""

HTML_CARAPICUIBA = """<html><body>
<a href="/portal/noticias/0/3/11356/prefeitura-promove-processo-seletivo/"><div>
<img src="/fotos/a.jpg" alt="Prefeitura promove processo seletivo móvel com 300 vagas_foto1">
<div>Há 9 horas NOV 23 DESENV. ECONÔMICO</div></div></a>
</body></html>"""

HTML_SANTANA = """<html><body>
<a href="/Plataforma/noticia/detalhe-noticia/natal-de-luz-inicia-em-27-de-novembro"><img src="a.jpg"></a>
<a href="/Plataforma/noticia/detalhe-noticia/santana-de-parnaiba-celebra-446-anos">Santana de Parnaíba celebra 446 anos com grande show</a>
</body></html>"""


# ---------------------------------------------------------------- robots

def test_robots_barueri_libera_noticias_e_bloqueia_resto():
    r = Robots(ROBOTS_BARUERI)
    assert r.permite("https://portal.barueri.sp.gov.br/Noticia/VerTodas")
    assert not r.permite("https://portal.barueri.sp.gov.br/")
    assert not r.permite("https://portal.barueri.sp.gov.br/admin")


def test_robots_vazio_libera_tudo():
    assert Robots(None).permite("https://x.com/qualquer")
    assert Robots("User-agent: *\nDisallow:").permite("https://x.com/a")


def test_robots_grupo_especifico():
    texto = "User-agent: *\nDisallow: /\n\nUser-agent: OesteEmPautaBot\nAllow: /"
    assert Robots(texto, "OesteEmPautaBot/1.0").permite("https://x.com/a")


# ---------------------------------------------------------------- classificação

@pytest.mark.parametrize("titulo,esperado", [
    ("Barueri disponibiliza 53 vagas de emprego", "empregos"),
    ("Senai abre inscrições para cursos gratuitos em Jandira", "cursos"),
    ("PM prende suspeito de roubo em Osasco", "policial"),
    ("Câmara Municipal aprova orçamento de 2027", "politica"),
    ("Natal de Luz começa dia 27 com show", "geral"),
])
def test_editorias(titulo, esperado):
    assert classificar_editoria(titulo) == esperado


def test_cidades_e_filtro_regional():
    cidades = SITE["cidades"]
    assert detectar_cidades("Obra em Alphaville e na Granja Viana", cidades) == ["Barueri", "Cotia"]
    assert e_regional("Trânsito na Castello Branco", cidades, SITE["termos_regiao"])
    assert not e_regional("Lenovo recebe prêmio internacional", cidades, SITE["termos_regiao"])
    # "Parnaíba" sozinho (cidade do Piauí) não deve contar
    assert not detectar_cidades("Enchente em Parnaíba (PI)", cidades)


# ---------------------------------------------------------------- leitura das fontes

FONTES = {f["id"]: f for f in util.config_fontes()}


def test_ler_html_barueri():
    itens = collect.ler_html(FONTES["pref-barueri"], HTML_BARUERI, FUSO)
    titulos = {i["titulo"] for i in itens}
    assert titulos == {"Semurb promove ações de educação para o trânsito",
                       "Barueri disponibiliza 53 vagas de emprego a partir de terça"}
    vagas = next(i for i in itens if "vagas" in i["titulo"])
    assert vagas["publicado"].date().isoformat() == "2026-11-21"


def test_ler_html_carapicuiba_usa_alt_da_imagem():
    itens = collect.ler_html(FONTES["pref-carapicuiba"], HTML_CARAPICUIBA, FUSO)
    assert itens[0]["titulo"] == "Prefeitura promove processo seletivo móvel com 300 vagas"


def test_ler_html_santana_link_sem_texto_usa_endereco():
    itens = collect.ler_html(FONTES["pref-santana-de-parnaiba"], HTML_SANTANA, FUSO)
    titulos = sorted(i["titulo"] for i in itens)
    assert titulos == ["Natal de luz inicia em 27 de novembro",
                       "Santana de Parnaíba celebra 446 anos com grande show"]


def test_ler_rss_limpa_rodape_wordpress():
    itens = collect.ler_rss(FONTES["jornal-barueri"], RSS, FUSO)
    assert itens[0]["resumo"] == "A prefeitura de Barueri anunciou..."
    assert itens[0]["publicado"].hour == 9  # 12h UTC = 9h em Brasília


# ---------------------------------------------------------------- coleta completa

class RespostaFalsa:
    def __init__(self, conteudo):
        self.content = conteudo if isinstance(conteudo, bytes) else conteudo.encode()
        self.text = self.content.decode()


class NavegadorFalso:
    def __init__(self, paginas):
        self.paginas = paginas

    def baixar(self, url):
        if url not in self.paginas:
            raise RuntimeError("fora do ar")
        return RespostaFalsa(self.paginas[url])


@pytest.fixture
def pasta_temporaria(tmp_path, monkeypatch):
    for modulo in (util, collect, draft, build):
        if hasattr(modulo, "PASTA_DADOS"):
            monkeypatch.setattr(modulo, "PASTA_DADOS", tmp_path / "data")
        if hasattr(modulo, "PASTA_POSTS"):
            monkeypatch.setattr(modulo, "PASTA_POSTS", tmp_path / "posts")
        if hasattr(modulo, "PASTA_RASCUNHOS"):
            monkeypatch.setattr(modulo, "PASTA_RASCUNHOS", tmp_path / "rascunhos")
    monkeypatch.setattr(build, "SAIDA", tmp_path / "_site")
    monkeypatch.setattr(draft, "ARQ_OFERECIDAS", tmp_path / "oferecidas.json")
    return tmp_path


def _paginas():
    return {
        FONTES["jornal-barueri"]["url"]: RSS,
        FONTES["pref-barueri"]["url"]: HTML_BARUERI,
        FONTES["pref-carapicuiba"]["url"]: HTML_CARAPICUIBA,
        FONTES["pref-santana-de-parnaiba"]["url"]: HTML_SANTANA,
        # a Folha de Alphaville repete a notícia de vagas com título quase igual
        FONTES["folha-alphaville"]["url"]: RSS.replace(
            b"https://jornal.exemplo/barueri-vagas", b"https://folha.exemplo/vagas"
        ).replace(b"300 vagas de emprego na Casa", b"300 vagas de emprego na casa"),
    }


def test_coleta_completa(pasta_temporaria):
    momento = datetime(2026, 11, 23, 15, 0, tzinfo=FUSO)
    rel = collect.coletar(NavegadorFalso(_paginas()), momento)
    noticias = util.ler_json(pasta_temporaria / "data" / "2026-11-23.json", [])
    titulos = [n["titulo"] for n in noticias]

    assert not any("Lenovo" in t for t in titulos), "notícia sem relação com a região deveria ser filtrada"
    assert sum("300 vagas de emprego" in t for t in titulos) == 1, "duplicata entre fontes deveria ser unida"
    vagas = next(n for n in noticias if "300 vagas de emprego" in n["titulo"])
    assert {vagas["fonte"], vagas["outras_fontes"][0]["fonte"]} == {"Folha de Alphaville", "Jornal de Barueri"}
    assert vagas["editoria"] == "empregos" and vagas["cidades"] == ["Barueri"]
    assert "erro" in rel["fontes"]["pref-osasco"]  # fonte fora do ar não derruba a coleta

    # segunda rodada: nada novo
    rel2 = collect.coletar(NavegadorFalso(_paginas()), momento)
    assert rel2["novas"] == 0


def test_rascunho_e_site(pasta_temporaria, monkeypatch):
    momento = datetime(2026, 11, 23, 15, 0, tzinfo=FUSO)
    collect.coletar(NavegadorFalso(_paginas()), momento)
    noticias = draft.selecionar(datetime(2026, 11, 24, 6, 12, tzinfo=FUSO))
    ids = {n["titulo"]: n["id"] for n in noticias}
    id_vagas = next(v for k, v in ids.items() if "300 vagas de emprego" in k)
    id_pm = next(v for k, v in ids.items() if "PM prende" in k)

    resposta_ia = {
        "titulo": "Barueri tem 300 vagas e mais destaques da região",
        "descricao": "Vagas de emprego, segurança e agenda cultural na Região Oeste.",
        "abertura": "Bom dia! Veja o que aconteceu na região.",
        "secoes": [
            {"editoria": "empregos", "itens": [{"id": id_vagas, "titulo": "300 vagas em Barueri", "texto": "A Casa do Trabalhador abriu 300 vagas."}]},
            {"editoria": "policial", "itens": [{"id": id_pm, "titulo": "Suspeito detido em Alphaville", "texto": "A PM deteve um suspeito de roubo."}]},
            {"editoria": "geral", "itens": [{"id": "inventado", "titulo": "X", "texto": "Y"}]},
        ],
        "newsletter_assunto": "Região Oeste hoje",
        "newsletter_abertura": "Olá!",
        "tiktok_roteiro": "Gancho...",
        "instagram_slides": ["Capa", "Vagas"],
        "instagram_legenda": "Fonte: Jornal de Barueri #barueri",
        "alertas": ["Conferir o número de vagas"],
    }
    monkeypatch.setattr(draft, "gerar_json", lambda prompt, modelo: resposta_ia)
    r = draft.gerar(datetime(2026, 11, 24, 6, 12, tzinfo=FUSO))
    assert r["com_ia"]

    post = (pasta_temporaria / "posts" / "2026-11-24.md").read_text()
    # política vem antes, depois segurança, depois empregos (ordem fixa, não a da IA)
    assert post.index("## Segurança") < post.index("## Empregos")
    assert "https://jornal.exemplo/barueri-vagas" in post and "https://folha.exemplo/vagas" in post
    assert "inventado" not in post
    revisao = (pasta_temporaria / "rascunhos" / "2026-11-24" / "revisao.md").read_text()
    assert "notícia inexistente" in revisao and "PM prende suspeito" in revisao

    build.construir()
    pagina = (pasta_temporaria / "_site" / "posts" / "2026-11-24.html").read_text()
    assert "300 vagas em Barueri" in pagina and 'target="_blank"' in pagina
    assert (pasta_temporaria / "_site" / "feed.xml").exists()


def test_rascunho_sem_ia(pasta_temporaria):
    collect.coletar(NavegadorFalso(_paginas()), datetime(2026, 11, 23, 15, 0, tzinfo=FUSO))
    r = draft.gerar(datetime(2026, 11, 24, 6, 12, tzinfo=FUSO), usar_ia=False)
    assert not r["com_ia"]
    assert "[ESCREVER]" in (pasta_temporaria / "posts" / "2026-11-24.md").read_text()


def test_ler_wordpress():
    dados = b'[{"date":"2026-11-23T18:50:26","link":"https://cotia.sp.gov.br/pat-de-cotia/","title":{"rendered":"PAT de Cotia oferece mais de 150 vagas"},"excerpt":{"rendered":"<p>Cotia est\\u00e1 com vagas [&hellip;]</p>"}}]'
    itens = collect.ler_wordpress(FONTES["pref-cotia"], dados, FUSO)
    assert itens[0]["titulo"] == "PAT de Cotia oferece mais de 150 vagas"
    assert itens[0]["publicado"].hour == 18
    assert classificar_editoria(itens[0]["titulo"]) == "empregos"


def test_ignora_noticia_antiga_e_edital(pasta_temporaria):
    momento = datetime(2026, 11, 23, 15, 0, tzinfo=FUSO)
    antiga = {"titulo": "Barueri abre vagas", "link": "https://x/a", "resumo": "",
              "publicado": datetime(2026, 11, 1, 12, tzinfo=FUSO)}
    edital = {"titulo": "Edital de Convocação - Assembleia Geral", "link": "https://x/b", "resumo": "",
              "publicado": None}
    fonte = FONTES["pref-barueri"]
    assert collect.enriquecer(antiga, fonte, SITE, momento) is None
    assert collect.enriquecer(edital, fonte, SITE, momento) is None


def test_data_no_texto_carapicuiba():
    html = ('<a href="/portal/noticias/0/3/1/a/"><img alt="Noticia antiga de Carapicuiba_foto1">'
            '<div>09 NOV 2026 - 14h37 NOV 09</div></a>')
    itens = collect.ler_html(FONTES["pref-carapicuiba"], html, FUSO)
    assert itens[0]["publicado"].day == 9


def test_nao_repete_noticia_ja_publicada(pasta_temporaria):
    collect.coletar(NavegadorFalso(_paginas()), datetime(2026, 11, 23, 15, 0, tzinfo=FUSO))
    (pasta_temporaria / "posts").mkdir(parents=True, exist_ok=True)
    (pasta_temporaria / "posts" / "2026-11-23.md").write_text(
        "- **x** *Fonte: [J](https://jornal.exemplo/barueri-vagas)*", encoding="utf-8")
    titulos = [n["titulo"] for n in draft.selecionar(datetime(2026, 11, 24, 6, 12, tzinfo=FUSO))]
    assert not any("300 vagas de emprego" in t for t in titulos)
    assert any("PM prende" in t for t in titulos)


def test_policial_nao_por_orgao_no_resumo():
    assert classificar_editoria("Corrida Pela Vida reúne famílias em Cotia",
                                "Promovida pela Guarda Civil Municipal") == "geral"
    assert classificar_editoria("Ação em Osasco", "Suspeito foi preso pela GCM") == "policial"


def test_nao_repete_noticia_ja_oferecida(pasta_temporaria, monkeypatch):
    collect.coletar(NavegadorFalso(_paginas()), datetime(2026, 11, 23, 15, 0, tzinfo=FUSO))
    draft.gerar(datetime(2026, 11, 23, 20, 0, tzinfo=FUSO), usar_ia=False)
    assert draft.selecionar(datetime(2026, 11, 24, 6, 12, tzinfo=FUSO)) == []
