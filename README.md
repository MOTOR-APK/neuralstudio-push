# 🎨 NeuralStudio — Estúdio Local

Gerador de imagens a partir de texto, **100% offline**, com interface de estúdio
profissional em **português**. Roda na sua máquina, sem nuvem, sem créditos e sem
enviar nada para fora.

Modelo: **SD-Turbo** (Stability AI), otimizado para CPU.

![tema](https://img.shields.io/badge/tema-dark%20glassmorphism-06b6d4) ![offline](https://img.shields.io/badge/offline-100%25-10b981) ![python](https://img.shields.io/badge/python-3.12-6366f1)

---

## ✨ Recursos

- Interface **dark glassmorphism** em 3 colunas (parâmetros · canvas · histórico)
- **100% offline** — fontes e estilos empacotados localmente (sem CDN)
- **11 estilos visuais** prontos
- **4 proporções**: 1:1, 16:9, 9:16, 4:3
- **Tradução automática PT → EN** via Ollama local
- **Progresso em tempo real** por passo de difusão
- **Histórico** com miniaturas, tempo relativo e reutilização de parâmetros
- **Telemetria real** de CPU e RAM
- Metadados (prompt, estilo, semente) salvos em PNG + JSON
- Atalho **Ctrl+Enter** para sintetizar

---

## 🚀 Como usar

```bash
./abrir.sh
```

Abre em <http://127.0.0.1:7860>.

> Na primeira geração, o modelo (~2,5 GB) é baixado e carregado na memória.
> Isso pode levar 1–3 minutos. Depois, cada imagem sai em ~45–90 s.

---

## ⏱️ Desempenho (CPU)

| Passos | Tempo aprox. | Qualidade |
|--------|--------------|-----------|
| 1      | ~45 s        | boa       |
| 2      | ~90 s        | ótima     |
| 4      | ~3 min       | máxima    |

---

## 🔧 Instalação do zero

```bash
./instalar.sh
```

O script cria o `.venv`, instala o PyTorch (CPU) e as dependências.

---

## 📁 Estrutura

```
Projeto Padrão/
├── servidor.py          # backend FastAPI (rotas + fila de geração)
├── core/
│   ├── gerador.py       # pipeline SD-Turbo, progresso e salvamento
│   ├── estilos.py       # estilos, proporções e prompts prontos
│   └── traducao.py      # tradução PT→EN via Ollama
├── web/
│   ├── index.html       # interface
│   ├── estilo.css       # design system "Studio Neural Sombrio"
│   ├── app.js           # lógica do frontend
│   └── fonts/           # fontes locais (Plus Jakarta Sans, JetBrains Mono)
├── saidas/              # imagens geradas (.png + .json)
├── abrir.sh
├── instalar.sh
└── requirements.txt
```

---

## ⚠️ Limitações

- **Não gera vídeo** — exigiria outro tipo de modelo e GPU dedicada.
- Roda em **CPU**: funciona, mas com paciência.
- SD-Turbo ignora *prompt negativo* (guidance = 0); por isso a interface usa
  **estilos** em vez de prompt negativo.
- O modelo foi treinado em inglês; a tradução automática ajuda bastante.

---

## 🧠 Dica de prompt

Estrutura que funciona bem: **sujeito + cenário + iluminação + estilo**.
Ex.: *"um farol antigo em um penhasco, tempestade, luz dramática, fotografia cinematográfica"*.
# neuralstudio
