import { useEffect, useRef, useState } from "react";
import PatchViewer from "../components/PatchViewer";
import { api, ApiError } from "../services/api";
import { subscribe } from "../services/sse";

const STAGES = [
  { key: "locating", label: "定位代码" },
  { key: "generating", label: "生成分析" },
  { key: "validating", label: "校验补丁" },
  { key: "done", label: "完成" },
];

export default function BugAnalysisPage() {
  const [projects, setProjects] = useState<any[]>([]);
  const [projectId, setProjectId] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [stage, setStage] = useState<string | null>(null);
  const [located, setLocated] = useState<any[]>([]);
  const [result, setResult] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const closeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    api
      .listProjects()
      .then((list) => setProjects(list.filter((p) => p.status === "READY")))
      .catch((e) => setError(e instanceof ApiError ? e.message : "加载项目失败"));
    return () => closeRef.current?.();
  }, []);

  const refreshHistory = async (pid: string) => {
    try {
      setHistory(await api.listAnalyses(pid));
    } catch {
      setHistory([]);
    }
  };

  useEffect(() => {
    if (projectId) refreshHistory(projectId);
  }, [projectId]);

  const loadResult = async (id: string) => {
    const row = await api.getAnalysis(id);
    setResult(row);
    if (row.located_files) setLocated(row.located_files);
    if (projectId) refreshHistory(projectId);
    return row;
  };

  const run = async () => {
    if (!projectId) {
      setError("请先选择一个已就绪的项目（在「项目源码」页接入）");
      return;
    }
    if (!description.trim()) {
      setError("请描述 Bug 现象");
      return;
    }
    setError("");
    setResult(null);
    setLocated([]);
    setStage("locating");
    setBusy(true);
    try {
      const res = await api.createAnalysis(projectId, description.trim());
      closeRef.current = subscribe(res.stream_url, {
        onEvent: async (event, data) => {
          if (event === "stage") setStage(data.stage);
          if (event === "located") setLocated(data.files || []);
          if (event === "done") {
            setStage("done");
            setBusy(false);
            await loadResult(data.analysis_id);
            closeRef.current?.();
          }
          if (event === "error") {
            setError(`${data.message}${data.hint ? `（${data.hint}）` : ""}`);
          }
        },
        onError: (msg) => {
          setError(msg);
          setBusy(false);
        },
      });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "提交失败");
      setBusy(false);
    }
  };

  const retry = async (id: string) => {
    try {
      await api.retryAnalysis(id);
      setBusy(true);
      setError("");
      const res = { stream_url: `/api/v1/analyses/${id}/stream` };
      closeRef.current = subscribe(res.stream_url, {
        onEvent: async (event, data) => {
          if (event === "stage") setStage(data.stage);
          if (event === "located") setLocated(data.files || []);
          if (event === "done") {
            setStage("done");
            setBusy(false);
            await loadResult(data.analysis_id);
            closeRef.current?.();
          }
          if (event === "error") setError(data.message);
        },
        onError: (msg) => {
          setError(msg);
          setBusy(false);
        },
      });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "重试失败");
      setBusy(false);
    }
  };

  const openHistory = async (id: string) => {
    setStage("done");
    await loadResult(id);
  };

  const stageIndex = STAGES.findIndex((s) => s.key === stage);

  return (
    <div>
      <h2>Bug 自动定位 · 根因解析 · Patch 生成</h2>
      {error && <div className="error-banner">{error}</div>}

      <div className="panel" style={{ marginBottom: 16 }}>
        <div className="toolbar">
          <select
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            style={{ width: 320 }}
            data-testid="project-select"
          >
            <option value="">选择已就绪项目…</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}（{p.file_count} 文件）
              </option>
            ))}
          </select>
          <button onClick={run} disabled={busy} data-testid="submit-analysis">
            {busy ? "分析中…" : "开始分析"}
          </button>
        </div>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="描述 Bug 现象，可粘贴报错信息，例如：调用 /api/login 时报 KeyError: 'token'，用户无法登录"
          data-testid="bug-description"
        />
        <div className="stage-list">
          {STAGES.map((s, i) => (
            <span
              key={s.key}
              className={`stage ${stage === s.key ? "active" : ""} ${stageIndex > i ? "done" : ""}`}
            >
              {s.label}
            </span>
          ))}
        </div>
      </div>

      {located.length > 0 && (
        <div className="panel" style={{ marginBottom: 16 }}>
          <h3>定位到的代码</h3>
          {located.map((f, i) => (
            <div key={i} className="kv">
              {f.file} {f.line_start ? `(${f.line_start}-${f.line_end})` : ""}
              {f.snippet && <pre className="patch" style={{ marginTop: 6 }}>{f.snippet}</pre>}
            </div>
          ))}
        </div>
      )}

      {result && (
        <div className="panel" style={{ marginBottom: 16 }}>
          <h3>
            分析结果{" "}
            <span className={`badge ${result.status === "SUCCEEDED" ? "succeeded" : "failed"}`}>
              {result.status}
            </span>
          </h3>
          {result.error_message && <div className="error-banner">{result.error_message}</div>}
          {result.root_cause && (
            <>
              <h3>根因解析</h3>
              <div style={{ whiteSpace: "pre-wrap", fontSize: 14 }}>{result.root_cause}</div>
            </>
          )}
          {result.fix_suggestion && (
            <>
              <h3>修复建议</h3>
              <div style={{ whiteSpace: "pre-wrap", fontSize: 14 }}>{result.fix_suggestion}</div>
            </>
          )}
          <h3>Patch 补丁</h3>
          <PatchViewer
            patch={result.patch_text}
            applicable={result.patch_applicable}
            validationLog={result.validation_log}
          />
        </div>
      )}

      {history.length > 0 && (
        <div className="panel">
          <h3>历史分析</h3>
          {history.map((h) => (
            <div key={h.id} className="kv">
              [{h.status}] {h.bug_description.slice(0, 60)}{" "}
              <button className="ghost" onClick={() => openHistory(h.id)}>
                查看
              </button>{" "}
              {h.status === "FAILED" && (
                <button className="ghost" onClick={() => retry(h.id)}>
                  重试
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
