export default function SourceCitations({
  items,
}: {
  items: { title: string; category: string; snippet: string }[];
}) {
  if (!items || items.length === 0) return null;
  return (
    <div className="citations" data-testid="source-citations">
      {items.map((s, i) => (
        <span key={i} className="citation" title={s.snippet}>
          {s.title} · {s.category === "graph" ? "图谱" : "文档"}
        </span>
      ))}
    </div>
  );
}
