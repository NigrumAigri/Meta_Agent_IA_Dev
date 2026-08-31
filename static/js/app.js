/**
 * Meta Developer Agent v5.0.0 — Master SPA Application Controller
 * Gestion des 8 Écrans, Navigation, Modales et Initialisation
 */

class App {
  constructor() {
    this.currentScreen = "screen-dashboard";
  }

  async init() {
    this.setupNavigation();
    this.setupModals();
    this.setupGlobalShortcuts();

    // Initialisation des sous-systèmes
    window.copilotModal.init();
    window.hitlModal.init();
    window.canvasView.init("canvas-container");

    // Affichage de l'écran initial
    await this.navigate("screen-dashboard");

    // Rafraîchir les icônes Lucide
    if (window.lucide) window.lucide.createIcons();
  }

  setupNavigation() {
    document.querySelectorAll(".nav-item").forEach((btn) => {
      btn.onclick = () => {
        const targetScreen = btn.dataset.screen;
        if (targetScreen) this.navigate(targetScreen);
      };
    });
  }

  async navigate(screenId, params = {}) {
    this.currentScreen = screenId;

    // Mise à jour de la classe active sur la sidebar
    document.querySelectorAll(".nav-item").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.screen === screenId);
    });

    // Affichage de l'écran cible
    document.querySelectorAll(".screen").forEach((scr) => {
      scr.classList.toggle("active", scr.id === screenId);
    });

    // Chargement dynamique des données de l'écran
    if (screenId === "screen-dashboard") {
      await this.loadDashboard();
    } else if (screenId === "screen-studio" && params.projectId) {
      await window.studioChat.loadProject(params.projectId);
    } else if (screenId === "screen-canvas") {
      await window.canvasView.loadAgents();
    } else if (screenId === "screen-finops") {
      await this.loadFinOpsScreen();
    } else if (screenId === "screen-benchmarks") {
      await this.loadBenchmarksScreen();
    } else if (screenId === "screen-mcp") {
      await this.loadMcpScreen();
    } else if (screenId === "screen-pillars") {
      await this.loadPillarsScreen();
    } else if (screenId === "screen-settings") {
      await this.loadSettingsScreen();
    }

    if (window.lucide) window.lucide.createIcons();
  }

  setupModals() {
    // Modale Nouveau Projet
    const newProjectModal = document.getElementById("modal-new-project");
    const openNewProjectBtns = document.querySelectorAll(".btn-open-new-project");
    const closeNewProjectBtn = document.getElementById("btn-close-new-project");
    const formNewProject = document.getElementById("form-new-project");

    openNewProjectBtns.forEach((b) => (b.onclick = () => newProjectModal?.classList.add("active")));
    if (closeNewProjectBtn) closeNewProjectBtn.onclick = () => newProjectModal?.classList.remove("active");

    if (formNewProject) {
      formNewProject.onsubmit = async (e) => {
        e.preventDefault();
        const name = document.getElementById("input-project-name").value;
        const budget = parseFloat(document.getElementById("input-project-budget").value || 10.0);
        const profile = document.getElementById("select-project-profile").value;

        try {
          const project = await window.api.createProject({
            name,
            budget_limit_usd: budget,
            selected_finops_profile: profile,
          });
          newProjectModal.classList.remove("active");
          window.api.showToast(`Projet '${name}' créé avec succès`, "success");
          await this.navigate("screen-studio", { projectId: project.id });
        } catch (err) {
          window.api.showToast(err.message, "danger");
        }
      };
    }
  }

  setupGlobalShortcuts() {
    window.addEventListener("keydown", (e) => {
      // Ctrl+K : Ouvrir Copilote Système
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        window.copilotModal.toggle();
      }
    });
  }

  // --- SCREEN 1 : DASHBOARD ---
  async loadDashboard() {
    const grid = document.getElementById("projects-grid");
    if (!grid) return;

    grid.innerHTML = `<div style="color: var(--text-muted);">Chargement des projets...</div>`;
    const projects = await window.api.getProjects();
    grid.innerHTML = "";

    if (projects.length === 0) {
      grid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: var(--text-muted);">
          <i data-lucide="folder-plus" style="width: 48px; height: 48px; margin: 0 auto 12px; display: block;"></i>
          Aucun projet pour le moment. Cliquez sur <strong>Nouveau Projet</strong> pour commencer le cadrage.
        </div>
      `;
      return;
    }

    projects.forEach((p) => {
      const card = document.createElement("div");
      card.className = "project-card";
      card.innerHTML = `
        <div class="project-card-header">
          <h3 class="project-card-title">${p.name}</h3>
          <span class="badge badge-success">${p.status}</span>
        </div>
        <p style="font-size: 0.8rem; color: var(--text-secondary); line-height: 1.4;">
          Profil FinOps: <strong>${p.selected_finops_profile}</strong>
        </p>
        <div class="project-card-meta">
          <span>Budget: <strong class="currency-nowrap">$ ${p.budget_limit_usd.toFixed(2)}</strong></span>
          <span>Threads: <strong>${p.threads ? p.threads.length : 1}</strong></span>
        </div>
        <div style="display: flex; gap: 8px; margin-top: 6px;">
          <button class="btn btn-primary btn-sm" style="flex: 1;" onclick="window.app.navigate('screen-studio', { projectId: '${p.id}' })">
            <i data-lucide="play"></i> Ouvrir Studio
          </button>
          <a href="/api/v1/projects/${p.id}/export/zip" class="btn btn-secondary btn-sm" title="Télécharger ZIP">
            <i data-lucide="download"></i>
          </a>
        </div>
      `;
      grid.appendChild(card);
    });
  }

  // --- SCREEN 4 : FINOPS ---
  async loadFinOpsScreen() {
    const tableBody = document.getElementById("finops-ledger-body");
    if (!tableBody) return;

    const ledger = await window.api.getFinOpsLedger();
    tableBody.innerHTML = "";

    ledger.forEach((entry) => {
      const row = document.createElement("tr");
      row.style.borderBottom = "1px solid var(--border-subtle)";
      row.innerHTML = `
        <td style="padding: 10px;">${new Date(entry.timestamp).toLocaleTimeString()}</td>
        <td style="padding: 10px;"><strong>${entry.agent_name}</strong></td>
        <td style="padding: 10px;"><code class="no-truncate">${entry.model}</code></td>
        <td style="padding: 10px;">${entry.total_tokens.toLocaleString()}</td>
        <td style="padding: 10px;"><strong class="currency-nowrap">$ ${entry.cost_usd.toFixed(4)}</strong></td>
        <td style="padding: 10px;">${entry.latency_ms} ms</td>
        <td style="padding: 10px;"><span class="badge badge-success">${entry.status}</span></td>
      `;
      tableBody.appendChild(row);
    });
  }

  // --- SCREEN 5 : 19 BENCHMARKS ---
  async loadBenchmarksScreen() {
    const grid = document.getElementById("benchmarks-grid");
    if (!grid) return;

    const benchmarks = await window.api.getBenchmarks();
    grid.innerHTML = "";

    benchmarks.forEach((b) => {
      const card = document.createElement("div");
      card.className = "project-card";
      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
          <div>
            <h4 style="font-size: 0.95rem; font-weight: 600;">${b.name}</h4>
            <span style="font-size: 0.75rem; color: var(--text-muted);">${b.creator}</span>
          </div>
          <span class="badge badge-info">${b.badge}</span>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.775rem; color: var(--text-secondary); margin-bottom: 8px;">
          <div>Qualité Index: <strong>${b.quality_index}</strong></div>
          <div>Coding Score: <strong>${b.coding_score}</strong></div>
          <div>Raisonnement: <strong>${b.reasoning_score}</strong></div>
          <div>Vitesse: <strong>${b.speed_tok_s} tok/s</strong></div>
        </div>
        <div style="font-size: 0.75rem; color: var(--text-muted); border-top: 1px solid var(--border-subtle); padding-top: 6px;">
          Prix $/M (In/Out) : <strong class="currency-nowrap">$ ${b.price_in_usd} / $ ${b.price_out_usd}</strong>
        </div>
      `;
      grid.appendChild(card);
    });
  }

  // --- SCREEN 6 : MCP ---
  async loadMcpScreen() {
    const toolsGrid = document.getElementById("mcp-tools-grid");
    if (!toolsGrid) return;

    const tools = await window.api.getMcpTools();
    toolsGrid.innerHTML = "";

    tools.forEach((t) => {
      const card = document.createElement("div");
      card.className = "project-card";
      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
          <h4 style="font-size: 0.9rem; font-weight: 600;">${t.name}</h4>
          <span class="badge ${t.is_core ? 'badge-success' : 'badge-info'}">${t.is_core ? 'Natif' : 'Externe'}</span>
        </div>
        <p style="font-size: 0.775rem; color: var(--text-secondary); line-height: 1.4;">${t.description}</p>
        <span style="font-size: 0.725rem; color: var(--text-muted);">Catégorie : <strong>${t.category}</strong></span>
      `;
      toolsGrid.appendChild(card);
    });
  }

  // --- SCREEN 7 : PILIERS ---
  async loadPillarsScreen() {
    const skillsList = document.getElementById("pillars-skills-list");
    const rulesList = document.getElementById("pillars-rules-list");
    if (skillsList) {
      const skills = await window.api.getSkills();
      skillsList.innerHTML = skills.map((s) => `
        <div style="background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 12px; margin-bottom: 8px;">
          <div style="font-weight: 600; font-size: 0.875rem;">${s.name} <span class="badge badge-info">${s.version}</span></div>
          <p style="font-size: 0.775rem; color: var(--text-secondary);">${s.description}</p>
        </div>
      `).join("");
    }
    if (rulesList) {
      const rules = await window.api.getRules();
      rulesList.innerHTML = rules.map((r) => `
        <div style="background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 12px; margin-bottom: 8px;">
          <div style="font-weight: 600; font-size: 0.875rem;">${r.name} <span class="badge badge-warning">${r.category}</span></div>
          <pre style="font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;"><code>${r.content}</code></pre>
        </div>
      `).join("");
    }
  }

  // --- SCREEN 8 : SETTINGS ---
  async loadSettingsScreen() {
    const config = await window.api.getConfig();
    const keyInput = document.getElementById("settings-openrouter-key");
    const aaKeyInput = document.getElementById("settings-aa-key");
    const discModel = document.getElementById("settings-discovery-model");
    const coderModel = document.getElementById("settings-coder-model");

    if (keyInput) keyInput.placeholder = config.llm_api_key_masked || "sk-or-v1-••••";
    if (aaKeyInput) aaKeyInput.placeholder = config.artificial_analysis_key_masked || "aa_••••";
    if (discModel) discModel.value = config.llm_discovery_model || "";
    if (coderModel) coderModel.value = config.llm_coder_model || "";

    const form = document.getElementById("form-settings");
    if (form) {
      form.onsubmit = async (e) => {
        e.preventDefault();
        const payload = {};
        if (keyInput.value) payload.llm_api_key = keyInput.value;
        if (aaKeyInput.value) payload.artificial_analysis_api_key = aaKeyInput.value;
        if (discModel.value) payload.llm_discovery_model = discModel.value;
        if (coderModel.value) payload.llm_coder_model = coderModel.value;

        await window.api.updateConfig(payload);
        window.api.showToast("Paramètres sauvegardés et rechargés à chaud", "success");
      };
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.app = new App();
  window.app.init();
});
