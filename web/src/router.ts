import { useEffect, useState } from "react";

/** Minimal hash router: #/results/<report>/<dataset>, #/run, #/playground. */
export function useRoute(): string[] {
  const read = () => window.location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const [parts, setParts] = useState(read);
  useEffect(() => {
    const on = () => setParts(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return parts;
}

export function navigate(path: string) {
  window.location.hash = path;
  window.scrollTo(0, 0);
}
