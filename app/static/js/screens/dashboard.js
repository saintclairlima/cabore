
export function criarModuloDashboard({
    state,
    api,
    $,
    escapeHtml,
    clearError,
    handleAuthError,
    showError,
    formatNumber,
    formatDuration,
    formatDate,
    statCard,
    renderVolumeChart,
    renderOperations,
}) {
    const icons = {
        pulse: '<svg viewBox="0 0 24 24" fill="none"><path d="M3 12h4l3-8 4 16 3-8h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        clock: '<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.8"/><path d="M12 7v5l3 2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
        layers: '<svg viewBox="0 0 24 24" fill="none"><path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>',
        search: '<svg viewBox="0 0 24 24" fill="none"><circle cx="10.8" cy="10.8" r="6.5" stroke="currentColor" stroke-width="1.8"/><path d="m16 16 4.5 4.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    };

    async function loadDashboard() {
        const errorElement = $("#dashboard-error");
        clearError(errorElement);

        try {
            const days = $("#period-select").value;
            state.analytics = await api(`/admin/analytics?dias=${days}`);
            renderDashboard(state.analytics);
        } catch (error) {
            if (!handleAuthError(error)) {
                showError(
                    errorElement,
                    error.message || "Não foi possível carregar a auditoria."
                );
            }
        }
    }

    function renderDashboard(data) {
        const metrics = data.metricas;

        $("#stats").innerHTML = [
            statCard(
                "Requisições no período",
                formatNumber(metrics.requisicoes),
                `${data.periodo_dias} dias de atividade`,
                icons.pulse
            ),
            statCard(
                "Requisições hoje",
                formatNumber(metrics.requisicoes_hoje),
                "Desde a meia-noite",
                icons.search
            ),
            statCard(
                "Latência média",
                formatDuration(metrics.latencia_media_ms),
                `P95: ${formatDuration(metrics.latencia_p95_ms)}`,
                icons.clock
            ),
            statCard(
                "Resultados retornados",
                formatNumber(metrics.resultados),
                "Soma da auditoria no período",
                icons.layers
            ),
        ].join("");

        renderVolumeChart(data.serie_diaria, data.periodo_dias);
        renderOperations(data.operacoes);
        renderRanking(data.aplicacoes_top);
        renderLatency(metrics);
        renderRecent(data.recentes);
    }

    function renderRanking(applications) {
        const host = $("#ranking-list");

        if (!applications.length) {
            host.innerHTML =
                '<div class="chart-empty">Sem aplicações com atividade neste período.</div>';
            return;
        }

        const max = Math.max(
            ...applications.map((item) => Number(item.requisicoes)),
            1
        );

        host.innerHTML = applications.map((item) => `
            <div class="ranking-row">
                <span class="ranking-name" title="${escapeHtml(item.nome)}">
                    ${escapeHtml(item.nome)}
                </span>
                <span class="bar-track">
                    <span class="bar-fill" style="display:block;width:${Math.max(2, (item.requisicoes / max) * 100)}%"></span>
                </span>
                <span class="bar-number">${formatNumber(item.requisicoes)}</span>
            </div>
        `).join("");
    }

    function renderLatency(metrics) {
        const max = Math.max(Number(metrics.latencia_p95_ms), 1);
        const averageWidth = Math.min(
            100,
            (Number(metrics.latencia_media_ms) / max) * 100
        );

        $("#latency-summary").innerHTML = `
            <div style="display:grid;gap:15px;padding:2px 0 7px">
                <div style="display:flex;align-items:center;justify-content:space-between;color:#68756d;font-size:11px">
                    <span>Latência média</span>
                    <strong style="color:#26372d;font-size:13px">${formatDuration(metrics.latencia_media_ms)}</strong>
                </div>
                <div class="bar-track" style="height:8px">
                    <span class="bar-fill" style="display:block;width:${averageWidth}%"></span>
                </div>
                <div style="display:flex;align-items:center;justify-content:space-between;color:#68756d;font-size:11px">
                    <span>Percentil 95</span>
                    <strong style="color:#26372d;font-size:13px">${formatDuration(metrics.latencia_p95_ms)}</strong>
                </div>
                <div class="bar-track" style="height:8px">
                    <span class="bar-fill" style="display:block;width:100%;background:#d98a47"></span>
                </div>
                <div style="display:flex;gap:18px;flex-wrap:wrap;padding-top:5px;color:#829087;font-size:10px">
                    <span><b style="color:#24372c">${formatNumber(metrics.aplicacoes_ativas)}</b> aplicações</span>
                    <span><b style="color:#24372c">${formatNumber(metrics.chaves_ativas)}</b> chaves ativas</span>
                    <span><b style="color:#24372c">${formatNumber(metrics.modelos_ativos)}</b> modelos ativos</span>
                </div>
            </div>
        `;
    }

    function renderRecent(events) {
        const host = $("#recent-table");

        if (!events.length) {
            host.innerHTML =
                '<div class="chart-empty">A tabela de auditoria ainda não possui registros.</div>';
            return;
        }

        host.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Aplicação</th>
                        <th>Operação</th>
                        <th>Latência</th>
                        <th>Resultados</th>
                        <th>Data</th>
                    </tr>
                </thead>
                <tbody>
                    ${events.map((event) => `
                        <tr>
                            <td>
                                <span class="table-strong">
                                    ${escapeHtml(event.aplicacao_nome)}
                                </span>
                            </td>
                            <td>
                                <span class="badge">
                                    ${escapeHtml(event.operacao)}
                                </span>
                            </td>
                            <td class="mono">
                                ${formatDuration(event.tempo_execucao_ms)}
                            </td>
                            <td>${formatNumber(event.quantidade_resultados)}</td>
                            <td>${formatDate(event.criado_em, true)}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        `;
    }

    return {
        loadDashboard,
        renderDashboard,
    };
}
