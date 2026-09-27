export default function FileTree({ entries }: { entries: string[] }) {
  if (!entries || entries.length === 0) {
    return <div className="muted">暂无文件结构</div>;
  }
  return (
    <div className="file-list" data-testid="file-tree">
      {entries.map((e) => (
        <div key={e}>{e}</div>
      ))}
    </div>
  );
}
