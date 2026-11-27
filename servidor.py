#!/usr/bin/env python3
"""
Servidor do Gerador de Imagens Local.

Backend FastAPI + frontend estático (web/).
100% offline — nenhuma requisição sai da máquina.
"""

import os
import json
import re
import time
import uuid
import threading
import subprocess
import webbrowser
import shutil

import psutil
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.gerador import gerador, PASTA_SAIDAS
from core.estilos import ESTILOS, PROPORCOES
from core import traducao, modelos

BASE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(BASE, "web")

app = FastAPI(title="Gerador de Imagens Local")

# ---------------------------------------------------------------------------
# Estado dos trabalhos de geração
# ---------------------------------------------------------------------------
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
JOBS_MODELOS: dict[str, dict] = {}
MODELOS_LOCK = threading.Lock()
GERACAO_LOCK = threading.Lock()  # apenas 1 geração por vez (limite de RAM)
CANCEL_EVENTS: dict[str, threading.Event] = {}
CANCEL_LOCK = threading.Lock()


def cancelar_evento(job_id: str) -> threading.Event:
    """Retorna (criando se necessário) o Event de cancelamento de um job."""
    with CANCEL_LOCK:
        ev = CANCEL_EVENTS.get(job_id)
        if ev is None:
            ev = threading.Event()
            CANCEL_EVENTS[job_id] = ev
        return ev


def limpar_cancelamento(job_id: str):
    with CANCEL_LOCK:
        CANCEL_EVENTS.pop(job_id, None)


# ---------------------------------------------------------------------------
# Detecção de placa de vídeo (GPU)
# ---------------------------------------------------------------------------
def detectar_gpu() -> dict:
    """Detecta qual placa de vídeo está disponível no sistema.

    Retorna um dicionário com:
      - tipo: "cuda" | "rocm" | "mps" | "intel" | "amd" | "cpu"
      - disponivel: bool
      - nome: string legível em português
      - aceleracao: bool (se dá para usar a GPU para gerar imagens)
    """
    resultado = {
        "tipo": "cpu",
        "disponivel": False,
        "nome": "Processador (CPU) apenas",
        "aceleracao": False,
    }

    # --- NVIDIA CUDA ---
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            nome_gpu = torch.cuda.get_device_name(0)
            resultado.update({
                "tipo": "cuda",
                "disponivel": True,
                "nome": f"NVIDIA {nome_gpu}",
                "aceleracao": True,
            })
            return resultado
    except Exception:
        pass

    # --- Apple Silicon (MPS) — incluso por completude ---
    try:
        import torch  # type: ignore
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            resultado.update({
                "tipo": "mps",
                "disponivel": True,
                "nome": "Apple Silicon (MPS)",
                "aceleracao": True,
            })
            return resultado
    except Exception:
        pass

    # --- ROCm (AMD) ---
    try:
        import torch  # type: ignore
        if getattr(torch, "cuda", None) is not None and hasattr(torch.cuda, "is_hip_ext"):
            if torch.cuda.is_hip_ext():
                resultado.update({
                    "tipo": "rocm",
                    "disponivel": True,
                    "nome": "AMD Radeon (ROCm)",
                    "aceleracao": True,
                })
                return resultado
    except Exception:
        pass

    # --- Detecção via hardware Linux (lspci / /sys/class/drm) ---
    # Tenta identificar se há uma placa de vídeo dedicada mesmo sem PyTorch suporte.
    try:
        if shutil.which("lspci"):
            out = subprocess.check_output(
                ["lspci", "-nn"], stderr=subprocess.DEVNULL, timeout=3
            ).decode("utf-8", errors="ignore")
            for linha in out.splitlines():
                lower = linha.lower()
                if "vga" in lower or "3d controller" in lower or "display" in lower:
                    # extrai o nome após os colchetes do ID do dispositivo
                    nome = "Placa de vídeo"
                    m = re.search(r"\[(AMD|ATI|NVIDIA|Intel)[^\]]*\](.*?)\[", linha)
                    if m:
                        marca = m.group(1)
                        modelo = m.group(2).strip(" :")
                        nome = f"{marca} {modelo}" if modelo else marca
                    else:
                        # tenta capturar texto descritivo
                        partes = linha.split(":", 3)
                        if len(partes) >= 3:
                            nome = partes[-1].strip().split(" [")[0].strip()
                            if not nome:
                                nome = "Placa de vídeo"

                    if "nvidia" in lower:
                        resultado.update({
                            "tipo": "cuda",
                            "disponivel": True,
                            "nome": f"NVIDIA {nome}".replace("NVIDIA NVIDIA", "NVIDIA"),
                            "aceleracao": False,
                        })
                        return resultado
                    if "amd" in lower or "ati" in lower or "radeon" in lower:
                        resultado.update({
                            "tipo": "amd",
                            "disponivel": True,
                            "nome": f"AMD {nome}".replace("AMD AMD", "AMD"),
                            "aceleracao": False,
                        })
                        return resultado
                    if "intel" in lower:
                        resultado.update({
                            "tipo": "intel",
                            "disponivel": True,
                            "nome": f"Intel {nome}".replace("Intel Intel", "Intel"),
                            "aceleracao": False,
                        })
                        return resultado
    except Exception:
        pass

    return resultado


GPU_INFO = detectar_gpu()

os.makedirs(PASTA_SAIDAS, exist_ok=True)

# aplica o modelo ativo salvo em estado.json
_ativo_id = modelos.modelo_ativo()
_ativo = modelos.buscar(_ativo_id)
if _ativo:
    gerador.definir_modelo(_ativo["repo"])


class PedidoGeracao(BaseModel):
    prompt: str = Field(min_length=1)
    estilo: str = "Sem estilo"
    proporcao: str = "1:1"
    passos: int = 2
    semente: int = -1
    traduzir: bool = True


class PedidoModelo(BaseModel):
    id: str


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _atualizar(job_id: str, **campos):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(campos)


def _ler_historico(limite: int = 14):
    if not os.path.isdir(PASTA_SAIDAS):
        return []
    itens = []
    for nome in os.listdir(PASTA_SAIDAS):
        if not nome.endswith(".json"):
            continue
        caminho_json = os.path.join(PASTA_SAIDAS, nome)
        caminho_png = caminho_json[:-5] + ".png"
        if not os.path.exists(caminho_png):
            continue
        try:
            with open(caminho_json, encoding="utf-8") as f:
                info = json.load(f)
        except Exception:
            continue
        info["url"] = f"/saidas/{info.get('arquivo', os.path.basename(caminho_png))}"
        info["mtime"] = os.path.getmtime(caminho_png)
        itens.append(info)
    itens.sort(key=lambda i: i.get("mtime", 0), reverse=True)
    return itens[:limite]


def _executar_geracao(job_id: str, pedido: PedidoGeracao):
    ev = cancelar_evento(job_id)
    try:
        _atualizar(job_id, status="fila", mensagem="Aguardando na fila...")
        with GERACAO_LOCK:
            texto = pedido.prompt.strip()

            # tradução automática sempre ativa (PT → EN)
            if traducao.ollama_disponivel():
                _atualizar(job_id, status="traduzindo", mensagem="Traduzindo prompt...")
                traduzido = traducao.traduzir(texto)
                if traduzido and traduzido.strip():
                    texto = traduzido.strip()

            sufixo = ESTILOS.get(pedido.estilo, "")
            prompt_final = f"{texto}{sufixo}"
            largura, altura = PROPORCOES.get(pedido.proporcao, (512, 512))

            if not gerador.carregado:
                _atualizar(job_id, status="carregando",
                           mensagem="Carregando modelo na memória (primeira vez)...")

            def ao_passo(passo, total):
                # verifica se o usuário pediu para interromper
                if ev.is_set():
                    raise InterruptedError("Geração interrompida pelo usuário")
                pct = int(passo / total * 100)
                _atualizar(job_id, status="gerando", passo=passo,
                           total_passos=total, progresso=pct,
                           mensagem=f"Gerando... passo {passo}/{total}")

            if ev.is_set():
                raise InterruptedError("Geração interrompida pelo usuário")

            _atualizar(job_id, status="gerando", progresso=0,
                       mensagem="Iniciando difusão...")

            imagem, duracao, semente = gerador.gerar(
                prompt_final,
                passos=pedido.passos,
                largura=largura,
                altura=altura,
                semente=pedido.semente,
                ao_passo=ao_passo,
            )

            if ev.is_set():
                raise InterruptedError("Geração interrompida pelo usuário")

            info = gerador.salvar(
                imagem, prompt_final, pedido.estilo, semente,
                largura, altura, pedido.passos, duracao,
                prompt_original=pedido.prompt,
            )
            info["url"] = f"/saidas/{info['arquivo']}"

            _atualizar(
                job_id,
                status="pronto",
                progresso=100,
                mensagem="Renderização concluída",
                resultado=info,
            )
    except InterruptedError:
        _atualizar(job_id, status="interrompido",
                   mensagem="Geração interrompida pelo usuário")
    except Exception as exc:  # noqa: BLE001
        _atualizar(job_id, status="erro", mensagem=f"Erro: {exc}", erro=str(exc))
    finally:
        limpar_cancelamento(job_id)


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
@app.post("/api/gerar")
def gerar(pedido: PedidoGeracao):
    if pedido.proporcao not in PROPORCOES:
        raise HTTPException(400, "Proporção inválida")
    job_id = uuid.uuid4().hex[:12]
    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "status": "fila",
            "progresso": 0,
            "passo": 0,
            "total_passos": max(1, min(30, pedido.passos)),
            "mensagem": "Na fila...",
            "resultado": None,
            "erro": None,
            "iniciado": time.time(),
        }
    threading.Thread(target=_executar_geracao, args=(job_id, pedido), daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/job/{job_id}")
def status_job(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "Job não encontrado")
        return dict(job)


@app.get("/api/historico")
def historico(limite: int = 14):
    return _ler_historico(max(1, min(60, limite)))


@app.get("/api/status")
def status_sistema():
    mem = psutil.virtual_memory()
    ativo_id = modelos.modelo_ativo()
    m = modelos.buscar(ativo_id) or {}
    return {
        "ollama": traducao.ollama_disponivel(),
        "modelo": gerador.modelo.split("/")[-1],
        "modelo_id": ativo_id,
        "modelo_nome": m.get("nome", gerador.modelo),
        "modelo_tipo": m.get("tipo", "Texto → Imagem"),
        "modelo_carregado": gerador.carregado,
        "passos_min": m.get("passos_min", 1),
        "passos_max": m.get("passos_max", 4),
        "passos_padrao": m.get("passos_padrao", 2),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_usada_gb": round(mem.used / 1e9, 1),
        "ram_total_gb": round(mem.total / 1e9, 1),
        "ram_percent": mem.percent,
        "gpu": GPU_INFO,
        "estilos": list(ESTILOS.keys()),
        "proporcoes": {k: list(v) for k, v in PROPORCOES.items()},
    }


@app.post("/api/job/{job_id}/cancelar")
def cancelar_geracao(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "Job não encontrado")
        if job.get("status") in ("pronto", "erro", "interrompido"):
            raise HTTPException(400, "Job já finalizado")
    ev = cancelar_evento(job_id)
    ev.set()
    _atualizar(job_id, status="interrompendo", mensagem="Interrompendo geração...")
    return {"ok": True, "mensagem": "Sinal de interrupção enviado"}


@app.get("/api/modelos")
def listar_modelos():
    return modelos.listar()


@app.post("/api/modelos/baixar")
def baixar_modelo(pedido: PedidoModelo):
    try:
        job_id = modelos.iniciar_download(pedido.id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"job_id": job_id}


@app.get("/api/modelos/download/{job_id}")
def status_download(job_id: str):
    job = modelos.status_download(job_id)
    if not job:
        raise HTTPException(404, "Download não encontrado")
    return job


@app.post("/api/modelos/ativo")
def ativar_modelo(pedido: PedidoModelo):
    modelo = modelos.buscar(pedido.id)
    if not modelo:
        raise HTTPException(404, "Modelo desconhecido")
    if not modelo.get("suportado"):
        raise HTTPException(400, modelo.get("aviso") or "Modelo não suportado")
    if modelo["repo"] not in modelos._repos_no_cache():
        raise HTTPException(400, "Baixe este modelo antes de usá-lo")
    if GERACAO_LOCK.locked():
        raise HTTPException(409, "Aguarde a geração atual terminar")

    modelos.definir_ativo(pedido.id)
    gerador.definir_modelo(modelo["repo"])
    return {"ok": True, "modelo": modelo["nome"]}


@app.post("/api/abrir-pasta")
def abrir_pasta():
    try:
        subprocess.Popen(["xdg-open", PASTA_SAIDAS])
        return {"ok": True, "pasta": PASTA_SAIDAS}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"ok": False, "erro": str(exc)})


@app.get("/")
def index():
    return FileResponse(os.path.join(WEB, "index.html"))


# arquivos estáticos e imagens geradas
app.mount("/static", StaticFiles(directory=WEB), name="static")
app.mount("/saidas", StaticFiles(directory=PASTA_SAIDAS), name="saidas")


if __name__ == "__main__":
    import uvicorn

    print("=" * 62)
    print("  Gerador de Imagens Local — http://127.0.0.1:7860")
    print("=" * 62)
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:7860")).start()
    uvicorn.run(app, host="127.0.0.1", port=7860, log_level="warning")
