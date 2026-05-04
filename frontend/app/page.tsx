"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ArtifactItem, Chat, ChatMessage, DatasetItem, setAuthToken, User } from "@/lib/api";
import { normalizeLab3ResponseToBlocks } from "@/lib/messageBlocks";
import { AppShell } from "@/components/workspace/AppShell";
import { ArtifactExplorer } from "@/components/workspace/ArtifactExplorer";
import { ChatPanel } from "@/components/workspace/ChatPanel";
import { DashboardPanel } from "@/components/workspace/DashboardPanel";
import { DatasetExplorer } from "@/components/workspace/DatasetExplorer";
import { DatasetSwitcher } from "@/components/workspace/DatasetSwitcher";
import { EmptyState } from "@/components/workspace/EmptyState";
import { ErrorBanner } from "@/components/workspace/ErrorBanner";
import { IconRail } from "@/components/workspace/IconRail";
import { PipelinePanel } from "@/components/workspace/PipelinePanel";
import { TopBar } from "@/components/workspace/TopBar";
import { ActiveSection } from "@/components/workspace/types";
import { WorkspaceSidebar } from "@/components/workspace/WorkspaceSidebar";

export default function HomePage() {
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authForm, setAuthForm] = useState({ email: "", password: "", displayName: "" });
  const [loading, setLoading] = useState(false);
  const [agentLoading, setAgentLoading] = useState(false);
  const [pipelineLoading, setPipelineLoading] = useState(false);
  const [error, setError] = useState<string>("");

  const [activeSection, setActiveSection] = useState<ActiveSection>("dashboard");
  const [search, setSearch] = useState("");
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([]);
  const [allChats, setAllChats] = useState<Chat[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<string>("");
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const [selectedArtifactId, setSelectedArtifactId] = useState<string>("");

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [lab3Response, setLab3Response] = useState<any>(null);
  const [pipelineSample, setPipelineSample] = useState<any>(null);
  const [pipelineResult, setPipelineResult] = useState<any>(null);
  const [pipelineForm, setPipelineForm] = useState({ limit: 20, min_score: "", max_score: "" });
  const [datasetPreview, setDatasetPreview] = useState<any>(null);
  const [datasetProfile, setDatasetProfile] = useState<any>(null);
  const [datasetNotice, setDatasetNotice] = useState("");

  const selectedDataset = useMemo(() => datasets.find((d) => d.id === selectedDatasetId), [datasets, selectedDatasetId]);
  const selectedArtifact = useMemo(() => artifacts.find((a) => a.id === selectedArtifactId), [artifacts, selectedArtifactId]);
  const lab3Chats = useMemo(() => allChats.filter((c) => c.kind === "lab3_chat"), [allChats]);
  const pipelineChats = useMemo(() => allChats.filter((c) => c.kind === "lab2_pipeline"), [allChats]);
  const latestPipelineChat = pipelineChats[0];

  async function refreshSharedData() {
    const [ds, arts] = await Promise.all([api.listDatasets(), api.listArtifacts()]);
    setDatasets(ds.items || []);
    setArtifacts(arts.items || []);
    setSelectedDatasetId((prev) => prev || ds.items?.[0]?.id || "");
  }

  async function refreshChats() {
    const listedChats = await api.listChats();
    setAllChats(listedChats.items || []);
    return listedChats.items || [];
  }

  async function selectChat(chatId: string) {
    const detail = await api.getChat(chatId);
    setSelectedChatId(chatId);
    setMessages(detail.messages || []);
    const mappedDataset = datasets.find((d) => d.name === detail.chat.dataset_name);
    if (mappedDataset?.id) setSelectedDatasetId(mappedDataset.id);
    setActiveSection(detail.chat.kind === "lab2_pipeline" ? "pipeline" : "agent");
  }

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const me = await api.me();
        setUser(me);
        await refreshSharedData();
        await refreshChats();
      } catch {
        setAuthToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function doAuth(type: "demo" | "login" | "register") {
    try {
      setError("");
      setLoading(true);
      const response =
        type === "demo"
          ? await api.demoLogin()
          : type === "login"
            ? await api.login(authForm.email, authForm.password)
            : await api.register(authForm.email, authForm.password, authForm.displayName || authForm.email);

      setAuthToken(response.access_token);
      setUser(response.user);
      await refreshSharedData();
      await refreshChats();
      setActiveSection("dashboard");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function createChat() {
    try {
      const dsName = selectedDataset?.name || datasets[0]?.name || "customers_reviews.csv";
      const created = await api.createChat({ title: "Новый чат", kind: "lab3_chat", dataset_name: dsName });
      await refreshChats();
      setSelectedChatId(created.id);
      setMessages([]);
      setActiveSection("agent");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function getOrCreatePipelineChat() {
    const existing = pipelineChats[0];
    if (existing) return existing;
    const created = await api.createChat({ title: "Pipeline run", kind: "lab2_pipeline", dataset_name: "customers_reviews.csv" });
    await refreshChats();
    return created;
  }

  async function updateChatDatasetContext(datasetId: string) {
    setSelectedDatasetId(datasetId);
    const ds = datasets.find((d) => d.id === datasetId);
    if (!ds) return;

    if (activeSection === "datasets") {
      await loadDatasetPreview(datasetId, false);
      return;
    }

    if (selectedChatId) {
      try {
        await api.updateChat(selectedChatId, { dataset_name: ds.name });
        await refreshChats();
      } catch {
        // Keep local context if PATCH fails.
      }
      setDatasetNotice(`Датасет для следующих запросов: ${ds.name}`);
      setTimeout(() => setDatasetNotice(""), 2400);
    }
  }

  async function sendAgentMessage(text: string) {
    let chatId = selectedChatId;
    if (!chatId) {
      await createChat();
      const updated = await refreshChats();
      chatId = updated.find((c) => c.kind === "lab3_chat")?.id || "";
    }
    if (!chatId) return;

    const optimistic: ChatMessage = {
      id: `tmp-${Date.now()}`,
      chat_id: chatId,
      role: "user",
      content: text,
      blocks: [{ type: "markdown", content: text }],
      metadata: {},
      created_at: new Date().toISOString()
    };

    setMessages((prev) => [...prev, optimistic]);
    setAgentLoading(true);
    setLab3Response(null);

    try {
      await api.addMessage(chatId, { role: "user", content: text, blocks: optimistic.blocks, metadata: {} });
      const answer = await api.askLab3Agent({
        dataset_name: selectedDataset?.name || datasets[0]?.name || "customers_reviews.csv",
        question: text,
        analysis_mode: "code_interpreter",
        include_history: true,
        max_tool_calls: 6
      });
      setLab3Response(answer);

      const assistantText = String(answer?.final_answer || "Ответ получен");
      const blocks = normalizeLab3ResponseToBlocks(answer);
      await api.addMessage(chatId, {
        role: "assistant",
        content: assistantText,
        blocks,
        metadata: { provider: answer?.provider, model: answer?.model, elapsed_seconds: answer?.elapsed_seconds }
      });
      const refreshed = await api.getChat(chatId);
      setMessages(refreshed.messages || []);
      await refreshSharedData();
      await refreshChats();
    } catch (e) {
      const errorText = (e as Error).message;
      setLab3Response({ error: errorText });
      try {
        await api.addMessage(chatId, {
          role: "assistant",
          content: `Ошибка: ${errorText}`,
          blocks: [{ type: "warning", content: errorText }],
          metadata: { error: true }
        });
        const refreshed = await api.getChat(chatId);
        setMessages(refreshed.messages || []);
      } catch {
        setError(errorText);
      }
    } finally {
      setAgentLoading(false);
    }
  }

  async function runPipelineSample() {
    try {
      setPipelineLoading(true);
      setPipelineSample(
        await api.getLab2SampleData({
          limit: pipelineForm.limit,
          min_score: pipelineForm.min_score ? Number(pipelineForm.min_score) : null,
          max_score: pipelineForm.max_score ? Number(pipelineForm.max_score) : null
        })
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPipelineLoading(false);
    }
  }

  async function runPipeline() {
    try {
      setPipelineLoading(true);
      const pipelineChat = await getOrCreatePipelineChat();
      const prompt = `Запуск pipeline: limit=${pipelineForm.limit}, min_score=${pipelineForm.min_score || "-"}, max_score=${pipelineForm.max_score || "-"}`;
      await api.addMessage(pipelineChat.id, { role: "user", content: prompt, blocks: [{ type: "markdown", content: prompt }], metadata: {} });
      const result = await api.runLab2Pipeline({
        limit: pipelineForm.limit,
        min_score: pipelineForm.min_score ? Number(pipelineForm.min_score) : null,
        max_score: pipelineForm.max_score ? Number(pipelineForm.max_score) : null
      });
      setPipelineResult(result);
      await api.addMessage(pipelineChat.id, {
        role: "assistant",
        content: "Pipeline завершен",
        blocks: [
          { type: "markdown", content: "Pipeline завершен" },
          { type: "table", title: "Результаты", columns: result?.results?.length ? Object.keys(result.results[0]) : [], rows: result?.results?.slice(0, 20) || [] },
          { type: "raw", title: "Raw JSON", payload: result }
        ],
        metadata: { kind: "lab2_result" }
      });
      await refreshSharedData();
      await refreshChats();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPipelineLoading(false);
    }
  }

  async function loadDatasetPreview(id: string, switchSection: boolean) {
    try {
      setSelectedDatasetId(id);
      if (switchSection) setActiveSection("datasets");
      const [preview, profile] = await Promise.all([api.previewDataset(id, 30), api.profileDataset(id)]);
      setDatasetPreview(preview);
      setDatasetProfile(profile);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleSidebarUseDataset(id: string) {
    if (activeSection === "datasets") {
      await loadDatasetPreview(id, false);
      return;
    }
    await updateChatDatasetContext(id);
  }

  async function openDatasetPreview(id: string) {
    await loadDatasetPreview(id, true);
  }

  async function uploadDataset(file: File) {
    try {
      setLoading(true);
      await api.uploadDataset(file);
      await refreshSharedData();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const title =
    activeSection === "dashboard"
      ? "Дашборд"
      : activeSection === "agent"
        ? "Агент"
        : activeSection === "pipeline"
          ? "Lab 2 Pipeline"
          : activeSection === "datasets"
            ? "Датасеты"
            : activeSection === "artifacts"
              ? "Артефакты"
              : "Настройки";

  const subtitle = activeSection === "dashboard" ? "Последние анализы, датасеты и запуски pipeline" : "LLM Data Analyst Workspace";

  if (!user) {
    return (
      <div className="auth-wrap">
        <div className="auth-card">
          <h1>LLM Data Analyst Workspace</h1>
          <p>AI-аналитика датасетов с Code Interpreter и API Pipeline</p>
          <ErrorBanner message={error} />
          <input placeholder="Email" value={authForm.email} onChange={(e) => setAuthForm((p) => ({ ...p, email: e.target.value }))} />
          <input placeholder="Password" type="password" value={authForm.password} onChange={(e) => setAuthForm((p) => ({ ...p, password: e.target.value }))} />
          {authMode === "register" ? <input placeholder="Display name" value={authForm.displayName} onChange={(e) => setAuthForm((p) => ({ ...p, displayName: e.target.value }))} /> : null}
          <div className="auth-row">
            <button className="btn-primary" onClick={() => doAuth(authMode)} disabled={loading}>{authMode === "login" ? "Войти" : "Зарегистрироваться"}</button>
            <button className="btn-secondary" onClick={() => doAuth("demo")} disabled={loading}>Войти в демо</button>
          </div>
          <button className="btn-secondary" onClick={() => setAuthMode((m) => (m === "login" ? "register" : "login"))}>
            {authMode === "login" ? "Нужен аккаунт? Регистрация" : "Уже есть аккаунт? Вход"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="workspace-root">
      <ErrorBanner message={error} />
      <AppShell
        section={activeSection}
        rail={<IconRail active={activeSection} onChange={setActiveSection} onLogout={() => { setAuthToken(null); setUser(null); }} />}
        sidebar={
          <WorkspaceSidebar
            user={user}
            section={activeSection}
            search={search}
            onSearch={setSearch}
            chats={lab3Chats}
            selectedChatId={selectedChatId}
            onSelectChat={selectChat}
            onCreateChat={createChat}
            onOpenPipeline={() => setActiveSection("pipeline")}
            datasets={datasets}
            selectedDatasetId={selectedDatasetId}
            onUseDataset={handleSidebarUseDataset}
            onPreviewDataset={openDatasetPreview}
            onUploadDataset={uploadDataset}
            artifacts={artifacts}
            onSelectArtifact={(id) => {
              setSelectedArtifactId(id);
              setActiveSection("artifacts");
            }}
          />
        }
        main={
          <div className="main-wrap">
            {activeSection !== "pipeline" ? <TopBar title={title} subtitle={subtitle} /> : null}
            {activeSection === "dashboard" ? (
              <DashboardPanel
                chats={lab3Chats}
                datasets={datasets}
                artifacts={artifacts}
                onOpenChat={selectChat}
                onCreateChat={createChat}
                onOpenPipeline={() => setActiveSection("pipeline")}
                onOpenDatasets={() => setActiveSection("datasets")}
                onOpenArtifacts={() => setActiveSection("artifacts")}
              />
            ) : null}

            {activeSection === "agent" ? (
              <>
                <div className="context-strip">
                  <DatasetSwitcher
                    datasets={datasets}
                    selectedDatasetId={selectedDatasetId}
                    onSelect={updateChatDatasetContext}
                    onPreview={(id) => {
                      if (!id) return;
                      openDatasetPreview(id);
                    }}
                  />
                </div>
                <ChatPanel messages={messages} onSend={sendAgentMessage} loading={agentLoading} lab3Response={lab3Response} datasetName={selectedDataset?.name} datasetNotice={datasetNotice} />
              </>
            ) : null}

            {activeSection === "pipeline" ? (
              <PipelinePanel
                sample={pipelineSample}
                result={pipelineResult}
                lastRun={latestPipelineChat || null}
                running={pipelineLoading}
                onSample={runPipelineSample}
                onRun={runPipeline}
                loading={pipelineLoading}
                form={pipelineForm}
                onForm={(k, v) => setPipelineForm((prev) => ({ ...prev, [k]: k === "limit" ? Number(v || 1) : v }))}
              />
            ) : null}

            {activeSection === "datasets" ? <DatasetExplorer datasets={datasets} selected={selectedDatasetId} preview={datasetPreview} profile={datasetProfile} onSelect={(id) => loadDatasetPreview(id, false)} onUpload={uploadDataset} onUseInChat={(id) => { setActiveSection("agent"); updateChatDatasetContext(id); }} /> : null}
            {activeSection === "artifacts" ? <ArtifactExplorer items={artifacts} onSelect={setSelectedArtifactId} selected={selectedArtifact} /> : null}
            {activeSection === "settings" ? <EmptyState title="Настройки" description={`${user.display_name} (${user.email})`} /> : null}
          </div>
        }
      />
    </div>
  );
}
