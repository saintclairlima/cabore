export function criarModuloChaves({
    state,
    api,
    $,
    escapeHtml,
    formatDate,
    clearError,
    handleAuthError,
    showError,
}) {
    async function loadKeys() {
        const errorElement = $("#keys-error");
        clearError(errorElement);

        try {
            if (!state.applications.length) {
                state.applications = await api(
                    "/aplicacoes/?limite=100&deslocamento=0"
                );
            }

            const groupedKeys = await Promise.all(
                state.applications.map(async (application) => {
                    const keys = await api(
                        `/aplicacoes/${encodeURIComponent(application.id)}/chaves`
                    );

                    return keys.map((key) => ({
                        ...key,
                        aplicacao_nome: application.nome,
                    }));
                })
            );

            state.keys = groupedKeys.flat();
            renderKeys();

        } catch (error) {
            if (!handleAuthError(error)) {
                showError(
                    errorElement,
                    error.message || "Não foi possível carregar as chaves."
                );
            }
        }
    }

    function renderKeys() {
        const host = $("#keys-list");

        if (!state.keys.length) {
            host.innerHTML = `
                <div class="empty-state">
                    <strong>Nenhuma chave de API</strong>
                    Gere uma chave para permitir que uma aplicação acesse a API.
                </div>
            `;
            return;
        }

        state.keys.sort(
            (a, b) => new Date(b.criado_em) - new Date(a.criado_em)
        );

        host.innerHTML = state.keys.map((key) => `
            <article class="list-card">
                <div class="card-title-row">
                    <div>
                        <div class="card-name">${escapeHtml(key.nome)}</div>
                        <div class="card-subtitle">
                            ${escapeHtml(key.aplicacao_nome)}
                        </div>
                    </div>

                    <span class="badge ${key.revogada ? "red" : "green"}">
                        ${key.revogada ? "Revogada" : "Ativa"}
                    </span>
                </div>

                <div class="card-meta">
                    <span class="badge mono" title="${escapeHtml(key.id)}">
                        ID ${escapeHtml(key.id)}
                    </span>

                    <span class="badge">
                        Criada em ${formatDate(key.criado_em)}
                    </span>
                </div>

                <div class="card-actions">
                    ${key.revogada ? "" : `
                        <button
                            class="button small danger"
                            data-action="revoke-key"
                            data-id="${escapeHtml(key.id)}"
                        >
                            Revogar chave
                        </button>
                    `}
                </div>
            </article>
        `).join("");
    }

    return {
        loadKeys,
        renderKeys,
    };
}