import { useRef, useState } from "react";

export default function Uploader({
  onUpload,
  busy,
}: {
  onUpload: (files: File[]) => Promise<void>;
  busy?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);

  const pick = (list: FileList | null) => {
    if (!list) return;
    setFiles(Array.from(list));
  };

  return (
    <div data-testid="uploader">
      <input
        ref={inputRef}
        type="file"
        multiple
        onChange={(e) => pick(e.target.files)}
        data-testid="uploader-input"
      />
      {files.length > 0 && <div className="kv">已选择 {files.length} 个文件</div>}
      <button
        style={{ marginTop: 8 }}
        disabled={busy || files.length === 0}
        onClick={() => onUpload(files)}
      >
        {busy ? "上传中…" : "上传源码"}
      </button>
    </div>
  );
}
