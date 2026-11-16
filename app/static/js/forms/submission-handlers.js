
export function criarManipuladorEnvioFormularios({
    api,
    $,
    state,
    escapeHtml,
    closeDialog,
    showToast,
    loadApplications,
    loadKeys,
    loadModels,
    loadCollections,
}) {
    async function submitApplication(form) {
        const id = form.dataset.id;
        const body = JSON.stringify({
            nome: new FormData(form).get("nome"),
        });

        await api(id ? `/aplicacoes/${encodeURIComponent(id)}` : "/aplicacoes/", {
            method: id ? "PATCH" : "POST",
            body,
        });

        closeDialog();
        showToast(id ? "Aplicação atualizada." : "Aplicação criada.");

        await loadApplications();

        if (state.activeView === "keys") {
            await loadKeys();
        }
    }

    async function submitKey(form) {
        const values = Object.fromEntries(new FormData(form).entries());

        const result = await api("/aplicacoes/chaves", {
            method: "POST",
            body: JSON.stringify(values),
        });

        state.keys = [];

        $("#dialog-content").innerHTML = `
            <div class="dialog-head">
                <div>
                    <h2>Chave criada</h2>
                    <p>Copie e guarde a credencial em um local seguro.</p>
                </div>
                <button class="close-button" type="button" data-action="close-dialog" aria-label="Fechar">×</button>
            </div>
            <div class="secret-box mono" id="created-secret">${escapeHtml(result.chave_api)}</div>
            <div class="secret-warning">Esta chave será exibida apenas agora. Depois de fechar esta janela, ela não poderá ser recuperada.</div>
            <div class="dialog-footer">
                <button class="button" type="button" data-action="copy-secret">Copiar chave</button>
                <button class="button primary" type="button" data-action="close-dialog">Concluído</button>
            </div>
        `;

        await loadKeys();
    }

    async function submitModel(form) {
        const values = Object.fromEntries(new FormData(form).entries());
        const id = form.dataset.id;

        if (!id) {
            values.dimensoes = Number(values.dimensoes);
        }

        if (!values.identificador_repositorio) {
            values.identificador_repositorio = null;
        }

        await api(id ? `/modelos/${encodeURIComponent(id)}` : "/modelos/", {
            method: id ? "PATCH" : "POST",
            body: JSON.stringify(values),
        });

        closeDialog();
        showToast(id ? "Modelo atualizado." : "Modelo cadastrado.");

        await loadModels();
    }

    async function submitCollection(form) {
        const id = form.dataset.id;
        const formData = new FormData(form);

        const values = {
            nome: formData.get("nome"),
            publica: form.elements.publica.checked,
        };

        if (id) {
            await api(`/admin/colecoes/${encodeURIComponent(id)}`, {
                method: "PATCH",
                body: JSON.stringify(values),
            });

            closeDialog();
            showToast("Coleção atualizada com sucesso.");
        } else {
            values.aplicacao_id = formData.get("aplicacao_id");
            values.modelo_embedding_id = formData.get("modelo_embedding_id");
            values.tipo_armazenamento = formData.get("tipo_armazenamento");

            await api("/admin/colecoes", {
                method: "POST",
                body: JSON.stringify(values),
            });

            closeDialog();
            showToast("Coleção criada com sucesso.");
        }

        await loadCollections();
    }

    return {
        submitApplication,
        submitKey,
        submitModel,
        submitCollection,
    };
}
