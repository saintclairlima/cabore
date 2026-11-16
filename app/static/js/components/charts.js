
export function criarComponentesGraficos({
    $,
    escapeHtml,
    formatNumber,
    formatDuration,
}) {
    function renderVolumeChart(series, days, hostSelector = "#volume-chart") {
        const host = $(hostSelector);

        if (!series.length) {
            host.innerHTML = '<div class="chart-empty">Ainda não há requisições registradas neste período.</div>';
            return;
        }

        const byDate = new Map(series.map((item) => [String(item.dia).slice(0, 10), item]));
        const today = new Date();

        const completeSeries = Array.from({ length: days }, (_, index) => {
            const date = new Date(Date.UTC(
                today.getUTCFullYear(),
                today.getUTCMonth(),
                today.getUTCDate() - (days - index - 1)
            ));

            const day = date.toISOString().slice(0, 10);

            return byDate.get(day) || {
                dia: day,
                requisicoes: 0,
                latencia_media_ms: 0,
            };
        });

        series = completeSeries;

        const values = series.map((item) => Number(item.requisicoes));
        const latencies = series.map((item) => Number(item.latencia_media_ms));

        const width = 620;
        const height = 196;
        const left = 34;
        const right = 12;
        const top = 12;
        const bottom = 27;

        const chartWidth = width - left - right;
        const chartHeight = height - top - bottom;

        const maxRequests = Math.max(...values, 1);
        const maxLatency = Math.max(...latencies, 1);

        const x = (index) =>
            left + (
                series.length === 1
                    ? chartWidth / 2
                    : (index / (series.length - 1)) * chartWidth
            );

        const requestY = (value) =>
            top + chartHeight - (value / maxRequests) * chartHeight;

        const latencyY = (value) =>
            top + chartHeight - (value / maxLatency) * chartHeight;

        const requestPoints = values
            .map((value, index) => `${x(index)},${requestY(value)}`)
            .join(" ");

        const latencyPoints = latencies
            .map((value, index) => `${x(index)},${latencyY(value)}`)
            .join(" ");

        const area = `${left},${top + chartHeight} ${requestPoints} ${left + chartWidth},${top + chartHeight}`;

        const step = Math.max(1, Math.ceil(series.length / 6));

        const labels = series.map((item, index) => {
            if (index % step !== 0 && index !== series.length - 1) {
                return "";
            }

            const dia = String(item.dia).slice(0, 10);
            const data = new Date(`${dia}T12:00:00`);

            if (Number.isNaN(data.getTime())) {
                return "";
            }

            const rotulo = new Intl.DateTimeFormat("pt-BR", {
                day: "2-digit",
                month: "short",
            }).format(data);

            return `
                <text
                    x="${x(index)}"
                    y="${height - 5}"
                    text-anchor="middle"
                    fill="#9aa49d"
                    font-size="9"
                >${rotulo}</text>
            `;
        }).join("");

        const grid = [0, 1, 2, 3].map((index) => {
            const y = top + (chartHeight / 3) * index;

            return `<line x1="${left}" y1="${y}" x2="${width - right}" y2="${y}" stroke="#edf0ed" stroke-width="1"/>`;
        }).join("");

        const dots = series.map((item, index) =>
            `<circle cx="${x(index)}" cy="${requestY(values[index])}" r="3.1" fill="#fff" stroke="#43845e" stroke-width="2"><title>${escapeHtml(item.dia)} · ${formatNumber(item.requisicoes)} requisições · ${formatDuration(item.latencia_media_ms)}</title></circle>`
        ).join("");

        host.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Gráfico diário de requisições e latência média nos últimos ${days} dias">
            ${grid}
            <polygon points="${area}" fill="#eaf4ee" opacity=".8"/>
            <polyline points="${requestPoints}" fill="none" stroke="#43845e" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
            <polyline points="${latencyPoints}" fill="none" stroke="#d98a47" stroke-width="2" stroke-dasharray="4 4" stroke-linecap="round" stroke-linejoin="round"/>
            ${dots}${labels}
        </svg>`;
    }

    function renderOperations(operations, hostSelector = "#operation-list") {
        const host = $(hostSelector);

        // Normaliza os formatos utilizados pelo dashboard e pelos detalhes.
        const normalized = operations.map((item) => ({
            nome: item.nome ?? item.operacao,
            total: Number(item.total ?? item.quantidade ?? 0),
        }));

        if (!normalized.length) {
            host.innerHTML = '<div class="chart-empty">Sem operações para exibir.</div>';
            return;
        }

        const max = Math.max(
            ...normalized.map((item) => item.total),
            1
        );

        host.innerHTML = normalized.map((item) => `
            <div class="operation-row">
                <span class="operation-name" title="${escapeHtml(item.nome)}">
                    ${escapeHtml(item.nome)}
                </span>
                <span class="bar-track">
                    <span
                        class="bar-fill"
                        style="display:block;width:${Math.max(2, (item.total / max) * 100)}%"
                    ></span>
                </span>
                <span class="bar-number">${formatNumber(item.total)}</span>
            </div>
        `).join("");
    }

    return {
        renderVolumeChart,
        renderOperations,
    };
}
