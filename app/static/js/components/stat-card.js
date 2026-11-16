export function statCard(label, value, foot, icon) {
    return `<article class="stat-card">
        <div class="stat-top"><span>${label}</span><span class="stat-icon">${icon}</span></div>
        <div class="stat-value">${value}</div><div class="stat-foot">${foot}</div>
    </article>`;
}