import { useEffect, useState } from "react";
import FileTree from "../components/FileTree";
import PathConnectForm from "../components/PathConnectForm";
import Uploader from "../components/Uploader";
import { api, ApiError } from "../services/api";

const STATUS_TEXT: Record<string, string> = {
  INGESTING: "接入中",
  READY: "就绪",
  FAILED: "失败",
};

export default function ProjectsPage() {
  const [folders, setFolders] = useState<any[]>([]);
  const [projects, setProjects] = useState<any[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [folderName, setFolderName] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    try {
      const [f, p] = await Promise.all([api.listFolders(), api.listProjects()]);
      setFolders(f);
      setProjects(p);
      if (f.some((x: any) => x.projects?.some((y: any) => y.status === "INGESTING"))) {
        window.setTimeout(refresh, 2000);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载失败");
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const flash = (msg: string) => {
    setError("");
    setOk(msg);
  };

  const createFolder = async () => {
    try {
      await api.createFolder(folderName.trim());
      setFolderName("");
      flash("文件夹已创建");
      refresh();
    } catch (e) {
      setOk("");
      setError(e instanceof ApiError ? e.message : "创建失败");
    }
  };

  const connectPath = async (path: string, name: string) => {
    if (!selected) {
      setError("请先选择一个文件夹");
      return;
    }
    setBusy(true);
    try {
      const p = await api.connectPath(selected, name, path);
      flash(`路径接入成功：${p.name}（${p.file_count} 个文件）`);
      refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "接入失败");
    } finally {
      setBusy(false);
    }
  };

  const upload = async (files: File[]) => {
    if (!selected) {
      setError("请先选择一个文件夹");
      return;
    }
    setBusy(true);
    try {
      const p = await api.uploadProject(selected, "", files);
      flash(`上传接入成功：${p.name}`);
      refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "上传失败");
    } finally {
      setBusy(false);
    }
  };

  const preview = async (id: string) => {
    try {
      const p = await api.getProject(id);
      setProjects((prev) => prev.map((x) => (x.id === id ? { ...x, tree_preview: p.tree_preview } : x)));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "预览失败");
    }
  };

  const removeProject = async (id: string) => {
    try {
      await api.deleteProject(id);
      refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "删除失败");
    }
  };

  return (
    <div>
      <h2>项目源码接入</h2>
      {error && <div className="error-banner">{error}</div>}
      {ok && <div className="ok-banner">{ok}</div>}

      <div className="panel toolbar">
        <input
          placeholder="新建文件夹名称"
          value={folderName}
          onChange={(e) => setFolderName(e.target.value)}
          style={{ width: 240 }}
          data-testid="folder-name-input"
        />
        <button onClick={createFolder} disabled={!folderName.trim()} data-testid="create-folder">
          创建文件夹
        </button>
        <select
          value={selected || ""}
          onChange={(e) => setSelected(e.target.value || null)}
          style={{ width: 220 }}
          data-testid="folder-select"
        >
          <option value="">选择文件夹…</option>
          {folders.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </select>
      </div>

      <div className="row" style={{ marginBottom: 16 }}>
        <div className="panel col">
          <h3>按路径接入</h3>
          <PathConnectForm onSubmit={connectPath} busy={busy} />
        </div>
        <div className="panel col">
          <h3>上传源码文件 / 压缩包</h3>
          <Uploader onUpload={upload} busy={busy} />
        </div>
      </div>

      {projects.length === 0 ? (
        <div className="empty">尚未接入任何项目</div>
      ) : (
        <div className="card-grid">
          {projects.map((p) => (
            <div className="card" key={p.id}>
              <h4>
                {p.name} <span className={`badge ${p.status.toLowerCase()}`}>{STATUS_TEXT[p.status] || p.status}</span>
              </h4>
              <div className="kv">接入方式：{p.source_type === "path" ? "路径" : "上传"}</div>
              {p.source_path && <div className="kv">路径：{p.source_path}</div>}
              <div className="kv">文件数：{p.file_count}</div>
              <div className="kv">接入时间：{p.created_at}</div>
              {p.error_message && <div className="error-banner">{p.error_message}</div>}
              <div className="actions">
                <button className="ghost" onClick={() => preview(p.id)}>
                  查看结构
                </button>
                <button className="danger" onClick={() => removeProject(p.id)}>
                  删除
                </button>
              </div>
              {p.tree_preview && <FileTree entries={p.tree_preview} />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
