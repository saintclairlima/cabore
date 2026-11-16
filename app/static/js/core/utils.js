export const $ = (selector, root = document) =>
    root.querySelector(selector);

export const $$ = (selector, root = document) =>
    [...root.querySelectorAll(selector)];

export const escapeHtml = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (character) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    })[character]);