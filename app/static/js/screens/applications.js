
export function criarModuloAplicacoes({
    state,
    api,
    $,
    escapeHtml,
    formatDate,
    clearError,
    handleAuthError,
    showError,
}) {
    async function loadApplications() {
        const errorElement = $("#applications-error");
        clearError(errorElement);

        try {
            state.applications = await api(
                "/aplicacoes/?limite=100&deslocamento=0"
            );

            renderApplications();

        } catch (error) {
            if (!handleAuthError(error)) {
                showError(
                    errorElement,
                    error.message || "Não foi possível carregar as aplicações."
                );
            }
        }
    }

    function renderApplications() {
        const host = $("#applications-list");

        if (!state.applications.length) {
            host.innerHTML = `
                <div class="empty-state">
                    <strong>Nenhuma aplicação cadastrada</strong>
                    Crie a primeira aplicação para começar a organizar seus tenants.
                </div>
            `;
            return;
        }

        host.innerHTML = state.applications.map((application) => `
            <article class="list-card">
                <div class="card-title-row">
                    <div>
                        <div class="card-name">${escapeHtml(application.nome)}</div>
                        <div class="card-subtitle">
                            Criada em ${formatDate(application.criado_em)}
                        </div>
                    </div>

                    <span class="badge ${application.ativa ? "green" : "red"}">
                        ${application.ativa ? "Ativa" : "Suspensa"}
                    </span>
                </div>

                <div class="card-meta">
                    <span class="badge mono" title="${escapeHtml(application.id)}">
                        ${escapeHtml(application.id)}
                    </span>
                </div>

                <div class="card-actions">
                    <button
                        class="button small"
                        data-action="application-details"
                        data-id="${escapeHtml(application.id)}"
                    >
                        Detalhes
                    </button>

                    <button
                        class="button small"
                        data-action="edit-application"
                        data-id="${escapeHtml(application.id)}"
                    >
                        Renomear
                    </button>

                    <button
                        class="button small ${application.ativa ? "danger" : ""}"
                        data-action="toggle-application"
                        data-id="${escapeHtml(application.id)}"
                    >
                        ${application.ativa ? "Suspender" : "Reativar"}
                    </button>

                    <button
                        class="button small danger"
                        data-action="delete-application"
                        data-id="${escapeHtml(application.id)}"
                    >
                        Excluir
                    </button>
                </div>
            </article>
        `).join("");
    }

    return {
        loadApplications,
        renderApplications,
    };
}
