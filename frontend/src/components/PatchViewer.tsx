import { useState } from "react";

export default function PatchViewer({
  patch,
  applicable,
  validationLog,
}: {
  patch: string | null;
  applicable: boolean | null;
  validationLog?: string | null;
}) {
  const [copied, setCopied] = useState(false);

  if (!patch) {
    return <div className="muted">本次分析未生成补丁</div>;
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(patch);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  const download = () => {
    const blob = new Blob([patch], { type: "text/x-diff" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "fix.patch";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div data-testid="patch-viewer">
      <div className="toolbar">
        <span className={`badge ${applicable ? "ready" : "failed"}`}>
          {applicable ? "补丁校验通过，可直接应用" : "补丁校验未通过，请人工确认"}
        </span>
        <button onClick={copy}>{copied ? "已复制" : "复制补丁"}</button>
        <button className="ghost" onClick={download}>
          下载 fix.patch
        </button>
      </div>
      <pre className="patch">{patch}</pre>
      {validationLog && <details className="muted"><summary>校验日志</summary>{validationLog}</details>}
    </div>
  );
}
