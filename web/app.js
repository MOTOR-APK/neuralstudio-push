/* =====================================================================
   NeuralStudio — lógica da interface
   ===================================================================== */

const $ = (sel) => document.querySelector(sel);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const estado = {
  estilo: "Sem estilo",
  proporcao: "1:1",
  passos: 2,
  ocupado: false,
  historico: [],
  modelos: [],
  modeloId: null,
};

const PROPS = {
  "1:1": [512, 512],
  "16:9": [640, 384],
  "9:16": [384, 640],
  "4:3": [512, 384],
};

/* ------------------------------ utilidades ------------------------------ */
function escaparHtml(txt) {
  return String(txt ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function tempoRelativo(iso) {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const seg = Math.max(0, (Date.now() - t) / 1000);
  if (seg < 60) return "Agora mesmo";
  if (seg < 3600) return `Há ${Math.floor(seg / 60)} min`;
  if (seg < 86400) return `Há ${Math.floor(seg / 3600)} h`;
  return `Há ${Math.floor(seg / 86400)} d`;
}

function toast(msg, ok = false) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.toggle("ok", ok);
  el.hidden = false;
  clearTimeout(el._t);
  el._t = setTimeout(() => (el.hidden = true), 4200);
}

async function api(url, opcoes) {
  const r = await fetch(url, opcoes);
  if (!r.ok) {
    let detalhe = r.statusText;
    try { detalhe = (await r.json()).detail || detalhe; } catch (_) {}
    throw new Error(detalhe);
  }
  return r.json();
}

/* -------------------------------- status -------------------------------- */
async function atualizarStatus() {
  try {
    const s = await api("/api/status");

    $("#chip-cpu").textContent = `CPU ${Math.round(s.cpu_percent)}%`;
    $("#chip-ram").textContent = `RAM ${s.ram_usada_gb} / ${s.ram_total_gb} GB`;
    $("#chip-modelo").textContent = s.modelo_nome || s.modelo;
    $("#modelo-status").textContent = s.modelo_carregado ? "Carregado" : "Sob demanda";
    $("#meta-modelo").textContent = s.modelo_nome || s.modelo;
    $("#modelo-ativo-nome").textContent = s.modelo_nome || s.modelo;
    $("#modelo-ativo-tipo").textContent = s.modelo_tipo || "Texto → Imagem";

    // chip de GPU
    const gpu = s.gpu || {};
    const chipGpu = $("#chip-gpu");
    chipGpu.textContent = `${gpu.nome || "Sem GPU detectada"}`;
    chipGpu.className = "chip";
    if (gpu.tipo === "cpu" || !gpu.disponivel) {
      chipGpu.classList.add("chip-cyan");
    } else if (gpu.aceleracao) {
      chipGpu.classList.add("chip-ok");
    } else {
      chipGpu.classList.add("chip-cyan");
    }

    if (s.modelo_id !== estado.modeloId) {
      estado.modeloId = s.modelo_id;
      aplicarLimitesPassos(s.passos_min, s.passos_max, s.passos_padrao);
    }

    $("#hw-cpu-val").textContent = `${Math.round(s.cpu_percent)}%`;
    $("#hw-cpu-barra").style.width = `${Math.min(100, s.cpu_percent)}%`;
    $("#hw-ram-val").textContent = `${s.ram_usada_gb} / ${s.ram_total_gb} GB`;
    $("#hw-ram-barra").style.width = `${Math.min(100, s.ram_percent)}%`;

    const ol = $("#hw-ollama");
    ol.textContent = s.ollama ? "Ollama online" : "Ollama offline";
    ol.style.color = s.ollama ? "var(--cyan-bright)" : "var(--amber)";

    if (!document.querySelector("#chips-estilo .chip-estilo")) {
      montarEstilos(s.estilos);
    }
  } catch (e) {
    $("#chip-cpu").textContent = "CPU —";
  }
}

/* ------------------------------- controles ------------------------------ */
function montarEstilos(lista) {
  const box = $("#chips-estilo");
  box.innerHTML = "";
  lista.forEach((nome) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip-estilo" + (nome === estado.estilo ? " ativo" : "");
    b.textContent = nome;
    b.addEventListener("click", () => {
      estado.estilo = nome;
      $("#estilo-atual").textContent = nome;
      box.querySelectorAll(".chip-estilo").forEach((c) => c.classList.remove("ativo"));
      b.classList.add("ativo");
    });
    box.appendChild(b);
  });
}

function montarProporcoes() {
  const box = $("#proporcoes");
  box.innerHTML = "";
  Object.keys(PROPS).forEach((p) => {
    const [w, h] = PROPS[p];
    const b = document.createElement("button");
    b.type = "button";
    b.className = "prop" + (p === estado.proporcao ? " ativo" : "");
    b.dataset.prop = p;
    b.innerHTML = `<span class="forma"></span><span>${p}</span>`;
    b.title = `${w} × ${h} px`;
    b.addEventListener("click", () => {
      estado.proporcao = p;
      box.querySelectorAll(".prop").forEach((c) => c.classList.remove("ativo"));
      b.classList.add("ativo");
      $("#resolucao-label").textContent = `${w} × ${h} px (${p})`;
    });
    box.appendChild(b);
  });
  const [w, h] = PROPS[estado.proporcao];
  $("#resolucao-label").textContent = `${w} × ${h} px (${estado.proporcao})`;
}

function atualizarEstimativa() {
  const min = estado.passos_min ?? 1;
  const max = estado.passos_max ?? 4;
  const p = Math.min(max, Math.max(min, estado.passos));
  const s = p * 45;
  const txt = s < 60 ? `~${s} s` : `~${Math.round(s / 60)} min`;
  $("#estimativa").textContent = txt;
}

function aplicarLimitesPassos(min, max, padrao) {
  const slider = $("#passos");
  slider.min = min;
  slider.max = max;
  slider.value = Math.min(max, Math.max(min, slider.value));
  estado.passos = Number(slider.value);
  $("#passos-valor").textContent = `${estado.passos} ${estado.passos === 1 ? "passo" : "passos"}`;
  atualizarEstimativa();
}

/* -------------------------------- modelos ------------------------------- */
async function carregarModelos() {
  try {
    const dados = await api("/api/modelos");
    estado.modelos = dados.modelos;
    renderModelos(dados);
    if (!$("#modal-modelos").hidden) renderModeloCards(dados);
  } catch (_) {}
}

function renderModelos(dados) {
  const m = dados.modelos.find((x) => x.id === dados.ativo) || {};
  $("#modelo-ativo-nome").textContent = m.nome || "SD-Turbo";
  $("#modelo-ativo-tipo").textContent = m.tipo || "Texto → Imagem";
  $("#modelo-ativo-tam").textContent = `${m.tamanho_gb ?? "?"} GB`;
  const btn = $("#btn-modelos");
  btn.classList.remove("ativo", "indisponivel");
  btn.classList.add(m.instalado ? "ativo" : "indisponivel");
  if (m.instalado) btn.title = "Modelo instalado · clique para trocar";
  else btn.title = "Baixar modelo";
}

function renderModeloCards(dados) {
  const box = $("#modelos-lista");
  box.innerHTML = "";
  for (const m of dados.modelos) {
    const card = document.createElement("div");
    card.className = "modelo-card" + (m.instalado ? "" : " indisponivel") + (m.ativo ? " ativo" : "");

    const instalado = m.instalado ? '<span class="tag-instalado">Instalado</span>' : "";
    const ativoTag = m.ativo ? '<span class="tag-ativo">Ativo</span>' : "";
    const avisoHtml = m.aviso
      ? `<div class="modelo-aviso"><svg class="ico"><use href="#i-warn"/></svg>${escaparHtml(m.aviso)}</div>`
      : "";

    card.innerHTML = `
      <div class="modelo-cab">
        <div>
          <h3>${escaparHtml(m.nome)} ${ativoTag} ${instalado}</h3>
          <span class="modelo-tipo">${escaparHtml(m.tipo)}</span>
          <span class="modelo-tam">~${m.tamanho_gb} GB</span>
        </div>
      </div>
      <p class="modelo-desc">${escaparHtml(m.descricao)}</p>
      ${avisoHtml}
      <div class="modelo-acoes">
        <span class="modelo-status" id="dl-status-${m.id}">${m.instalado ? "Pronto" : "Não instalado"}</span>
        <button class="btn-modelo ${m.instalado ? "principal" : ""}" id="btn-dl-${m.id}" ${!m.instalado ? "disabled" : ""}>
          ${m.instalado ? "Usar como padrão" : "Baixar agora"}
        </button>
      </div>
      <div class="modelo-barra" id="dl-barra-${m.id}" style="margin-top:8px"><div></div></div>
    `;
    box.appendChild(card);

    const btnDl = card.querySelector(`#btn-dl-${m.id}`);
    if (m.instalado) {
      btnDl.onclick = async () => {
        try {
          await api("/api/modelos/ativo", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: m.id }),
          });
          toast(`Modelo "${m.nome}" ativado.`, true);
          renderModelos(await api("/api/modelos"));
          renderModeloCards(await api("/api/modelos"));
          await atualizarStatus();
        } catch (e) {
          toast("Não foi possível ativar: " + e.message);
        }
      };
    } else {
      btnDl.onclick = async () => {
        try {
          const { job_id } = await api("/api/modelos/baixar", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: m.id }),
          });
          toast("Download iniciado — continue navegando; ele baixa em segundo plano.", true);
          acompanharDownload(job_id, m.id);
        } catch (e) {
          toast("Não foi possível iniciar o download: " + e.message);
        }
      };
    }
  }
}

let dlInterval = null;

async function acompanharDownload(jobId, modeloId) {
  if (dlInterval) clearInterval(dlInterval);
  dlInterval = setInterval(async () => {
    try {
      const j = await api(`/api/modelos/download/${jobId}`);
      const st = $(`#dl-status-${modeloId}`);
      const bar = $(`#dl-barra-${modeloId} > div`);
      const btn = $(`#btn-dl-${modeloId}`);
      if (st) st.textContent =
        j.status === "baixando" ? `Baixando ${j.progresso}%` :
        j.status === "concluido" ? "Concluído" :
        j.status === "erro" ? "Erro" : j.status;
      if (bar) bar.style.width = `${j.progresso}%`;
      if (btn) {
        if (j.status === "concluido") {
          btn.disabled = false;
          btn.textContent = "Usar como padrão";
          btn.className = "btn-modelo principal";
        } else if (j.status === "erro") {
          btn.disabled = false;
          btn.textContent = "Tentar novamente";
        }
      }
      if (j.status === "concluido" || j.status === "erro") {
        clearInterval(dlInterval);
        dlInterval = null;
        renderModelos(await api("/api/modelos"));
        renderModeloCards(await api("/api/modelos"));
      }
    } catch (_) {}
  }, 1000);
}

/* ------------------------------- histórico ------------------------------ */
function renderHistorico(itens) {
  estado.historico = itens;
  const box = $("#historico-lista");
  $("#hist-contagem").textContent = `${itens.length} ${itens.length === 1 ? "render" : "renders"}`;

  if (!itens.length) {
    box.innerHTML = '<div class="hist-vazio">Nenhuma imagem ainda.<br>Gere a primeira! 🎨</div>';
    return;
  }

  box.innerHTML = itens.map((it, i) => {
    const texto = it.prompt_original || it.prompt || "Sem descrição";
    const res = `${it.largura || 512}px`;
    return `
      <div class="hist-item" data-idx="${i}" title="${escaparHtml(texto)}">
        <img class="hist-thumb" src="${it.url}" alt="" loading="lazy">
        <div class="hist-info">
          <div class="hist-linha">
            <span class="hist-tempo">${tempoRelativo(it.criado_em)}</span>
            <span class="hist-dur">${it.duracao ? it.duracao.toFixed(1) + "s" : ""}</span>
          </div>
          <p class="hist-prompt">${escaparHtml(texto)}</p>
          <span class="hist-meta">${escaparHtml(it.modelo || "sd-turbo")} · ${res} · ${it.passos || 2} passos</span>
        </div>
      </div>`;
  }).join("");

  box.querySelectorAll(".hist-item").forEach((el) => {
    el.addEventListener("click", () => {
      const it = estado.historico[Number(el.dataset.idx)];
      if (!it) return;
      box.querySelectorAll(".hist-item").forEach((c) => c.classList.remove("ativo"));
      el.classList.add("ativo");
      carregarItem(it);
    });
  });
}

function carregarItem(it) {
  const img = $("#imagem");
  img.src = it.url;
  img.hidden = false;
  $("#vazio").hidden = true;
  $("#btn-baixar").hidden = false;
  $("#btn-baixar").href = it.url;
  $("#btn-baixar").download = it.arquivo || "imagem.png";

  $("#meta-tempo").textContent = it.duracao ? `${it.duracao.toFixed(2)}s` : "—";
  $("#meta-resolucao").textContent = `${it.largura} × ${it.altura}`;
  $("#meta-semente").textContent = it.semente ?? "—";
  $("#meta-modelo").textContent = it.modelo || "sd-turbo";

  if (it.prompt_original || it.prompt) $("#prompt").value = it.prompt_original || it.prompt;
  if (it.semente >= 0) $("#semente").value = it.semente;
  if (it.estilo && it.estilo !== estado.estilo) {
    estado.estilo = it.estilo;
    $("#estilo-atual").textContent = it.estilo;
    document.querySelectorAll("#chips-estilo .chip-estilo").forEach((c) => {
      c.classList.toggle("ativo", c.textContent === it.estilo);
    });
  }
  const prop = Object.entries(PROPS).find(([, [w, h]]) => w === it.largura && h === it.altura);
  if (prop) {
    estado.proporcao = prop[0];
    document.querySelectorAll(".prop").forEach((c) => {
      c.classList.toggle("ativo", c.dataset.prop === prop[0]);
    });
    $("#resolucao-label").textContent = `${it.largura} × ${it.altura} px (${prop[0]})`;
  }
  setStatus("ok", "Imagem do histórico");
  atualizarContador();
}

async function carregarHistorico() {
  try {
    renderHistorico(await api("/api/historico?limite=14"));
  } catch (_) {}
}

/* -------------------------------- geração ------------------------------- */
function setOcupado(v) {
  estado.ocupado = v;
  const b = $("#btn-gerar");
  b.disabled = v;
  b.querySelector("span").textContent = v ? "Sintetizando..." : "Sintetizar Imagem";
  const btnInt = $("#btn-interromper");
  btnInt.hidden = !v;
}

function setStatus(tipo, texto) {
  const badge = $("#status-badge");
  badge.className = "badge-status" + (tipo === "erro" ? " erro" : tipo === "gerando" ? " gerando" : "");
  badge.querySelector("span").textContent = texto;
}

function mostrarProgresso(visivel, pct = 0, texto = "") {
  $("#progresso").hidden = !visivel;
  $("#barra-preenchida").style.width = `${pct}%`;
  if (texto) $("#progresso-texto").textContent = texto;
}

async function acompanhar(jobId) {
  while (true) {
    const j = await api(`/api/job/${jobId}`);

    if (j.status === "traduzindo") {
      setStatus("gerando", "Traduzindo...");
      mostrarProgresso(true, 8, "🌐 Traduzindo prompt para inglês...");
    } else if (j.status === "carregando") {
      setStatus("gerando", "Carregando modelo");
      mostrarProgresso(true, 15, "Carregando modelo na memória (primeira vez)...");
    } else if (j.status === "gerando") {
      setStatus("gerando", "Renderizando");
      const pct = 20 + (j.progresso || 0) * 0.8;
      mostrarProgresso(true, pct, `⚡ ${j.mensagem || "Gerando..."}`);
    } else if (j.status === "pronto") {
      return j.resultado;
    } else if (j.status === "erro") {
      throw new Error(j.erro || j.mensagem || "Erro desconhecido");
    } else if (j.status === "interrompido" || j.status === "interrompendo") {
      throw new Error(j.mensagem || "Geração interrompida");
    } else {
      setStatus("gerando", "Na fila");
      mostrarProgresso(true, 5, j.mensagem || "Aguardando...");
    }
    await sleep(700);
  }
}

async function gerar() {
  if (estado.ocupado) return;
  const prompt = $("#prompt").value.trim();
  if (!prompt) {
    toast("Escreva uma descrição para a imagem.");
    $("#prompt").focus();
    return;
  }

  setOcupado(true);
  setStatus("gerando", "Iniciando");
  mostrarProgresso(true, 3, "Enviando pedido...");
  $("#btn-baixar").hidden = true;

  try {
    const pedido = {
      prompt,
      estilo: estado.estilo,
      proporcao: estado.proporcao,
      passos: estado.passos,
      semente: Number($("#semente").value) || -1,
      traduzir: true,
    };
    const { job_id } = await api("/api/gerar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(pedido),
    });
    $("#job-id").textContent = `ID: #${job_id.slice(0, 8).toUpperCase()}`;

    const info = await acompanhar(job_id);
    exibirResultado(info);
    await carregarHistorico();
    toast("Imagem gerada com sucesso!", true);
  } catch (e) {
    setStatus("erro", "Erro");
    mostrarProgresso(false);
    toast(`Falha: ${e.message}`);
  } finally {
    setOcupado(false);
  }
}

function exibirResultado(info) {
  mostrarProgresso(false);
  const img = $("#imagem");
  img.src = `${info.url}?t=${Date.now()}`;
  img.hidden = false;
  $("#vazio").hidden = true;

  $("#btn-baixar").hidden = false;
  $("#btn-baixar").href = info.url;
  $("#btn-baixar").download = info.arquivo || "imagem.png";

  $("#meta-tempo").textContent = `${info.duracao.toFixed(2)}s`;
  $("#meta-resolucao").textContent = `${info.largura} × ${info.altura}`;
  $("#meta-semente").textContent = info.semente;
  $("#meta-modelo").textContent = info.modelo || "sd-turbo";

  setStatus("ok", "Renderização concluída");
}

/* ------------------------------- eventos -------------------------------- */
function ligarEventos() {
  $("#btn-gerar").addEventListener("click", gerar);
  $("#btn-atualizar").addEventListener("click", () => {
    carregarHistorico();
    atualizarStatus();
  });

  $("#btn-interromper").addEventListener("click", async () => {
    const id = $("#job-id").textContent.replace("ID: #", "").toLowerCase();
    if (!id) return;
    try {
      await api(`/api/job/${id}/cancelar`, { method: "POST" });
      $("#btn-interromper").disabled = true;
      toast("Interrompendo geração...");
    } catch (e) {
      toast("Não foi possível interromper: " + e.message);
    }
  });

  $("#btn-pasta").addEventListener("click", async () => {
    try {
      await api("/api/abrir-pasta", { method: "POST" });
    } catch (e) {
      toast(`Não foi possível abrir a pasta: ${e.message}`);
    }
  });

  $("#btn-surpresa").addEventListener("click", () => {
    const ideias = [
      "um farol antigo em um penhasco durante uma tempestade, luz dramática, fotografia cinematográfica",
      "uma raposa dormindo em uma floresta nevada ao amanhecer, luz suave, detalhes realistas",
      "uma cidade futurista à noite, letreiros de neon, chuva, reflexos no asfalto",
      "um pequeno robô lendo um livro em uma biblioteca aconchegante, iluminação quente",
      "um templo antigo na selva, vinhas cobrindo as pedras, raios de sol, atmosfera misteriosa",
      "um retrato de um pescador idoso, rosto marcado pelo tempo, luz natural, olhar profundo",
      "um bowl de ramen fumegante visto de cima, cores vibrantes, fotografia gastronômica",
      "um dragão sobrevoando um castelo medieval, escala épica, pôr do sol dourado",
      "uma estação espacial orbitando um planeta colorido, estrelas, ficção científica detalhada",
      "um gato usando um capacete de astronauta, foto de estúdio, adorável",
    ];
    $("#prompt").value = ideias[Math.floor(Math.random() * ideias.length)];
    atualizarContador();
  });

  $("#btn-limpar").addEventListener("click", () => {
    $("#prompt").value = "";
    atualizarContador();
    $("#prompt").focus();
  });

  $("#btn-dado").addEventListener("click", () => {
    $("#semente").value = Math.floor(Math.random() * 2 ** 31);
  });

  $("#passos").addEventListener("input", (e) => {
    estado.passos = Number(e.target.value);
    $("#passos-valor").textContent = `${estado.passos} ${estado.passos === 1 ? "passo" : "passos"}`;
    atualizarEstimativa();
  });

  $("#prompt").addEventListener("input", atualizarContador);
  $("#prompt").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      gerar();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      gerar();
    }
  });

  // modal de modelos
  $("#btn-modelos").addEventListener("click", () => {
    $("#modal-modelos").hidden = false;
    carregarModelos();
  });
  $("#fechar-modal").addEventListener("click", () => {
    $("#modal-modelos").hidden = true;
  });
  $("#modal-modelos").addEventListener("click", (e) => {
    if (e.target === $("#modal-modelos")) $("#modal-modelos").hidden = true;
  });
}

function atualizarContador() {
  const n = $("#prompt").value.length;
  const palavras = $("#prompt").value.trim() ? $("#prompt").value.trim().split(/\s+/).length : 0;
  $("#contador").textContent = `${n} caracteres · ${palavras} palavras`;
}

/* -------------------------------- início -------------------------------- */
(async function iniciar() {
  montarProporcoes();
  ligarEventos();
  atualizarEstimativa();
  atualizarContador();
  await atualizarStatus();
  await carregarHistorico();
  await carregarModelos();
  if (estado.historico.length) {
    carregarItem(estado.historico[0]);
    const primeiro = document.querySelector('.hist-item[data-idx="0"]');
    if (primeiro) primeiro.classList.add("ativo");
  }
  setInterval(atualizarStatus, 4000);
})();
