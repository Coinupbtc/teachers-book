/**
 * Chrome / Chromebook install: Chrome will not auto-pin a tab.
 * Capture beforeinstallprompt and show an in-app Install button, plus
 * fallback steps when the browser never fires the prompt.
 */
(function () {
  "use strict";

  const STANDALONE = window.matchMedia("(display-mode: standalone)").matches
    || window.navigator.standalone === true;
  let deferredPrompt = null;

  function hideBar() {
    document.getElementById("pwa-install-bar")?.remove();
  }

  function barHtml(canPrompt) {
    const action = canPrompt
      ? `<button type="button" class="button primary" id="pwa-install-go">Install Teachers B00k</button>`
      : `<button type="button" class="button primary" id="pwa-install-how">How to install in Chrome</button>`;
    return `<aside id="pwa-install-bar" class="pwa-install-bar" role="region" aria-label="Install app">
      <div>
        <strong>Use it like an app, not a leftover tab.</strong>
        <p>Install Teachers B00k so it opens from your shelf / Start menu and works offline.</p>
      </div>
      <div class="pwa-install-actions">
        ${action}
        <button type="button" class="text-button" id="pwa-install-dismiss">Not now</button>
      </div>
    </aside>`;
  }

  function howModal() {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `<section class="modal-card" role="dialog" aria-modal="true">
      <button class="modal-close" aria-label="Close">×</button>
      <h2>Install in Google Chrome</h2>
      <ol class="install-steps">
        <li>Stay on this page in <strong>Google Chrome</strong> (not Safari, Edge, or the Chromebook “Files” preview).</li>
        <li>Click the <strong>⋮</strong> menu (top right).</li>
        <li>Open <strong>Cast, save, and share</strong> (or <strong>Save and share</strong>).</li>
        <li>Click <strong>Install page as app…</strong> / <strong>Install Teachers B00k…</strong>.</li>
        <li>Confirm. It appears on your shelf like any other app.</li>
      </ol>
      <p class="form-note">If you do not see Install, you are already in the app, or this browser cannot install PWAs. Chrome on Windows, Chromebook, and Android can.</p>
      <div class="modal-actions"><button type="button" class="button primary modal-cancel">Got it</button></div>
    </section>`;
    document.body.append(overlay);
    const close = () => overlay.remove();
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay || e.target.closest(".modal-close") || e.target.closest(".modal-cancel")) close();
    });
  }

  function bindBar() {
    document.getElementById("pwa-install-dismiss")?.addEventListener("click", () => {
      sessionStorage.setItem("tb_hide_install", "1");
      hideBar();
    });
    document.getElementById("pwa-install-how")?.addEventListener("click", howModal);
    document.getElementById("pwa-install-go")?.addEventListener("click", async () => {
      if (!deferredPrompt) return howModal();
      deferredPrompt.prompt();
      const choice = await deferredPrompt.userChoice.catch(() => ({ outcome: "dismissed" }));
      deferredPrompt = null;
      if (choice.outcome === "accepted") hideBar();
    });
  }

  function showBar() {
    if (STANDALONE || sessionStorage.getItem("tb_hide_install") === "1") return;
    if (document.getElementById("pwa-install-bar")) {
      bindBar();
      return;
    }
    const host = document.getElementById("pwa-install-host") || document.body;
    if (!host) return;
    host.insertAdjacentHTML("afterbegin", barHtml(Boolean(deferredPrompt)));
    bindBar();
  }

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    showBar();
  });

  window.addEventListener("appinstalled", hideBar);

  document.addEventListener("DOMContentLoaded", () => {
    if (!STANDALONE) showBar();
  });

  // Re-attach after the SPA wipes #app innerHTML
  const _orig = window.TBInstallRebind;
  window.TBInstallRebind = function () {
    if (typeof _orig === "function") _orig();
    showBar();
  };
})();
