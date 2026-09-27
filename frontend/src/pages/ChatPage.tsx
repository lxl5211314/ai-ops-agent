import { FormEvent, useEffect, useRef, useState } from "react";
import ChatWindow, { ChatMessage } from "../components/ChatWindow";
import { api, ApiError } from "../services/api";
import { subscribe } from "../services/sse";

export default function ChatPage() {
  const [conversations, setConversations] = useState<any[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const closeRef = useRef<(() => void) | null>(null);

  const refreshConversations = async () => {
    try {
      setConversations(await api.listConversations());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载会话失败");
    }
  };

  useEffect(() => {
    refreshConversations();
    return () => closeRef.current?.();
  }, []);

  const openConversation = async (id: string) => {
    closeRef.current?.();
    setCurrentId(id);
    setError("");
    try {
      const conv = await api.getConversation(id);
      setMessages(
        (conv.messages || []).map((m: any) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          sources: m.meta?.sources,
        })),
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载消息失败");
    }
  };

  const newConversation = async () => {
    try {
      const conv = await api.createConversation();
      await refreshConversations();
      setCurrentId(conv.id);
      setMessages([]);
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "创建会话失败");
    }
  };

  const removeConversation = async (id: string) => {
    try {
      await api.deleteConversation(id);
      if (id === currentId) {
        setCurrentId(null);
        setMessages([]);
      }
      refreshConversations();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "删除失败");
    }
  };

  const send = async (e: FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setError("");
    setBusy(true);
    setInput("");
    try {
      let cid = currentId;
      if (!cid) {
        const conv = await api.createConversation(text.slice(0, 40));
        cid = conv.id;
        setCurrentId(cid);
        await refreshConversations();
      }
      const userMsg: ChatMessage = { id: `u-${Date.now()}`, role: "user", content: text };
      const botMsg: ChatMessage = { id: `a-${Date.now()}`, role: "assistant", content: "", streaming: true };
      setMessages((prev) => [...prev, userMsg, botMsg]);

      const res = await api.postMessage(cid, text);
      closeRef.current = subscribe(res.stream_url, {
        onEvent: (event, data) => {
          setMessages((prev) => {
            const next = [...prev];
            const last = { ...next[next.length - 1] };
            if (event === "delta") last.content = (last.content || "") + (data.text || "");
            if (event === "sources") last.sources = data.items || [];
            if (event === "done") last.streaming = false;
            if (event === "error") {
              last.streaming = false;
              last.content = last.content || `⚠ ${data.message}`;
            }
            next[next.length - 1] = last;
            return next;
          });
          if (event === "done" || event === "error") {
            setBusy(false);
            closeRef.current?.();
            refreshConversations();
          }
        },
        onError: (msg) => {
          setError(msg);
          setBusy(false);
        },
      });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "发送失败");
      setBusy(false);
    }
  };

  return (
    <div className="chat-layout">
      <aside className="panel conv-list">
        <button onClick={newConversation} style={{ width: "100%", marginBottom: 8 }}>
          + 新会话
        </button>
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`conv-item ${c.id === currentId ? "active" : ""}`}
            onClick={() => openConversation(c.id)}
          >
            <span>{c.title || "未命名会话"}</span>
            <span
              className="del"
              onClick={(e) => {
                e.stopPropagation();
                removeConversation(c.id);
              }}
            >
              ✕
            </span>
          </div>
        ))}
      </aside>

      <section className="panel chat-panel">
        <h2>运维助手 小龙</h2>
        {error && <div className="error-banner">{error}</div>}
        <ChatWindow messages={messages} />
        <form className="composer" onSubmit={send}>
          <textarea
            value={input}
            placeholder="描述你的运维问题，Enter 发送，Shift+Enter 换行"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(e as unknown as FormEvent);
              }
            }}
          />
          <button type="submit" disabled={busy || !input.trim()}>
            {busy ? "回复中…" : "发送"}
          </button>
        </form>
      </section>
    </div>
  );
}
