export function criarModuloColecoes({
    state,
    api,
    $,
    escapeHtml,
    formatNumber,
    formatDate,
    clearError,
    handleAuthError,
    showError,
}) {
    async function loadCollections() {
        const errorElement = $("#collections-error");
        clearError(errorElement);

        const host = $("#collections-list");
        host.innerHTML =
            '<tr><td colspan="7" class="loading">Carregando coleções…</td></tr>';

        try {
            const [applications, models] = await Promise.all([
                state.applications.length
                    ? Promise.resolve(state.applications)
                    : api("/aplicacoes/?limite=100&deslocamento=0"),

                state.models.length
                    ? Promise.resolve(state.models)
                    : api("/modelos/?limite=100&deslocamento=0"),
            ]);

            state.applications = applications;
            state.models = models;

            const applicationFilter = $("#collection-application-filter");
            const modelFilter = $("#collection-model-filter");

            const selectedApplication = applicationFilter.value;
            const selectedModel = modelFilter.value;

            applicationFilter.innerHTML =
                '<option value="">Todas as aplicações</option>' +
                applications.map((item) =>
                    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.nome)}</option>`
                ).join("");

            modelFilter.innerHTML =
                '<option value="">Todos os modelos</option>' +
                models.map((item) =>
                    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.nome)} · ${formatNumber(item.dimensoes)} dim.</option>`
                ).join("");

            applicationFilter.value = selectedApplication;
            modelFilter.value = selectedModel;

            const params = new URLSearchParams({
                limite: "1000",
                deslocamento: "0",
            });

            if (applicationFilter.value) {
                params.set("aplicacao_id", applicationFilter.value);
            }

            if (modelFilter.value) {
                params.set("modelo_embedding_id", modelFilter.value);
            }

            state.collections = await api(
                `/admin/colecoes?${params.toString()}`
            );

            renderCollections();

        } catch (error) {
            host.innerHTML =
                '<tr><td colspan="7" class="loading">Não foi possível carregar as coleções.</td></tr>';

            if (!handleAuthError(error)) {
                showError(
                    errorElement,
                    error.message || "Não foi possível carregar as coleções."
                );
            }
        }
    }

    function renderCollections() {
        const host = $("#collections-list");
        const summary = $("#collections-summary");

        summary.textContent =
            `${formatNumber(state.collections.length)} coleção(ões) nesta visualização`;

        if (!state.collections.length) {
            host.innerHTML = `
                <tr>
                    <td colspan="7">
                        <div class="empty-state">
                            <strong>Nenhuma coleção encontrada</strong>
                            Não há coleções para os filtros selecionados.
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        host.innerHTML = state.collections.map((collection) => `
            <tr>
                <td>
                    <div class="table-strong">
                        ${escapeHtml(collection.nome)}
                    </div>
                    <div class="card-subtitle mono">
                        ${escapeHtml(collection.id)}
                    </div>
                </td>

                <td>
                    <div class="table-strong">
                        ${escapeHtml(collection.aplicacao_nome)}
                    </div>
                    <div class="card-subtitle">
                        ${collection.aplicacao_ativa ? "Aplicação ativa" : "Aplicação inativa"}
                    </div>
                </td>

                <td>
                    <div class="table-strong">
                        ${escapeHtml(collection.modelo_nome)}
                    </div>
                    <div class="card-subtitle">
                        ${escapeHtml(collection.modelo_embedding_id)}
                        · ${formatNumber(collection.modelo_dimensoes)} dim.
                        · ${escapeHtml(collection.metrica_distancia)}
                    </div>
                </td>

                <td class="table-strong">
                    ${formatNumber(collection.quantidade_embeddings)}
                </td>

                <td>
                    <span class="badge ${collection.publica ? "green" : ""}">
                        ${collection.publica ? "Pública" : "Privada"}
                    </span>
                </td>

                <td>${formatDate(collection.criado_em)}</td>

                <td>
                    <div class="card-actions">
                        <button
                            class="button small"
                            data-action="edit-collection"
                            data-id="${escapeHtml(collection.id)}"
                        >
                            Editar
                        </button>

                        <button
                            class="button small danger"
                            data-action="delete-collection"
                            data-id="${escapeHtml(collection.id)}"
                        >
                            Excluir
                        </button>
                    </div>
                </td>
            </tr>
        `).join("");
    }

    return {
        loadCollections,
        renderCollections,
    };
}