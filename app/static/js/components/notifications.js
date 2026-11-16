import { state } from "../core/state.js";
import { $ } from "../core/utils.js";

export function showToast(message) {
    const toast = $("#toast");
    toast.textContent = message;
    toast.classList.add("visible");

    clearTimeout(state.toastTimer);

    state.toastTimer = setTimeout(() => {
        toast.classList.remove("visible");
    }, 3200);
}

export function showError(element, message) {
    element.textContent = message;
    element.style.display = "block";
}

export function clearError(element) {
    element.textContent = "";
    element.style.display = "none";
}
