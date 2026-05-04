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
import { WorkspaceSidebar } from "@/components/workspace/WorkspaceSidebar";
import { ActiveSection } from "@/components/workspace/types";

export default function HomePage() {
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authForm, setAuthForm] = useState({ email: "", password: "", displayName: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  const [section, setSection] = useState<ActiveSection>("agent");
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([]);
  const [chats, setChats] = useState<Chat[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [selectedDatasetName, setSelectedDatasetName] = useState<string>("");
  const [lab3Response, setLab3Response] = useState<any>(null);
  const [pipelineSample, setPipelineSample] = useState<any>(null);
  const [pipelineResult, setPipelineResult] = useState<any>(null);
  const [pipelineForm, setPipelineForm] = useState({ limit: 20, min_score: "", max_score: "" });
  const [datasetId, setDatasetId] = useState<string>("");
  const [datasetPreview, setDatasetPreview] = useState<any>(null);
  const [datasetProfile, setDatasetProfile] = useState<any>(null);
  const [selectedArtifact, setSelectedArtifact] = useState<ArtifactItem | undefined>(undefined);

  const chatKind = section === "pipeline" ? "lab2_pipeline" : "lab3_chat";

  async function bootstrapWorkspace(currentUser: User) {
    const [ds, arts, listedChats] = await Promise.all([
      api.listDatasets(),
      api.listArtifacts(),
      api.listChats({ kind: chatKind })
    ]);
    setDatasets(ds.items || []);
    setArtifacts(arts.items || []);
    setChats(listedChats.items || []);

    const defaultDataset = ds.items?.[0]?.name || "";
    setSelectedDatasetName(defaultDataset);
    if (ds.items?.[0]?.id) setDatasetId(ds.items[0].id);
    if (listedChats.items?.[0]?.id) {
      await selectChat(listedChats.items[0].id);
    }
  }

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const me = await api.me();
        setUser(me);
        await bootstrapWorkspace(me);
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
    (async () => {
      try {
        const listedChats = await api.listChats({ kind: chatKind });
        setChats(listedChats.items || []);
      } catch (e) {
        setError((e as Error).message);
      }
    })();
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
      await bootstrapWorkspace(response.user);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function createChat(kind: "lab3_chat" | "lab2_pipeline") {
    try {
      const newChat = await api.createChat({
        title: kind === "lab3_chat" ? "New analysis" : "New pipeline run",
        kind,
        dataset_name: selectedDatasetName || null
      });
      const listedChats = await api.listChats({ kind });
      setChats(listedChats.items || []);
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
      const current = await api.getChat(selectedChatId);
      setMessages(current.messages || []);

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
      setArtifacts((await api.listArtifacts()).items || []);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function reloadDatasetView(id: string) {
    try {
      setDatasetId(id);
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
      const ds = await api.listDatasets();
      setDatasets(ds.items || []);
      if (ds.items?.[0]?.id) await reloadDatasetView(ds.items[0].id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const sidebarTitle = section === "agent" ? "Lab 3 chats" : section === "pipeline" ? "Lab 2 runs" : section;

  const mainContent = useMemo(() => {
    if (section === "agent") {
      return <ChatPanel messages={messages} selectedDataset={selectedDatasetName} datasets={datasets} onDataset={setSelectedDatasetName} onSend={sendAgentMessage} loading={loading} lab3Response={lab3Response} />;
    }
    if (section === "pipeline") {
      return <PipelinePanel sample={pipelineSample} result={pipelineResult} onSample={runPipelineSample} onRun={runPipeline} loading={loading} form={pipelineForm} onForm={(k, v) => setPipelineForm((prev) => ({ ...prev, [k]: k === "limit" ? Number(v || 1) : v }))} />;
    }
    if (section === "datasets") {
      return <DatasetExplorer datasets={datasets} selected={datasetId} preview={datasetPreview} profile={datasetProfile} onSelect={reloadDatasetView} onUpload={uploadDataset} />;
    }
    if (section === "artifacts") {
      return <ArtifactExplorer items={artifacts} previewUrl={api.artifactPreviewUrl} downloadUrl={api.artifactDownloadUrl} onSelect={(id) => setSelectedArtifact(artifacts.find((a) => a.id === id))} selected={selectedArtifact} />;
    }
    return <EmptyState title="Settings" description={user ? `${user.display_name} (${user.email})` : "No user"} />;
  }, [section, messages, selectedDatasetName, datasets, loading, lab3Response, pipelineSample, pipelineResult, pipelineForm, datasetId, datasetPreview, datasetProfile, artifacts, selectedArtifact, user]);

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
        sidebar={<WorkspaceSidebar user={user} chats={chats} title={sidebarTitle} onCreate={() => createChat(chatKind)} onSelect={(id) => selectChat(id)} selectedId={selectedChatId} />}
        main={<div className="main-wrap"><TopBar title="Workspace" subtitle="AI analytics dashboard" />{mainContent}</div>}
      />
    </div>
  );
}

