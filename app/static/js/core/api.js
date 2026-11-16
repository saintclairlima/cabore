import { state } from "./state.js";

export const apiRoot = "/v1";

export class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.status = status;
    }
}

export async function api(path, options = {}) {
    const response = await fetch(`${apiRoot}${path}`, {
        ...options,
        headers: {
            ...(options.body ? { "Content-Type": "application/json" } : {}),
            "X-Admin-Key": state.key,
            ...options.headers,
        },
    });

    const payload = response.status === 204
        ? null
        : await response.json().catch(() => null);

    if (!response.ok) {
        const detail = payload?.detail
            || payload?.erro
            || `Falha na requisição (${response.status}).`;

        throw new ApiError(
            typeof detail === "string"
                ? detail
                : "Os dados enviados são inválidos.",
            response.status
        );
    }

    return payload;
}
