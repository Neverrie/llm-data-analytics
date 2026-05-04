"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ArtifactItem, Chat, ChatMessage, DatasetItem, setAuthToken, User } from "@/lib/api";
import { AppShell } from "@/components/workspace/AppShell";
import { ArtifactExplorer } from "@/components/workspace/ArtifactExplorer";
import { ChatPanel } from "@/components/workspace/ChatPanel";
import { DashboardPanel } from "@/components/workspace/DashboardPanel";
import { DatasetExplorer } from "@/components/workspace/DatasetExplorer";
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
  const [error, setError] = useState<string>("");

  const [activeSection, setActiveSection] = useState<ActiveSection>("dashboard");
  const [search, setSearch] = useState("");
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([]);
  const [chats, setChats] = useState<Chat[]>([]);
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

  const selectedDataset = useMemo(() => datasets.find((d) => d.id === selectedDatasetId), [datasets, selectedDatasetId]);
  const selectedArtifact = useMemo(() => artifacts.find((a) => a.id === selectedArtifactId), [artifacts, selectedArtifactId]);

  const refreshSharedData = useCallback(async () => {
    const [ds, arts] = await Promise.all([api.listDatasets(), api.listArtifacts()]);
    setDatasets(ds.items || []);
    setArtifacts(arts.items || []);
    if (!selectedDatasetId && ds.items?.[0]?.id) setSelectedDatasetId(ds.items[0].id);
  }, [selectedDatasetId]);

  const refreshChats = useCallback(async () => {
    const listedChats = await api.listChats({ kind: "lab3_chat" });
    setChats(listedChats.items || []);
    return listedChats.items || [];
  }, []);

  const selectChat = useCallback(async (chatId: string) => {
    const detail = await api.getChat(chatId);
    setSelectedChatId(chatId);
    setMessages(detail.messages || []);
    setActiveSection("agent");
  }, []);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const me = await api.me();
        setUser(me);
        await refreshSharedData();
        const list = await refreshChats();
        if (list[0]?.id) await selectChat(list[0].id);
      } catch {
        setAuthToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [refreshSharedData, refreshChats, selectChat]);

  async function doAuth(type: "demo" | "login" | "register") {
    try {
      setError("");
      setLoading(true);
      const response = type === "demo"
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
      const newChat = await api.createChat({ title: "Новый анализ", kind: "lab3_chat", dataset_name: dsName });
      await refreshChats();
      setSelectedChatId(newChat.id);
      setMessages([]);
      setActiveSection("agent");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function sendAgentMessage(text: string) {
    if (!selectedChatId) {
      await createChat();
    }
    const chatId = selectedChatId || (await api.listChats({ kind: "lab3_chat" })).items[0]?.id;
    if (!chatId) return;

    const optimistic: ChatMessage = {
      id: `tmp-${Date.now()}`,
      chat_id: chatId,
      role: "user",
      content: text,
      blocks: [],
      metadata: {},
      created_at: new Date().toISOString()
    };

    setMessages((prev) => [...prev, optimistic]);
    setLoading(true);
    setLab3Response(null);
    try {
      await api.addMessage(chatId, { role: "user", content: text, blocks: [], metadata: {} });
      const answer = await api.askLab3Agent({
        dataset_name: selectedDataset?.name || datasets[0]?.name || "customers_reviews.csv",
        question: text,
        analysis_mode: "code_interpreter",
        include_history: true,
        max_tool_calls: 6
      });
      setLab3Response(answer);

      const assistantText = String(answer?.final_answer || "Ответ получен");
      await api.addMessage(chatId, {
        role: "assistant",
        content: assistantText,
        blocks: answer?.code_steps || [],
        metadata: { raw: answer }
      });
      const refreshed = await api.getChat(chatId);
      setMessages(refreshed.messages || []);
      await refreshSharedData();
      await refreshChats();
    } catch (e) {
      setLab3Response({ error: (e as Error).message });
    } finally {
      setLoading(false);
    }
  }

  async function runPipelineSample() {
    try {
      setLoading(true);
      setPipelineSample(await api.getLab2SampleData({
        limit: pipelineForm.limit,
        min_score: pipelineForm.min_score ? Number(pipelineForm.min_score) : null,
        max_score: pipelineForm.max_score ? Number(pipelineForm.max_score) : null
      }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function runPipeline() {
    try {
      setLoading(true);
      setPipelineResult(await api.runLab2Pipeline({
        limit: pipelineForm.limit,
        min_score: pipelineForm.min_score ? Number(pipelineForm.min_score) : null,
        max_score: pipelineForm.max_score ? Number(pipelineForm.max_score) : null
      }));
      await refreshSharedData();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function openDatasetPreview(id: string) {
    try {
      setSelectedDatasetId(id);
      const [preview, profile] = await Promise.all([api.previewDataset(id, 30), api.profileDataset(id)]);
      setDatasetPreview(preview);
      setDatasetProfile(profile);
      setActiveSection("datasets");
    } catch (e) {
      setError((e as Error).message);
    }
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

  const title = activeSection === "dashboard"
    ? "Dashboard"
    : activeSection === "agent"
      ? "Agent Workspace"
      : activeSection === "pipeline"
        ? "Lab 2 Pipeline"
        : activeSection === "datasets"
          ? "Datasets"
          : activeSection === "artifacts"
            ? "Artifacts"
            : "Settings";

  const subtitle = activeSection === "dashboard"
    ? "Ваши аналитические сценарии и последние запуски"
    : "LLM Data Analyst Workspace";

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
            chats={chats}
            selectedChatId={selectedChatId}
            onSelectChat={selectChat}
            onCreateChat={createChat}
            onOpenDashboard={() => setActiveSection("dashboard")}
            onOpenAgent={() => setActiveSection("agent")}
            onOpenPipeline={() => setActiveSection("pipeline")}
            datasets={datasets}
            selectedDatasetId={selectedDatasetId}
            onUseDataset={setSelectedDatasetId}
            onPreviewDataset={openDatasetPreview}
            onUploadDataset={uploadDataset}
            artifacts={artifacts}
            onSelectArtifact={(id) => { setSelectedArtifactId(id); setActiveSection("artifacts"); }}
          />
        }
        main={
          <div className="main-wrap">
            <TopBar title={title} subtitle={subtitle} />
            {activeSection === "dashboard" ? (
              <DashboardPanel
                chats={chats}
                datasets={datasets}
                artifacts={artifacts}
                onOpenChat={selectChat}
                onOpenPipeline={() => setActiveSection("pipeline")}
                onOpenDatasets={() => setActiveSection("datasets")}
                onOpenArtifacts={() => setActiveSection("artifacts")}
              />
            ) : null}

            {activeSection === "agent" ? (
              <>
                <div className="context-strip"><span>Dataset: {selectedDataset?.name || "not selected"}</span></div>
                <ChatPanel messages={messages} onSend={sendAgentMessage} loading={loading} lab3Response={lab3Response} datasetName={selectedDataset?.name} />
              </>
            ) : null}

            {activeSection === "pipeline" ? (
              <>
                <div className="context-strip"><span>Pipeline dataset: customers_reviews.csv</span></div>
                <PipelinePanel sample={pipelineSample} result={pipelineResult} onSample={runPipelineSample} onRun={runPipeline} loading={loading} form={pipelineForm} onForm={(k, v) => setPipelineForm((prev) => ({ ...prev, [k]: k === "limit" ? Number(v || 1) : v }))} />
              </>
            ) : null}

            {activeSection === "datasets" ? <DatasetExplorer datasets={datasets} selected={selectedDatasetId} preview={datasetPreview} profile={datasetProfile} onSelect={openDatasetPreview} onUpload={uploadDataset} /> : null}
            {activeSection === "artifacts" ? <ArtifactExplorer items={artifacts} onSelect={setSelectedArtifactId} selected={selectedArtifact} /> : null}
            {activeSection === "settings" ? <EmptyState title="Settings" description={`${user.display_name} (${user.email})`} /> : null}
          </div>
        }
      />
    </div>
  );
}
