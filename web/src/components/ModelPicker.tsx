import type { ModelSpec } from "../api";

const GROUPS: [string, (m: ModelSpec) => boolean][] = [
  ["Decision models", (m) => m.provider === "decisions"],
  ["LLMs", (m) => m.provider === "llm"],
  ["Offline mocks", (m) => m.provider === "mock"],
];

export function ModelPicker({
  models,
  selected,
  onChange,
}: {
  models: ModelSpec[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
}) {
  const toggle = (name: string) => {
    const next = new Set(selected);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    onChange(next);
  };
  return (
    <div className="checklist">
      {GROUPS.map(([label, match]) => {
        const group = models.filter(match);
        if (!group.length) return null;
        const allOn = group.every((m) => selected.has(m.name));
        return (
          <div key={label}>
            <div className="group-label">
              <span>{label}</span>
              <button
                onClick={() => {
                  const next = new Set(selected);
                  group.forEach((m) => (allOn ? next.delete(m.name) : next.add(m.name)));
                  onChange(next);
                }}
              >
                {allOn ? "none" : "all"}
              </button>
            </div>
            {group.map((m) => (
              <label key={m.name} className="check">
                <input type="checkbox" checked={selected.has(m.name)} onChange={() => toggle(m.name)} />
                <span className={`kind ${m.kind}`} aria-hidden />
                <span>{m.name}</span>
                <span className="meta">{m.provider === "mock" ? "mock" : m.model}</span>
              </label>
            ))}
          </div>
        );
      })}
    </div>
  );
}
