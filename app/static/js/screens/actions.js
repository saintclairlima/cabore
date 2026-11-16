
export function criarModuloAcoes({
    state,
    api,
    $,
    formatNumber,
    showToast,
    showError,
    handleAuthError,
    closeDialog,
    loadDashboard,
    loadApplications,
    loadKeys,
    loadModels,
    loadCollections,
    loadInfrastructure,
    loadView,
    openApplicationForm,
    openKeyForm,
    openModelForm,
    openCollectionForm,
}) {
    async function onAction(action, button) {
        const id = button.dataset.id;

        if (action === "close-dialog") closeDialog();
        if (action === "refresh-dashboard") await loadDashboard();
        if (action === "new-application") openApplicationForm();

        if (action === "new-key") {
            if (!state.applications.length) await loadApplications();
            openKeyForm();
        }

        if (action === "new-model") openModelForm();

        if (action === "edit-application") {
            openApplicationForm(state.applications.find((item) => item.id === id));
        }

        if (action === "application-details") {
            state.selectedApplicationId = id;
            await loadView("application-details");
        }

        if (action === "back-applications") {
            await loadView("applications");
        }

        if (action === "toggle-application") {
            const application = state.applications.find(
                (item) => item.id === id
            );

            if (application) {
                const novoStatus = !application.ativa;
                const acao = novoStatus ? "reativar" : "suspender";

                const mensagem = novoStatus
                    ? `Reativar a aplicação "${application.nome}"?`
                    : `Suspender a aplicação "${application.nome}"? As chaves de API vinculadas deixarão de funcionar.`;

                if (!window.confirm(mensagem)) return;

                try {
                    await api(
                        `/aplicacoes/${encodeURIComponent(id)}/status`,
                        {
                            method: "PATCH",
                            body: JSON.stringify({ ativa: novoStatus }),
                        }
                    );

                    showToast(
                        novoStatus
                            ? "Aplicação reativada com sucesso."
                            : "Aplicação suspensa com sucesso."
                    );

                    await loadApplications();

                    if (state.activeView === "collections") {
                        await loadCollections();
                    }

                    if (state.activeView === "keys") {
                        await loadKeys();
                    }
                } catch (error) {
                    if (!handleAuthError(error)) {
                        showError(
                            $("#applications-error"),
                            error.message || `Não foi possível ${acao} a aplicação.`
                        );
                    }
                }
            }
        }

        if (action === "edit-model") {
            openModelForm(state.models.find((item) => item.id === id));
        }

        if (action === "delete-application") {
            const application = state.applications.find((item) => item.id === id);

            if (
                application &&
                window.confirm(
                    `Excluir "${application.nome}" e todos os recursos vinculados? Esta ação não pode ser desfeita.`
                )
            ) {
                try {
                    await api(`/aplicacoes/${encodeURIComponent(id)}`, {
                        method: "DELETE",
                    });

                    showToast("Aplicação e recursos vinculados excluídos.");
                    await loadApplications();
                } catch (error) {
                    if (!handleAuthError(error)) {
                        showError($("#applications-error"), error.message);
                    }
                }
            }
        }

        if (action === "new-collection") {
            await loadCollections();
            openCollectionForm();
        }

        if (action === "refresh-collections") {
            await loadCollections();
        }

        if (action === "refresh-infrastructure") {
            await loadInfrastructure();
            return;
        }

        if (action === "edit-collection") {
            const collection = state.collections.find(
                (item) => item.id === id
            );

            if (collection) {
                openCollectionForm(collection);
            }
        }

        if (action === "delete-collection") {
            const collection = state.collections.find((item) => item.id === id);

            if (
                collection &&
                window.confirm(
                    `Excluir a coleção "${collection.nome}" da aplicação "${collection.aplicacao_nome}"? ` +
                    `${formatNumber(collection.quantidade_embeddings)} embedding(s) vinculados também serão removidos. Esta ação não pode ser desfeita.`
                )
            ) {
                try {
                    await api(`/admin/colecoes/${encodeURIComponent(id)}`, {
                        method: "DELETE",
                    });

                    showToast("Coleção e embeddings vinculados removidos.");
                    await loadCollections();
                } catch (error) {
                    if (!handleAuthError(error)) {
                        showError($("#collections-error"), error.message);
                    }
                }
            }
        }

        if (action === "revoke-key") {
            const key = state.keys.find((item) => item.id === id);

            if (
                key &&
                window.confirm(
                    `Revogar a chave "${key.nome}"? A credencial deixará de funcionar imediatamente.`
                )
            ) {
                try {
                    await api(
                        `/aplicacoes/chaves/${encodeURIComponent(id)}/revogar`,
                        { method: "PATCH" }
                    );

                    showToast("Chave revogada.");
                    await loadKeys();
                } catch (error) {
                    if (!handleAuthError(error)) {
                        showError($("#keys-error"), error.message);
                    }
                }
            }
        }

        if (action === "toggle-model") {
            const model = state.models.find((item) => item.id === id);

            if (model) {
                try {
                    await api(`/modelos/${encodeURIComponent(id)}`, {
                        method: "PATCH",
                        body: JSON.stringify({ ativo: !model.ativo }),
                    });

                    showToast(model.ativo ? "Modelo desativado." : "Modelo ativado.");
                    await loadModels();
                } catch (error) {
                    if (!handleAuthError(error)) {
                        showError($("#models-error"), error.message);
                    }
                }
            }
        }

        if (action === "copy-secret") {
            const secret = $("#created-secret")?.textContent;

            if (secret) {
                try {
                    await navigator.clipboard.writeText(secret);
                    showToast("Chave copiada.");
                } catch {
                    showToast(
                        "Não foi possível copiar automaticamente; selecione e copie a chave."
                    );
                }
            }
        }
    }

    return {
        onAction,
    };
}
