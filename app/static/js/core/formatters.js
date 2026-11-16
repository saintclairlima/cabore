
export function formatNumber(value, digits = 0) {
    return new Intl.NumberFormat("pt-BR", {
        maximumFractionDigits: digits,
    }).format(Number(value || 0));
}

export function formatDuration(value) {
    const number = Number(value || 0);
    return `${formatNumber(number, number < 10 ? 2 : 1)} ms`;
}

export function formatDate(value, includeTime = false) {
    if (!value) return "—";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) return "—";

    const options = includeTime
        ? {
            day: "2-digit",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
        }
        : {
            day: "2-digit",
            month: "short",
            year: "numeric",
        };

    return new Intl.DateTimeFormat("pt-BR", options).format(date);
}
