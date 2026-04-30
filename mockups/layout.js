// Layout commun (header + sidebar) injecté par JS pour éviter la duplication.
// Charger après data.js.

function renderLayout(activePage) {
  const navItems = [
    { id: "dashboard", label: "Dashboard", href: "index.html", icon: "📊" },
    { id: "gantt", label: "Planning", href: "gantt.html", icon: "📅" },
    { id: "conversation", label: "Conversation", href: "conversation.html", icon: "💬" },
    { id: "infeasibility", label: "Infaisabilité", href: "infeasibility.html", icon: "⚠️" },
    { id: "versioning", label: "Historique", href: "versioning.html", icon: "🕐" },
  ];

  const sidebar = `
    <aside class="w-56 bg-slate-900 text-slate-100 flex flex-col h-screen">
      <div class="px-5 py-5 border-b border-slate-800">
        <div class="font-semibold text-base">${ATELIER.nom}</div>
        <div class="text-xs text-slate-400 mt-0.5">${ATELIER.ville}</div>
      </div>
      <nav class="flex-1 mt-3">
        ${navItems
          .map(
            (item) => `
          <a href="${item.href}"
             class="flex items-center gap-3 px-5 py-3 text-sm hover:bg-slate-800 transition-colors ${
               activePage === item.id ? "bg-slate-800 border-l-4 border-indigo-500 pl-4 text-white" : "text-slate-300"
             }">
            <span class="text-base">${item.icon}</span>
            <span>${item.label}</span>
          </a>`
          )
          .join("")}
      </nav>
      <div class="px-5 py-4 border-t border-slate-800 text-xs text-slate-400">
        <div class="flex items-center gap-2 mb-1">
          <div class="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs font-semibold">PM</div>
          <div>
            <div class="text-slate-200 font-medium">${ATELIER.chefAtelier}</div>
            <div>chef d'atelier</div>
          </div>
        </div>
        <div class="mt-2 pt-2 border-t border-slate-800">
          Version active : <span class="text-emerald-400 font-mono">${KPI.versionActive}</span>
        </div>
      </div>
    </aside>
  `;

  const header = `
    <header class="bg-white border-b border-slate-200 px-8 py-4 flex items-center justify-between">
      <div>
        <div class="text-xs uppercase tracking-wider text-slate-500 mb-0.5">${ATELIER.date}</div>
        <h1 class="text-xl font-semibold text-slate-900" id="page-title">${getPageTitle(activePage)}</h1>
      </div>
      <div class="flex items-center gap-3">
        <button class="text-sm px-3 py-1.5 rounded border border-slate-300 hover:bg-slate-50 text-slate-700">
          Importer données
        </button>
        <button class="text-sm px-3 py-1.5 rounded bg-indigo-600 text-white hover:bg-indigo-700 font-medium">
          Replanifier
        </button>
      </div>
    </header>
  `;

  return { sidebar, header };
}

function getPageTitle(activePage) {
  const titles = {
    dashboard: "Vue d'ensemble",
    gantt: "Planning de la semaine",
    conversation: "Demander une modification",
    infeasibility: "Diagnostic d'infaisabilité",
    versioning: "Historique des plannings",
  };
  return titles[activePage] || "Mockup";
}

function injectLayout(activePage) {
  const { sidebar, header } = renderLayout(activePage);
  const root = document.getElementById("app-root");
  if (!root) return;
  const main = root.innerHTML;
  root.innerHTML = `
    <div class="flex h-screen overflow-hidden bg-slate-50">
      ${sidebar}
      <div class="flex-1 flex flex-col overflow-hidden">
        ${header}
        <main class="flex-1 overflow-auto">${main}</main>
      </div>
    </div>
  `;
}

// Tier badge helper
function tierBadge(tier) {
  const info = TIER_INFO[tier];
  return `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium" style="background:${info.bg};color:${info.couleur}">T${tier}</span>`;
}

// Validation card (used by conversation + replanif modal)
function validationCard({ titre, body, onConfirm = "alert('Mockup : modification appliquée')", onCancel = "alert('Mockup : annulé')" }) {
  return `
    <div class="border-2 border-amber-300 bg-amber-50 rounded-lg p-4 my-3">
      <div class="flex items-start gap-3">
        <div class="text-amber-600 text-lg">⚠</div>
        <div class="flex-1">
          <div class="font-semibold text-amber-900 mb-1">${titre}</div>
          <div class="text-sm text-amber-900/80 mb-3">${body}</div>
          <div class="flex gap-2">
            <button onclick="${onConfirm}" class="px-3 py-1.5 bg-emerald-600 text-white text-sm font-medium rounded hover:bg-emerald-700">
              ✓ Appliquer
            </button>
            <button onclick="${onCancel}" class="px-3 py-1.5 bg-white border border-slate-300 text-sm font-medium text-slate-700 rounded hover:bg-slate-50">
              ✗ Annuler
            </button>
            <button class="px-3 py-1.5 text-sm text-slate-600 rounded hover:bg-slate-100">
              Voir le détail complet
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
}
