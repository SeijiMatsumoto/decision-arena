import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Playground } from "./pages/Playground";
import { Results } from "./pages/Results";
import { Run } from "./pages/Run";
import { useRoute } from "./router";
import "./styles.css";

function App() {
  const [page = "results", a, b] = useRoute();
  const tabs = [
    ["results", "Results"],
    ["run", "Run evals"],
    ["playground", "Playground"],
  ];
  return (
    <>
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden />
          Decision Arena
        </div>
        <nav className="nav">
          {tabs.map(([id, label]) => (
            <a key={id} href={`#/${id}`} className={page === id ? "active" : ""}>
              {label}
            </a>
          ))}
        </nav>
      </header>
      <main>
        {page === "run" ? <Run /> : page === "playground" ? <Playground /> : <Results reportId={a} dataset={b} />}
      </main>
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
