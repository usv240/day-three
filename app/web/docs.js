(() => {
  "use strict";
  const toggle = document.querySelector("#theme-toggle");
  const themes = ["light", "dark"];
  let theme = localStorage.getItem("theme");
  if (!themes.includes(theme)) theme = "light";
  const applyTheme = () => {
    document.documentElement.dataset.theme = theme;
    toggle.textContent = theme === "light" ? "Use dark mode" : "Use light mode";
    toggle.setAttribute("aria-pressed", String(theme === "dark"));
    localStorage.setItem("theme", theme);
  };
  toggle.addEventListener("click", () => {
    theme = themes[(themes.indexOf(theme) + 1) % themes.length];
    applyTheme();
  });
  applyTheme();
  SwaggerUIBundle({
    url: "/openapi.json",
    dom_id: "#swagger-ui",
    deepLinking: true,
    displayRequestDuration: true,
    filter: true,
    showExtensions: true,
    showCommonExtensions: true,
    persistAuthorization: false,
    presets: [SwaggerUIBundle.presets.apis],
    layout: "BaseLayout"
  });
})();