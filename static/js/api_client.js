/**
 * Meta Developer Agent v5.0.0 — Enterprise API Client
 * Gestionnaire des requêtes REST et flux streaming SSE
 */

class ApiClient {
  constructor(baseUrl = "") {
    this.baseUrl = baseUrl;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      if (response.status === 204) {
        return null;
      }

      const data = await response.json();
      if (!response.ok) {
        const errorMsg = data.detail || `Erreur HTTP ${response.status}`;
        this.showToast(errorMsg, "danger");
        throw new Error(errorMsg);
      }
      return data;
    } catch (error) {
      console.error(`API Error on ${endpoint}:`, error);
      throw error;
    }
  }

  // --- Projets & Threads ---
  async getProjects() { return this.request("/api/v1/projects"); }
  async createProject(payload) { return this.request("/api/v1/projects", { method: "POST", body: JSON.stringify(payload) }); }
  async getProject(id) { return this.request(`/api/v1/projects/${id}`); }
  async updateProject(id, payload) { return this.request(`/api/v1/projects/${id}`, { method: "PATCH", body: JSON.stringify(payload) }); }
  async deleteProject(id) { return this.request(`/api/v1/projects/${id}`, { method: "DELETE" }); }

  async getThreads(projectId) { return this.request(`/api/v1/projects/${projectId}/threads`); }
  async createThread(projectId, payload) { return this.request(`/api/v1/projects/${projectId}/threads`, { method: "POST", body: JSON.stringify(payload) }); }
  async getThreadMessages(projectId, threadId) { return this.request(`/api/v1/projects/${projectId}/threads/${threadId}/messages`); }

  async uploadDocument(projectId, payload) { return this.request(`/api/v1/projects/${projectId}/documents`, { method: "POST", body: JSON.stringify(payload) }); }
  async getCheckpoints(projectId) { return this.request(`/api/v1/projects/${projectId}/checkpoints`); }
  async rollbackProject(projectId) { return this.request(`/api/v1/projects/${projectId}/rollback`, { method: "POST" }); }

  // --- Chat & Commandes ---
  async sendChatMessage(payload) { return this.request("/api/v1/chat/message", { method: "POST", body: JSON.stringify(payload) }); }
  async executeCommand(payload) { return this.request("/api/v1/chat/command", { method: "POST", body: JSON.stringify(payload) }); }

  // --- Copilote Système ---
  async getCopilotMessages() { return this.request("/api/v1/copilot/messages"); }
  async sendCopilotMessage(message) { return this.request("/api/v1/copilot/chat", { method: "POST", body: JSON.stringify({ message }) }); }
  async clearCopilotMessages() { return this.request("/api/v1/copilot/messages", { method: "DELETE" }); }

  // --- Agents & Topologies ---
  async getAgents(projectId = null) { return this.request(projectId ? `/api/v1/agents?project_id=${projectId}` : "/api/v1/agents"); }
  async updateAgent(id, payload) { return this.request(`/api/v1/agents/${id}`, { method: "PUT", body: JSON.stringify(payload) }); }
  async getTopology() { return this.request("/api/v1/agents/topology"); }
  async switchTopology(topology) { return this.request("/api/v1/agents/topology", { method: "POST", body: JSON.stringify({ topology }) }); }
  async getAgentLinks(projectId = null) { return this.request(projectId ? `/api/v1/agents/links?project_id=${projectId}` : "/api/v1/agents/links"); }
  async createAgentLink(payload) { return this.request("/api/v1/agents/links", { method: "POST", body: JSON.stringify(payload) }); }
  async deleteAgentLink(id) { return this.request(`/api/v1/agents/links/${id}`, { method: "DELETE" }); }
  async applyLinksTemplate(templateName, projectId = null) { return this.request("/api/v1/agents/links/template", { method: "POST", body: JSON.stringify({ template_name: templateName, project_id: projectId }) }); }

  // --- FinOps & Benchmarks ---
  async getFinOpsLedger() { return this.request("/api/v1/finops/ledger"); }
  async getBenchmarks() { return this.request("/api/v1/finops/benchmarks"); }
  async refreshBenchmarks() { return this.request("/api/v1/finops/benchmarks/refresh", { method: "POST" }); }
  async matchModels(role = "coding") { return this.request(`/api/v1/finops/models/match?role=${role}`); }
  async getVisionModels(q = "") { return this.request(`/api/v1/finops/models/vision${q ? `?q=${encodeURIComponent(q)}` : ""}`); }

  // --- MCP & Piliers ---
  async getMcpTools(projectId = null, activeOnly = false) {
    const params = new URLSearchParams();
    if (projectId) params.append("project_id", projectId);
    if (activeOnly) params.append("active_only", "true");
    const query = params.toString();
    return this.request(`/api/v1/mcp/tools${query ? `?${query}` : ""}`);
  }
  async searchMcpTools(q, projectId = null, agentType = null) {
    const params = new URLSearchParams({ q });
    if (projectId) params.append("project_id", projectId);
    if (agentType) params.append("agent_type", agentType);
    return this.request(`/api/v1/mcp/tools/search?${params.toString()}`);
  }
  async getMcpServers(projectId = null) {
    return this.request(projectId ? `/api/v1/mcp/servers?project_id=${projectId}` : "/api/v1/mcp/servers");
  }
  async getSandboxStatus() { return this.request("/api/v1/mcp/sandbox/status"); }
  async executeMcpTool(toolId, args, projectId = null) {
    return this.request(`/api/v1/mcp/tools/${toolId}/execute`, {
      method: "POST",
      body: JSON.stringify({ arguments: args, project_id: projectId }),
    });
  }

  async getSkills() { return this.request("/api/v1/pillars/skills"); }
  async searchSkills(q = "", limit = 4, projectId = null) {
    const params = new URLSearchParams({ q, limit: String(limit) });
    if (projectId) params.append("project_id", projectId);
    return this.request(`/api/v1/pillars/skills/search?${params.toString()}`);
  }
  async getSkillBody(skillName, projectId = null) {
    const params = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
    return this.request(`/api/v1/pillars/skills/${encodeURIComponent(skillName)}/body${params}`);
  }
  async getRules() { return this.request("/api/v1/pillars/rules"); }
  async getHooks() { return this.request("/api/v1/pillars/hooks"); }
  async getHooksHistory(limit = 50, projectId = null) {
    const params = new URLSearchParams({ limit: String(limit) });
    if (projectId) params.append("project_id", projectId);
    return this.request(`/api/v1/pillars/hooks/history?${params.toString()}`);
  }
  async testHook(hookId, testPayload = {}) {
    return this.request(`/api/v1/pillars/hooks/${encodeURIComponent(hookId)}/test`, {
      method: "POST",
      body: JSON.stringify({ test_payload: testPayload }),
    });
  }
  async getCommands() { return this.request("/api/v1/pillars/commands"); }

  // --- HITL ---
  async getHitlRequests() { return this.request("/api/v1/hitl/requests"); }
  async approveHitlRequest(id) { return this.request(`/api/v1/hitl/requests/${id}/approve`, { method: "POST" }); }
  async rejectHitlRequest(id, reason) { return this.request(`/api/v1/hitl/requests/${id}/reject`, { method: "POST", body: JSON.stringify({ reason }) }); }

  // --- Configuration ---
  async getConfig() { return this.request("/api/v1/config"); }
  async updateConfig(payload) { return this.request("/api/v1/config", { method: "PUT", body: JSON.stringify(payload) }); }

  // Système de Toasts
  showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    
    let iconName = "info";
    if (type === "success") iconName = "check-circle";
    if (type === "danger") iconName = "alert-circle";
    if (type === "warning") iconName = "alert-triangle";

    toast.innerHTML = `
      <i data-lucide="${iconName}"></i>
      <span>${message}</span>
    `;

    container.appendChild(toast);
    if (window.lucide) window.lucide.createIcons();

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(20px)";
      setTimeout(() => toast.remove(), 200);
    }, 4000);
  }
}

window.api = new ApiClient();
