export const state = {
    key: sessionStorage.getItem("cabore_admin_key") || "",
    applications: [],
    models: [],
    collections: [],
    keys: [],
    analytics: null,
    activeView: "dashboard",
    toastTimer: null,
    applicationDetails: null,
    selectedApplicationId: null,
};