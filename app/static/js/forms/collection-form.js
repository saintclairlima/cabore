import { $, escapeHtml } from "../core/utils.js";
import { state } from "../core/state.js";
import { openDialog } from "../components/dialogs.js";
import { showToast } from "../components/notifications.js";

export function openCollectionForm(
    collection,
    handleFormSubmission,
    formatNumber
) {
    const editing = Boolean(collection);

    if (editing) {
        openDialog(
            "Editar coleção",
            "Altere o nome e a visibilidade da coleção.",
            `
            <form
                id="collection-form"
                method="POST"
                action="#"
                data-id="${escapeHtml(collection.id)}"
            >
                <div class="error-banner" data-form-error role="alert"></div>

                <div class="form-grid">
                    <div class="collection-info">
                        <div class="collection-info-item">
                            <span class="collection-info-label">Aplicação</span>
                            <strong>${escapeHtml(collection.aplicacao_nome)}</strong>
                        </div>

                        <div class="collection-info-item">
                            <span class="collection-info-label">Armazenamento</span>
                            <strong>${escapeHtml(collection.tipo_armazenamento)}</strong>
                        </div>

                        <div class="collection-info-item collection-info-model">
                            <span class="collection-info-label">Modelo de embedding</span>
                            <strong>${escapeHtml(collection.modelo_nome)}</strong>
                            <small>
                                ${formatNumber(collection.modelo_dimensoes)} dimensões
                                · ${escapeHtml(collection.metrica_distancia)}
                            </small>
                        </div>
                    </div>

                    <div class="field full">
                        <label for="collection-name">Nome da coleção</label>
                        <input
                            id="collection-name"
                            name="nome"
                            maxlength="100"
                            required
                            value="${escapeHtml(collection.nome)}"
                        >
                    </div>

                    <div class="field full">
                        <label class="switch-field" for="collection-public">
                            <span class="switch-description">
                                Coleção pública
                                <small>
                                    Permite acesso público conforme as regras da API.
                                </small>
                            </span>

                            <span class="switch-control">
                                <input
                                    type="checkbox"
                                    id="collection-public"
                                    name="publica"
                                    value="true"
                                    ${collection.publica ? "checked" : ""}
                                >
                                <span class="switch-slider"></span>
                            </span>
                        </label>
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
                        Salvar alterações
                    </button>
                </div>
            </form>
            `,
            handleFormSubmission
        );

        $("#collection-name").focus();
        return;
    }

    const applications = state.applications.filter(
        (item) => item.ativa !== false
    );

    const models = state.models.filter(
        (item) => item.ativo
    );

    if (!applications.length) {
        showToast("Cadastre ou ative uma aplicação antes de criar uma coleção.");
        return;
    }

    if (!models.length) {
        showToast("Cadastre ou ative um modelo de embedding antes de criar uma coleção.");
        return;
    }

    openDialog(
        "Nova coleção",
        "Configure a coleção e associe-a a uma aplicação e a um modelo de embedding.",
        `
        <form id="collection-form" method="POST" action="#">
            <div class="error-banner" data-form-error role="alert"></div>

            <div class="form-grid">
                <div class="field full">
                    <label for="collection-name">Nome da coleção</label>
                    <input
                        id="collection-name"
                        name="nome"
                        maxlength="100"
                        required
                        placeholder="Ex.: Documentos legislativos"
                    >
                </div>

                <div class="field full">
                    <label for="collection-application">Aplicação</label>
                    <select
                        id="collection-application"
                        name="aplicacao_id"
                        required
                    >
                        <option value="">Selecione uma aplicação</option>
                        ${applications.map((item) => `
                            <option value="${escapeHtml(item.id)}">
                                ${escapeHtml(item.nome)}
                            </option>
                        `).join("")}
                    </select>
                </div>

                <div class="field full">
                    <label for="collection-model">Modelo de embedding</label>
                    <select
                        id="collection-model"
                        name="modelo_embedding_id"
                        required
                    >
                        <option value="">Selecione um modelo</option>
                        ${models.map((item) => `
                            <option value="${escapeHtml(item.id)}">
                                ${escapeHtml(item.nome)} · ${formatNumber(item.dimensoes)} dimensões
                            </option>
                        `).join("")}
                    </select>
                </div>

                <div class="field full">
                    <label for="collection-storage">Tipo de armazenamento</label>
                    <select
                        id="collection-storage"
                        name="tipo_armazenamento"
                        required
                    >
                        <option value="vector">Vector</option>
                        <option value="halfvec">Halfvec</option>
                    </select>
                </div>

                <div class="field full">
                    <label class="switch-field" for="collection-public">
                        <span class="switch-description">
                            Coleção pública
                            <small>
                                Permite acesso público conforme as regras da API.
                            </small>
                        </span>

                        <span class="switch-control">
                            <input
                                type="checkbox"
                                id="collection-public"
                                name="publica"
                                value="true"
                            >
                            <span class="switch-slider"></span>
                        </span>
                    </label>
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
                    Criar coleção
                </button>
            </div>
        </form>
        `,
        handleFormSubmission
    );

    $("#collection-name").focus();
}