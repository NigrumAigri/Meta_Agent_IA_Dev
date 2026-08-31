/**
 * Meta Developer Agent v5.0.0 — Interactive 2D Visual Flow Canvas (Style n8n)
 * Zoom, Panoramique, Déplacement des nœuds, Câbles animés et Drawer de Configuration
 */

class CanvasView {
  constructor() {
    this.wrapper = null;
    this.viewport = null;
    this.svgLayer = null;
    this.nodesLayer = null;
    this.scale = 1.0;
    this.panX = 80;
    this.panY = 50;
    this.isPanning = false;
    this.startX = 0;
    this.startY = 0;
    this.agents = [];
    this.links = [];
    this.activeAgent = null;
    this.draggedNode = null;
    this.connectingFrom = null;
  }

  init(containerId) {
    this.wrapper = document.getElementById(containerId);
    if (!this.wrapper) return;

    this.wrapper.innerHTML = `
      <div class="canvas-viewport" id="canvas-viewport">
        <svg class="canvas-svg-layer" id="canvas-svg-layer"></svg>
        <div id="canvas-nodes-layer"></div>
      </div>
      <div class="canvas-controls">
        <span style="font-size: 0.775rem; color: var(--text-muted); padding-right: 8px; border-right: 1px solid var(--border-subtle);" id="canvas-agent-count">6 Agents (6 Actifs)</span>
        <button class="btn btn-ghost btn-sm btn-icon" id="btn-zoom-in" title="Zoomer"><i data-lucide="plus"></i></button>
        <button class="btn btn-ghost btn-sm btn-icon" id="btn-zoom-out" title="Dézoomer"><i data-lucide="minus"></i></button>
        <span style="font-size: 0.775rem; font-weight: 600; min-width: 44px; text-align: center;" id="zoom-percent-display">100%</span>
        <button class="btn btn-ghost btn-sm btn-icon" id="btn-zoom-reset" title="Centrer (100%)"><i data-lucide="crosshair"></i></button>
        <button class="btn btn-ghost btn-sm btn-icon" id="btn-grid-snap" title="Aligner sur la grille"><i data-lucide="grid"></i></button>
      </div>
    `;

    this.viewport = document.getElementById("canvas-viewport");
    this.svgLayer = document.getElementById("canvas-svg-layer");
    this.nodesLayer = document.getElementById("canvas-nodes-layer");

    this.setupEvents();
    this.updateTransform();
  }

  setupEvents() {
    // Panoramique (Drag sur le canvas)
    this.wrapper.addEventListener("mousedown", (e) => {
      if (e.target === this.wrapper || e.target === this.viewport || e.target === this.svgLayer) {
        this.isPanning = true;
        this.startX = e.clientX - this.panX;
        this.startY = e.clientY - this.panY;
      }
    });

    window.addEventListener("mousemove", (e) => {
      if (this.isPanning) {
        this.panX = e.clientX - this.startX;
        this.panY = e.clientY - this.startY;
        this.updateTransform();
      }
      if (this.draggedNode) {
        const rect = this.viewport.getBoundingClientRect();
        const newX = (e.clientX - rect.left) / this.scale - this.dragOffsetX;
        const newY = (e.clientY - rect.top) / this.scale - this.dragOffsetY;
        
        this.draggedNode.style.left = `${Math.max(0, newX)}px`;
        this.draggedNode.style.top = `${Math.max(0, newY)}px`;
        this.drawConnections();
      }
    });

    window.addEventListener("mouseup", () => {
      this.isPanning = false;
      if (this.draggedNode) {
        const agentId = this.draggedNode.dataset.agentId;
        const x = parseFloat(this.draggedNode.style.left);
        const y = parseFloat(this.draggedNode.style.top);
        window.api.updateAgent(agentId, { canvas_x: x, canvas_y: y }).catch(console.error);
        this.draggedNode = null;
      }
    });

    // Zoom molette
    this.wrapper.addEventListener("wheel", (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
      this.scale = Math.min(Math.max(0.4, this.scale * zoomFactor), 2.0);
      this.updateTransform();
    });

    // Contrôles
    document.getElementById("btn-zoom-in")?.addEventListener("click", () => {
      this.scale = Math.min(2.0, this.scale * 1.2);
      this.updateTransform();
    });
    document.getElementById("btn-zoom-out")?.addEventListener("click", () => {
      this.scale = Math.max(0.4, this.scale * 0.8);
      this.updateTransform();
    });
    document.getElementById("btn-zoom-reset")?.addEventListener("click", () => {
      this.scale = 1.0;
      this.panX = 80;
      this.panY = 50;
      this.updateTransform();
    });
    document.getElementById("btn-grid-snap")?.addEventListener("click", () => {
      this.snapAllNodesToGrid();
    });
  }

  snapAllNodesToGrid() {
    const gridSize = 40;
    this.agents.forEach((a) => {
      const node = this.nodesLayer.querySelector(`[data-agent-id="${a.id}"]`);
      if (node) {
        const curX = parseFloat(node.style.left);
        const curY = parseFloat(node.style.top);
        const snappedX = Math.round(curX / gridSize) * gridSize;
        const snappedY = Math.round(curY / gridSize) * gridSize;
        node.style.left = `${snappedX}px`;
        node.style.top = `${snappedY}px`;
        window.api.updateAgent(a.id, { canvas_x: snappedX, canvas_y: snappedY });
      }
    });
    this.drawConnections();
  }

  updateTransform() {
    if (this.viewport) {
      this.viewport.style.transform = `translate(${this.panX}px, ${this.panY}px) scale(${this.scale})`;
    }
    const percentEl = document.getElementById("zoom-percent-display");
    if (percentEl) {
      percentEl.innerText = `${Math.round(this.scale * 100)}%`;
    }
  }

  async loadAgents(projectId = null) {
    try {
      this.agents = await window.api.getAgents(projectId);
      try {
        this.links = await window.api.getAgentLinks(projectId);
      } catch (err) {
        this.links = [];
      }
      this.renderNodes();
    } catch (e) {
      console.error("Échec chargement agents canvas:", e);
    }
  }

  async loadProjectAgents(projectId) {
    return this.loadAgents(projectId);
  }

  renderNodes() {
    if (!this.nodesLayer) return;
    this.nodesLayer.innerHTML = "";

    const activeCount = this.agents.filter(a => a.is_active).length;
    const countEl = document.getElementById("canvas-agent-count");
    if (countEl) countEl.innerText = `${this.agents.length} Agents (${activeCount} Actifs)`;

    this.agents.forEach((agent) => {
      const node = document.createElement("div");
      node.className = `agent-node ${agent.is_active ? 'active' : 'inactive'}`;
      node.dataset.agentId = agent.id;
      node.style.left = `${agent.canvas_x || 100}px`;
      node.style.top = `${agent.canvas_y || 100}px`;

      node.innerHTML = `
        <div class="node-port node-port-in" data-port-in="${agent.id}" title="Port Entrée (Input)"></div>
        <div class="node-port node-port-out" data-port-out="${agent.id}" title="Port Sortie (Output)"></div>
        
        <!-- En-Tête -->
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <div class="brand-logo" style="width: 26px; height: 26px;">
              <i data-lucide="${agent.icon || 'layers'}"></i>
            </div>
            <strong style="font-size: 0.85rem;" class="no-truncate">${agent.name}</strong>
          </div>
          <div style="display: flex; align-items: center; gap: 6px;">
            <button class="btn btn-ghost btn-icon btn-sm btn-agent-settings" data-agent-id="${agent.id}" title="Paramètres Complets">
              <i data-lucide="settings"></i>
            </button>
            <input type="checkbox" ${agent.is_active ? 'checked' : ''} class="agent-active-toggle" data-agent-id="${agent.id}" title="Activer / Désactiver">
          </div>
        </div>

        <!-- Rôle & Description -->
        <p style="font-size: 0.775rem; color: var(--text-muted); margin-bottom: 8px; line-height: 1.4;">
          ${agent.role_description}
        </p>

        <!-- Modèle & Tarifs In/Out/Cache -->
        <div style="background: rgba(0,0,0,0.25); border-radius: var(--radius-sm); padding: 6px 8px; margin-bottom: 8px; font-size: 0.725rem; color: var(--text-secondary);">
          <div>Modèle: <strong class="no-truncate" style="color: var(--text-primary);">${agent.model}</strong></div>
          <div style="color: var(--text-muted); font-size: 0.675rem; margin-top: 2px;">
            In: <span class="currency-nowrap">$ 0.80/M</span> · Out: <span class="currency-nowrap">$ 2.50/M</span> · Cache: <span class="currency-nowrap">$ 0.20/M</span>
          </div>
        </div>

        <!-- Consommation Live -->
        <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.725rem; color: var(--text-muted); border-top: 1px solid var(--border-subtle); padding-top: 6px;">
          <span>Conso Live: <strong class="currency-nowrap" style="color: var(--status-success);">$ 0.0000</strong></span>
          <span>Itér: <strong>${agent.max_iter}</strong></span>
        </div>
      `;

      // Déplacement du nœud
      node.addEventListener("mousedown", (e) => {
        if (e.target.closest(".btn-agent-settings") || e.target.closest(".agent-active-toggle") || e.target.closest(".node-port")) {
          return;
        }
        if (e.button === 0) {
          e.stopPropagation();
          this.draggedNode = node;
          const rect = node.getBoundingClientRect();
          this.dragOffsetX = (e.clientX - rect.left) / this.scale;
          this.dragOffsetY = (e.clientY - rect.top) / this.scale;
        }
      });

      // Bouton Settings
      node.querySelector(".btn-agent-settings")?.addEventListener("click", (e) => {
        e.stopPropagation();
        this.openAgentDrawer(agent);
      });

      // Switch On/Off
      node.querySelector(".agent-active-toggle")?.addEventListener("change", async (e) => {
        const isActive = e.target.checked;
        await window.api.updateAgent(agent.id, { is_active: isActive });
        agent.is_active = isActive;
        node.classList.toggle("active", isActive);
        node.classList.toggle("inactive", !isActive);
      });

      this.nodesLayer.appendChild(node);
    });

    if (window.lucide) window.lucide.createIcons();
    this.drawConnections();
  }

  drawConnections() {
    if (!this.svgLayer) return;
    this.svgLayer.innerHTML = "";

    // 1. Si des liaisons explicites DAG existent dans this.links, on les trace
    if (this.links && this.links.length > 0) {
      this.links.forEach((link) => {
        const sourceNode = this.nodesLayer.querySelector(`[data-agent-id="${link.source_agent_id}"]`);
        const targetNode = this.nodesLayer.querySelector(`[data-agent-id="${link.target_agent_id}"]`);

        if (sourceNode && targetNode) {
          const pX = parseFloat(sourceNode.style.left) + 280; // Port droit
          const pY = parseFloat(sourceNode.style.top) + 60;
          const cX = parseFloat(targetNode.style.left);        // Port gauche
          const cY = parseFloat(targetNode.style.top) + 60;

          const dx = Math.abs(cX - pX) * 0.5;
          const pathD = `M ${pX} ${pY} C ${pX + dx} ${pY}, ${cX - dx} ${cY}, ${cX} ${cY}`;

          // Ligne de base
          const baseCable = document.createElementNS("http://www.w3.org/2000/svg", "path");
          baseCable.setAttribute("d", pathD);
          baseCable.setAttribute("fill", "none");
          baseCable.setAttribute("stroke", "#27272a");
          baseCable.setAttribute("stroke-width", "3");
          this.svgLayer.appendChild(baseCable);

          // Câble animé avec pulsation lumineuse
          const animatedCable = document.createElementNS("http://www.w3.org/2000/svg", "path");
          animatedCable.setAttribute("d", pathD);
          animatedCable.setAttribute("fill", "none");
          animatedCable.setAttribute("stroke", link.link_type === "debate" ? "#8b5cf6" : "#22c55e");
          animatedCable.setAttribute("stroke-width", "2");
          animatedCable.setAttribute("stroke-dasharray", "6 18");
          animatedCable.setAttribute("class", "flowing-cable");
          this.svgLayer.appendChild(animatedCable);
        }
      });
      return;
    }

    // 2. Fallback sur parent_id
    this.agents.forEach((agent) => {
      if (agent.parent_id) {
        const parentNode = this.nodesLayer.querySelector(`[data-agent-id="${agent.parent_id}"]`);
        const childNode = this.nodesLayer.querySelector(`[data-agent-id="${agent.id}"]`);

        if (parentNode && childNode) {
          const pX = parseFloat(parentNode.style.left) + 280;
          const pY = parseFloat(parentNode.style.top) + 60;
          const cX = parseFloat(childNode.style.left);
          const cY = parseFloat(childNode.style.top) + 60;

          const dx = Math.abs(cX - pX) * 0.5;
          const pathD = `M ${pX} ${pY} C ${pX + dx} ${pY}, ${cX - dx} ${cY}, ${cX} ${cY}`;

          const baseCable = document.createElementNS("http://www.w3.org/2000/svg", "path");
          baseCable.setAttribute("d", pathD);
          baseCable.setAttribute("fill", "none");
          baseCable.setAttribute("stroke", "#27272a");
          baseCable.setAttribute("stroke-width", "3");
          this.svgLayer.appendChild(baseCable);

          const animatedCable = document.createElementNS("http://www.w3.org/2000/svg", "path");
          animatedCable.setAttribute("d", pathD);
          animatedCable.setAttribute("fill", "none");
          animatedCable.setAttribute("stroke", "#22c55e");
          animatedCable.setAttribute("stroke-width", "2");
          animatedCable.setAttribute("stroke-dasharray", "6 18");
          animatedCable.setAttribute("class", "flowing-cable");
          this.svgLayer.appendChild(animatedCable);
        }
      }
    });
  }

  openAgentDrawer(agent) {
    const drawer = document.getElementById("agent-drawer");
    if (!drawer) return;

    document.getElementById("drawer-agent-name").innerText = agent.name;
    document.getElementById("drawer-input-role").value = agent.role_description;
    document.getElementById("drawer-input-model").value = agent.model;
    document.getElementById("drawer-input-temp").value = agent.temperature;
    document.getElementById("drawer-temp-val").innerText = agent.temperature;
    document.getElementById("drawer-input-max-iter").value = agent.max_iter;
    document.getElementById("drawer-input-reasoning").value = agent.reasoning_effort || "medium";

    const saveBtn = document.getElementById("btn-save-agent-drawer");
    if (saveBtn) {
      saveBtn.onclick = async () => {
        await window.api.updateAgent(agent.id, {
          role_description: document.getElementById("drawer-input-role").value,
          model: document.getElementById("drawer-input-model").value,
          temperature: parseFloat(document.getElementById("drawer-input-temp").value) || 0.2,
          max_iter: parseInt(document.getElementById("drawer-input-max-iter").value, 10) || 5,
          reasoning_effort: document.getElementById("drawer-input-reasoning").value,
        });
        window.api.showToast(`Configuration de l'agent '${agent.name}' mise à jour`, "success");
        drawer.classList.remove("open");
        await this.loadAgents();
      };
    }

    drawer.classList.add("open");
  }
}

window.canvasView = new CanvasView();
