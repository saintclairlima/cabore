export function criarModuloModelos({
    state,
    api,
    $,
    escapeHtml,
    formatNumber,
    clearError,
    handleAuthError,
    showError,
}) {
    async function loadModels() {
        const errorElement = $("#models-error");
        clearError(errorElement);

        try {
            state.models = await api(
                "/modelos/?limite=100&deslocamento=0"
            );

            renderModels();

        } catch (error) {
            if (!handleAuthError(error)) {
                showError(
                    errorElement,
                    error.message || "Não foi possível carregar os modelos."
                );
            }
        }
    }

    function renderModels() {
        const host = $("#models-list");

        if (!state.models.length) {
            host.innerHTML = `
                <div class="empty-state">
                    <strong>Nenhum modelo cadastrado</strong>
                    Cadastre um modelo de embedding para associá-lo às coleções.
                </div>
            `;
            return;
        }

        host.innerHTML = state.models.map((model) => `
            <article class="list-card">
                <div class="card-title-row">
                    <div>
                        <div class="card-name">
                            ${escapeHtml(model.nome)}
                        </div>
                        <div class="card-subtitle">
                            ${escapeHtml(model.provedor)}
                            · ${formatNumber(model.dimensoes)} dimensões
                        </div>
                    </div>

                    <span class="badge ${model.ativo ? "green" : "red"}">
                        ${model.ativo ? "Ativo" : "Inativo"}
                    </span>
                </div>

                <div class="card-meta">
                    <span class="badge mono">
                        ${escapeHtml(model.id)}
                    </span>

                    <span class="badge">
                        ${escapeHtml(model.metrica_distancia)}
                    </span>

                    ${model.identificador_repositorio ? `
                        <span class="badge">
                            ${escapeHtml(model.identificador_repositorio)}
                        </span>
                    ` : ""}
                </div>

                <div class="card-actions">
                    <button
                        class="button small"
                        data-action="edit-model"
                        data-id="${escapeHtml(model.id)}"
                    >
                        Editar
                    </button>

                    <button
                        class="button small"
                        data-action="toggle-model"
                        data-id="${escapeHtml(model.id)}"
                    >
                        ${model.ativo ? "Desativar" : "Ativar"}
                    </button>
                </div>
            </article>
        `).join("");
    }

    return {
        loadModels,
        renderModels,
    };
}