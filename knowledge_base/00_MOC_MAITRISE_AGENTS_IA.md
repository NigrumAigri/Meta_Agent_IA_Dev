---
titre: Carte du Savoir - Maîtrise des Agents IA
projet: Pilier 2 - Agence d'Automatisation
statut: En cours (Modules 1 à 13 Validés)
date_mise_a_jour: 2026-08-07
tags:
  - moc
  - index
  - architecture
  - agent-ia
  - prompt-engineering
  - tools
  - mcp
  - rag
  - graph-rag
  - reflexion
  - self-correction
  - tool-maker
  - fine-tuning
  - peft
  - lora
  - qlora
  - dpo
  - hitl
  - checkpoints
  - state-persistence
  - security
  - observability
  - tracing
---

# 🧠 MOC - Maîtrise des Agents IA & Architecture Sur-Mesure

> [!ABSTRACT] Vision Globale
> Ce coffre contient l'apprentissage pas-à-pas, interactif et sur-mesure de l'ingénierie des Agents IA.

---

## 📌 INDEX DES FICHES DE MAÎTRISE SUR-MESURE

> [!SUCCESS] Fiches de Maîtrise Complétées (Phase I, Phase II, Phase III & Phase IV)
> - [[01_Fondations_Et_Anatomie_Agent_IA]] — **Module 1** : Fondations & Anatomie d'un Agent IA (Du LLM passif à l'Agent autonome, Boucle ReAct en 5 temps, 8 Piliers en 3 familles : Cadrage role/goal/backstory, Moteur llm/tools, Sécurité max_iter/verbose/allow_delegation, 3 Pièges : Hallucination/Boucle Infinie/Outil Muet, Cadrage & Contrôle Budgétaire, Check-list 8 points).
> - [[02_Masterclass_Prompt_Engineering_Et_Prompt_Parfait]] — **Module 2** : Le Prompt Engineering & L'Art du Prompt Parfait (3 Couches System/User/Context, 5 Techniques : Zero-Shot, Few-Shot, CoT, ReAct, Structured Output, Règle des 6 Piliers, Lost in the Middle, Balises XML & Anti-Injection, Multimodal, Méta-Prompting & Check-list 8 points).
> - [[03_Architectures_Multi_Agents_Et_Topologies]] — **Module 3** : Les Architectures & Topologies Multi-Agents (Séquentielle, Hiérarchique, Débat & Consensus, Essaim/Swarms & Handoffs, Fan-Out/Fan-In, Routing & Délégation, Fallback & Échecs en cascade, État Partagé/Tableau Noir, HITL, Circuit Breaker, Arbre de Décision & Check-list 10 points).
> - [[04_Comprendre_Evaluer_Configurer_LLM_Agents_IA]] — **Module 4** : Comprendre, Évaluer & Configurer les LLM pour les Agents IA (LLM auto-régressif, Tokens & Chunking, Fenêtre de Contexte & FinOps, Hyperparamètres, Architectures Dense vs MoE, Quantification, Reasoning/Thinking, Sorties Structurées, Benchmarks & Model-Matching).
> - [[05_Tool_Engineering_et_Standard_MCP]] — **Module 5** : Tool Engineering & Le Standard MCP (Function Calling, Anatomie d'un Outil, Typologie, Standard MCP & 3 Primitives, Découverte Dynamique, Description Engineering, Troncature/Retry/Caching, Sécurité/Sandboxing/HITL, Orchestration Multi-Outils & Sampling).
> - [[06_Le_RAG_Et_Graph_RAG_Masterclass]] — **Module 6** : Le RAG & Graph RAG Masterclass (Pipeline Naïf 3 étapes, Embeddings & Vector DBs, HNSW, Graph RAG avec Knowledge Graphs & algorithmes Leiden/Louvain, Advanced RAG avec Parent-Child/Small-to-Big Retrieval, HyDE, Re-ranking Cross-Encoders, Recherche Hybride BM25+Vecteurs & RRF, RAG Multimodal, RBAC & Isolation Multi-Tenant, Agentic RAG / CRAG, Trièdre d'Évaluation Ragas).
> - [[07_Reflexion_Auto_Amelioration_Et_Auto_Creation_Outils]] — **Module 7** : Auto-Amélioration (Reflexion), Self-Correction & Auto-Création d'Outils et Sous-Agents (One-Shot vs Iterative Reflexion, Architecture à 3 rôles Actor/Critic/Memory, Self-Refinement, Tool-Maker Agents, Sub-Agent Spawning, Sécurisation par AST Parsing & Sandboxing, Prévention Over-Correction, Mémoire d'échecs épisodique cross-run, Gouvernance & HITL).
> - [[08_Fine_Tuning_Et_Customization_Modeles_Agents_IA]] — **Module 8** : Fine-Tuning & Customization des Modèles pour Agents IA (Triangle d'arbitrage Prompt/RAG/Fine-Tuning, PEFT/LoRA/QLoRA, Function-Calling Fine-Tuning, Alignement DPO des paires de trajectoires, Génération de données synthétiques agentiques, Data Mixing & Replay Buffers, Fusion d'adaptateurs, Formats GGUF/AWQ/EXL2, Déploiement vLLM/Ollama, Evaluation comparative).
> - [[09_Human_In_The_Loop_Et_Supervision_Humain_Agent_Masterclass]] — **Module 9** : Human-in-the-Loop (HITL) & Supervision Humain-Agent Masterclass (Gradation autonomie vs contrôle, 3 postures HITL/HOTL/HOOTL, Trigger Points sur incertitude/sensibilité/anomalies, Architecture Snapshotting & Webhook Async Resume, Timeout & Escalation Policies, Canaux Web/Slack/CLI, Modalités Binaire/Edit/Steering, Active Learning & RLAIF, Audit Trails & Responsabilité partagée).
> - [[10_Persistence_Etat_Checkpoints_Reprise_Et_Time_Travel_Masterclass]] — **Module 10** : Persistence d'État, Checkpoints, Reprise d'Agent & Time Travel Masterclass (Stateless vs Stateful, Checkpointing & Game Auto-Save, Agent State Anatomy, thread_id/run_id, Step Hook Middleware, Step vs Task level, Parent-Child State Sync, JSON/Pydantic vs Pickle, Atomic Writes & WAL, Schema Migration v1 ➔ v2, Datastores In-Memory/SQLite/Postgres/Redis, Crash Recovery, HITL Pause/Resume, Concurrency Locks & Redis Redlock, Time Travel, Event-Sourcing, State Forking & Rewind/Edit, Lifecycle Retention & AES-256 Encryption, RGPD Compliance & 10-Point Architect Checklist).
> - [[11_Masterclass_Securite_Sandboxing_Docker_MicroVMs_Et_Anti_Injection]] — **Module 11** : Masterclass Sécurité, Sandboxing Docker, Micro-VMs & Anti-Injection (Docker Hardening nonroot/read-only/cap-drop/tmpfs, gVisor Kernel Sandbox, Micro-VMs Firecracker, WASM Memory Sandbox, Surface d'attaque OWASP, Prompt Injections Directes/Jailbreak, Injections Indirectes n°1, Privilege Confusion, Balises XML, Guardrails Llama-Guard, Dual-LLM Pattern, Egress Filtering Whitelisting, Vault Secrets & Moindre Privilège, 10-Point Security Checklist).
> - [[12_Masterclass_Observabilite_Tracing_Agentique_Et_Telemetrie]] — **Module 12** : Masterclass Observabilité, Tracing Agentique & Télémétrie (Problème Boîte Noire, Logging 1D vs Tracing 3D, Boîte noire avion & Formule 1, Anatomie Trace & Spans LLM/Tool/Retriever/Agent, 3 Piliers Trajectoire/FinOps/Performance TTFT, Standard OpenTelemetry OTEL GenAI, Instrumentation non intrusive @observe/callbacks, Online LLM-as-a-Judge, User Feedback Loop, Alertes Token Spikes & Disjoncteurs Boucles Infinies, PII Redaction Regex/NER, Gouvernance Self-Hosted RGPD, 10-Point Observability Checklist).
> - [[13_Guide_Execution_Operationnelle_Projet_Agent_IA]] — **Module 13** : Guide d'Exécution Opérationnel - Développement d'un Agent IA de A à Z (Feuille de Route 0% Théorie 100% Action en 4 phases et 12 étapes, Choix et comparaison de 2 bibliothèques Python par étape avec Avantages et Inconvénients, Stack Technique complète de production).


