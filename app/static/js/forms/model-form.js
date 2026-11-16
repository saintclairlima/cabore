import { $, escapeHtml } from "../core/utils.js";
import { openDialog } from "../components/dialogs.js";

export function openModelForm(model, handleFormSubmission) {
    const editing = Boolean(model);

    openDialog(
        editing ? "Editar modelo" : "Novo modelo",
        editing
            ? "Atualize os dados cadastrais do modelo."
            : "Informe os dados do modelo de embedding.",
        `
        <form
            id="model-form"
            method="POST"
            action="#"
            data-id="${editing ? escapeHtml(model.id) : ""}"
        >
            <div class="error-banner" data-form-error role="alert"></div>

            <div class="form-grid">
                <div class="field full">
                    <label for="model-id">Identificador</label>
                    <input
                        id="model-id"
                        name="id"
                        maxlength="50"
                        required
                        ${editing
                            ? `value="${escapeHtml(model.id)}" readonly`
                            : 'placeholder="Ex.: bge-m3"'}
                    >
                </div>

                <div class="field">
                    <label for="model-name">Nome</label>
                    <input
                        id="model-name"
                        name="nome"
                        maxlength="100"
                        required
                        value="${editing ? escapeHtml(model.nome) : ""}"
                    >
                </div>

                <div class="field">
                    <label for="model-provider">Provedor</label>
                    <input
                        id="model-provider"
                        name="provedor"
                        maxlength="50"
                        required
                        value="${editing ? escapeHtml(model.provedor) : ""}"
                    >
                </div>

                ${editing ? "" : `
                    <div class="field">
                        <label for="model-dimensions">Dimensões</label>
                        <select
                            id="model-dimensions"
                            name="dimensoes"
                            required
                        >
                            <option value="512">512</option>
                            <option value="768" selected>768</option>
                            <option value="1024">1024</option>
                            <option value="1536">1536</option>
                            <option value="3072">3072</option>
                        </select>
                    </div>
                `}

                <div class="field">
                    <label for="model-distance">Métrica de distância</label>
                    <select
                        id="model-distance"
                        name="metrica_distancia"
                        required
                    >
                        <option value="cosine">Cosseno</option>
                        <option value="l2">L2</option>
                        <option value="ip">Produto interno</option>
                    </select>
                </div>

                <div class="field ${editing ? "full" : ""}">
                    <label for="model-repository">Repositório (opcional)</label>
                    <input
                        id="model-repository"
                        name="identificador_repositorio"
                        maxlength="255"
                        value="${editing
                            ? escapeHtml(model.identificador_repositorio || "")
                            : ""}"
                        placeholder="Organização/modelo"
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

                <button
                    class="button primary"
                    id="model-submit"
                    type="submit"
                >
                    ${editing ? "Salvar alterações" : "Cadastrar modelo"}
                </button>
            </div>
        </form>
        `,
        handleFormSubmission
    );

    if (!editing) {
        $("#model-dimensions").value = "768";
    }

    $("#model-distance").value = editing
        ? model.metrica_distancia
        : "cosine";

    $("#model-id").focus();
}