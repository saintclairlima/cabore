(() => {
    const apiRoot = "/v1";
    const state = {
        key: sessionStorage.getItem("caborer_admin_key") || "",
        applications: [],
        models: [],
        keys: [],
        analytics: null,
        activeView: "dashboard",
        toastTimer: null,
    };

    const $ = (selector, root = document) => root.querySelector(selector);
    const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
    const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[character]);

    class ApiError extends Error {
        constructor(message, status) {
            super(message);
            this.status = status;
        }
    }

    async function api(path, options = {}) {
        const response = await fetch(`${apiRoot}${path}`, {
            ...options,
            headers: {
                ...(options.body ? { "Content-Type": "application/json" } : {}),
                "X-Admin-Key": state.key,
                ...options.headers,
            },
        });
        const payload = response.status === 204 ? null : await response.json().catch(() => null);
        if (!response.ok) {
            const detail = payload?.detail || payload?.erro || `Falha na requisição (${response.status}).`;
            throw new ApiError(typeof detail === "string" ? detail : "Os dados enviados são inválidos.", response.status);
        }
        return payload;
    }

    function showToast(message) {
        const toast = $("#toast");
        toast.textContent = message;
        toast.classList.add("visible");
        clearTimeout(state.toastTimer);
        state.toastTimer = setTimeout(() => toast.classList.remove("visible"), 3200);
    }

    function showError(element, message) {
        element.textContent = message;
        element.style.display = "block";
    }

    function clearError(element) {
        element.textContent = "";
        element.style.display = "none";
    }

    function handleAuthError(error) {
        if (error instanceof ApiError && error.status === 403) {
            state.key = "";
            sessionStorage.removeItem("caborer_admin_key");
            $("#app-shell").classList.add("hidden");
            $("#auth-screen").classList.remove("hidden");
            showError($("#auth-error"), "A chave não foi aceita. Confira a configuração ADMIN_KEY e tente novamente.");
            $("#admin-key").value = "";
            return true;
        }
        return false;
    }

    async function loadDashboard() {
        const errorElement = $("#dashboard-error");
        clearError(errorElement);
        try {
            const days = $("#period-select").value;
            state.analytics = await api(`/admin/analytics?dias=${days}`);
            renderDashboard(state.analytics);
        } catch (error) {
            if (!handleAuthError(error)) showError(errorElement, error.message || "Não foi possível carregar a auditoria.");
        }
    }

    async function loadApplications() {
        const errorElement = $("#applications-error");
        clearError(errorElement);
        try {
            state.applications = await api("/aplicacoes/?limite=100&deslocamento=0");
            renderApplications();
        } catch (error) {
            if (!handleAuthError(error)) showError(errorElement, error.message || "Não foi possível carregar as aplicações.");
        }
    }

    async function loadKeys() {
        const errorElement = $("#keys-error");
        clearError(errorElement);
        try {
            if (!state.applications.length) {
                state.applications = await api("/aplicacoes/?limite=100&deslocamento=0");
            }
            const groupedKeys = await Promise.all(state.applications.map(async (application) => {
                const keys = await api(`/aplicacoes/${encodeURIComponent(application.id)}/chaves`);
                return keys.map((key) => ({ ...key, aplicacao_nome: application.nome }));
            }));
            state.keys = groupedKeys.flat();
            renderKeys();
        } catch (error) {
            if (!handleAuthError(error)) showError(errorElement, error.message || "Não foi possível carregar as chaves.");
        }
    }

    async function loadModels() {
        const errorElement = $("#models-error");
        clearError(errorElement);
        try {
            state.models = await api("/modelos/?limite=100&deslocamento=0");
            renderModels();
        } catch (error) {
            if (!handleAuthError(error)) showError(errorElement, error.message || "Não foi possível carregar os modelos.");
        }
    }

    async function loadView(view) {
        state.activeView = view;
        $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
        $$(".view").forEach((section) => section.classList.toggle("hidden", section.id !== `view-${view}`));
        if (view === "dashboard") await loadDashboard();
        if (view === "applications") await loadApplications();
        if (view === "keys") await loadKeys();
        if (view === "models") await loadModels();
    }

    function formatNumber(value, digits = 0) {
        return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: digits }).format(Number(value || 0));
    }

    function formatDuration(value) {
        const number = Number(value || 0);
        return `${formatNumber(number, number < 10 ? 2 : 1)} ms`;
    }

    function formatDate(value, includeTime = false) {
        if (!value) return "—";
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return "—";
        const options = includeTime
            ? { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }
            : { day: "2-digit", month: "short", year: "numeric" };
        return new Intl.DateTimeFormat("pt-BR", options).format(date);
    }

    function statCard(label, value, foot, icon) {
        return `<article class="stat-card">
            <div class="stat-top"><span>${label}</span><span class="stat-icon">${icon}</span></div>
            <div class="stat-value">${value}</div><div class="stat-foot">${foot}</div>
        </article>`;
    }

    const icons = {
        pulse: '<svg viewBox="0 0 24 24" fill="none"><path d="M3 12h4l3-8 4 16 3-8h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        clock: '<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.8"/><path d="M12 7v5l3 2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
        layers: '<svg viewBox="0 0 24 24" fill="none"><path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>',
        search: '<svg viewBox="0 0 24 24" fill="none"><circle cx="10.8" cy="10.8" r="6.5" stroke="currentColor" stroke-width="1.8"/><path d="m16 16 4.5 4.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    };

    function renderDashboard(data) {
        const metrics = data.metricas;
        $("#stats").innerHTML = [
            statCard("Requisições no período", formatNumber(metrics.requisicoes), `${data.periodo_dias} dias de atividade`, icons.pulse),
            statCard("Requisições hoje", formatNumber(metrics.requisicoes_hoje), "Desde a meia-noite", icons.search),
            statCard("Latência média", formatDuration(metrics.latencia_media_ms), `P95: ${formatDuration(metrics.latencia_p95_ms)}`, icons.clock),
            statCard("Resultados retornados", formatNumber(metrics.resultados), "Soma da auditoria no período", icons.layers),
        ].join("");
        renderVolumeChart(data.serie_diaria, data.periodo_dias);
        renderOperations(data.operacoes);
        renderRanking(data.aplicacoes_top);
        renderLatency(metrics);
        renderRecent(data.recentes);
    }

    function renderVolumeChart(series, days) {
        const host = $("#volume-chart");
        if (!series.length) {
            host.innerHTML = '<div class="chart-empty">Ainda não há requisições registradas neste período.</div>';
            return;
        }
        const byDate = new Map(series.map((item) => [item.dia, item]));
        const today = new Date();
        const completeSeries = Array.from({ length: days }, (_, index) => {
            const date = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate() - (days - index - 1)));
            const day = date.toISOString().slice(0, 10);
            return byDate.get(day) || { dia: day, requisicoes: 0, latencia_media_ms: 0 };
        });
        series = completeSeries;
        const values = series.map((item) => Number(item.requisicoes));
        const latencies = series.map((item) => Number(item.latencia_media_ms));
        const width = 620;
        const height = 196;
        const left = 34;
        const right = 12;
        const top = 12;
        const bottom = 27;
        const chartWidth = width - left - right;
        const chartHeight = height - top - bottom;
        const maxRequests = Math.max(...values, 1);
        const maxLatency = Math.max(...latencies, 1);
        const x = (index) => left + (series.length === 1 ? chartWidth / 2 : (index / (series.length - 1)) * chartWidth);
        const requestY = (value) => top + chartHeight - (value / maxRequests) * chartHeight;
        const latencyY = (value) => top + chartHeight - (value / maxLatency) * chartHeight;
        const requestPoints = values.map((value, index) => `${x(index)},${requestY(value)}`).join(" ");
        const latencyPoints = latencies.map((value, index) => `${x(index)},${latencyY(value)}`).join(" ");
        const area = `${left},${top + chartHeight} ${requestPoints} ${left + chartWidth},${top + chartHeight}`;
        const step = Math.max(1, Math.ceil(series.length / 6));
        const labels = series.map((item, index) => (
            index % step === 0 || index === series.length - 1
                ? `<text x="${x(index)}" y="${height - 5}" text-anchor="middle" fill="#9aa49d" font-size="9">${new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short" }).format(new Date(`${item.dia}T12:00:00`))}</text>`
                : ""
        )).join("");
        const grid = [0, 1, 2, 3].map((index) => {
            const y = top + (chartHeight / 3) * index;
            return `<line x1="${left}" y1="${y}" x2="${width - right}" y2="${y}" stroke="#edf0ed" stroke-width="1"/>`;
        }).join("");
        const dots = series.map((item, index) => `<circle cx="${x(index)}" cy="${requestY(values[index])}" r="3.1" fill="#fff" stroke="#43845e" stroke-width="2"><title>${escapeHtml(item.dia)} · ${formatNumber(item.requisicoes)} requisições · ${formatDuration(item.latencia_media_ms)}</title></circle>`).join("");
        host.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Gráfico diário de requisições e latência média nos últimos ${days} dias">
            ${grid}<polygon points="${area}" fill="#eaf4ee" opacity=".8"/>
            <polyline points="${requestPoints}" fill="none" stroke="#43845e" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
            <polyline points="${latencyPoints}" fill="none" stroke="#d98a47" stroke-width="2" stroke-dasharray="4 4" stroke-linecap="round" stroke-linejoin="round"/>
            ${dots}${labels}
        </svg>`;
    }

    function renderOperations(operations) {
        const host = $("#operation-list");
        if (!operations.length) {
            host.innerHTML = '<div class="chart-empty">Sem operações para exibir.</div>';
            return;
        }
        const max = Math.max(...operations.map((item) => Number(item.total)), 1);
        host.innerHTML = operations.map((item) => `<div class="operation-row">
            <span class="operation-name" title="${escapeHtml(item.nome)}">${escapeHtml(item.nome)}</span>
            <span class="bar-track"><span class="bar-fill" style="display:block;width:${Math.max(2, (item.total / max) * 100)}%"></span></span>
            <span class="bar-number">${formatNumber(item.total)}</span>
        </div>`).join("");
    }

    function renderRanking(applications) {
        const host = $("#ranking-list");
        if (!applications.length) {
            host.innerHTML = '<div class="chart-empty">Sem aplicações com atividade neste período.</div>';
            return;
        }
        const max = Math.max(...applications.map((item) => Number(item.requisicoes)), 1);
        host.innerHTML = applications.map((item) => `<div class="ranking-row">
            <span class="ranking-name" title="${escapeHtml(item.nome)}">${escapeHtml(item.nome)}</span>
            <span class="bar-track"><span class="bar-fill" style="display:block;width:${Math.max(2, (item.requisicoes / max) * 100)}%"></span></span>
            <span class="bar-number">${formatNumber(item.requisicoes)}</span>
        </div>`).join("");
    }

    function renderLatency(metrics) {
        const max = Math.max(Number(metrics.latencia_p95_ms), 1);
        const averageWidth = Math.min(100, (Number(metrics.latencia_media_ms) / max) * 100);
        $("#latency-summary").innerHTML = `<div style="display:grid;gap:15px;padding:2px 0 7px">
            <div style="display:flex;align-items:center;justify-content:space-between;color:#68756d;font-size:11px"><span>Latência média</span><strong style="color:#26372d;font-size:13px">${formatDuration(metrics.latencia_media_ms)}</strong></div>
            <div class="bar-track" style="height:8px"><span class="bar-fill" style="display:block;width:${averageWidth}%"></span></div>
            <div style="display:flex;align-items:center;justify-content:space-between;color:#68756d;font-size:11px"><span>Percentil 95</span><strong style="color:#26372d;font-size:13px">${formatDuration(metrics.latencia_p95_ms)}</strong></div>
            <div class="bar-track" style="height:8px"><span class="bar-fill" style="display:block;width:100%;background:#d98a47"></span></div>
            <div style="display:flex;gap:18px;flex-wrap:wrap;padding-top:5px;color:#829087;font-size:10px">
                <span><b style="color:#24372c">${formatNumber(metrics.aplicacoes_ativas)}</b> aplicações</span>
                <span><b style="color:#24372c">${formatNumber(metrics.chaves_ativas)}</b> chaves ativas</span>
                <span><b style="color:#24372c">${formatNumber(metrics.modelos_ativos)}</b> modelos ativos</span>
            </div>
        </div>`;
    }

    function renderRecent(events) {
        const host = $("#recent-table");
        if (!events.length) {
            host.innerHTML = '<div class="chart-empty">A tabela de auditoria ainda não possui registros.</div>';
            return;
        }
        host.innerHTML = `<table><thead><tr><th>Aplicação</th><th>Operação</th><th>Latência</th><th>Resultados</th><th>Data</th></tr></thead><tbody>
            ${events.map((event) => `<tr>
                <td><span class="table-strong">${escapeHtml(event.aplicacao_nome)}</span></td>
                <td><span class="badge">${escapeHtml(event.operacao)}</span></td>
                <td class="mono">${formatDuration(event.tempo_execucao_ms)}</td>
                <td>${formatNumber(event.quantidade_resultados)}</td>
                <td>${formatDate(event.criado_em, true)}</td>
            </tr>`).join("")}
        </tbody></table>`;
    }

    function renderApplications() {
        const host = $("#applications-list");
        if (!state.applications.length) {
            host.innerHTML = '<div class="empty-state"><strong>Nenhuma aplicação cadastrada</strong>Crie a primeira aplicação para começar a organizar seus tenants.</div>';
            return;
        }
        host.innerHTML = state.applications.map((application) => `<article class="list-card">
            <div class="card-title-row"><div><div class="card-name">${escapeHtml(application.nome)}</div><div class="card-subtitle">Criada em ${formatDate(application.criado_em)}</div></div><span class="badge green">Ativa</span></div>
            <div class="card-meta"><span class="badge mono" title="${escapeHtml(application.id)}">${escapeHtml(application.id)}</span></div>
            <div class="card-actions">
                <button class="button small" data-action="edit-application" data-id="${escapeHtml(application.id)}">Renomear</button>
                <button class="button small danger" data-action="delete-application" data-id="${escapeHtml(application.id)}">Excluir</button>
            </div>
        </article>`).join("");
    }

    function renderKeys() {
        const host = $("#keys-list");
        if (!state.keys.length) {
            host.innerHTML = '<div class="empty-state"><strong>Nenhuma chave de API</strong>Gere uma chave para permitir que uma aplicação acesse a API.</div>';
            return;
        }
        state.keys.sort((a, b) => new Date(b.criado_em) - new Date(a.criado_em));
        host.innerHTML = state.keys.map((key) => `<article class="list-card">
            <div class="card-title-row"><div><div class="card-name">${escapeHtml(key.nome)}</div><div class="card-subtitle">${escapeHtml(key.aplicacao_nome)}</div></div><span class="badge ${key.revogada ? "red" : "green"}">${key.revogada ? "Revogada" : "Ativa"}</span></div>
            <div class="card-meta"><span class="badge mono" title="${escapeHtml(key.id)}">ID ${escapeHtml(key.id)}</span><span class="badge">Criada em ${formatDate(key.criado_em)}</span></div>
            <div class="card-actions">${key.revogada ? "" : `<button class="button small danger" data-action="revoke-key" data-id="${escapeHtml(key.id)}">Revogar chave</button>`}</div>
        </article>`).join("");
    }

    function renderModels() {
        const host = $("#models-list");
        if (!state.models.length) {
            host.innerHTML = '<div class="empty-state"><strong>Nenhum modelo cadastrado</strong>Cadastre um modelo de embedding para associá-lo às coleções.</div>';
            return;
        }
        host.innerHTML = state.models.map((model) => `<article class="list-card">
            <div class="card-title-row"><div><div class="card-name">${escapeHtml(model.nome)}</div><div class="card-subtitle">${escapeHtml(model.provedor)} · ${formatNumber(model.dimensoes)} dimensões</div></div><span class="badge ${model.ativo ? "green" : "red"}">${model.ativo ? "Ativo" : "Inativo"}</span></div>
            <div class="card-meta"><span class="badge mono">${escapeHtml(model.id)}</span><span class="badge">${escapeHtml(model.metrica_distancia)}</span>${model.identificador_repositorio ? `<span class="badge">${escapeHtml(model.identificador_repositorio)}</span>` : ""}</div>
            <div class="card-actions"><button class="button small" data-action="edit-model" data-id="${escapeHtml(model.id)}">Editar</button><button class="button small" data-action="toggle-model" data-id="${escapeHtml(model.id)}">${model.ativo ? "Desativar" : "Ativar"}</button></div>
        </article>`).join("");
    }

    async function handleFormSubmission(form, submit) {
        const errorElement = $("[data-form-error]", form);
        if (errorElement) clearError(errorElement);
        if (!form.reportValidity()) {
            if (errorElement) showError(errorElement, "Revise os campos obrigatórios antes de continuar.");
            return;
        }

        const submitLabel = submit?.textContent;
        if (submit) {
            submit.disabled = true;
            submit.textContent = "Salvando…";
        }
        try {
            const formId = form.getAttribute("id");
            if (formId === "application-form") await submitApplication(form);
            if (formId === "key-form") await submitKey(form);
            if (formId === "model-form") await submitModel(form);
        } catch (error) {
            console.error("Erro na submissão do formulário:", error);
            if (!handleAuthError(error)) {
                if (errorElement) showError(errorElement, error.message || "Não foi possível concluir a operação.");
                else showToast(error.message || "Não foi possível concluir a operação.");
            }
            if (submit) {
                submit.disabled = false;
                submit.textContent = submitLabel;
            }
        }
    }

    function openDialog(title, description, formMarkup) {
        $("#dialog-content").innerHTML = `<div class="dialog-head"><div><h2>${title}</h2><p>${description}</p></div><button class="close-button" type="button" data-action="close-dialog" aria-label="Fechar">×</button></div>${formMarkup}`;
        const form = $("#dialog-content form");
        if (form) {
            form.noValidate = true;
            form.addEventListener("submit", (event) => {
                event.preventDefault();
                event.stopPropagation();
                const submit = form.querySelector('button[type="submit"]') || $("#model-submit", form);
                void handleFormSubmission(form, submit);
                return false;
            });
        }
        $("#management-dialog").showModal();
    }

    function closeDialog() {
        $("#management-dialog").close();
        $("#dialog-content").innerHTML = "";
    }

    function openApplicationForm(application = null) {
        const editing = Boolean(application);
        openDialog(editing ? "Renomear aplicação" : "Nova aplicação", "Os dados da aplicação podem ser alterados posteriormente.", `
            <form id="application-form" method="POST" action="#" data-id="${editing ? escapeHtml(application.id) : ""}">
                <div class="error-banner" data-form-error role="alert"></div>
                <div class="field"><label for="application-name">Nome da aplicação</label><input id="application-name" name="nome" maxlength="100" required value="${editing ? escapeHtml(application.nome) : ""}" placeholder="Ex.: Catálogo de produtos"></div>
                <div class="dialog-footer"><button type="button" class="button" data-action="close-dialog">Cancelar</button><button class="button primary" type="submit">${editing ? "Salvar alterações" : "Criar aplicação"}</button></div>
            </form>`);
        $("#application-name").focus();
    }

    function openKeyForm() {
        if (!state.applications.length) {
            showToast("Cadastre uma aplicação antes de gerar uma chave.");
            return;
        }
        openDialog("Gerar chave de API", "Escolha a aplicação e identifique o uso desta credencial.", `
            <form id="key-form" method="POST" action="#">
                <div class="error-banner" data-form-error role="alert"></div>
                <div class="form-grid">
                    <div class="field full"><label for="key-application">Aplicação</label><select id="key-application" name="aplicacao_id" required>${state.applications.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.nome)}</option>`).join("")}</select></div>
                    <div class="field full"><label for="key-name">Nome da chave</label><input id="key-name" name="nome" maxlength="100" required placeholder="Ex.: Produção · backend"></div>
                </div>
                <div class="dialog-footer"><button type="button" class="button" data-action="close-dialog">Cancelar</button><button class="button primary" type="submit">Gerar chave</button></div>
            </form>`);
        $("#key-name").focus();
    }

    function openModelForm(model = null) {
        const editing = Boolean(model);
        openDialog(editing ? "Editar modelo" : "Novo modelo", editing ? "Atualize os dados cadastrais do modelo." : "Informe os dados do modelo de embedding.", `
            <form id="model-form" method="POST" action="#" data-id="${editing ? escapeHtml(model.id) : ""}">
                <div class="error-banner" data-form-error role="alert"></div>
                <div class="form-grid">
                    <div class="field full"><label for="model-id">Identificador</label><input id="model-id" name="id" maxlength="50" required ${editing ? `value="${escapeHtml(model.id)}" readonly` : 'placeholder="Ex.: bge-m3"'}></div>
                    <div class="field"><label for="model-name">Nome</label><input id="model-name" name="nome" maxlength="100" required value="${editing ? escapeHtml(model.nome) : ""}"></div>
                    <div class="field"><label for="model-provider">Provedor</label><input id="model-provider" name="provedor" maxlength="50" required value="${editing ? escapeHtml(model.provedor) : ""}"></div>
                    ${editing ? "" : `<div class="field"><label for="model-dimensions">Dimensões</label><select id="model-dimensions" name="dimensoes" required><option value="512">512</option><option value="768" selected>768</option><option value="1024">1024</option><option value="1536">1536</option><option value="3072">3072</option></select></div>`}
                    <div class="field"><label for="model-distance">Métrica de distância</label><select id="model-distance" name="metrica_distancia" required><option value="cosine">Cosseno</option><option value="l2">L2</option><option value="ip">Produto interno</option></select></div>
                    <div class="field ${editing ? "full" : ""}"><label for="model-repository">Repositório (opcional)</label><input id="model-repository" name="identificador_repositorio" maxlength="255" value="${editing ? escapeHtml(model.identificador_repositorio || "") : ""}" placeholder="Organização/modelo"></div>
                </div>
                <div class="dialog-footer"><button type="button" class="button" data-action="close-dialog">Cancelar</button><button class="button primary" id="model-submit" type="submit">${editing ? "Salvar alterações" : "Cadastrar modelo"}</button></div>
            </form>`);
        if (!editing) $("#model-dimensions").value = "768";
        $("#model-distance").value = editing ? model.metrica_distancia : "cosine";
        $("#model-id").focus();
    }

    async function submitApplication(form) {
        const id = form.dataset.id;
        const body = JSON.stringify({ nome: new FormData(form).get("nome") });
        await api(id ? `/aplicacoes/${encodeURIComponent(id)}` : "/aplicacoes/", {
            method: id ? "PATCH" : "POST",
            body,
        });
        closeDialog();
        showToast(id ? "Aplicação atualizada." : "Aplicação criada.");
        await loadApplications();
        if (state.activeView === "keys") await loadKeys();
    }

    async function submitKey(form) {
        const values = Object.fromEntries(new FormData(form).entries());
        const result = await api("/aplicacoes/chaves", { method: "POST", body: JSON.stringify(values) });
        state.keys = [];
        $("#dialog-content").innerHTML = `<div class="dialog-head"><div><h2>Chave criada</h2><p>Copie e guarde a credencial em um local seguro.</p></div><button class="close-button" type="button" data-action="close-dialog" aria-label="Fechar">×</button></div>
            <div class="secret-box mono" id="created-secret">${escapeHtml(result.chave_api)}</div>
            <div class="secret-warning">Esta chave será exibida apenas agora. Depois de fechar esta janela, ela não poderá ser recuperada.</div>
            <div class="dialog-footer"><button class="button" type="button" data-action="copy-secret">Copiar chave</button><button class="button primary" type="button" data-action="close-dialog">Concluído</button></div>`;
        await loadKeys();
    }

    async function submitModel(form) {
        const values = Object.fromEntries(new FormData(form).entries());
        const id = form.dataset.id;

        if (!id) {
            values.dimensoes = Number(values.dimensoes);
        }

        if (!values.identificador_repositorio) {
            values.identificador_repositorio = null;
        }

        await api(id ? `/modelos/${encodeURIComponent(id)}` : "/modelos/", {
            method: id ? "PATCH" : "POST",
            body: JSON.stringify(values),
        });
        closeDialog();
        showToast(id ? "Modelo atualizado." : "Modelo cadastrado.");
        await loadModels();
    }

    async function onAction(action, button) {
        const id = button.dataset.id;
        if (action === "close-dialog") closeDialog();
        if (action === "refresh-dashboard") await loadDashboard();
        if (action === "new-application") openApplicationForm();
        if (action === "new-key") {
            if (!state.applications.length) await loadApplications();
            openKeyForm();
        }
        if (action === "new-model") openModelForm();
        if (action === "edit-application") openApplicationForm(state.applications.find((item) => item.id === id));
        if (action === "edit-model") openModelForm(state.models.find((item) => item.id === id));
        if (action === "delete-application") {
            const application = state.applications.find((item) => item.id === id);
            if (application && window.confirm(`Excluir "${application.nome}" e todos os recursos vinculados? Esta ação não pode ser desfeita.`)) {
                try {
                    await api(`/aplicacoes/${encodeURIComponent(id)}`, { method: "DELETE" });
                    showToast("Aplicação e recursos vinculados excluídos.");
                    await loadApplications();
                } catch (error) {
                    if (!handleAuthError(error)) showError($("#applications-error"), error.message);
                }
            }
        }
        if (action === "revoke-key") {
            const key = state.keys.find((item) => item.id === id);
            if (key && window.confirm(`Revogar a chave "${key.nome}"? A credencial deixará de funcionar imediatamente.`)) {
                try {
                    await api(`/aplicacoes/chaves/${encodeURIComponent(id)}/revogar`, { method: "PATCH" });
                    showToast("Chave revogada.");
                    await loadKeys();
                } catch (error) {
                    if (!handleAuthError(error)) showError($("#keys-error"), error.message);
                }
            }
        }
        if (action === "toggle-model") {
            const model = state.models.find((item) => item.id === id);
            if (model) {
                try {
                    await api(`/modelos/${encodeURIComponent(id)}`, {
                        method: "PATCH",
                        body: JSON.stringify({ ativo: !model.ativo }),
                    });
                    showToast(model.ativo ? "Modelo desativado." : "Modelo ativado.");
                    await loadModels();
                } catch (error) {
                    if (!handleAuthError(error)) showError($("#models-error"), error.message);
                }
            }
        }
        if (action === "copy-secret") {
            const secret = $("#created-secret")?.textContent;
            if (secret) {
                try {
                    await navigator.clipboard.writeText(secret);
                    showToast("Chave copiada.");
                } catch {
                    showToast("Não foi possível copiar automaticamente; selecione e copie a chave.");
                }
            }
        }
    }

    async function connectWithKey(key) {
        state.key = key.trim();
        try {
            await api("/admin/analytics?dias=7");
            sessionStorage.setItem("caborer_admin_key", state.key);
            $("#auth-screen").classList.add("hidden");
            $("#app-shell").classList.remove("hidden");
            clearError($("#auth-error"));
            await loadDashboard();
        } catch (error) {
            if (error instanceof ApiError && error.status === 403) {
                state.key = "";
                sessionStorage.removeItem("caborer_admin_key");
                showError($("#auth-error"), "A chave não foi aceita. Confira a configuração ADMIN_KEY e tente novamente.");
                $("#admin-key").value = "";
            } else {
                sessionStorage.setItem("caborer_admin_key", state.key);
                $("#auth-screen").classList.add("hidden");
                $("#app-shell").classList.remove("hidden");
                await loadDashboard();
                if (error.message) showError($("#dashboard-error"), error.message);
            }
        }
    }

    $("#auth-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = $("#auth-submit");
        button.disabled = true;
        button.textContent = "Validando…";
        await connectWithKey($("#admin-key").value);
        button.disabled = false;
        button.textContent = "Entrar no painel";
    });

    $("#logout-button").addEventListener("click", () => {
        state.key = "";
        sessionStorage.removeItem("caborer_admin_key");
        $("#app-shell").classList.add("hidden");
        $("#auth-screen").classList.add("hidden");
        $("#admin-key").value = "";
        $("#admin-key").focus();
    });

    $("#period-select").addEventListener("change", loadDashboard);

    document.addEventListener("click", async (event) => {
        const nav = event.target.closest("[data-view]");
        if (nav) {
            await loadView(nav.dataset.view);
            return;
        }
        const button = event.target.closest("[data-action]");
        if (button) {
            await onAction(button.dataset.action, button);
        }
    });

    $("#management-dialog").addEventListener("cancel", (event) => {
        event.preventDefault();
    });

    if (state.key) {
        $("#admin-key").value = state.key;
        connectWithKey(state.key);
    }
})();