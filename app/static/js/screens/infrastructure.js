
export function criarModuloInfraestrutura({
    state,
    $,
    apiRoot,
    escapeHtml,
    formatNumber,
}) {
    async function loadInfrastructure() {
        const container = $("#infrastructure-content");
        const errorBanner = $("#infrastructure-error");

        errorBanner.textContent = "";
        errorBanner.classList.add("hidden");

        try {
            const response = await fetch(`${apiRoot}/admin/health`, {
                headers: {
                    "X-Admin-Key": state.key,
                },
            });

            const payload = await response.json().catch(() => null);

            // O status 503 também contém informações úteis sobre a infraestrutura.
            if (!response.ok && response.status !== 503) {
                const detail =
                    payload?.detail ||
                    payload?.erro ||
                    `Falha na requisição (${response.status}).`;

                throw new Error(detail);
            }

            if (!payload) {
                throw new Error("Não foi possível interpretar a resposta do servidor.");
            }

            const inferencia = payload.inferencia || {};
            const modelos = payload.modelos;

            const definirStatus = (id, status, textoOperacional = "Operacional") => {
                const elemento = $(`#${id}`);
                if (!elemento) return;

                const operacional = status === "operacional";

                elemento.textContent = operacional
                    ? textoOperacional
                    : "Indisponível";

                elemento.classList.toggle("operational", operacional);
                elemento.classList.toggle("unavailable", !operacional);
            };

            const definirTexto = (id, valor) => {
                const elemento = $(`#${id}`);
                if (elemento) elemento.textContent = valor ?? "—";
            };

            // Situação geral
            definirStatus(
                "infra-overall-status",
                payload.status,
                payload.status === "degradado" ? "Degradado" : "Operacional"
            );

            // API
            definirStatus("infra-api-status", payload.api?.status);

            // Banco de dados
            definirStatus("infra-database-status", payload.banco?.status);

            // Motor de inferência
            const motorDisponivel = inferencia.inicializado === true;

            definirStatus(
                "infra-engine-status",
                motorDisponivel ? "operacional" : "indisponivel",
                motorDisponivel ? "Disponível" : "Indisponível"
            );

            definirTexto("infra-engine-device", inferencia.dispositivo);
            definirTexto(
                "infra-engine-models",
                inferencia.quantidade_modelos_carregados ?? 0
            );

            // Modelos cadastrados
            const totalModelos = modelos?.total_modelos ?? 0;
            const modelosCarregados = modelos?.modelos_carregados ?? 0;
            const modelosNaoCarregados = modelos?.modelos_nao_carregados ?? 0;

            definirStatus(
                "infra-models-status",
                modelos ? "operacional" : "indisponivel",
                modelos ? "Informações disponíveis" : "Não consultados"
            );

            definirTexto("infra-models-total", totalModelos);
            definirTexto("infra-models-loaded", modelosCarregados);
            definirTexto("infra-models-unloaded", modelosNaoCarregados);
            definirTexto("infra-models-device", inferencia.dispositivo);

            // Tabela detalhada dos modelos cadastrados
            const tabelaModelos = $("#infra-models-table");

            if (tabelaModelos) {
                if (!modelos) {
                    tabelaModelos.innerHTML = `
                        <div class="application-detail-empty">
                            Não foi possível consultar os modelos porque o banco de dados está indisponível.
                        </div>
                    `;
                } else if (!modelos.modelos?.length) {
                    tabelaModelos.innerHTML = `
                        <div class="application-detail-empty">
                            Nenhum modelo de embedding cadastrado.
                        </div>
                    `;
                } else {
                    tabelaModelos.innerHTML = `
                        <table class="infrastructure-models-table">
                            <thead>
                                <tr>
                                    <th>Modelo</th>
                                    <th>Provedor</th>
                                    <th>Dimensões</th>
                                    <th>Repositório</th>
                                    <th>Cadastro</th>
                                    <th>Inferência</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${modelos.modelos.map((modelo) => {
                                    const statusCadastro = modelo.ativo
                                        ? "Ativo"
                                        : "Inativo";

                                    const classeCadastro = modelo.ativo
                                        ? "loaded"
                                        : "inactive";

                                    const statusInferencia = modelo.carregado
                                        ? "Carregado"
                                        : "Não carregado";

                                    const classeInferencia = modelo.carregado
                                        ? "loaded"
                                        : "not-loaded";

                                    return `
                                        <tr>
                                            <td>
                                                <div class="infrastructure-model-name">
                                                    <strong>${escapeHtml(modelo.nome || "Sem nome")}</strong>
                                                    <small class="mono">${escapeHtml(modelo.id)}</small>
                                                </div>
                                            </td>

                                            <td>${escapeHtml(modelo.provedor || "—")}</td>

                                            <td class="mono">
                                                ${formatNumber(modelo.dimensoes)}
                                            </td>

                                            <td>
                                                <div class="infrastructure-model-details">
                                                    <small>
                                                        ${escapeHtml(modelo.identificador_repositorio || "Não informado")}
                                                    </small>
                                                </div>
                                            </td>

                                            <td>
                                                <span class="infrastructure-model-status ${classeCadastro}">
                                                    ${statusCadastro}
                                                </span>
                                            </td>

                                            <td>
                                                <span class="infrastructure-model-status ${classeInferencia}">
                                                    ${statusInferencia}
                                                </span>
                                            </td>
                                        </tr>
                                    `;
                                }).join("")}
                            </tbody>
                        </table>
                    `;
                }
            }

            // Indicadores superiores
            definirTexto("infra-loaded-count", modelosCarregados);
            definirTexto("infra-registered-count", totalModelos);
            definirTexto("infra-device", inferencia.dispositivo);

            const overallStatus = $("#infra-overall-status");
            if (overallStatus) {
                overallStatus.classList.toggle(
                    "operational",
                    payload.status === "operacional"
                );
                overallStatus.classList.toggle(
                    "unavailable",
                    payload.status !== "operacional"
                );
            }

            // Data e hora da última atualização
            definirTexto(
                "infra-last-update",
                new Date().toLocaleString("pt-BR")
            );

            if (container) {
                container.classList.remove("hidden");
            }

            if (response.status === 503) {
                errorBanner.textContent =
                    "A infraestrutura apresenta degradação. Consulte os indicadores abaixo.";
                errorBanner.classList.remove("hidden");
            }
        } catch (error) {
            errorBanner.textContent =
                error.message || "Não foi possível consultar a infraestrutura.";
            errorBanner.classList.remove("hidden");

            console.error("Erro ao consultar infraestrutura:", error);
        }
    }

    return {
        loadInfrastructure,
    };
}
