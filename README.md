# Oeste em Pauta

Site que resume todo dia as notícias da Região Oeste da Grande SP: **política, segurança,
empregos e cursos gratuitos** de Santana de Parnaíba, Barueri, Osasco, Carapicuíba, Itapevi,
Jandira, Cotia, Cajamar e Pirapora do Bom Jesus.

## Como funciona

```
 a cada 2 horas            todo dia por volta das 18h                 você aprova            site no ar
┌──────────────┐        ┌────────────────────┐        ┌─────────────────┐     ┌──────────────┐
│  Coletor lê  │  ───►  │ Gemini escreve o   │  ───►  │ Pull Request no │ ──► │ GitHub Pages │
│ RSS e páginas│        │ resumo, newsletter,│        │ GitHub: edite e │     │ publica o    │
│ das fontes   │        │ TikTok e Instagram │        │ clique em Merge │     │ resumo       │
└──────────────┘        └────────────────────┘        └─────────────────┘     └──────────────┘
```

**Nada é publicado sem a sua aprovação.**

| Pasta / arquivo | Para que serve |
|---|---|
| `config/sources.yaml` | Lista de fontes (ligar/desligar, adicionar novas) |
| `config/site.yaml` | Nome do site, e-mail de contato, cidades e bairros, modelo do Gemini |
| `data/noticias/` | Notícias coletadas (um arquivo por dia) — só título, trecho curto e link |
| `conteudo/posts/` | Resumos **aprovados** — é isso que aparece no site |
| `rascunhos/AAAA-MM-DD/` | Newsletter, roteiro de TikTok, carrossel de Instagram e checklist de revisão |
| `oeste/` | Código (coletor, rascunho, gerador do site) |
| `.github/workflows/` | As automações do GitHub |

## Colocando no ar (uma vez só)

1. **Crie o repositório** no GitHub com o nome `oeste-em-pauta` (público — o GitHub Pages
   gratuito exige repositório público) e envie todos os arquivos desta pasta.
2. **Chave do Gemini:** pegue uma chave em <https://aistudio.google.com/apikey>. No repositório,
   vá em *Settings → Secrets and variables → Actions → New repository secret*,
   nome `GEMINI_API_KEY`, cole a chave e salve. **Nunca coloque a chave dentro de um arquivo.**
3. **Permissões das automações:** *Settings → Actions → General → Workflow permissions*:
   marque **Read and write permissions** e **Allow GitHub Actions to create and approve pull requests**. Salve.
4. **Ative o site:** *Settings → Pages → Build and deployment → Source:* **GitHub Actions**.
5. **Edite `config/site.yaml`:** o e-mail de contato do projeto é `oesteempauta@gmail.com`
   (ele aparece no rodapé para pedidos de correção — isso é importante juridicamente).
6. **Primeiro teste:** aba *Actions* → **Coletar notícias** → *Run workflow*. Depois
   **Rascunho do dia** → *Run workflow*. Em alguns minutos aparece um Pull Request na aba *Pull requests*.

## Rotina diária (5 a 10 minutos)

1. Por volta das 18h o GitHub abre um Pull Request "📰 Resumo do dia …" e você recebe um aviso
   (e-mail ou app do GitHub no celular).
2. Leia o checklist na descrição do PR — ele lista as notícias policiais e o que a IA pediu para conferir.
3. Na aba **Files changed**, leia o post (`conteudo/posts/…md`). Para corrigir: abra o arquivo,
   clique no lápis ✏️, edite e clique em *Commit changes*.
4. Tudo certo? Clique em **Merge pull request**. O site atualiza em 1 a 2 minutos.
   Não quer publicar? *Close pull request*.
5. Copie os textos de `rascunhos/…/tiktok.md` e `instagram.md` para as redes.

### Newsletter

O site gera um feed em `/feed.xml`. Ferramentas como **Beehiiv**, **Substack** ou **Mailchimp**
conseguem enviar um e-mail automático a cada resumo novo a partir desse feed ("RSS to email").
O texto em `rascunhos/…/newsletter.md` serve se preferir enviar manualmente.

## Rodando no seu computador (opcional)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (no Ubuntu: source .venv/bin/activate)
pip install -r requirements.txt
python -m oeste.collect         # coleta as notícias
python -m oeste.draft --sem-ia  # rascunho sem IA (ou defina GEMINI_API_KEY e rode sem --sem-ia)
python -m oeste.build           # gera o site em _site/  (abra _site/index.html no navegador)
pip install pytest && python -m pytest   # testes
```

## Cuidados embutidos

- **Respeita o robots.txt** de cada site (com a regra correta para casos como Barueri, que
  bloqueia o site inteiro mas libera a seção de notícias).
- **Guarda só título, trecho curto e link** — o texto completo das fontes nunca é republicado.
- **Os links vêm sempre dos dados coletados, nunca da IA** — se a IA citar uma notícia que não
  existe, o item é descartado e aparece um alerta na revisão.
- **Regras para a IA:** escrever com palavras próprias, não inventar dados, não citar nomes de
  suspeitos, vítimas ou menores, neutralidade em política.
- **Filtro regional:** nos jornais, só entram notícias que citam alguma cidade ou bairro da região.
- **Notícias repetidas** em fontes diferentes viram um item só, com todas as fontes citadas.

## Fontes

| Fonte | Como é lida | Situação |
|---|---|---|
| Folha de Alphaville | RSS | ativa |
| Jornal de Barueri | RSS (com filtro regional) | ativa |
| Prefeitura de Osasco | RSS | ativa |
| Prefeitura de Cotia | RSS | ativa |
| Prefeitura de Santana de Parnaíba | página inicial | ativa |
| Prefeitura de Barueri | lista de notícias | ativa |
| Prefeitura de Carapicuíba | lista de notícias | ativa |
| Prefeitura de Itapevi | RSS | desligada (feed parado desde jun/2026) |
| Prefeitura de Jandira | — | desligada (notícias carregadas por JavaScript) |
| Prefeitura de Cajamar | — | fora (site com certificado inválido) |

Para adicionar uma fonte, copie um bloco em `config/sources.yaml` e ajuste. Se uma prefeitura
mudar o site, a fonte para de trazer notícias (aparece "0 lidas" no log da coleta) e o padrão
do link precisa ser atualizado.

## Ainda a fazer

- Coleta semanal de **vagas** (PATs, Emprega SP) e **cursos** (Qualifica SP, Senai, Etec/Fatec).
- Fontes de Jandira, Itapevi, Cajamar e Pirapora do Bom Jesus.
- Nome e domínio definitivos.
