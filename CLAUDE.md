# Oeste em Pauta — instruções para o Claude Code

Site de notícias regionais (Região Oeste da Grande SP: Santana de Parnaíba, Barueri, Osasco,
Carapicuíba, Itapevi, Jandira, Cotia, Cajamar, Pirapora do Bom Jesus). Editorias: política,
segurança, empregos, cursos gratuitos. Responda sempre em português do Brasil.

## Como funciona
- `oeste/collect.py` — coletor: lê as fontes de `config/sources.yaml` (RSS ou página HTML),
  respeita robots.txt, filtra notícias regionais, classifica e grava `data/noticias/AAAA-MM-DD.json`.
- `oeste/draft.py` — Gemini (`GEMINI_API_KEY`) escreve o resumo do dia, newsletter, TikTok e Instagram.
  Gera `conteudo/posts/AAAA-MM-DD.md` + `rascunhos/AAAA-MM-DD/`.
- `oeste/build.py` — gera o site estático em `_site/`.
- `.github/workflows/` — coleta a cada 2h, rascunho diário via Pull Request (o dono aprova com Merge),
  publicação no GitHub Pages.

## Comandos (Windows, na raiz do projeto)
```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt pytest
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m oeste.collect
.venv\Scripts\python -m oeste.build
```
Atalho: `testar.bat` faz tudo e salva a saída em `resultado-teste.log`.

## Regras do projeto (não quebrar)
- Nada é publicado sem aprovação humana: NÃO gerar/commitar arquivos em `conteudo/posts/`
  fora do fluxo de Pull Request. Se rodar `oeste.draft` localmente para testar, apague o post gerado.
- Nunca republicar texto completo das fontes: guardar só título, trecho curto (≤400 caracteres) e link.
- Respeitar robots.txt (regra mais específica vence, ver `oeste/robots.py`).
- Links nos posts vêm dos dados coletados, nunca da IA.
- Notícias policiais: sem nomes de suspeitos, vítimas ou menores.
- Nunca colocar a chave do Gemini em arquivo; usar a variável de ambiente / secret do GitHub.

## Próximo passo esperado
Rodar a primeira coleta real e ajustar `config/sources.yaml` para fontes que vierem com erro ou
"0 lidas" (padrão de link das prefeituras pode mudar). Depois publicar no GitHub (repositório
`wellingtonpereiragodoi/oeste-em-pauta`) e configurar secret, permissões de Actions e Pages
conforme o README.
