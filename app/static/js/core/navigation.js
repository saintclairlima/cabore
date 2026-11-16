import { $$ } from "./utils.js";

export function atualizarNavegacao(view) {
    const navigationView = view === "application-details"
        ? "applications"
        : view;

    $$(".nav-item").forEach((item) => {
        item.classList.toggle(
            "active",
            item.dataset.view === navigationView
        );
    });

    $$(".view").forEach((section) => {
        section.classList.toggle(
            "hidden",
            section.id !== `view-${view}`
        );
    });
}
