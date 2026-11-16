export function criarManipuladorFormulario({
    submitApplication,
    submitKey,
    submitModel,
    submitCollection,
    handleAuthError,
    showError,
    clearError,
    showToast,
}) {
    return async function handleFormSubmission(form, submit) {
        const errorElement = form.querySelector("[data-form-error]");

        if (errorElement) clearError(errorElement);

        if (!form.reportValidity()) {
            if (errorElement) {
                showError(
                    errorElement,
                    "Revise os campos obrigatórios antes de continuar."
                );
            }
            return;
        }

        const submitLabel = submit?.textContent;

        if (submit) {
            submit.disabled = true;
            submit.textContent = "Salvando…";
        }

        try {
            const formId = form.getAttribute("id");

            if (formId === "application-form") {
                await submitApplication(form);
            }

            if (formId === "key-form") {
                await submitKey(form);
            }

            if (formId === "model-form") {
                await submitModel(form);
            }

            if (formId === "collection-form") {
                await submitCollection(form);
            }
        } catch (error) {
            console.error("Erro na submissão do formulário:", error);

            if (!handleAuthError(error)) {
                if (errorElement) {
                    showError(
                        errorElement,
                        error.message || "Não foi possível concluir a operação."
                    );
                } else {
                    showToast(
                        error.message || "Não foi possível concluir a operação."
                    );
                }
            }

            if (submit) {
                submit.disabled = false;
                submit.textContent = submitLabel;
            }
        }
    };
}
