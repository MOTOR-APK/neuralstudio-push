"""Núcleo de geração de imagens com SD-Turbo (100% local/offline)."""

import os
import json
import threading
import time
import datetime
import random

import torch
from diffusers import AutoPipelineForText2Image

MODELO_PADRAO = "stabilityai/sd-turbo"

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_SAIDAS = os.path.join(BASE, "saidas")


class Gerador:
    """Carrega o modelo uma única vez e reaproveita entre gerações."""

    def __init__(self, modelo: str = MODELO_PADRAO):
        self.modelo = modelo
        self._pipe = None
        self._lock = threading.Lock()
        self.carregado = False

    # ------------------------------------------------------------------
    def definir_modelo(self, repo: str):
        """Troca o modelo ativo (recarrega na próxima geração)."""
        with self._lock:
            if repo == self.modelo and self._pipe is not None:
                return
            self._pipe = None
            self.modelo = repo
            self.carregado = False

    # ------------------------------------------------------------------
    def _eh_turbo(self) -> bool:
        return "turbo" in self.modelo.lower()

    def _eh_sdxl(self) -> bool:
        return "sdxl" in self.modelo.lower()

    # ------------------------------------------------------------------
    def carregar(self):
        with self._lock:
            if self._pipe is None:
                pipe = AutoPipelineForText2Image.from_pretrained(
                    self.modelo,
                    dtype=torch.float32,
                    safety_checker=None,
                    low_cpu_mem_usage=True,
                )
                pipe.to("cpu")
                # reduz o pico de memória (essencial em máquinas com ~8–10 GB de RAM)
                try:
                    pipe.enable_attention_slicing()
                    pipe.enable_vae_slicing()
                except Exception:
                    pass
                self._pipe = pipe
                self.carregado = True
        return self._pipe

    # ------------------------------------------------------------------
    def gerar(self, prompt: str, passos: int = 2, largura: int = 512,
              altura: int = 512, semente: int = -1, ao_passo=None):
        """Gera uma imagem.

        ao_passo: função opcional (passo_atual, total) chamada a cada passo.
        Devolve (imagem, segundos, semente_usada).
        """
        pipe = self.carregar()

        if semente is None or int(semente) < 0:
            semente = random.randint(0, 2**31 - 1)
        gerador = torch.Generator("cpu").manual_seed(int(semente))

        total = max(1, min(30, int(passos)))

        # SDXL precisa de resolução maior para render bem (mantendo a proporção)
        if self._eh_sdxl():
            fator = 1024 / max(int(largura), int(altura))
            largura = max(512, int(round(int(largura) * fator / 8) * 8))
            altura = max(512, int(round(int(altura) * fator / 8) * 8))

        # modelos turbo usam guidance 0; os clássicos usam ~7
        guidance = 0.0 if self._eh_turbo() else 7.0

        def _callback(_pipe, indice, _timestep, kwargs):
            if ao_passo:
                try:
                    ao_passo(indice + 1, total)
                except Exception:
                    pass
            return kwargs

        inicio = time.time()
        imagem = pipe(
            prompt=prompt,
            num_inference_steps=total,
            guidance_scale=guidance,
            width=int(largura),
            height=int(altura),
            generator=gerador,
            callback_on_step_end=_callback,
        ).images[0]
        duracao = time.time() - inicio
        return imagem, duracao, int(semente)

    # ------------------------------------------------------------------
    def salvar(self, imagem, prompt: str, estilo: str = "", semente: int = -1,
               largura: int = 512, altura: int = 512, passos: int = 2,
               duracao: float = 0.0, prompt_original: str = "") -> dict:
        os.makedirs(PASTA_SAIDAS, exist_ok=True)
        agora = datetime.datetime.now()
        nome_base = agora.strftime("imagem_%Y%m%d_%H%M%S_%f")
        nome = f"{nome_base}.png"
        caminho = os.path.join(PASTA_SAIDAS, nome)

        from PIL import PngImagePlugin

        meta = PngImagePlugin.PngInfo()
        meta.add_text("prompt", prompt)
        meta.add_text("estilo", estilo)
        meta.add_text("semente", str(semente))
        meta.add_text("modelo", self.modelo)
        imagem.save(caminho, pnginfo=meta)

        info = {
            "arquivo": nome,
            "prompt": prompt,
            "prompt_original": prompt_original or prompt,
            "estilo": estilo,
            "semente": semente,
            "largura": largura,
            "altura": altura,
            "passos": passos,
            "duracao": round(duracao, 2),
            "modelo": self.modelo.split("/")[-1],
            "criado_em": agora.isoformat(timespec="seconds"),
        }
        with open(os.path.join(PASTA_SAIDAS, f"{nome_base}.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

        return info


# instância única compartilhada pela aplicação
gerador = Gerador()
