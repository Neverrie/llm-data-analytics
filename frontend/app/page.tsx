"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ArtifactItem, Chat, ChatMessage, DatasetItem, setAuthToken, User } from "@/lib/api";
import { AppShell } from "@/components/workspace/AppShell";
import { ArtifactExplorer } from "@/components/workspace/ArtifactExplorer";
import { ChatPanel } from "@/components/workspace/ChatPanel";
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

  const [section, setSection] = useState<ActiveSection>("agent");
  const [search, setSearch] = useState("");
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([]);
  const [chats, setChats] = useState<Chat[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [selectedDatasetName, setSelectedDatasetName] = useState<string>("");
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const [selectedArtifact, setSelectedArtifact] = useState<ArtifactItem | undefined>(undefined);

  const [lab3Response, setLab3Response] = useState<any>(null);
  const [pipelineSample, setPipelineSample] = useState<any>(null);
  const [pipelineResult, setPipelineResult] = useState<any>(null);
  const [pipelineForm, setPipelineForm] = useState({ limit: 20, min_score: "", max_score: "" });
  const [datasetPreview, setDatasetPreview] = useState<any>(null);
  const [datasetProfile, setDatasetProfile] = useState<any>(null);

  const chatKind = section === "pipeline" ? "lab2_pipeline" : "lab3_chat";

  async function refreshSharedData() {
    const [ds, arts] = await Promise.all([api.listDatasets(), api.listArtifacts()]);
    setDatasets(ds.items || []);
    setArtifacts(arts.items || []);
    if (!selectedDatasetId && ds.items?.[0]?.id) {
      setSelectedDatasetId(ds.items[0].id);
      setSelectedDatasetName(ds.items[0].name);
    }
  }

  async function refreshChats(kind = chatKind) {
    const listedChats = await api.listChats({ kind });
    setChats(listedChats.items || []);
    return listedChats.items || [];
  }

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const me = await api.me();
        setUser(me);
        await refreshSharedData();
        const loadedChats = await refreshChats();
        if (loadedChats[0]?.id) {
          await selectChat(loadedChats[0].id);
        }
      } catch {
        setAuthToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!user) return;
    refreshChats().catch((e) => setError((e as Error).message));
  }, [section, user]);

  async function selectChat(chatId: string) {
    const detail = await api.getChat(chatId);
    setSelectedChatId(chatId);
    setMessages(detail.messages || []);
  }

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
      const loadedChats = await refreshChats();
      if (loadedChats[0]?.id) await selectChat(loadedChats[0].id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function createChat(kind: "lab3_chat" | "lab2_pipeline") {
    try {
      const newChat = await api.createChat({
        title: kind === "lab3_chat" ? "Новый анализ" : "Новый pipeline run",
        kind,
        dataset_name: selectedDatasetName || null
      });
      await refreshChats(kind);
      await selectChat(newChat.id);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function sendAgentMessage(text: string) {
    if (!selectedChatId) return;
    try {
      setLoading(true);
      await api.addMessage(selectedChatId, { role: "user", content: text, blocks: [], metadata: {} });
      setMessages((prev) => [...prev, { id: `tmp-${Date.now()}`, chat_id: selectedChatId, role: "user", content: text, blocks: [], metadata: {}, created_at: new Date().toISOString() }]);

      const answer = await api.askLab3Agent({
        dataset_name: selectedDatasetName,
        question: text,
        analysis_mode: "code_interpreter",
        include_history: true,
        max_tool_calls: 6
      });
      setLab3Response(answer);

      const assistantText = String(answer?.final_answer || "Ответ получен");
      await api.addMessage(selectedChatId, {
        role: "assistant",
        content: assistantText,
        blocks: answer?.code_steps || [],
        metadata: { raw: answer }
      });
      const refreshed = await api.getChat(selectedChatId);
      setMessages(refreshed.messages || []);
      await refreshSharedData();
    } catch (e) {
      setError((e as Error).message);
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

  async function reloadDatasetView(id: string) {
    try {
      setSelectedDatasetId(id);
      const selected = datasets.find((d) => d.id === id);
      if (selected) setSelectedDatasetName(selected.name);
      const [preview, profile] = await Promise.all([api.previewDataset(id), api.profileDataset(id)]);
      setDatasetPreview(preview);
      setDatasetProfile(profile);
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

  const mainContent = useMemo(() => {
    if (section === "agent") {
      return (
        <>
          <div className="context-strip">
            <span>Dataset:</span>
            <select value={selectedDatasetId} onChange={(e) => reloadDatasetView(e.target.value)}>
              {datasets.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
            <span className="muted">Mode: Lab 3 Code Interpreter</span>
          </div>
          <ChatPanel messages={messages} onSend={sendAgentMessage} loading={loading} lab3Response={lab3Response} />
        </>
      );
    }
    if (section === "pipeline") {
      return <PipelinePanel sample={pipelineSample} result={pipelineResult} onSample={runPipelineSample} onRun={runPipeline} loading={loading} form={pipelineForm} onForm={(k, v) => setPipelineForm((prev) => ({ ...prev, [k]: k === "limit" ? Number(v || 1) : v }))} />;
    }
    if (section === "datasets") {
      return <DatasetExplorer datasets={datasets} selected={selectedDatasetId} preview={datasetPreview} profile={datasetProfile} onSelect={reloadDatasetView} onUpload={uploadDataset} />;
    }
    if (section === "artifacts") {
      return <ArtifactExplorer items={artifacts} onSelect={(id) => { setSelectedArtifact(artifacts.find((a) => a.id === id)); setSection("artifacts"); }} selected={selectedArtifact} />;
    }
    return <EmptyState title="Settings" description={user ? `${user.display_name} (${user.email})` : "No user"} />;
  }, [section, selectedDatasetId, datasets, messages, loading, lab3Response, pipelineSample, pipelineResult, pipelineForm, datasetPreview, datasetProfile, artifacts, selectedArtifact, user]);

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
        section={section}
        rail={<IconRail active={section} onChange={setSection} onLogout={() => { setAuthToken(null); setUser(null); }} />}
        sidebar={
          <WorkspaceSidebar
            user={user}
            section={section}
            search={search}
            onSearch={setSearch}
            chats={chats}
            selectedChatId={selectedChatId}
            onSelectChat={selectChat}
            onCreateChat={() => createChat(chatKind)}
            onOpenPipeline={() => setSection("pipeline")}
            datasets={datasets}
            selectedDatasetId={selectedDatasetId}
            onSelectDataset={(id) => { setSection("datasets"); reloadDatasetView(id); }}
            onUploadDataset={uploadDataset}
            artifacts={artifacts}
            onSelectArtifact={(id) => { setSelectedArtifact(artifacts.find((a) => a.id === id)); setSection("artifacts"); }}
          />
        }
        main={<div className="main-wrap"><TopBar title={section === "agent" ? "Agent Workspace" : section === "pipeline" ? "Lab 2 Pipeline" : section === "datasets" ? "Datasets" : section === "artifacts" ? "Artifacts" : "Settings"} subtitle="LLM Data Analyst Workspace" />{mainContent}</div>}
      />
    </div>
  );
}
