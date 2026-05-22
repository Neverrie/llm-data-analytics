"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api, ArtifactItem, Chat, ChatMessage, DatasetItem, setAuthToken, User } from "@/lib/api";
import { AppShell } from "@/components/workspace/AppShell";
import { ArtifactExplorer } from "@/components/workspace/ArtifactExplorer";
import { ChatPanel } from "@/components/workspace/ChatPanel";
import { DatasetExplorer } from "@/components/workspace/DatasetExplorer";
import { ErrorBanner } from "@/components/workspace/ErrorBanner";
import { TopBar } from "@/components/workspace/TopBar";
import { ActiveSection } from "@/components/workspace/types";
import { WorkspaceSidebar } from "@/components/workspace/WorkspaceSidebar";

function isStreamAbortError(message: string): boolean {
  const m = (message || "").toLowerCase();
  return m.includes("aborted") || m.includes("aborterror") || m.includes("body stream buffer was aborted");
}

export default function HomePage() {
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authForm, setAuthForm] = useState({ email: "", password: "", displayName: "" });
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string>("");
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  const [activeSection, setActiveSection] = useState<ActiveSection>("chats");
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([]);
  const [allChats, setAllChats] = useState<Chat[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<string>("");
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const [selectedArtifactId, setSelectedArtifactId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [datasetPreview, setDatasetPreview] = useState<any>(null);
  const [datasetProfile, setDatasetProfile] = useState<any>(null);
  const [datasetNotice, setDatasetNotice] = useState("");
  const [chatStreamInfo, setChatStreamInfo] = useState<{ logs: string[]; error?: string }>({ logs: [] });
  const streamAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const saved = (typeof window !== "undefined" ? window.localStorage.getItem("workspace_theme") : null) as "dark" | "light" | null;
    const next = saved || "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    if (typeof window !== "undefined") window.localStorage.setItem("workspace_theme", theme);
  }, [theme]);

  const selectedDataset = useMemo(() => datasets.find((d) => d.id === selectedDatasetId), [datasets, selectedDatasetId]);
  const selectedArtifact = useMemo(() => artifacts.find((a) => a.id === selectedArtifactId), [artifacts, selectedArtifactId]);

  async function refreshSharedData() {
    const [ds, arts] = await Promise.all([api.listDatasets(), api.listArtifacts()]);
    setDatasets(ds.items || []);
    setArtifacts(arts.items || []);
    setSelectedDatasetId((prev) => prev || ds.items?.[0]?.id || "");
  }

  async function refreshChats() {
    const listedChats = await api.listChats({ archived: false });
    const items = listedChats.items || [];
    setAllChats(items);
    return items;
  }

  async function selectChat(chatId: string) {
    const detail = await api.getChat(chatId);
    setSelectedChatId(chatId);
    setMessages(detail.messages || []);
    const mappedDataset = datasets.find((d) => d.name === detail.chat.dataset_name);
    if (mappedDataset?.id) setSelectedDatasetId(mappedDataset.id);
    setActiveSection("chats");
  }

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const me = await api.me();
        setUser(me);
        await refreshSharedData();
        const chats = await refreshChats();
        if (chats[0]) await selectChat(chats[0].id);
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
      const response = type === "demo"
        ? await api.demoLogin()
        : type === "login"
          ? await api.login(authForm.email, authForm.password)
          : await api.register(authForm.email, authForm.password, authForm.displayName || authForm.email);

      setAuthToken(response.access_token);
      setUser(response.user);
      await refreshSharedData();
      const chats = await refreshChats();
      if (chats[0]) await selectChat(chats[0].id);
      setActiveSection("chats");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function createChat() {
    try {
      const dsName = selectedDataset?.name || datasets[0]?.name || null;
      const created = await api.createChat({ title: "Новый чат", kind: "general", dataset_name: dsName });
      await refreshChats();
      await selectChat(created.id);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function renameChat(chatId: string, title: string) {
    try {
      await api.updateChat(chatId, { title });
      await refreshChats();
      if (selectedChatId === chatId) {
        const detail = await api.getChat(chatId);
        setMessages(detail.messages || []);
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function deleteChat(chatId: string) {
    try {
      await api.deleteChat(chatId);
      const updated = await refreshChats();
      if (selectedChatId === chatId) {
        const next = updated[0];
        if (next) {
          await selectChat(next.id);
        } else {
          setSelectedChatId("");
          setMessages([]);
        }
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function updateChatDatasetContext(datasetId: string) {
    setSelectedDatasetId(datasetId);
    const ds = datasets.find((d) => d.id === datasetId);
    if (!ds) return;

    if (selectedChatId) {
      try {
        await api.updateChat(selectedChatId, { dataset_name: ds.name });
        await refreshChats();
      } catch {
        // no-op
      }
      setDatasetNotice(`Датасет для чата: ${ds.name}`);
      setTimeout(() => setDatasetNotice(""), 2000);
    }
  }

  async function streamToChat(chatId: string, text: string) {
    const optimistic: ChatMessage = {
      id: `tmp-${Date.now()}`,
      chat_id: chatId,
      role: "user",
      content: text,
      blocks: [{ type: "markdown", content: text }],
      metadata: {},
      created_at: new Date().toISOString()
    };

    const assistantId = `tmp-assistant-${Date.now()}`;
    const optimisticAssistant: ChatMessage = {
      id: assistantId,
      chat_id: chatId,
      role: "assistant",
      content: "_Agent started..._",
      blocks: [{ type: "markdown", content: "_Agent started..._" }],
      metadata: { streaming: true },
      created_at: new Date().toISOString()
    };

    setMessages((prev) => [...prev, optimistic, optimisticAssistant]);
    setChatStreamInfo({ logs: [] });
    const controller = new AbortController();
    streamAbortRef.current = controller;

    try {
      let streamedText = "";
      const onEvt = (evt: any) => {
        if (evt.event === "message_delta") {
          const delta = String(evt.data?.content || "");
          if (!delta) return;
          streamedText += delta;
          setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, content: streamedText, blocks: [{ type: "markdown", content: streamedText }] } : m)));
        } else if (evt.event === "error") {
          const msg = String(evt.data?.message || "Stream error");
          setChatStreamInfo({ logs: [msg], error: msg });
          setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, content: `**Error:** ${msg}`, blocks: [{ type: "markdown", content: `**Error:** ${msg}` }] } : m)));
        } else if (evt.event === "agent_status") {
          const stage = String(evt.data?.stage || "status");
          const message = String(evt.data?.message || "");
          const line = message ? `${stage}: ${message}` : stage;
          setChatStreamInfo({ logs: [line] });
          if (!streamedText) {
            setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, content: `_${line}_`, blocks: [{ type: "markdown", content: `_${line}_` }] } : m)));
          }
        } else if (evt.event === "artifact_created") {
          const filename = String(evt.data?.filename || "artifact");
          setChatStreamInfo({ logs: [`artifact: ${filename}`] });
        } else if (evt.event === "done") {
          setChatStreamInfo({ logs: [] });
        }
      };

      await api.streamChatMessage(chatId, { role: "user", content: text, blocks: optimistic.blocks, metadata: { mode: "chat" } }, onEvt, controller.signal);

      const refreshed = await api.getChat(chatId);
      setMessages(refreshed.messages || []);
      await refreshSharedData();
      await refreshChats();
    } catch (e) {
      const msg = (e as Error).message;
      if (isStreamAbortError(msg)) {
        setChatStreamInfo({ logs: [] });
        return;
      }
      setChatStreamInfo({ logs: [msg], error: msg });
      setError(msg);
    } finally {
      setSending(false);
      streamAbortRef.current = null;
    }
  }

  async function sendMessage(text: string) {
    if (!text.trim()) return;
    let chatId = selectedChatId;
    if (!chatId) {
      await createChat();
      const updated = await refreshChats();
      chatId = updated[0]?.id || "";
    }
    if (!chatId) return;

    setSending(true);
    await streamToChat(chatId, text);
  }

  function stopStream() {
    if (selectedChatId) {
      void api.cancelChatRun(selectedChatId).catch(() => {});
    }
    streamAbortRef.current?.abort();
    setSending(false);
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

  async function deleteDataset(id: string) {
    try {
      setLoading(true);
      await api.deleteDataset(id);
      const ds = await api.listDatasets();
      setDatasets(ds.items || []);
      const nextId = (ds.items || [])[0]?.id || "";
      if (selectedDatasetId === id) {
        setSelectedDatasetId(nextId);
        setDatasetPreview(null);
        setDatasetProfile(null);
      }
      if (selectedChatId) {
        const selected = (ds.items || []).find((d) => d.id === nextId);
        if (selected) {
          await api.updateChat(selectedChatId, { dataset_name: selected.name });
          await refreshChats();
        }
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function deleteArtifact(id: string) {
    try {
      setLoading(true);
      await api.deleteArtifact(id);
      const updated = await api.listArtifacts();
      const items = updated.items || [];
      setArtifacts(items);
      if (selectedArtifactId === id) {
        setSelectedArtifactId(items[0]?.id || "");
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const title = activeSection === "chats" ? "Чаты" : activeSection === "datasets" ? "Датасеты" : "Артефакты";

  if (!user) {
    return (
      <div className="auth-wrap">
        <div className="auth-card">
          <h1>LLM Data Analyst</h1>
          <p>Рабочее пространство</p>
          <ErrorBanner message={error} />
          <input placeholder="Email" value={authForm.email} onChange={(e) => setAuthForm((p) => ({ ...p, email: e.target.value }))} />
          <input placeholder="Password" type="password" value={authForm.password} onChange={(e) => setAuthForm((p) => ({ ...p, password: e.target.value }))} />
          {authMode === "register" ? <input placeholder="Display name" value={authForm.displayName} onChange={(e) => setAuthForm((p) => ({ ...p, displayName: e.target.value }))} /> : null}
          <div className="auth-row">
            <button className="btn-primary" onClick={() => doAuth(authMode)} disabled={loading}>{authMode === "login" ? "Войти" : "Зарегистрироваться"}</button>
            <button className="btn-secondary" onClick={() => doAuth("demo")} disabled={loading}>Демо</button>
          </div>
          <button className="btn-ghost" onClick={() => setAuthMode((m) => (m === "login" ? "register" : "login"))}>
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
        sidebar={
          <WorkspaceSidebar
            user={user}
            section={activeSection}
            chats={allChats}
            selectedChatId={selectedChatId}
            onSelectChat={selectChat}
            onCreateChat={createChat}
            onRenameChat={renameChat}
            onDeleteChat={deleteChat}
            datasets={datasets}
            selectedDatasetId={selectedDatasetId}
            onUseDataset={updateChatDatasetContext}
            onPreviewDataset={(id) => loadDatasetPreview(id, true)}
            onDeleteDataset={deleteDataset}
            onUploadDataset={uploadDataset}
            artifacts={artifacts}
            onSelectArtifact={(id) => {
              setSelectedArtifactId(id);
              setActiveSection("artifacts");
            }}
            onDeleteArtifact={deleteArtifact}
            onLogout={() => { setAuthToken(null); setUser(null); }}
            theme={theme}
            onToggleTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
          />
        }
        main={
          <div className="main-wrap">
            <TopBar title={title} />
            {activeSection === "chats" ? <ChatPanel messages={messages} onSend={sendMessage} onStop={stopStream} loading={sending} chatResponse={chatStreamInfo} datasetName={selectedDataset?.name} datasetNotice={datasetNotice} interruptedRequest={null} /> : null}
            {activeSection === "datasets" ? <DatasetExplorer datasets={datasets} selected={selectedDatasetId} preview={datasetPreview} profile={datasetProfile} onSelect={(id) => loadDatasetPreview(id, false)} onUpload={uploadDataset} onUseInChat={(id) => { setActiveSection("chats"); updateChatDatasetContext(id); }} onDelete={deleteDataset} /> : null}
            {activeSection === "artifacts" ? <ArtifactExplorer items={artifacts} onSelect={setSelectedArtifactId} selected={selectedArtifact} /> : null}
          </div>
        }
      />
    </div>
  );
}
