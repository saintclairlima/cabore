import { $, escapeHtml } from "../core/utils.js";
import { state } from "../core/state.js";
import { openDialog } from "../components/dialogs.js";
import { showToast } from "../components/notifications.js";

export function openKeyForm(handleFormSubmission) {
    if (!state.applications.length) {
        showToast("Cadastre uma aplicação antes de gerar uma chave.");
        return;
    }

    openDialog(
        "Gerar chave de API",
        "Escolha a aplicação e identifique o uso desta credencial.",
        `
        <form id="key-form" method="POST" action="#">
            <div class="error-banner" data-form-error role="alert"></div>

            <div class="form-grid">
                <div class="field full">
                    <label for="key-application">Aplicação</label>
                    <select id="key-application" name="aplicacao_id" required>
                        ${state.applications.map((item) => `
                            <option value="${escapeHtml(item.id)}">
                                ${escapeHtml(item.nome)}
                            </option>
                        `).join("")}
                    </select>
                </div>

                <div class="field full">
                    <label for="key-name">Nome da chave</label>
                    <input
                        id="key-name"
                        name="nome"
                        maxlength="100"
                        required
                        placeholder="Ex.: Produção · backend"
                    >
                </div>
            </div>

            <div class="dialog-footer">
                <button
                    type="button"
                    class="button"
                    data-action="close-dialog"
                >
                    Cancelar
                </button>

                <button class="button primary" type="submit">
                    Gerar chave
                </button>
            </div>
        </form>
        `,
        handleFormSubmission
    );

    $("#key-name").focus();
}