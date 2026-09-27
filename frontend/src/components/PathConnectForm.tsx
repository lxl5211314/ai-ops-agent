import { useState } from "react";

export default function PathConnectForm({
  onSubmit,
  busy,
}: {
  onSubmit: (path: string, name: string) => Promise<void>;
  busy?: boolean;
}) {
  const [path, setPath] = useState("");
  const [name, setName] = useState("");

  return (
    <div data-testid="path-connect-form">
      <input
        placeholder="本地项目源码绝对路径，如 /workspace/my-service"
        value={path}
        onChange={(e) => setPath(e.target.value)}
        data-testid="path-input"
      />
      <input
        placeholder="项目名称（可选，默认取目录名）"
        value={name}
        onChange={(e) => setName(e.target.value)}
        style={{ marginTop: 8 }}
      />
      <button
        style={{ marginTop: 8 }}
        disabled={busy || !path.trim()}
        onClick={() => onSubmit(path.trim(), name.trim())}
        data-testid="path-submit"
      >
        {busy ? "接入中…" : "按路径接入"}
      </button>
    </div>
  );
}
