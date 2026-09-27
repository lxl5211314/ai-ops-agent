import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../services/api";

const STATUS_TEXT: Record<string, string> = {
  PENDING: "摄入中",
  INDEXED: "已入库",
  FAILED: "失败",
};

export default function KbPage() {
  const [docs, setDocs] = useState<any[]>([]);
  const [category, setCategory] = useState("ops_knowledge");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const timer = useRef<number | null>(null);

  const refresh = async () => {
    try {
      const list = await api.listDocuments();
      setDocs(list);
      if (list.some((d) => d.status === "PENDING")) {
        timer.current = window.setTimeout(refresh, 2000);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载知识库失败");
    }
  };

  useEffect(() => {
    refresh();
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, []);

  const upload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("请先选择文档");
      return;
    }
    setError("");
    setOk("");
    try {
      await api.uploadDocument(category, file);
      setOk(`已提交《${file.name}》，正在解析与索引…`);
      if (fileRef.current) fileRef.current.value = "";
      refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "上传失败");
    }
  };

  const remove = async (id: string) => {
    try {
      await api.deleteDocument(id);
      refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "删除失败");
    }
  };

  return (
    <div>
      <h2>知识库（企业项目背景 / 运维技术知识）</h2>
      {error && <div className="error-banner">{error}</div>}
      {ok && <div className="ok-banner">{ok}</div>}

      <div className="panel toolbar">
        <select value={category} onChange={(e) => setCategory(e.target.value)} style={{ width: 220 }}>
          <option value="ops_knowledge">运维技术知识</option>
          <option value="enterprise_background">企业项目背景</option>
        </select>
        <input type="file" ref={fileRef} accept=".md,.txt,.pdf,.docx" style={{ width: 320 }} />
        <button onClick={upload}>上传文档</button>
      </div>

      {docs.length === 0 ? (
        <div className="empty">尚未上传任何知识文档</div>
      ) : (
        <div className="card-grid">
          {docs.map((d) => (
            <div className="card" key={d.id}>
              <h4>
                {d.title} <span className={`badge ${d.status.toLowerCase()}`}>{STATUS_TEXT[d.status] || d.status}</span>
              </h4>
              <div className="kv">分类：{d.category === "enterprise_background" ? "企业项目背景" : "运维技术知识"}</div>
              <div className="kv">切块：{d.chunk_count} · 图谱实体：{d.graph_node_count}</div>
              {d.job?.stage && <div className="kv">阶段：{d.job.stage}</div>}
              {d.error_message && <div className="error-banner">{d.error_message}</div>}
              <div className="actions">
                <button className="danger" onClick={() => remove(d.id)}>
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
