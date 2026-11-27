"""Catálogo e gerenciamento de modelos locais (download offline).

Cada modelo é baixado uma única vez para o cache do Hugging Face e passa a
funcionar sem internet. O catálogo explica em português o que cada um faz.
"""

import fnmatch
import json
import os
import threading
import time
import uuid

from huggingface_hub import HfApi, scan_cache_dir, snapshot_download
from huggingface_hub.constants import HF_HUB_CACHE

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESTADO = os.path.join(BASE, "estado.json")

# Só baixamos o formato "diffusers" (pastas unet/, vae/, text_encoder/...).
# Isso evita baixar duplicatas enormes em arquivo único (.ckpt/.bin).
PERMITIR = [
    "model_index.json",
    "scheduler/*",
    "text_encoder/*",
    "text_encoder_2/*",
    "tokenizer/*",
    "tokenizer_2/*",
    "unet/*",
    "vae/*",
    "feature_extractor/*",
    "*.txt",
]

# ---------------------------------------------------------------------------
# Catálogo — cada item explica em português o que o modelo faz.
# ---------------------------------------------------------------------------
CATALOGO = [
    {
        "id": "sd-turbo",
        "repo": "stabilityai/sd-turbo",
        "nome": "SD-Turbo",
        "tipo": "Texto → Imagem",
        "descricao": (
            "Cria imagens a partir de uma descrição em texto. É o mais rápido: "
            "gera em 1 a 4 passos, ideal para computadores sem placa de vídeo dedicada."
        ),
        "tamanho_gb": 2.5,
        "baixavel": True,
        "suportado": True,
        "recomendado": True,
        "passos_min": 1,
        "passos_max": 4,
        "passos_padrao": 2,
    },
    {
        "id": "dreamshaper-8",
        "repo": "Lykon/dreamshaper-8",
        "nome": "DreamShaper 8",
        "tipo": "Texto → Imagem",
        "descricao": (
            "Gera imagens com estilo artístico e fotorrealista. Usa mais passos, "
            "então é mais lento que o SD-Turbo, porém com mais riqueza de detalhes."
        ),
        "tamanho_gb": 2.1,
        "baixavel": True,
        "suportado": True,
        "recomendado": False,
        "passos_min": 4,
        "passos_max": 25,
        "passos_padrao": 8,
        "aviso": "Mais lento: ~45 s por passo na CPU.",
    },
    {
        "id": "sd15",
        "repo": "stable-diffusion-v1-5/stable-diffusion-v1-5",
        "nome": "Stable Diffusion 1.5",
        "tipo": "Texto → Imagem",
        "descricao": (
            "Modelo base clássico, compatível com milhares de estilos e extensões. "
            "Bom para quem quer experimentar variações e aprender."
        ),
        "tamanho_gb": 2.1,
        "baixavel": True,
        "suportado": True,
        "recomendado": False,
        "passos_min": 4,
        "passos_max": 25,
        "passos_padrao": 8,
        "aviso": "Mais lento: ~45 s por passo na CPU.",
    },
    {
        "id": "sdxl-turbo",
        "repo": "stabilityai/sdxl-turbo",
        "nome": "SDXL-Turbo",
        "tipo": "Texto → Imagem (alta resolução)",
        "descricao": (
            "Gera imagens em 1024×1024 com mais qualidade e detalhes. "
            "É bem mais pesado que o SD-Turbo."
        ),
        "tamanho_gb": 6.9,
        "baixavel": False,
        "suportado": False,
        "recomendado": False,
        "passos_min": 1,
        "passos_max": 4,
        "passos_padrao": 2,
        "aviso": "Precisa de ~16 GB de RAM — não cabe neste computador (9,6 GB).",
    },
    {
        "id": "inpaint",
        "repo": "Lykon/dreamshaper-8-inpainting",
        "nome": "DreamShaper 8 Inpainting",
        "tipo": "Edição de imagem",
        "descricao": (
            "Corrige defeitos, apaga ou adiciona objetos em partes específicas da "
            "imagem (pintando uma máscara sobre a área desejada)."
        ),
        "tamanho_gb": 2.1,
        "baixavel": False,
        "suportado": False,
        "recomendado": False,
        "passos_min": 4,
        "passos_max": 25,
        "passos_padrao": 8,
        "aviso": "Em desenvolvimento — a ferramenta de máscara ainda não está pronta.",
    },
    {
        "id": "upscale",
        "repo": "ai-forever/Real-ESRGAN",
        "nome": "Real-ESRGAN",
        "tipo": "Melhoria de resolução",
        "descricao": (
            "Aumenta a resolução e recupera detalhes de imagens (upscale), "
            "deixando fotos e artes mais nítidas."
        ),
        "tamanho_gb": 0.1,
        "baixavel": False,
        "suportado": False,
        "recomendado": False,
        "passos_min": 1,
        "passos_max": 1,
        "passos_padrao": 1,
        "aviso": "Em desenvolvimento — o botão de upscale ainda não está disponível.",
    },
    {
        "id": "video",
        "repo": "Wan-AI/Wan2.1-T2V-1.3B-Diffusers",
        "nome": "Wan 2.1 (vídeo)",
        "tipo": "Texto → Vídeo",
        "descricao": (
            "Gera pequenos vídeos a partir de uma descrição em texto. "
            "Exige placa de vídeo dedicada com bastante memória."
        ),
        "tamanho_gb": 8.0,
        "baixavel": False,
        "suportado": False,
        "recomendado": False,
        "passos_min": 1,
        "passos_max": 1,
        "passos_padrao": 1,
        "aviso": "Não é viável neste hardware (precisa de GPU dedicada).",
    },
]

_LOCK = threading.Lock()
_DL_LOCK = threading.Lock()
DOWNLOADS: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Estado persistido (modelo ativo)
# ---------------------------------------------------------------------------
def _ler_estado() -> dict:
    try:
        with open(ESTADO, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _salvar_estado(dados: dict):
    with open(ESTADO, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def modelo_ativo() -> str:
    return _ler_estado().get("modelo_ativo", "sd-turbo")


def definir_ativo(modelo_id: str):
    dados = _ler_estado()
    dados["modelo_ativo"] = modelo_id
    _salvar_estado(dados)


def buscar(modelo_id: str) -> dict | None:
    for m in CATALOGO:
        if m["id"] == modelo_id:
            return m
    return None


# ---------------------------------------------------------------------------
# Cache local
# ---------------------------------------------------------------------------
def _repos_no_cache() -> set:
    try:
        info = scan_cache_dir()
        return {r.repo_id for r in info.repos}
    except Exception:
        return set()


def _pasta_cache(repo: str) -> str:
    return os.path.join(HF_HUB_CACHE, "models--" + repo.replace("/", "--"))


def _tamanho_baixado(repo: str) -> int:
    total = 0
    for raiz, _, arquivos in os.walk(_pasta_cache(repo)):
        for nome in arquivos:
            try:
                total += os.path.getsize(os.path.join(raiz, nome))
            except OSError:
                pass
    return total


def _tamanho_esperado(repo: str) -> int:
    """Soma o tamanho dos arquivos que realmente vamos baixar."""
    try:
        info = HfApi().model_info(repo, files_metadata=True)
    except Exception:
        return 0
    total = 0
    for irmao in info.siblings or []:
        nome = irmao.rfilename
        if not any(fnmatch.fnmatch(nome, padrao) for padrao in PERMITIR):
            continue
        total += irmao.size or 0
    return total


def listar() -> dict:
    repos = _repos_no_cache()
    ativo = modelo_ativo()
    modelos = []
    for m in CATALOGO:
        item = dict(m)
        item["instalado"] = m["repo"] in repos
        item["ativo"] = m["id"] == ativo
        modelos.append(item)
    return {"ativo": ativo, "modelos": modelos}


# ---------------------------------------------------------------------------
# Download em segundo plano
# ---------------------------------------------------------------------------
def _atualizar_dl(job_id: str, **campos):
    with _DL_LOCK:
        if job_id in DOWNLOADS:
            DOWNLOADS[job_id].update(campos)


def status_download(job_id: str) -> dict | None:
    with _DL_LOCK:
        job = DOWNLOADS.get(job_id)
        return dict(job) if job else None


def _baixar(job_id: str, modelo: dict):
    repo = modelo["repo"]
    try:
        _atualizar_dl(job_id, status="preparando", mensagem="Consultando tamanho...")
        esperado = _tamanho_esperado(repo)
        _atualizar_dl(
            job_id,
            status="baixando",
            mensagem="Baixando arquivos...",
            total_bytes=esperado,
        )

        parar = threading.Event()

        def monitorar():
            while not parar.is_set():
                baixado = _tamanho_baixado(repo)
                if esperado:
                    pct = int(min(99, baixado / esperado * 100))
                else:
                    pct = 0
                _atualizar_dl(
                    job_id,
                    progresso=pct,
                    baixado_bytes=baixado,
                    mensagem=f"Baixando... {baixado / 1e9:.2f} GB",
                )
                parar.wait(1.2)

        vigia = threading.Thread(target=monitorar, daemon=True)
        vigia.start()

        with _LOCK:
            snapshot_download(repo_id=repo, allow_patterns=PERMITIR)

        parar.set()
        _atualizar_dl(
            job_id,
            status="concluido",
            progresso=100,
            mensagem="Modelo baixado e pronto para uso",
            baixado_bytes=_tamanho_baixado(repo),
        )
    except Exception as exc:  # noqa: BLE001
        _atualizar_dl(
            job_id,
            status="erro",
            mensagem="Falha no download",
            erro=str(exc),
        )


def iniciar_download(modelo_id: str) -> str:
    modelo = buscar(modelo_id)
    if not modelo:
        raise ValueError("Modelo desconhecido")
    if not modelo.get("baixavel"):
        raise ValueError(modelo.get("aviso") or "Download não disponível para este modelo")
    if modelo["repo"] in _repos_no_cache():
        raise ValueError("Este modelo já está instalado")

    job_id = uuid.uuid4().hex[:12]
    with _DL_LOCK:
        DOWNLOADS[job_id] = {
            "id": job_id,
            "modelo": modelo_id,
            "status": "preparando",
            "progresso": 0,
            "baixado_bytes": 0,
            "total_bytes": 0,
            "mensagem": "Preparando download...",
            "erro": None,
            "iniciado": time.time(),
        }
    threading.Thread(target=_baixar, args=(job_id, modelo), daemon=True).start()
    return job_id
