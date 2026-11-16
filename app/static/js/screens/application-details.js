
export function criarModuloDetalhesAplicacao({
    state,
    api,
    $,
    escapeHtml,
    clearError,
    handleAuthError,
    showError,
    formatDate,
    formatNumber,
    formatDuration,
    statCard,
    icons,
    renderVolumeChart,
    renderOperations,
}) {
    async function loadApplicationDetails() {
        const errorElement = $("#application-details-error");
        clearError(errorElement);

        const id = state.selectedApplicationId;

        if (!id) {
            showError(errorElement, "Nenhuma aplicação foi selecionada.");
            return;
        }

        try {
            const dias = $("#application-detail-period").value;

            const data = await api(
                `/aplicacoes/${encodeURIComponent(id)}/detalhes?dias=${dias}`
            );

            state.applicationDetails = data;

            const application = data.aplicacao;
            const summary = data.resumo;
            const usage = data.utilizacao;

            $("#detail-application-name").textContent = application.nome;

            const statusElement = $("#detail-application-status");
            statusElement.textContent = application.ativa ? "Ativa" : "Suspensa";
            statusElement.className =
                `badge ${application.ativa ? "green" : "red"}`;

            $("#detail-application-id").textContent = application.id;
            $("#detail-application-created").textContent =
                `Criada em ${formatDate(application.criado_em)}`;

            // Recursos cadastrados
            $("#application-resource-stats").innerHTML = [
                statCard(
                    "Coleções",
                    formatNumber(summary.total_colecoes),
                    "Coleções cadastradas",
                    icons.layers
                ),
                statCard(
                    "Embeddings",
                    formatNumber(summary.total_embeddings),
                    "Embeddings armazenados",
                    icons.search
                ),
                statCard(
                    "Chaves ativas",
                    formatNumber(summary.chaves_ativas),
                    `${formatNumber(summary.chaves_revogadas)} revogadas`,
                    icons.pulse
                ),
                statCard(
                    "Total de chaves",
                    formatNumber(summary.total_chaves),
                    "Credenciais cadastradas",
                    icons.clock
                ),
            ].join("");

            // Indicadores de utilização
            $("#application-usage-stats").innerHTML = [
                statCard(
                    "Requisições",
                    formatNumber(usage.requisicoes),
                    `Nos últimos ${dias} dias`,
                    icons.pulse
                ),
                statCard(
                    "Latência média",
                    formatDuration(usage.latencia_media_ms),
                    `P95: ${formatDuration(usage.latencia_p95_ms)}`,
                    icons.clock
                ),
                statCard(
                    "Resultados retornados",
                    formatNumber(usage.resultados),
                    "Soma dos resultados da auditoria",
                    icons.layers
                ),
                statCard(
                    "Requisições recentes",
                    formatNumber(usage.requisicoes_recentes.length),
                    "Últimas chamadas registradas",
                    icons.search
                ),
            ].join("");

            // Gráficos
            renderVolumeChart(
                usage.serie_diaria,
                Number(dias),
                "#application-volume-chart"
            );

            renderOperations(
                usage.operacoes,
                "#application-operation-list"
            );

            // Demais informações
            renderApplicationCollections(data.colecoes);
            renderApplicationKeys(data.chaves_api);
            renderApplicationRecent(usage.requisicoes_recentes);

        } catch (error) {
            if (!handleAuthError(error)) {
                showError(
                    errorElement,
                    error.message || "Não foi possível carregar os detalhes da aplicação."
                );
            }
        }
    }

    function renderApplicationCollections(collections) {
        const host = $("#detail-collections-table");

        $("#detail-collections-summary").textContent =
            `${formatNumber(collections.length)} coleção(ões) associada(s)`;

        if (!collections.length) {
            host.innerHTML = `
                <div class="application-detail-empty">
                    Nenhuma coleção associada a esta aplicação.
                </div>
            `;
            return;
        }

        host.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Nome</th>
                        <th>Modelo</th>
                        <th>Dimensões</th>
                        <th>Embeddings</th>
                        <th>Visibilidade</th>
                        <th>Criada em</th>
                    </tr>
                </thead>
                <tbody>
                    ${collections.map((collection) => `
                        <tr>
                            <td>
                                <span class="table-strong">
                                    ${escapeHtml(collection.nome)}
                                </span>
                            </td>
                            <td>${escapeHtml(collection.modelo.nome)}</td>
                            <td>${formatNumber(collection.modelo.dimensoes)}</td>
                            <td>${formatNumber(collection.quantidade_embeddings)}</td>
                            <td>
                                <span class="badge ${collection.publica ? "green" : ""}">
                                    ${collection.publica ? "Pública" : "Privada"}
                                </span>
                            </td>
                            <td>${formatDate(collection.criado_em)}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        `;
    }

    function renderApplicationKeys(keys) {
        const host = $("#detail-keys-list");

        if (!keys.length) {
            host.innerHTML = `
                <div class="empty-state">
                    <strong>Nenhuma chave cadastrada</strong>
                    Esta aplicação ainda não possui chaves de API.
                </div>
            `;
            return;
        }

        host.innerHTML = keys.map((key) => `
            <article class="list-card">
                <div class="card-title-row">
                    <div>
                        <div class="card-name">${escapeHtml(key.nome)}</div>
                        <div class="card-subtitle">
                            Criada em ${formatDate(key.criado_em)}
                        </div>
                    </div>

                    <span class="badge ${key.revogada ? "red" : "green"}">
                        ${key.revogada ? "Revogada" : "Ativa"}
                    </span>
                </div>

                <div class="card-meta">
                    <span class="badge mono">
                        ID ${escapeHtml(key.id)}
                    </span>
                </div>
            </article>
        `).join("");
    }

    function renderApplicationRecent(events) {
        const host = $("#detail-recent-table");

        if (!events.length) {
            host.innerHTML = `
                <div class="application-detail-empty">
                    Nenhuma requisição registrada para esta aplicação.
                </div>
            `;
            return;
        }

        host.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Operação</th>
                        <th>Coleção</th>
                        <th>Latência</th>
                        <th>Resultados</th>
                        <th>Data</th>
                    </tr>
                </thead>
                <tbody>
                    ${events.map((event) => `
                        <tr>
                            <td>
                                <span class="badge">
                                    ${escapeHtml(event.operacao)}
                                </span>
                            </td>
                            <td>${escapeHtml(event.colecao || "—")}</td>
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
        loadApplicationDetails,
    };
}
