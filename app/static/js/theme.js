// Theme toggle: light <-> dark, persisted to localStorage, with a
// prefers-color-scheme fallback. The initial theme is applied by an inline
// script in <head> (before paint) to avoid a flash; this file wires the button
// and keeps its label in sync.

(function () {
  const STORAGE_KEY = "outpost-theme";

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark"
      ? "dark"
      : "light";
  }

  function applyTheme(theme) {
    if (theme === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
    updateButton(theme);
  }

  function updateButton(theme) {
    const btn = document.getElementById("theme-toggle");
    if (!btn) return;
    const nextIsDark = theme !== "dark";
    btn.textContent = nextIsDark ? "◐ Dark" : "◑ Light";
    btn.setAttribute(
      "aria-label",
      nextIsDark ? "Switch to dark theme" : "Switch to light theme"
    );
  }

  function toggle() {
    const next = currentTheme() === "dark" ? "light" : "dark";
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  }

  document.addEventListener("DOMContentLoaded", function () {
    updateButton(currentTheme());
    const btn = document.getElementById("theme-toggle");
    if (btn) btn.addEventListener("click", toggle);
  });
})();
