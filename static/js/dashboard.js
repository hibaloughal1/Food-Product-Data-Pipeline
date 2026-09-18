/**
 * dashboard.js
 * ============
 * Récupère les données via l'API interne Flask et met à jour :
 *  - les KPI
 *  - les graphiques Chart.js
 *  - le tableau des produits et le tableau des promotions
 *  - la comparaison des prix entre enseignes
 * à chaque changement de filtre (enseigne, catégorie, recherche) — 10.7.
 */

/**
 * Gestion du thème clair / sombre (persisté en localStorage).
 */
const boutonTheme = document.getElementById("theme-toggle");
const iconeTheme = document.getElementById("theme-icon");
const labelTheme = document.getElementById("theme-label");

function appliquerTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("app-theme", theme);
    if (theme === "dark") {
        iconeTheme.textContent = "☀️";
        labelTheme.textContent = "Mode clair";
    } else {
        iconeTheme.textContent = "🌙";
        labelTheme.textContent = "Mode sombre";
    }
}

boutonTheme.addEventListener("click", () => {
    const themeActuel = document.documentElement.getAttribute("data-theme") || "light";
    appliquerTheme(themeActuel === "dark" ? "light" : "dark");
    // Redessine les graphiques pour appliquer les couleurs du nouveau thème
    Promise.all([majChartProduitsEnseigne(), majChartCategories(), majChartTopCheap()]);
});

// Synchronise le libellé du bouton avec le thème déjà appliqué au chargement
appliquerTheme(document.documentElement.getAttribute("data-theme") || "light");

const filtreEnseigne = document.getElementById("filtre-enseigne");
const filtreCategorie = document.getElementById("filtre-categorie");
const filtreRecherche = document.getElementById("filtre-recherche");

let chartEnseigne, chartCategories, chartTopCheap;

if (typeof Chart === "undefined") {
    console.error(
        "Chart.js n'a pas pu être chargé (vérifiez static/js/chart.umd.js). " +
        "Les graphiques resteront vides mais les tableaux fonctionneront normalement."
    );
}

// Palette de graphiques du tableau de bord (vert/émeraude)
const PALETTE_GRAPHIQUES = ["#0f9d70", "#2ecc93", "#5fd3a8", "#f0a51e", "#f2b544", "#3aa5c9", "#8bd3b6", "#d1495b"];

function couleurTexteGraphique() {
    const theme = document.documentElement.getAttribute("data-theme") || "light";
    return theme === "dark" ? "#eaf3f0" : "#1c2a27";
}

function couleurGrilleGraphique() {
    const theme = document.documentElement.getAttribute("data-theme") || "light";
    return theme === "dark" ? "#2a3b35" : "#dfe7e4";
}

function optionsGraphiqueBase() {
    return {
        color: couleurTexteGraphique(),
        scales: {
            x: { ticks: { color: couleurTexteGraphique() }, grid: { color: couleurGrilleGraphique() } },
            y: { ticks: { color: couleurTexteGraphique() }, grid: { color: couleurGrilleGraphique() } },
        },
    };
}

function paramsActuels() {
    const params = new URLSearchParams();
    if (filtreEnseigne.value) params.set("enseigne_id", filtreEnseigne.value);
    if (filtreCategorie.value) params.set("categorie", filtreCategorie.value);
    if (filtreRecherche.value) params.set("q", filtreRecherche.value);
    return params;
}

async function chargerJSON(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`Erreur API ${url}`);
    return resp.json();
}

function formatMAD(valeur) {
    if (valeur === null || valeur === undefined) return "-";
    return `${Number(valeur).toFixed(2)} DH`;
}

async function majKPIs() {
    const data = await chargerJSON(`/api/kpis?${paramsActuels()}`);
    document.getElementById("kpi-nb-produits").textContent = data.nb_produits;
    document.getElementById("kpi-nb-promotions").textContent = data.nb_promotions;
    document.getElementById("kpi-prix-min").textContent = formatMAD(data.prix_min);
    document.getElementById("kpi-prix-moyen").textContent = formatMAD(data.prix_moyen);
    document.getElementById("derniere-maj").textContent = `Dernière mise à jour : ${data.derniere_maj}`;

    const alerte = document.getElementById("alerte-base-vide");
    if (data.nb_produits === 0) {
        alerte.classList.remove("d-none");
    } else {
        alerte.classList.add("d-none");
    }
}

async function majChartProduitsEnseigne() {
    const data = await chargerJSON("/api/produits-par-enseigne");
    const ctx = document.getElementById("chart-produits-enseigne");
    if (chartEnseigne) chartEnseigne.destroy();
    chartEnseigne = new Chart(ctx, {
        type: "bar",
        data: { labels: data.labels, datasets: [{ label: "Produits", data: data.valeurs, backgroundColor: PALETTE_GRAPHIQUES[0] }] },
        options: { ...optionsGraphiqueBase(), plugins: { legend: { display: false } }, responsive: true },
    });
}

async function majChartCategories() {
    const data = await chargerJSON("/api/repartition-categories");
    const ctx = document.getElementById("chart-categories");
    if (chartCategories) chartCategories.destroy();
    chartCategories = new Chart(ctx, {
        type: "doughnut",
        data: { labels: data.labels, datasets: [{ data: data.valeurs, backgroundColor: PALETTE_GRAPHIQUES }] },
        options: { responsive: true, plugins: { legend: { labels: { color: couleurTexteGraphique() } } } },
    });
}

async function majChartTopCheap() {
    const params = paramsActuels();
    const data = await chargerJSON(`/api/top-moins-chers?${params}`);
    const ctx = document.getElementById("chart-top-cheap");
    if (chartTopCheap) chartTopCheap.destroy();
    chartTopCheap = new Chart(ctx, {
        type: "bar",
        data: {
            labels: data.map(d => d.produit.length > 20 ? d.produit.slice(0, 20) + "…" : d.produit),
            datasets: [{ label: "Prix (DH)", data: data.map(d => d.prix), backgroundColor: PALETTE_GRAPHIQUES[1] }],
        },
        options: { ...optionsGraphiqueBase(), indexAxis: "y", plugins: { legend: { display: false } } },
    });
}

async function majTablePromotions() {
    const data = await chargerJSON("/api/promotions");
    const tbody = document.querySelector("#table-promotions tbody");
    tbody.innerHTML = "";
    data.slice(0, 15).forEach(p => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${p.produit}</td>
            <td>${p.enseigne}</td>
            <td>${formatMAD(p.prix_normal)}</td>
            <td>${formatMAD(p.prix_promotion)}</td>
            <td><span class="badge bg-danger">-${p.reduction}%</span></td>`;
        tbody.appendChild(tr);
    });
}

async function majTableProduits() {
    const data = await chargerJSON(`/api/produits?${paramsActuels()}`);
    const tbody = document.querySelector("#table-produits tbody");
    tbody.innerHTML = "";
    data.forEach(p => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${p.nom}</td>
            <td>${p.reference}</td>
            <td>${p.marque ?? "-"}</td>
            <td>${p.categorie ?? "-"}</td>
            <td>${p.enseigne}</td>
            <td>${formatMAD(p.prix_normal)}</td>
            <td>${p.prix_promotion ? formatMAD(p.prix_promotion) : "-"}</td>
            <td>${p.date_collecte}</td>`;
        tbody.appendChild(tr);
    });
}

async function majComparaison() {
    const zone = document.getElementById("zone-comparaison");
    const terme = filtreRecherche.value;
    if (!terme) {
        zone.innerHTML = `<p class="text-muted mb-0">Utilisez le champ de recherche ci-dessus pour comparer un produit entre plusieurs enseignes.</p>`;
        return;
    }
    const data = await chargerJSON(`/api/comparaison?q=${encodeURIComponent(terme)}`);
    if (data.length === 0) {
        zone.innerHTML = `<p class="text-muted mb-0">Aucun résultat pour « ${terme} ».</p>`;
        return;
    }

    let html = "";
    data.forEach(groupe => {
        html += `<h6 class="mt-2">${groupe.produit}</h6>`;
        html += `<table class="table table-sm table-bordered mb-3"><thead><tr><th>Enseigne</th><th>Prix</th><th>Référence</th></tr></thead><tbody>`;
        groupe.offres.sort((a, b) => a.prix - b.prix).forEach(o => {
            html += `<tr class="${o.meilleure_offre ? "meilleure-offre" : ""}">
                <td>${o.enseigne}</td>
                <td>${formatMAD(o.prix)} ${o.meilleure_offre ? "✅ Meilleure offre" : ""}</td>
                <td>${o.reference}</td>
            </tr>`;
        });
        html += `</tbody></table>`;
    });
    zone.innerHTML = html;
}

async function rafraichirTout() {
    const taches = [
        majKPIs(),
        majChartProduitsEnseigne(),
        majChartCategories(),
        majChartTopCheap(),
        majTablePromotions(),
        majTableProduits(),
        majComparaison(),
    ];
    // allSettled : si un widget échoue (ex: graphique), les autres continuent
    // de se mettre à jour normalement au lieu d'être bloqués silencieusement.
    const resultats = await Promise.allSettled(taches);
    resultats.forEach(r => { if (r.status === "rejected") console.error(r.reason); });
}

function mettreAJourExportLien() {
    document.getElementById("export-csv").href = `/export/csv?${paramsActuels()}`;
}

[filtreEnseigne, filtreCategorie].forEach(el => el.addEventListener("change", () => {
    mettreAJourExportLien();
    rafraichirTout();
}));

let timeoutRecherche;
filtreRecherche.addEventListener("input", () => {
    clearTimeout(timeoutRecherche);
    timeoutRecherche = setTimeout(() => {
        mettreAJourExportLien();
        rafraichirTout();
    }, 400);
});

document.addEventListener("DOMContentLoaded", () => {
    mettreAJourExportLien();
    rafraichirTout();
});
