function sourceLabel(citation) {
  if (citation.domain) return citation.domain;
  try {
    return new URL(citation.url).hostname;
  } catch {
    return "fixture source";
  }
}

export default function CitationChips({ lore }) {
  const citations = lore?.citations || [];
  if (!lore?.summary && citations.length === 0) return null;

  return (
    <section className="citation-panel" aria-label="Tavily lore citations">
      {lore?.summary ? <p>{lore.summary}</p> : null}
      <div className="citation-chips">
        {citations.map((citation, index) => (
          <a key={`${citation.url}-${index}`} href={citation.url} target="_blank" rel="noreferrer">
            <strong>{citation.title || "Lore source"}</strong>
            <span>{sourceLabel(citation)}</span>
          </a>
        ))}
      </div>
    </section>
  );
}
