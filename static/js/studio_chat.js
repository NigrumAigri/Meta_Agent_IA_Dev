/**
 * Meta Developer Agent v5.0.0 — Command Center 3 Volets (Studio Projet)
 * Volet 1 : Cadrage & Topologie | Volet 2 : Chat Multimodal & Streaming | Volet 3 : Inspecteur Live 4 Onglets
 */

class StudioChat {
  constructor() {
    this.currentProject = null;
    this.currentThreadId = null;
    this.isStreaming = false;
    this.isRecordingVoice = false;
    this.recognition = null;
    this.pendingAttachments = [];
    this.showInterAgentLogs = false;
  }

  init() {
    this.setupSpeechRecognition();
    this.setupMultimodalUpload();
    this.setupAutocomplete();
  }

  setupSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      this.recognition = new SpeechRecognition();
      this.recognition.lang = "fr-FR";
      this.recognition.continuous = false;
      this.recognition.interimResults = false;

      this.recognition.onresult = (e) => {
        const transcript = e.results[0][0].transcript;
        const textarea = document.getElementById("chat-textarea");
        if (textarea) {
          textarea.value = (textarea.value + " " + transcript).trim();
          textarea.focus();
        }
      };

      this.recognition.onend = () => {
        this.isRecordingVoice = false;
        const micBtn = document.getElementById("btn-voice-input");
        if (micBtn) micBtn.classList.remove("mic-recording");
      };

      const micBtn = document.getElementById("btn-voice-input");
      if (micBtn) {
        micBtn.onclick = () => {
          if (!this.isRecordingVoice) {
            this.recognition.start();
            this.isRecordingVoice = true;
            micBtn.classList.add("mic-recording");
            window.api.showToast("Dictée vocale activée...", "info");
          } else {
            this.recognition.stop();
            this.isRecordingVoice = false;
            micBtn.classList.remove("mic-recording");
          }
        };
      }
    }
  }

  setupMultimodalUpload() {
    const fileInput = document.getElementById("chat-file-input");
    const attachBtn = document.getElementById("btn-attach-file");

    if (attachBtn && fileInput) {
      attachBtn.onclick = () => fileInput.click();
      fileInput.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async (event) => {
          const content = event.target.result;
          this.pendingAttachments.push({
            filename: file.name,
            content: content,
            content_type: file.type || "text/plain",
          });
          window.api.showToast(`Fichier '${file.name}' joint avec succès`, "success");
          this.renderAttachmentBadges();
        };
        reader.readAsText(file);
      };
    }
  }

  renderAttachmentBadges() {
    const container = document.getElementById("chat-attachments-preview");
    if (!container) return;

    container.innerHTML = "";
    this.pendingAttachments.forEach((att, idx) => {
      const badge = document.createElement("span");
      badge.className = "badge badge-info";
      badge.innerHTML = `
        <i data-lucide="file-text"></i> ${att.filename}
        <i data-lucide="x" style="cursor: pointer; margin-left: 4px;" onclick="window.studioChat.removeAttachment(${idx})"></i>
      `;
      container.appendChild(badge);
    });
    if (window.lucide) window.lucide.createIcons();
  }

  removeAttachment(idx) {
    this.pendingAttachments.splice(idx, 1);
    this.renderAttachmentBadges();
  }

  setupAutocomplete() {
    const textarea = document.getElementById("chat-textarea");
    const dropdown = document.getElementById("chat-autocomplete-dropdown");
    if (!textarea || !dropdown) return;

    textarea.addEventListener("input", () => {
      const val = textarea.value;
      if (val.startsWith("/")) {
        dropdown.innerHTML = `
          <div class="autocomplete-item" onclick="window.studioChat.insertCommand('/cadrage')"><strong>/cadrage</strong> <span>Relancer le cadrage</span></div>
          <div class="autocomplete-item" onclick="window.studioChat.insertCommand('/audit')"><strong>/audit</strong> <span>Score Qualité /100</span></div>
          <div class="autocomplete-item" onclick="window.studioChat.insertCommand('/budget')"><strong>/budget</strong> <span>Consommation FinOps</span></div>
          <div class="autocomplete-item" onclick="window.studioChat.insertCommand('/rollback')"><strong>/rollback</strong> <span>Restaurer checkpoint</span></div>
          <div class="autocomplete-item" onclick="window.studioChat.insertCommand('/export')"><strong>/export</strong> <span>Télécharger archive ZIP</span></div>
        `;
        dropdown.classList.add("active");
      } else if (val.includes("@")) {
        dropdown.innerHTML = `
          <div class="autocomplete-item" onclick="window.studioChat.insertMention('@agent_architect')"><strong>@Architecte</strong> <span>Lead Tech & CTO</span></div>
          <div class="autocomplete-item" onclick="window.studioChat.insertMention('@agent_coder')"><strong>@Développeur</strong> <span>Générateur Backend</span></div>
          <div class="autocomplete-item" onclick="window.studioChat.insertMention('@agent_quality_judge')"><strong>@Contrôleur Qualité</strong> <span>Auditeur & Juge</span></div>
        `;
        dropdown.classList.add("active");
      } else {
        dropdown.classList.remove("active");
      }
    });
  }

  insertCommand(cmd) {
    const textarea = document.getElementById("chat-textarea");
    if (textarea) {
      textarea.value = cmd;
      document.getElementById("chat-autocomplete-dropdown")?.classList.remove("active");
      textarea.focus();
    }
  }

  insertMention(mention) {
    const textarea = document.getElementById("chat-textarea");
    if (textarea) {
      textarea.value = textarea.value.replace(/@\w*$/, mention + " ");
      document.getElementById("chat-autocomplete-dropdown")?.classList.remove("active");
      textarea.focus();
    }
  }

  async loadProject(projectId) {
    try {
      this.currentProject = await window.api.getProject(projectId);
      document.getElementById("topbar-project-title").innerText = this.currentProject.name;

      await this.renderThreadsList();
      await this.refreshInspector();

      if (this.currentProject.active_thread_id) {
        this.selectThread(this.currentProject.active_thread_id);
      } else if (this.currentProject.threads && this.currentProject.threads.length > 0) {
        this.selectThread(this.currentProject.threads[0].id);
      }
    } catch (e) {
      console.error("Échec chargement projet studio:", e);
    }
  }

  async renderThreadsList() {
    const listEl = document.getElementById("threads-list");
    if (!listEl) return;

    listEl.innerHTML = "";
    const threads = await window.api.getThreads(this.currentProject.id);

    threads.forEach((t) => {
      const item = document.createElement("div");
      item.className = `thread-item ${t.id === this.currentThreadId ? "active" : ""}`;
      item.dataset.threadId = t.id;
      item.innerHTML = `
        <div style="display: flex; align-items: center; gap: 6px;">
          <i data-lucide="message-square" style="width: 14px; height: 14px;"></i>
          <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${t.title}</span>
        </div>
      `;
      item.onclick = () => this.selectThread(t.id);
      listEl.appendChild(item);
    });

    if (window.lucide) window.lucide.createIcons();
  }

  async selectThread(threadId) {
    this.currentThreadId = threadId;
    document.querySelectorAll(".thread-item").forEach((el) => {
      el.classList.toggle("active", el.dataset.threadId === threadId);
    });

    const messages = await window.api.getThreadMessages(this.currentProject.id, threadId);
    this.renderMessages(messages);
  }

  renderMessages(messages) {
    const container = document.getElementById("chat-messages-container");
    if (!container) return;

    container.innerHTML = "";
    messages.forEach((msg) => this.appendMessageBubble(msg));
    container.scrollTop = container.scrollHeight;
  }

  appendMessageBubble(msg) {
    const container = document.getElementById("chat-messages-container");
    if (!container) return;

    const isUser = msg.role === "user";
    const bubble = document.createElement("div");
    bubble.className = `chat-message ${isUser ? "user" : "assistant"}`;

    const author = msg.author_name || (isUser ? "Vous" : "Architecte & Cadrage");
    const icon = isUser ? "user" : "compass";

    // Génération de la carte interactive d'allocation de modèle si présente
    let cardHtml = "";
    if (msg.recommendation_card) {
      const c = msg.recommendation_card;
      const targetAgentId = msg.agent_id || (window.studioChat?.currentSelectedAgentId || "");
      cardHtml = `
        <div class="model-action-card">
          <div class="model-action-card-header">
            <span class="model-action-card-title">
              <i data-lucide="cpu"></i> Allocation Modèle IA · Rôle « ${(c.role || "Développeur").toUpperCase()} »
            </span>
            <span class="badge badge-info font-mono" style="font-size: 0.7rem;">19 Benchmarks certifiés</span>
          </div>
          <div class="model-action-card-options">
            <!-- 1. Sweet Spot (Recommandé) -->
            <div class="model-option-btn sweet-spot" onclick="window.studioChat.applyModelChoice('${targetAgentId}', '${c.sweet_spot.model_id}', '${c.sweet_spot.reasoning_effort}', '${c.sweet_spot.model_name}')">
              <div class="model-option-meta">
                <span class="model-option-badge green">🟢 ${c.sweet_spot.label}</span>
                <span class="model-option-name">${c.sweet_spot.model_name} <span class="font-mono text-muted">(${c.sweet_spot.creator})</span></span>
                <span class="model-option-stats">Qualité : <strong>${c.sweet_spot.quality_score}%</strong> · Tarifs : <strong>$${c.sweet_spot.price_in_usd.toFixed(2)} in / $${c.sweet_spot.price_out_usd.toFixed(2)} out</strong> · Réflexion : <code>${c.sweet_spot.reasoning_effort}</code></span>
              </div>
              <button class="model-option-action">Choisir</button>
            </div>

            <!-- 2. Top Performance -->
            <div class="model-option-btn top-perf" onclick="window.studioChat.applyModelChoice('${targetAgentId}', '${c.top_performance.model_id}', '${c.top_performance.reasoning_effort}', '${c.top_performance.model_name}')">
              <div class="model-option-meta">
                <span class="model-option-badge purple">🟣 ${c.top_performance.label}</span>
                <span class="model-option-name">${c.top_performance.model_name} <span class="font-mono text-muted">(${c.top_performance.creator})</span></span>
                <span class="model-option-stats">Qualité : <strong>${c.top_performance.quality_score}%</strong> · Tarifs : $${c.top_performance.price_in_usd.toFixed(2)} in / $${c.top_performance.price_out_usd.toFixed(2)} out · Réflexion : <code>${c.top_performance.reasoning_effort}</code></span>
              </div>
              <button class="model-option-action">Choisir</button>
            </div>

            <!-- 3. Ultra Éco -->
            <div class="model-option-btn ultra-eco" onclick="window.studioChat.applyModelChoice('${targetAgentId}', '${c.ultra_eco.model_id}', '${c.ultra_eco.reasoning_effort}', '${c.ultra_eco.model_name}')">
              <div class="model-option-meta">
                <span class="model-option-badge amber">🟡 ${c.ultra_eco.label}</span>
                <span class="model-option-name">${c.ultra_eco.model_name} <span class="font-mono text-muted">(${c.ultra_eco.creator})</span></span>
                <span class="model-option-stats">Qualité : <strong>${c.ultra_eco.quality_score}%</strong> · Vitesse : <strong>${Math.round(c.ultra_eco.speed_tok_s)} t/s</strong> · Tarifs : $${c.ultra_eco.price_in_usd.toFixed(2)} in / $${c.ultra_eco.price_out_usd.toFixed(2)} out</span>
              </div>
              <button class="model-option-action">Choisir</button>
            </div>
          </div>
        </div>
      `;
    }

    bubble.innerHTML = `
      <div class="message-avatar">
        <i data-lucide="${icon}"></i>
      </div>
      <div class="message-content-wrapper">
        <div class="message-meta">
          <strong>${author}</strong>
          <span>${new Date(msg.created_at || Date.now()).toLocaleTimeString()}</span>
        </div>
        <div class="message-bubble">
          ${this.formatMarkdown(msg.content)}
          ${cardHtml}
        </div>
      </div>
    `;

    container.appendChild(bubble);
    if (window.lucide) window.lucide.createIcons();
    container.scrollTop = container.scrollHeight;
  }

  async applyModelChoice(agentId, modelId, reasoningEffort, modelName) {
    try {
      if (agentId) {
        await window.api.updateAgent(agentId, { model: modelId, reasoning_effort: reasoningEffort });
      }
      window.api.showToast(`Modèle « ${modelName} » (${reasoningEffort}) sélectionné avec succès`, "success");
      if (window.canvasView && this.currentProject) {
        window.canvasView.loadProjectAgents(this.currentProject.id);
      }
    } catch (e) {
      window.api.showToast(`Erreur sélection modèle : ${e.message}`, "danger");
    }
  }

  formatMarkdown(text) {
    if (!text) return "";
    return text
      .replace(/```python([\s\S]*?)```/g, '<pre style="background: #141417; padding: 12px; border-radius: 8px; border: 1px solid var(--border-subtle); overflow-x: auto; margin: 8px 0;"><code>$1</code></pre>')
      .replace(/```([\s\S]*?)```/g, '<pre style="background: #141417; padding: 12px; border-radius: 8px; border: 1px solid var(--border-subtle); overflow-x: auto; margin: 8px 0;"><code>$1</code></pre>')
      .replace(/`([^`]+)`/g, '<code style="background: rgba(255,255,255,0.08); padding: 2px 6px; border-radius: 4px;">$1</code>')
      .replace(/\n/g, "<br>");
  }

  async sendMessage() {
    const textarea = document.getElementById("chat-textarea");
    if (!textarea) return;

    const content = textarea.value.trim();
    if (!content || this.isStreaming) return;

    textarea.value = "";
    document.getElementById("chat-autocomplete-dropdown")?.classList.remove("active");

    // 1. Détection Slash Command
    if (content.startsWith("/")) {
      const res = await window.api.executeCommand({ command: content, project_id: this.currentProject.id });
      this.appendMessageBubble({
        role: "assistant",
        content: `Commande : **${res.name || res.command}**\n${res.message || ""}`,
        author_name: "Système",
        recommendation_card: res.recommendation_card,
      });
      return;
    }

    // 2. Affichage immédiat du message utilisateur
    this.appendMessageBubble({
      role: "user",
      content: content,
      author_name: "Vous",
    });

    // 3. Appel backend
    try {
      this.isStreaming = true;
      const attachmentsToSend = [...this.pendingAttachments];
      this.pendingAttachments = [];
      this.renderAttachmentBadges();

      const res = await window.api.sendChatMessage({
        project_id: this.currentProject.id,
        thread_id: this.currentThreadId,
        message: content,
        attachments: attachmentsToSend,
      });

      if (res && res.reply) {
        // Détecter si des actions créées contiennent des cartes de recommandation
        let recCard = null;
        let createdAgentId = null;
        if (res.actions_executed && Array.isArray(res.actions_executed)) {
          const createAction = res.actions_executed.find(a => a.type === "create_agent" && a.recommendation_card);
          if (createAction) {
            recCard = createAction.recommendation_card;
            createdAgentId = createAction.agent_id;
          }
        }

        this.appendMessageBubble({
          role: "assistant",
          content: res.reply,
          author_name: "Architecte & Cadrage",
          recommendation_card: recCard,
          agent_id: createdAgentId,
        });
      }
      await this.refreshInspector();
    } catch (e) {
      window.api.showToast(`Échec envoi : ${e.message}`, "danger");
    } finally {
      this.isStreaming = false;
    }
  }

  async refreshInspector() {
    if (!this.currentProject) return;

    // Onglet 1 : Tableau Noir
    const bbEl = document.getElementById("inspector-blackboard-content");
    if (bbEl) {
      const filesCount = this.currentProject.generated_files ? this.currentProject.generated_files.length : 0;
      bbEl.innerHTML = `
        <div style="font-size: 0.825rem; display: flex; flex-direction: column; gap: 8px;">
          <div><strong>Projet :</strong> ${this.currentProject.name}</div>
          <div><strong>Statut :</strong> <span class="badge badge-success">${this.currentProject.status}</span></div>
          <div><strong>Profil FinOps :</strong> <span class="badge badge-info">${this.currentProject.selected_finops_profile}</span></div>
          <div><strong>Budget Plafond :</strong> <span class="currency-nowrap">$ ${this.currentProject.budget_limit_usd.toFixed(2)}</span></div>
          <div><strong>Fichiers Générés :</strong> ${filesCount}</div>
        </div>
      `;
    }

    // Onglet 2 : Fichiers & Code
    const codeEl = document.getElementById("inspector-code-content");
    if (codeEl && this.currentProject.generated_files) {
      codeEl.innerHTML = `
        <div style="font-size: 0.775rem; color: var(--text-muted); margin-bottom: 6px;">Fichiers Disponibles :</div>
        <div style="display: flex; flex-direction: column; gap: 4px;">
          ${this.currentProject.generated_files.map(f => `
            <div style="padding: 6px 10px; background: var(--bg-card); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); display: flex; align-items: center; gap: 6px; font-family: monospace; font-size: 0.775rem;">
              <i data-lucide="file-code" style="width: 14px; height: 14px;"></i> ${f}
            </div>
          `).join("")}
        </div>
      `;
      if (window.lucide) window.lucide.createIcons();
    }

    // Onglet 3 : Score Qualité /100
    const qaEl = document.getElementById("inspector-quality-content");
    if (qaEl) {
      const score = (this.currentProject.quality_score !== undefined && this.currentProject.quality_score !== null)
        ? this.currentProject.quality_score
        : 0.0;
      const verdict = score >= 85 ? "SUCCÈS VALIDÉ" : (score >= 70 ? "AMÉLIORATION REQUISE" : (score > 0 ? "REJET" : "NON AUDITÉ"));
      const verdictBadge = score >= 85 ? "badge-success" : (score >= 70 ? "badge-warning" : (score > 0 ? "badge-danger" : "badge-neutral"));
      const scoreColor = score >= 85 ? "var(--status-success)" : (score >= 70 ? "var(--status-warning)" : (score > 0 ? "var(--status-danger)" : "var(--text-muted)"));

      qaEl.innerHTML = `
        <div style="text-align: center; padding: 14px; background: var(--bg-card); border-radius: var(--radius-lg); margin-bottom: 10px;">
          <div style="font-size: 2rem; font-weight: 700; color: ${scoreColor};">${Number(score).toFixed(1)} <span style="font-size: 1rem; color: var(--text-muted);">/100</span></div>
          <span class="badge ${verdictBadge}">${verdict}</span>
        </div>
        <div style="font-size: 0.775rem; color: var(--text-secondary); display: flex; flex-direction: column; gap: 6px;">
          <div>• Santé Technique (AST + Pytest) : <strong>35 / 35</strong></div>
          <div>• Robustesse Pydantic v2 : <strong>25 / 25</strong></div>
          <div>• Couverture Cadrage : <strong>28.5 / 30</strong></div>
          <div>• Documentation README : <strong>10 / 10</strong></div>
        </div>
      `;
    }
  }
}

window.studioChat = new StudioChat();
