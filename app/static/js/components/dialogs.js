
import { $ } from "../core/utils.js";

export function openDialog(title, description, formMarkup, onSubmit) {
    $("#dialog-content").innerHTML = `
        <div class="dialog-head">
            <div>
                <h2>${title}</h2>
                <p>${description}</p>
            </div>
            <button
                class="close-button"
                type="button"
                data-action="close-dialog"
                aria-label="Fechar"
            >×</button>
        </div>
        ${formMarkup}
    `;

    const form = $("#dialog-content form");

    if (form) {
        form.noValidate = true;

        form.addEventListener("submit", (event) => {
            event.preventDefault();
            event.stopPropagation();

            const submit = form.querySelector('button[type="submit"]')
                || $("#model-submit", form);

            void onSubmit(form, submit);
            return false;
        });
    }

    $("#management-dialog").showModal();
}

export function closeDialog() {
    $("#management-dialog").close();
    $("#dialog-content").innerHTML = "";
}
