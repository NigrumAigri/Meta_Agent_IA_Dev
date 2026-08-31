/**
 * Meta Developer Agent v5.0.0 — Human-in-the-Loop (HITL) Modal Controller
 * Gestion des approbations et rejets d'actions sensibles
 */

class HitlModal {
  constructor() {
    this.modal = null;
  }

  init() {
    this.modal = document.getElementById("hitl-modal");
    const openBtn = document.getElementById("btn-open-hitl");
    const closeBtn = document.getElementById("btn-close-hitl");

    if (openBtn) openBtn.onclick = () => this.open();
    if (closeBtn) closeBtn.onclick = () => this.close();

    // Polling initial des requêtes en attente
    this.updatePendingBadge();
  }

  async open() {
    if (this.modal) {
      this.modal.classList.add("active");
      await this.loadPendingRequests();
    }
  }

  close() {
    if (this.modal) {
      this.modal.classList.remove("active");
    }
  }

  async updatePendingBadge() {
    try {
      const requests = await window.api.getHitlRequests();
      const badge = document.getElementById("hitl-pending-badge");
      if (badge) {
        if (requests.length > 0) {
          badge.style.display = "inline-flex";
          badge.innerText = requests.length;
        } else {
          badge.style.display = "none";
        }
      }
    } catch (e) {
      console.error("Échec rafraîchissement badge HITL:", e);
    }
  }

  async loadPendingRequests() {
    const listContainer = document.getElementById("hitl-requests-list");
    if (!listContainer) return;

    try {
      const requests = await window.api.getHitlRequests();
      listContainer.innerHTML = "";

      if (requests.length === 0) {
        listContainer.innerHTML = `
          <div style="text-align: center; color: var(--text-muted); padding: 30px 10px;">
            <i data-lucide="shield-check" style="width: 36px; height: 36px; margin: 0 auto 10px; display: block; color: var(--status-success);"></i>
            Aucune action sensible en attente de validation humaine.
          </div>
        `;
        if (window.lucide) window.lucide.createIcons();
        return;
      }

      requests.forEach((req) => {
        const item = document.createElement("div");
        item.style.cssText = "background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 16px; margin-bottom: 12px;";

        item.innerHTML = `
          <div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 8px;">
            <div>
              <span class="badge badge-warning" style="margin-bottom: 4px;">${req.request_type}</span>
              <h4 style="font-size: 0.95rem; font-weight: 600;">${req.title}</h4>
            </div>
            <span style="font-size: 0.725rem; color: var(--text-muted);">${new Date(req.created_at).toLocaleTimeString()}</span>
          </div>
          <p style="font-size: 0.825rem; color: var(--text-secondary); margin-bottom: 12px; line-height: 1.4;">
            ${req.description}
          </p>
          <div style="display: flex; gap: 8px; justify-content: flex-end;">
            <button class="btn btn-secondary btn-sm" id="btn-reject-${req.id}">
              <i data-lucide="x"></i> Rejeter
            </button>
            <button class="btn btn-primary btn-sm" id="btn-approve-${req.id}">
              <i data-lucide="check"></i> Approuver
            </button>
          </div>
        `;

        listContainer.appendChild(item);

        // Handlers
        item.querySelector(`#btn-approve-${req.id}`).onclick = async () => {
          await window.api.approveHitlRequest(req.id);
          window.api.showToast("Demande approuvée avec succès", "success");
          await this.loadPendingRequests();
          await this.updatePendingBadge();
        };

        item.querySelector(`#btn-reject-${req.id}`).onclick = async () => {
          const reason = prompt("Motif du rejet :", "Refusé par l'opérateur");
          if (reason) {
            await window.api.rejectHitlRequest(req.id, reason);
            window.api.showToast("Demande rejetée", "warning");
            await this.loadPendingRequests();
            await this.updatePendingBadge();
          }
        };
      });

      if (window.lucide) window.lucide.createIcons();
    } catch (e) {
      console.error("Échec chargement HITL:", e);
    }
  }
}

window.hitlModal = new HitlModal();
