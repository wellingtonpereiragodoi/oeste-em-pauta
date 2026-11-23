"""Chamada mínima à API do Gemini (REST), sem dependências extras."""
from __future__ import annotations

import json
import os
import time

import requests

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"


class ErroGemini(Exception):
    pass


def gerar_json(prompt: str, modelo: str, chave: str | None = None, tentativas: int = 3) -> dict:
    """Envia o prompt e devolve a resposta já convertida de JSON."""
    chave = chave or os.environ.get("GEMINI_API_KEY")
    if not chave:
        raise ErroGemini("variável GEMINI_API_KEY não definida")
    corpo = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4},
    }
    ultimo_erro = None
    for tentativa in range(tentativas):
        try:
            r = requests.post(
                ENDPOINT.format(modelo=modelo),
                headers={"x-goog-api-key": chave, "Content-Type": "application/json"},
                json=corpo,
                timeout=120,
            )
            if r.status_code in (429, 500, 502, 503, 504):
                raise ErroGemini(f"HTTP {r.status_code}: {r.text[:300]}")
            if not r.ok:
                # erro de configuração (chave, modelo): não adianta tentar de novo
                raise ErroGemini(f"HTTP {r.status_code}: {r.text[:500]}")
            dados = r.json()
            texto = dados["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(texto)
        except (ErroGemini, requests.RequestException, KeyError, IndexError, json.JSONDecodeError) as e:
            ultimo_erro = e
            if isinstance(e, ErroGemini) and "HTTP 4" in str(e) and "HTTP 429" not in str(e):
                break
            time.sleep(5 * (tentativa + 1))
    raise ErroGemini(str(ultimo_erro))
