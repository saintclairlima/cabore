import { $, $$, escapeHtml } from "./core/utils.js";
import { state } from "./core/state.js";
import { api, ApiError, apiRoot } from "./core/api.js";
import { atualizarNavegacao } from "./core/navigation.js";
import { showToast, showError, clearError } from "./components/notifications.js";
import {
    openDialog as renderDialog,
    closeDialog as closeManagementDialog
} from "./components/dialogs.js";
import { criarManipuladorFormulario } from "./forms/form-handler.js";
import {
    openApplicationForm as renderApplicationForm
} from "./forms/application-form.js";
import {
    openKeyForm as renderKeyForm
} from "./forms/key-form.js";
import {
    openModelForm as renderModelForm
} from "./forms/model-form.js";
import {
    openCollectionForm as renderCollectionForm
} from "./forms/collection-form.js";
import { criarModuloAplicacoes } from "./screens/applications.js";
import { criarModuloChaves } from "./screens/keys.js";
import { criarModuloModelos } from "./screens/models.js";
import { criarModuloColecoes } from "./screens/collections.js";
import { criarModuloDashboard } from "./screens/dashboard.js";
import { criarModuloDetalhesAplicacao } from "./screens/application-details.js";
import { criarModuloInfraestrutura } from "./screens/infrastructure.js";
import { criarModuloAcoes } from "./screens/actions.js";
import { criarModuloAutenticacao } from "./core/authentication.js";
import { criarManipuladorEnvioFormularios } from "./forms/submission-handlers.js";
import { criarComponentesGraficos } from "./components/charts.js";
import {
    formatNumber,
    formatDuration,
    formatDate,
} from "./core/formatters.js";
import { statCard } from "./components/stat-card.js";
import { icons } from "./components/icons.js";


(() => {

    const moduloEnvioFormularios = criarManipuladorEnvioFormularios({
        api,
        $,
        state,
        escapeHtml,
        closeDialog,
        showToast,
        loadApplications,
        loadKeys,
        loadModels,
        loadCollections,
    });

    const handleFormSubmission = criarManipuladorFormulario({
        submitApplication: moduloEnvioFormularios.submitApplication,
        submitKey: moduloEnvioFormularios.submitKey,
        submitModel: moduloEnvioFormularios.submitModel,
        submitCollection: moduloEnvioFormularios.submitCollection,
        handleAuthError,
        showError,
        clearError,
        showToast,
    });

    const moduloChaves = criarModuloChaves({
        state,
        api,
        $,
        escapeHtml,
        formatDate,
        clearError,
        handleAuthError,
        showError,
    });

    const moduloModelos = criarModuloModelos({
        state,
        api,
        $,
        escapeHtml,
        formatNumber,
        clearError,
        handleAuthError,
        showError,
    });

    const moduloColecoes = criarModuloColecoes({
        state,
        api,
        $,
        escapeHtml,
        formatNumber,
        formatDate,
        clearError,
        handleAuthError,
        showError,
    });

    const moduloAplicacoes = criarModuloAplicacoes({
        state,
        api,
        $,
        escapeHtml,
        formatDate,
        clearError,
        handleAuthError,
        showError,
    });

    const moduloDashboard = criarModuloDashboard({
        state,
        api,
        $,
        escapeHtml,
        clearError,
        handleAuthError,
        showError,
        formatNumber,
        formatDuration,
        formatDate,
        statCard,
        renderVolumeChart,
        renderOperations,
    });

    const moduloDetalhesAplicacao = criarModuloDetalhesAplicacao({
        state,
        api,
        $,
        escapeHtml,
        clearError,
        handleAuthError,
        showError,
        formatDate,
        formatNumber,
        formatDuration,
        statCard,
        icons,
        renderVolumeChart,
        renderOperations,
    });

    const moduloInfraestrutura = criarModuloInfraestrutura({
        state,
        $,
        apiRoot,
        escapeHtml,
        formatNumber,
    });

    const moduloAcoes = criarModuloAcoes({
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
    });

    function handleAuthError(error) {
        if (error instanceof ApiError && error.status === 403) {
            state.key = "";
            sessionStorage.removeItem("cabore_admin_key");
            $("#app-shell").classList.add("hidden");
            $("#auth-screen").classList.remove("hidden");
            showError($("#auth-error"), "A chave não foi aceita. Confira a configuração ADMIN_KEY e tente novamente.");
            $("#admin-key").value = "";
            return true;
        }
        return false;
    }
    
    async function loadDashboard() {
        await moduloDashboard.loadDashboard();
    }

    async function loadApplications() {
        await moduloAplicacoes.loadApplications();
    }

    async function loadApplicationDetails() {
        await moduloDetalhesAplicacao.loadApplicationDetails();
    }

    async function loadCollections() {
        await moduloColecoes.loadCollections();
    }

    async function loadKeys() {
        await moduloChaves.loadKeys();
    }

    async function loadModels() {
        await moduloModelos.loadModels();
    }

    async function loadInfrastructure() {
        await moduloInfraestrutura.loadInfrastructure();
    }

    async function loadView(view) {
        state.activeView = view;
        atualizarNavegacao(view);
        if (view === "dashboard") await loadDashboard();
        if (view === "applications") await loadApplications();
        if (view === "application-details") await loadApplicationDetails();
        if (view === "collections") await loadCollections();
        if (view === "keys") await loadKeys();
        if (view === "infrastructure") await loadInfrastructure();
        if (view === "models") await loadModels();
    }

    const moduloAutenticacao = criarModuloAutenticacao({
        state,
        api,
        ApiError,
        $,
        showError,
        clearError,
        loadDashboard,
    });

    const componentesGraficos = criarComponentesGraficos({
        $,
        escapeHtml,
        formatNumber,
        formatDuration,
    });

    function renderVolumeChart(series, days, hostSelector = "#volume-chart") {
        componentesGraficos.renderVolumeChart(series, days, hostSelector);
    }

    function renderOperations(operations, hostSelector = "#operation-list") {
        componentesGraficos.renderOperations(operations, hostSelector);
    }

    function openDialog(title, description, formMarkup) {
        renderDialog(title, description, formMarkup, handleFormSubmission);
    }

    function closeDialog() {
        closeManagementDialog();
    }

    function openApplicationForm(application = null) {
        renderApplicationForm(application, handleFormSubmission);
    }

    function openKeyForm() {
        renderKeyForm(handleFormSubmission);
    }

    function openModelForm(model = null) {
        renderModelForm(model, handleFormSubmission);
    }
    
    function openCollectionForm(collection = null) {
        renderCollectionForm(
            collection,
            handleFormSubmission,
            formatNumber
        );
    }

    async function onAction(action, button) {
        await moduloAcoes.onAction(action, button);
    }

    moduloAutenticacao.registrarEventos();

    $("#period-select").addEventListener("change", loadDashboard);
    $("#application-detail-period").addEventListener(
        "change",
        () => {
            if (state.activeView === "application-details") {
                loadApplicationDetails();
            }
        }
    );
    $("#collection-application-filter").addEventListener("change", loadCollections);
    $("#collection-model-filter").addEventListener("change", loadCollections);

    document.addEventListener("click", async (event) => {
        const nav = event.target.closest("[data-view]");
        if (nav) {
            await loadView(nav.dataset.view);
            return;
        }
        const button = event.target.closest("[data-action]");
        if (button) {
            await onAction(button.dataset.action, button);
        }
    });

    $("#management-dialog").addEventListener("cancel", (event) => {
        event.preventDefault();
    });
})();