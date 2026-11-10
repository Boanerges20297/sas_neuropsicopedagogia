(() => {
  "use strict";
  const root = document.querySelector("[data-clinic-workspace]");
  if (!root) return;
  const tabs = Array.from(root.querySelectorAll("[data-clinic-tab]"));
  const panes = Array.from(root.querySelectorAll("[data-clinic-pane]"));
  const valid = new Set(tabs.map(tab => tab.dataset.clinicTab));
  function activate(name, focus = false) {
    if (!valid.has(name)) name = "sessao";
    tabs.forEach(tab => {
      const active = tab.dataset.clinicTab === name;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
      if (active && focus) tab.focus();
    });
    panes.forEach(pane => { pane.hidden = pane.dataset.clinicPane !== name; });
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, "", "#" + name);
    }
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activate(tab.dataset.clinicTab));
    tab.addEventListener("keydown", event => {
      const keys = ["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft", "Home", "End"];
      if (!keys.includes(event.key)) return;
      event.preventDefault();
      const forward = event.key === "ArrowRight" || event.key === "ArrowDown";
      const backward = event.key === "ArrowLeft" || event.key === "ArrowUp";
      const next = event.key === "Home" ? 0 :
        event.key === "End" ? tabs.length - 1 :
          forward ? (index + 1) % tabs.length :
            backward ? (index - 1 + tabs.length) % tabs.length : index;
      activate(tabs[next].dataset.clinicTab, true);
    });
  });
  root.querySelectorAll("[data-clinic-open]").forEach(button =>
    button.addEventListener("click", () => {
      activate(button.dataset.clinicOpen);
      root.querySelector("[data-clinic-pane='" + button.dataset.clinicOpen + "']")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    })
  );
  const startingTab = decodeURIComponent(window.location.hash.replace(/^#/, ""));
  activate(valid.has(startingTab) ? startingTab : "sessao");
  window.addEventListener("hashchange", () => {
    const name = decodeURIComponent(window.location.hash.replace(/^#/, ""));
    if (valid.has(name)) activate(name);
  });

  const editor = document.getElementById("clinicEditor");
  const form = document.getElementById("clinicNoteForm");
  const output = document.getElementById("clinicHTML");
  const status = document.getElementById("clinicSaveStatus");
  const saveButton = document.getElementById("clinicSaveButton");
  if (!editor || !form || editor.getAttribute("contenteditable") !== "true") return;

  const revisionInput = form.querySelector("[name='revision']");
  let savedHtml = editor.innerHTML;
  let saving = false;
  const dirty = () => editor.innerHTML !== savedHtml;
  function announce(message, kind = "") {
    status.textContent = message;
    status.classList.remove("is-dirty", "is-error", "is-saved");
    if (kind) status.classList.add("is-" + kind);
  }
  editor.addEventListener("input", () => {
    if (saving) return;
    announce(dirty() ? "Alterações não salvas" : "Sem alterações pendentes",
      dirty() ? "dirty" : "");
  });
  form.querySelectorAll("[data-command]").forEach(button => {
    button.addEventListener("click", () => {
      editor.focus();
      document.execCommand(button.dataset.command, false, button.dataset.value || null);
      editor.dispatchEvent(new Event("input", { bubbles: true }));
    });
  });
  window.addEventListener("beforeunload", event => {
    if (!saving && dirty()) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
  form.addEventListener("submit", async event => {
    output.value = editor.innerHTML;
    if (!window.fetch) return; // Envio tradicional como alternativa.
    event.preventDefault();
    if (saving) return;
    const submittedHtml = output.value;
    saving = true;
    saveButton.disabled = true;
    announce("Salvando evolução...");
    try {
      const response = await fetch(form.action, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest" },
        body: new FormData(form)
      });
      let payload;
      try { payload = await response.json(); }
      catch (_) { throw new Error("Não foi possível confirmar o salvamento. Verifique a sessão."); }
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || "Não foi possível salvar. Tente novamente.");
      }
      revisionInput.value = String(payload.revision);
      savedHtml = submittedHtml;
      const changedDuringSave = dirty();
      announce(changedDuringSave
        ? "Versão " + payload.revision + " salva; há novas alterações pendentes"
        : "Versão " + payload.revision + " salva com sucesso",
        changedDuringSave ? "dirty" : "saved");
    } catch (error) {
      announce(error.message || "Falha de comunicação ao salvar. O texto continua nesta página.", "error");
    } finally {
      saving = false;
      saveButton.disabled = false;
    }
  });
})();
