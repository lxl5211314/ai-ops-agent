import { BASE } from "./api";

export interface SSEHandlers {
  onEvent?: (event: string, data: any) => void;
  onError?: (message: string) => void;
}

export function subscribe(url: string, handlers: SSEHandlers): () => void {
  const full = url.startsWith("http") || url.startsWith(BASE) ? url : `${BASE}${url}`;
  const source = new EventSource(full);
  const named = ["delta", "sources", "done", "error", "stage", "located", "snapshot"];

  named.forEach((name) => {
    source.addEventListener(name, (ev) => {
      const raw = (ev as MessageEvent).data;
      if (name === "error" && (raw === null || raw === undefined)) {
        if (source.readyState === EventSource.CLOSED) {
          handlers.onError?.("连接中断，可重试");
        }
        return;
      }
      let data: any = {};
      try {
        data = JSON.parse(raw);
      } catch {
        data = {};
      }
      if (name === "error") {
        handlers.onError?.(data?.message || "服务返回错误");
      }
      handlers.onEvent?.(name, data);
    });
  });

  source.onerror = () => {
    if (source.readyState === EventSource.CLOSED) {
      handlers.onError?.("连接中断，可重试");
    }
  };

  return () => source.close();
}
