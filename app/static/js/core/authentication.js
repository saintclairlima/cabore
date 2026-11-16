
export function criarModuloAutenticacao({
    state,
    api,
    ApiError,
    $,
    showError,
    clearError,
    loadDashboard,
}) {
    async function connectWithKey(key) {
        state.key = key.trim();

        try {
            await api("/admin/analytics?dias=7");

            sessionStorage.setItem("cabore_admin_key", state.key);

            $("#auth-screen").classList.add("hidden");
            $("#app-shell").classList.remove("hidden");

            clearError($("#auth-error"));

            await loadDashboard();
        } catch (error) {
            if (error instanceof ApiError && error.status === 403) {
                state.key = "";
                sessionStorage.removeItem("cabore_admin_key");

                showError(
                    $("#auth-error"),
                    "A chave não foi aceita. Confira a configuração ADMIN_KEY e tente novamente."
                );

                $("#admin-key").value = "";
            } else {
                sessionStorage.setItem("cabore_admin_key", state.key);

                $("#auth-screen").classList.add("hidden");
                $("#app-shell").classList.remove("hidden");

                await loadDashboard();

                if (error.message) {
                    showError($("#dashboard-error"), error.message);
                }
            }
        }
    }

    function logout() {
        state.key = "";
        sessionStorage.removeItem("cabore_admin_key");

        $("#app-shell").classList.add("hidden");
        $("#auth-screen").classList.remove("hidden");

        $("#admin-key").value = "";
        $("#admin-key").focus();
    }

    function restaurarSessao() {
        if (state.key) {
            $("#admin-key").value = state.key;
            connectWithKey(state.key);
        }
    }

    function registrarEventos() {
        $("#auth-form").addEventListener("submit", async (event) => {
            event.preventDefault();

            const button = $("#auth-submit");
            button.disabled = true;
            button.textContent = "Validando…";

            await connectWithKey($("#admin-key").value);

            button.disabled = false;
            button.textContent = "Entrar no painel";
        });

        $("#logout-button").addEventListener("click", logout);

        restaurarSessao();
    }

    return {
        connectWithKey,
        registrarEventos,
    };
}
