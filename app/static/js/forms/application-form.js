import { $, escapeHtml } from "../core/utils.js";
import { openDialog } from "../components/dialogs.js";

export function openApplicationForm(application, handleFormSubmission) {
    const editing = Boolean(application);

    openDialog(
        editing ? "Renomear aplicação" : "Nova aplicação",
        "Os dados da aplicação podem ser alterados posteriormente.",
        `
        <form
            id="application-form"
            method="POST"
            action="#"
            data-id="${editing ? escapeHtml(application.id) : ""}"
        >
            <div class="error-banner" data-form-error role="alert"></div>

            <div class="field">
                <label for="application-name">Nome da aplicação</label>
                <input
                    id="application-name"
                    name="nome"
                    maxlength="100"
                    required
                    value="${editing ? escapeHtml(application.nome) : ""}"
                    placeholder="Ex.: Catálogo de produtos"
                >
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
                    ${editing ? "Salvar alterações" : "Criar aplicação"}
                </button>
            </div>
        </form>
        `,
        handleFormSubmission
    );

    $("#application-name").focus();
}
