import { useEffect, useRef } from "react";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  sources?: { title: string; category: string; snippet: string }[];
}

export default function ChatWindow({ messages }: { messages: ChatMessage[] }) {
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="empty" data-testid="chat-empty">
        向小龙提问任何运维问题，例如「服务响应变慢怎么排查？」
      </div>
    );
  }

  return (
    <div className="messages" data-testid="chat-messages">
      {messages.map((m) => (
        <div key={m.id} className={`msg ${m.role}`}>
          <div className="bubble">
            {m.content || (m.streaming ? "…" : "")}
            {m.sources && m.sources.length > 0 && (
              <div className="citations">
                {m.sources.map((s, i) => (
                  <span key={i} className="citation" title={s.snippet}>
                    {s.title}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      ))}
      <div ref={bottom} />
    </div>
  );
}
