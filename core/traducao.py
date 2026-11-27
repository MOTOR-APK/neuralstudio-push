"""Tradução automática do prompt (PT → EN) usando o Ollama local.

O SD-Turbo entende inglês muito melhor. Se o Ollama estiver rodando,
traduzimos o texto do usuário antes de gerar a imagem.

Para economizar RAM (máquinas com pouca memória), preferimos o menor
modelo disponível e pedimos ao Ollama para descarregá-lo logo em seguida.
"""

import re
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_TAGS = "http://localhost:11434/api/tags"

# ordem de preferência: do mais leve para o mais pesado
MODELOS_PREFERIDOS = [
    "qwen2.5-coder:3b",
    "qwen2.5:3b",
    "llama3.2:3b",
    "gemma3:4b",
    "gemma4:latest",
]

INSTRUCAO = (
    "You are a translation engine. Translate the user's text to English. "
    "Keep it as a short image-generation prompt. "
    "Reply with ONLY the translated text, no quotes, no explanations, no notes."
)

_modelo_escolhido = None


def ollama_disponivel() -> bool:
    try:
        r = requests.get(OLLAMA_TAGS, timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def escolher_modelo() -> str | None:
    """Escolhe o menor modelo disponível no Ollama."""
    global _modelo_escolhido
    if _modelo_escolhido:
        return _modelo_escolhido
    try:
        r = requests.get(OLLAMA_TAGS, timeout=3)
        nomes = {m.get("name", "") for m in r.json().get("models", [])}
    except Exception:
        return None
    for candidato in MODELOS_PREFERIDOS:
        if candidato in nomes:
            _modelo_escolhido = candidato
            return candidato
    return None


def traduzir(texto: str, modelo: str | None = None, timeout: int = 90) -> str:
    """Traduz para inglês. Se falhar, devolve o texto original."""
    if not texto or not texto.strip():
        return texto

    modelo = modelo or escolher_modelo()
    if not modelo:
        return texto

    payload = {
        "model": modelo,
        "prompt": f"{INSTRUCAO}\n\nText: {texto.strip()}",
        "stream": False,
        "keep_alive": 0,  # libera a RAM logo após traduzir
        "options": {"temperature": 0.0, "num_predict": 120},
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
        r.raise_for_status()
        saida = (r.json().get("response") or "").strip()
    except Exception:
        return texto

    # limpeza defensiva
    saida = saida.split("\n")[0].strip()
    saida = re.sub(r'^["\'“”]+|["\'“”]+$', "", saida).strip()
    return saida or texto
