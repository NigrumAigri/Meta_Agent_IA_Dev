/**
 * Meta Developer Agent v5.0.0 — System Copilot Drawer Controller
 * Assistance transverse, reparamétrage à chaud et discussion étanche
 */

class CopilotModal {
  constructor() {
    this.drawer = null;
    this.isOpen = false;
  }

  init() {
    this.drawer = document.getElementById("copilot-drawer");
    const openBtn = document.getElementById("btn-open-copilot");
    const closeBtn = document.getElementById("btn-close-copilot");
    const sendBtn = document.getElementById("btn-copilot-send");
    const textarea = document.getElementById("copilot-textarea");

    if (openBtn) openBtn.onclick = () => this.toggle(true);
    if (closeBtn) closeBtn.onclick = () => this.toggle(false);

    if (sendBtn && textarea) {
      sendBtn.onclick = () => this.sendMessage();
      textarea.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage();
        }
      });
    }
  }

  async toggle(open) {
    this.isOpen = open !== undefined ? open : !this.isOpen;
    if (this.drawer) {
      this.drawer.classList.toggle("open", this.isOpen);
      if (this.isOpen) {
        await this.loadMessages();
        document.getElementById("copilot-textarea")?.focus();
      }
    }
  }

  async loadMessages() {
    const container = document.getElementById("copilot-messages");
    if (!container) return;

    try {
      const messages = await window.api.getCopilotMessages();
      container.innerHTML = "";

      if (messages.length === 0) {
        container.innerHTML = `
          <div style="text-align: center; color: var(--text-muted); padding: 20px; font-size: 0.825rem;">
            Bonjour ! Je suis le <strong>Méta-Agent Copilote Système</strong>.<br>
            Je peux reconfigurer les agents, ajuster les prompts ou diagnostiquer la plateforme.
          </div>
        `;
        return;
      }

      messages.forEach((msg) => {
        const isUser = msg.role === "user";
        const el = document.createElement("div");
        el.className = `chat-message ${isUser ? "user" : "assistant"}`;
        el.innerHTML = `
          <div class="message-avatar">
            <i data-lucide="${isUser ? 'user' : 'zap'}"></i>
          </div>
          <div class="message-content-wrapper">
            <div class="message-bubble" style="font-size: 0.85rem;">
              ${msg.content}
            </div>
          </div>
        `;
        container.appendChild(el);
      });

      if (window.lucide) window.lucide.createIcons();
      container.scrollTop = container.scrollHeight;
    } catch (e) {
      console.error("Échec chargement messages copilote:", e);
    }
  }

  async sendMessage() {
    const textarea = document.getElementById("copilot-textarea");
    if (!textarea) return;

    const content = textarea.value.trim();
    if (!content) return;

    textarea.value = "";

    // Affichage message utilisateur
    const container = document.getElementById("copilot-messages");
    const userEl = document.createElement("div");
    userEl.className = "chat-message user";
    userEl.innerHTML = `
      <div class="message-avatar"><i data-lucide="user"></i></div>
      <div class="message-content-wrapper">
        <div class="message-bubble" style="font-size: 0.85rem;">${content}</div>
      </div>
    `;
    container.appendChild(userEl);
    container.scrollTop = container.scrollHeight;

    try {
      const res = await window.api.sendCopilotMessage(content);
      const botEl = document.createElement("div");
      botEl.className = "chat-message assistant";
      botEl.innerHTML = `
        <div class="message-avatar"><i data-lucide="zap"></i></div>
        <div class="message-content-wrapper">
          <div class="message-bubble" style="font-size: 0.85rem;">${res.reply}</div>
        </div>
      `;
      container.appendChild(botEl);
      if (window.lucide) window.lucide.createIcons();
      container.scrollTop = container.scrollHeight;
    } catch (e) {
      window.api.showToast(`Erreur Copilote : ${e.message}`, "danger");
    }
  }
}

window.copilotModal = new CopilotModal();
