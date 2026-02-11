(() => {
  const qs = (sel, root=document) => root.querySelector(sel);
  const qsa = (sel, root=document) => Array.from(root.querySelectorAll(sel));
  const randomId = () => Math.random().toString(16).slice(2,10);

  // Tema claro/oscuro con persistencia en localStorage
  const root = document.documentElement;
  const storedTheme = window.localStorage ? localStorage.getItem("theme") : "";
  const prefersDark =
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
  const initialTheme = storedTheme || (prefersDark ? "dark" : "light");
  root.dataset.theme = initialTheme;

  const themeButtons = Array.from(
    document.querySelectorAll("[data-theme-toggle]"),
  );
  const updateThemeButtons = () => {
    const isDark = root.dataset.theme === "dark";
    themeButtons.forEach((button) => {
      const label = isDark ? "Cambiar a modo claro" : "Cambiar a modo nocturno";
      button.setAttribute("aria-pressed", isDark ? "true" : "false");
      button.setAttribute("aria-label", label);
      button.setAttribute("title", label);
    });
  };
  updateThemeButtons();

  themeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
      root.dataset.theme = nextTheme;
      if (window.localStorage) {
        localStorage.setItem("theme", nextTheme);
      }
      updateThemeButtons();
    });
  });

  const addHandlers = [
    {
      button: "[data-add='experience']",
      list: "#experience-list",
      tpl: "#tpl-experience",
    },
    {
      button: "[data-add='education']",
      list: "#education-list",
      tpl: "#tpl-education",
    },
    { button: "[data-add='skills']", list: "#skills-list", tpl: "#tpl-skills" },
      ];

  // Helpers para la lista de "hitos" en experiencia
  const highlightRow = (value = "") => {
    const row = document.createElement("div");
    row.className = "highlight-row";

    const input = document.createElement("input");
    input.type = "text";
    input.className = "highlight-input";
    input.value = value;

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "ghost small";
    remove.dataset.removeHighlight = ""; // -> data-remove-highlight
    remove.textContent = "Eliminar";

    row.appendChild(input);
    row.appendChild(remove);
    return row;
  };

  const ensureHighlightRows = (block) => {
    const list = block.querySelector(".highlight-list");
    if (!list) return;
    if (list.children.length === 0) {
      list.appendChild(highlightRow());
    }
  };

  // Fechas: guardamos YYYY o YYYY-MM en un input hidden
  const parseDateValue = (value) => {
    const normalized = value.trim();
    if (!normalized) return { year: "", month: "", current: false };
    if (/^(actualidad|presente|current|present|hoy)$/i.test(normalized)) {
      return { year: "", month: "", current: true };
    }
    const match = normalized.match(/^(\d{4})(?:-(\d{2}))?$/);
    if (match) return { year: match[1], month: match[2] || "", current: false };
    return { year: "", month: "", current: false };
  };

  const syncDateField = (block) => {
    const hidden = block.querySelector("input[type='hidden']");
    const monthSelect = block.querySelector("[data-month-select]");
    const yearSelect = block.querySelector("[data-year-select]");
    if (!hidden || !monthSelect || !yearSelect) return;

    const forceCurrent = block.dataset.forceCurrent === "1";
    if (forceCurrent) {
      hidden.value = "Actualidad";
      monthSelect.disabled = true;
      yearSelect.disabled = true;
      return;
    }

    monthSelect.disabled = false;
    yearSelect.disabled = false;

    const year = yearSelect.value || "";
    const month = monthSelect.value || "";
    hidden.value = year ? (month ? `${year}-${month}` : year) : "";
  };

  const initDateField = (block) => {
    if (!block || block.dataset.dateInit === "1") return;
    block.dataset.dateInit = "1";

    const hidden = block.querySelector("input[type='hidden']");
    const monthSelect = block.querySelector("[data-month-select]");
    const yearSelect = block.querySelector("[data-year-select]");
    if (!hidden || !monthSelect || !yearSelect) return;

    const { year, month, current } = parseDateValue(hidden.value || "");
    yearSelect.value = year || "";
    monthSelect.value = month || "";
    if (current) block.dataset.forceCurrent = "1";
    syncDateField(block);

    yearSelect.addEventListener("change", () => syncDateField(block));
    monthSelect.addEventListener("change", () => syncDateField(block));
  };

  const initCurrentToggle = (repeat) => {
    const toggle = repeat.querySelector("[data-role-current]");
    const endField = repeat.querySelector("[data-date-field][data-date-end]");
    if (!toggle || !endField) return;

    const hidden = endField.querySelector("input[type='hidden']");
    const yearSelect = endField.querySelector("[data-year-select]");
    const monthSelect = endField.querySelector("[data-month-select]");

    const apply = () => {
      const wasForcedCurrent = endField.dataset.forceCurrent === "1";
      if (toggle.checked) {
        // Guardar fecha previa solo al entrar por primera vez en "Actualidad".
        // Evita que handlers duplicados pisen prevYear/prevMonth con vacío.
        if (!wasForcedCurrent) {
          if (yearSelect) {
            endField.dataset.prevYear = yearSelect.value;
          }
          if (monthSelect) {
            endField.dataset.prevMonth = monthSelect.value;
          }
        }
        if (yearSelect) yearSelect.value = "";
        if (monthSelect) monthSelect.value = "";
        endField.dataset.forceCurrent = "1";
      } else {
        delete endField.dataset.forceCurrent;
        if (yearSelect && endField.dataset.prevYear !== undefined) {
          yearSelect.value = endField.dataset.prevYear;
        }
        if (monthSelect && endField.dataset.prevMonth !== undefined) {
          monthSelect.value = endField.dataset.prevMonth;
        }
      }
      syncDateField(endField);
    };

    if (
      hidden &&
      /^(actualidad|presente|current|present|hoy)$/i.test(hidden.value || "")
    ) {
      toggle.checked = true;
      endField.dataset.forceCurrent = "1";
    }

    toggle.addEventListener("change", apply);
    apply();
  };

  const initDateFields = (rootEl = document) => {
    rootEl
      .querySelectorAll("[data-date-field]")
      .forEach((block) => initDateField(block));
    rootEl
      .querySelectorAll(".repeat")
      .forEach((repeat) => initCurrentToggle(repeat));
  };

  // -------------------------------
  // NUEVO: modo por ENTRADA (entry)
  // -------------------------------
  const syncExtraEntryMode = (entry) => {
    // Modo por entrada (legacy) o por sección (actual).
    let mode = null;

    const select = entry.querySelector("[data-extra-entry-mode]");
    if (select) {
      mode = select.value || "subtitle_items";
      if (mode === "subtitles" || mode === "items") mode = "subtitle_items";
    } else {
      const section = entry.closest("[data-extra-section]");
      const secSelect = section ? section.querySelector("[data-extra-mode]") : null;
      mode = (secSelect && secSelect.value) ? secSelect.value : "subtitle_items";
    }

    entry.dataset.extraEntryMode = mode;

    entry.querySelectorAll("[data-extra-entry-show]").forEach((field) => {
      const allowed = (field.dataset.extraEntryShow || "").split(" ").filter(Boolean);
      const isHidden = allowed.length > 0 && !allowed.includes(mode);
      field.style.display = isHidden ? "none" : "";
    });
  };

  const initExtraEntry = (entry, sectionId) => {
    if (!entry) return;

    // Asegura que la entrada apunte a la sección sin borrar ids ya existentes
    const entrySectionInput = entry.querySelector(
      "input[name='extra_entry_section']",
    );
    if (entrySectionInput) {
      let resolvedSectionId = (sectionId || "").trim();
      if (!resolvedSectionId) {
        const sectionEl = entry.closest("[data-extra-section]");
        const sectionIdInput = sectionEl
          ? sectionEl.querySelector("input[name='extra_section_id']")
          : null;
        resolvedSectionId = (sectionIdInput && sectionIdInput.value
          ? sectionIdInput.value
          : entrySectionInput.value || "").trim();
      }
      if (resolvedSectionId) entrySectionInput.value = resolvedSectionId;
    }

    // Bind de cambio de modo por entrada
    const modeSelect = entry.querySelector("[data-extra-entry-mode]");
    if (modeSelect && modeSelect.dataset.bound !== "1") {
      modeSelect.dataset.bound = "1";
      modeSelect.addEventListener("change", () => syncExtraEntryMode(entry));
    }

    syncExtraEntryMode(entry);
    initDateFields(entry);
  };

  const initExtraSection = (section) => {
    // `section` es el root [data-extra-section]
    const moduleBlock = section.closest(".module-block") || section;

    // Si viene sin section_id (nuevo), lo generamos
    const idInput = section.querySelector('input[name="extra_section_id"]');
    if (idInput && !idInput.value) {
      idInput.value = `extra-${randomId()}`;
    }

    // El módulo usa el mismo id para el orden
    const sectionId = idInput ? idInput.value : `extra-${randomId()}`;
    if (moduleBlock.classList.contains("module-block")) {
      moduleBlock.dataset.moduleKey = sectionId;
    }

    // Mantener el tipo de módulo actualizado
    const modeSelect = section.querySelector('[data-extra-mode]');
    if (modeSelect && moduleBlock.classList.contains("module-block")) {
      moduleBlock.dataset.moduleType = modeSelect.value || "detailed";
      modeSelect.addEventListener("change", () => {
        moduleBlock.dataset.moduleType = modeSelect.value || "detailed";
      });
    }

    // Título: reflejarlo en el header del módulo (pill + nombre)
    const titleInput = section.querySelector('[data-extra-title]');
    const titleLabel = moduleBlock.querySelector('[data-module-name]');
    const syncTitle = () => {
      const t = (titleInput?.value || "").trim();
      if (titleLabel) titleLabel.textContent = t || "(sin título)";
    };
    if (titleInput) {
      titleInput.addEventListener("input", syncTitle);
      syncTitle();
    }

    // Eliminar: debe eliminar el módulo completo (no solo el contenido)
    const removeBtn = (moduleBlock || section).querySelector('[data-action="remove-extra-section"]');
    if (removeBtn) {
      removeBtn.addEventListener("click", () => {
        (moduleBlock.classList.contains("module-block") ? moduleBlock : section).remove();
        // actualizar orden interno
        if (window.__trufadocs_reorder) window.__trufadocs_reorder.sync();
      });
    }

    // Inicializar entradas (detalle / sub+items)
    const entriesRoot = section.querySelector("[data-extra-entries]");
    if (entriesRoot) {
      const items = Array.from(entriesRoot.querySelectorAll("[data-extra-entry]"));
      items.forEach((entry) => initExtraEntry(entry, sectionId));
    }
    applyExtraMode(section);

    const addEntryBtn = section.querySelector('[data-action="add-extra-entry"]');
    if (addEntryBtn) {
      addEntryBtn.addEventListener("click", () => {
        const tpl = qs('#tpl-extra-entry');
        if (!tpl || !entriesRoot) return;
        const node = tpl.content.firstElementChild.cloneNode(true);
        entriesRoot.appendChild(node);
        initExtraEntry(node, sectionId);
        applyExtraMode(section);
      });
    }
  };

  const initExtraSections = (rootEl = document) => {
    rootEl
      .querySelectorAll("[data-extra-section]")
      .forEach((section) => initExtraSection(section));
  };

  // --------------------
// Agregar repeats (Experience / Education / Skills)
// - Si existe <template>, lo usa.
// - Si NO existe, clona el último .repeat existente y limpia inputs.
// --------------------
const clearInputs = (rootEl) => {
  qsa("input, textarea, select", rootEl).forEach((el) => {
    const tag = el.tagName.toLowerCase();
    if (tag === "select") {
      // Reset a placeholder option if present
      if (el.querySelector('option[value=""]')) el.value = "";
      else el.selectedIndex = 0;
      return;
    }
    if (el.type === "checkbox" || el.type === "radio") {
      el.checked = false;
      return;
    }
    if (el.type === "hidden") {
      // Mantener hidden si es necesario; por defecto limpiamos fechas y ids
      const n = (el.getAttribute("name") || "").toLowerCase();
      if (n.endsWith("_start") || n.endsWith("_end") || n.includes("id")) el.value = "";
      return;
    }
    el.value = "";
  });
};

const cloneRepeatFallback = (listEl) => {
  const last = listEl.querySelector(".repeat:last-child") || listEl.querySelector(".repeat");
  if (!last) return null;
  const clone = last.cloneNode(true);

  // Quitar filas dinámicas de hitos y reconstruirlas desde cero
  qsa(".highlight-row", clone).forEach((r) => r.remove());
  // Limpiar errores/estados
  qsa("[data-reorder-init]", clone).forEach((n) => n.removeAttribute("data-reorder-init"));

  clearInputs(clone);
  return clone;
};

addHandlers.forEach(({ button, list, tpl }) => {
  const addButton = document.querySelector(button);
  const listEl = document.querySelector(list);
  const template = document.querySelector(tpl);

  if (!addButton || !listEl) return;

  addButton.addEventListener("click", () => {
    if (template && template.content) {
      const clone = template.content.cloneNode(true);
      listEl.appendChild(clone);
    } else {
      const clone = cloneRepeatFallback(listEl);
      if (!clone) return;
      listEl.appendChild(clone);
    }

    // Re-hidratar comportamientos internos
    listEl
      .querySelectorAll("[data-highlight-block]")
      .forEach((block) => ensureHighlightRows(block));
    initDateFields(listEl);
  });
});
  document
    .querySelectorAll("[data-highlight-block]")
    .forEach((block) => ensureHighlightRows(block));
  initDateFields();
  initExtraSections();

  // Cierra el dialogo de ayuda al hacer click fuera o con Escape
  const helpDialog = document.querySelector(".help");
  if (helpDialog) {
    const closeHelpIfOutside = (event) => {
      if (!helpDialog.open) return;
      const target = event.target;
      if (target instanceof Node && helpDialog.contains(target)) return;
      helpDialog.open = false;
    };
    document.addEventListener("pointerdown", closeHelpIfOutside, true);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") helpDialog.open = false;
    });
  }

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    if (target.matches("[data-add-highlight]")) {
      const block = target.closest("[data-highlight-block]");
      if (!block) return;
      const list = block.querySelector(".highlight-list");
      if (!list) return;
      list.appendChild(highlightRow());
      return;
    }

    if (target.matches("[data-remove-highlight]")) {
      const row = target.closest(".highlight-row");
      if (!row || !row.parentElement) return;
      const list = row.parentElement;
      list.removeChild(row);
      return;
    }

    if (target.matches("[data-remove]")) {
      const repeat = target.closest(".repeat");
      if (repeat && repeat.parentElement) {
        repeat.parentElement.removeChild(repeat);
      }
    }
  });

  // Fallback delegado: asegura que "Actualidad" funcione también en entradas extra
  // aunque la inicialización del repeat haya fallado por cambios dinámicos de modo.
  document.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (!target.matches("[data-role-current]")) return;

    const endField =
      target.closest("[data-date-field][data-date-end]") ||
      target.closest(".repeat")?.querySelector("[data-date-field][data-date-end]");
    if (!endField) return;

    const yearSelect = endField.querySelector("[data-year-select]");
    const monthSelect = endField.querySelector("[data-month-select]");
    const hidden = endField.querySelector("input[type='hidden']");
    const wasForcedCurrent = endField.dataset.forceCurrent === "1";

    if (target.checked) {
      // Igual que en initCurrentToggle: no sobreescribir fecha previa
      // cuando este handler delegado corre después del handler principal.
      if (!wasForcedCurrent) {
        if (yearSelect) endField.dataset.prevYear = yearSelect.value;
        if (monthSelect) endField.dataset.prevMonth = monthSelect.value;
      }
      if (yearSelect) yearSelect.value = "";
      if (monthSelect) monthSelect.value = "";
      endField.dataset.forceCurrent = "1";
      if (hidden) hidden.value = "Actualidad";
    } else {
      delete endField.dataset.forceCurrent;
      if (yearSelect && endField.dataset.prevYear !== undefined) {
        yearSelect.value = endField.dataset.prevYear;
      }
      if (monthSelect && endField.dataset.prevMonth !== undefined) {
        monthSelect.value = endField.dataset.prevMonth;
      }
      if (hidden && /^(actualidad|presente|current|present|hoy)$/i.test(hidden.value || ""))
        hidden.value = "";
    }

    syncDateField(endField);
  });

  const form = document.querySelector("#structured-form");
  if (form) {
    form.addEventListener("submit", () => {
      // Convierte filas de hitos a texto con saltos de linea
      form.querySelectorAll("[data-highlight-block]").forEach((block) => {
        const textarea = block.querySelector(".highlight-textarea");
        if (!textarea) return;
        const values = Array.from(block.querySelectorAll(".highlight-input"))
          .map((input) => input.value.trim())
          .filter(Boolean);
        textarea.value = values.join("\n");
      });

      form.querySelectorAll("[data-date-field]").forEach((block) => {
        syncDateField(block);
      });
    });
  }


// --- Add extra module (always before the add-module block) ---
(function initAddExtraModule(){
  document.addEventListener("click", (e) => {
    const btn = e.target && e.target.closest ? e.target.closest('[data-action="add-extra-module"]') : null;
    if (!btn) return;
    const container = qs("#modules-list") || qs("[data-modules]");
    if (!container) return;

    const addBlock = container.querySelector("[data-add-module]");
    const tpl = qs("#tpl-extra-module");
    if (!tpl) return;

    const node = tpl.content.firstElementChild.cloneNode(true);

    // IDs / keys
    const sid = `extra-${randomId()}`;
    node.dataset.moduleKey = sid;
    const hiddenId = node.querySelector('input[name="extra_section_id"]');
    if (hiddenId) hiddenId.value = sid;

    // Default: S.I. con una categoría inicial (skills-like)
    const modeSel = node.querySelector('[data-extra-mode]');
    if (modeSel) modeSel.value = "subtitle_items";

    const entriesRoot = node.querySelector('[data-extra-entries]');
    const entryTpl = qs('#tpl-extra-entry');
    if (entriesRoot && entryTpl) {
      const entryNode = entryTpl.content.firstElementChild.cloneNode(true);
      // Setear sección
      const secInput = entryNode.querySelector("input[name='extra_entry_section']");
      if (secInput) secInput.value = sid;
      // Categoría inicial
      const subInput = entryNode.querySelector('input[name="extra_entry_subtitle"]');
      if (subInput) subInput.value = "";
      entriesRoot.appendChild(entryNode);
    }

    // Insertar antes del módulo fijo "Agregar"
    if (addBlock) container.insertBefore(node, addBlock);
    else container.appendChild(node);

    // Inicializar comportamiento extra + modos + fechas + reorder
    initExtraSection(node.querySelector("[data-extra-section]") || node);
    if (window.__trufadocs_reorder) window.__trufadocs_reorder.sync();
  });
})();

})();

// --- Extras: modo por sección (subtitle_items vs detailed) ---
function applyExtraMode(sectionEl) {
  const sel = sectionEl.querySelector('[data-extra-mode]');
  if (!sel) return;
  const mode = sel.value || 'subtitle_items';

  const setEnabled = (containerEl, enabled) => {
    containerEl.querySelectorAll('input, select, textarea, button').forEach((node) => {
      // Nunca deshabilitar botones de "Eliminar entrada" ni el selector de modo
      if (node.matches('[data-remove-extra-entry], [data-extra-mode]')) return;

      // Para botones dentro del bloque, solo deshabilitar los que afectan al modo (add/remove highlights)
      if (node.tagName === 'BUTTON') {
        if (node.matches('[data-add-highlight], [data-remove-highlight]')) {
          node.disabled = !enabled;
        }
        return;
      }

      if (!enabled) {
        node.disabled = true;
        return;
      }

      // Respeta "Actualidad" en fecha fin: no volver a habilitar año/mes/check al aplicar modo.
      if (node.matches('[data-year-select], [data-month-select]')) {
        const dateField = node.closest('[data-date-field]');
        if (dateField && dateField.hasAttribute('data-date-end') && dateField.dataset.forceCurrent === '1') {
          node.disabled = true;
          return;
        }
      }
      node.disabled = false;
    });
  };

  sectionEl.querySelectorAll('[data-extra-entry]').forEach((entryEl) => {
    entryEl.querySelectorAll('[data-extra-entry-show]').forEach((el) => {
      const show = (el.getAttribute('data-extra-entry-show') || '')
        .split(/\s+/)
        .filter(Boolean);
      const visible = show.includes(mode);
      el.style.display = visible ? '' : 'none';
      setEnabled(el, visible);
    });
  });
}


document.addEventListener('change', (e) => {
  const t = e.target;
  if (t && t.matches && t.matches('[data-extra-mode]')) {
    const sectionEl = t.closest('[data-extra-section]');
    if (sectionEl) applyExtraMode(sectionEl);
  }
});

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-extra-section]').forEach(applyExtraMode);
});


// --- Core modules reorder (Experience / Education / Skills / Extras) ---
(function initCoreModuleReorder() {
  // Reordenamiento (flechas) + orden interno (core_order) para módulos movibles.
  // Movibles: experience, education, skills, extra:* (NO incluye Datos ni el módulo "Agregar módulo extra")
  const query = (sel, root = document) => root.querySelector(sel);
  const container = query("#modules-list") || query("[data-modules]") || document.body;
  const orderInput = query('#structured-form input[name="core_order"]') || query("#core-order");
  const orderMapInput = query('#structured-form input[name="module_order_map"]') || query("#module-order-map");

  const isMovable = (el) =>
    el &&
    el.classList &&
    el.classList.contains("module-block") &&
    !!el.dataset.moduleKey &&
    !el.classList.contains("module-fixed") &&
    !el.classList.contains("module-add");

  const getBlocks = () =>
    Array.from(container.querySelectorAll(".module-block[data-module-key]")).filter(isMovable);

  const syncInternalModuleOrder = () => {
    const blocks = getBlocks();
    blocks.forEach((block, idx) => {
      block.dataset.moduleOrder = String(idx + 1);
    });
    if (!orderMapInput) return;
    orderMapInput.value = blocks
      .map((block, idx) => `${block.dataset.moduleKey}:${idx + 1}`)
      .join(",");
  };

  const applyOrderFromHiddenInput = () => {
    if (!orderInput) return;
    const requested = (orderInput.value || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (!requested.length) return;

    const blocks = getBlocks();
    const byKey = new Map(blocks.map((block) => [block.dataset.moduleKey, block]));
    const used = new Set();
    const ordered = [];

    requested.forEach((key) => {
      const block = byKey.get(key);
      if (!block || used.has(key)) return;
      used.add(key);
      ordered.push(block);
    });

    blocks.forEach((block) => {
      const key = block.dataset.moduleKey;
      if (used.has(key)) return;
      used.add(key);
      ordered.push(block);
    });

    const addBlock = container.querySelector("[data-add-module]");
    ordered.forEach((block) => {
      if (addBlock) container.insertBefore(block, addBlock);
      else container.appendChild(block);
    });
  };

  const syncOrderToHiddenInput = () => {
    if (!orderInput) return;
    const order = getBlocks().map((b) => b.dataset.moduleKey).filter(Boolean);
    orderInput.value = order.join(",");
  };

  const updateMoveButtonsState = () => {
    const blocks = getBlocks();
    blocks.forEach((b, idx) => {
      const up = b.querySelector('[data-move="up"]');
      const down = b.querySelector('[data-move="down"]');
      if (up) up.disabled = idx === 0;
      if (down) down.disabled = idx === blocks.length - 1;
    });
  };

  const REORDER_ANIM_MS = 340;
  const FOLLOW_SCROLL_MS = 560;
  let followScrollRaf = 0;

  const easeInOutCubic = (t) =>
    t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

  const smoothScrollWindowTo = (targetY, durationMs = FOLLOW_SCROLL_MS) => {
    const clampedTarget = Math.max(0, targetY);
    const startY = window.scrollY || window.pageYOffset || 0;
    const distance = clampedTarget - startY;
    if (Math.abs(distance) < 1) return;

    const prefersReduced =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) {
      window.scrollTo(0, clampedTarget);
      return;
    }

    if (followScrollRaf) {
      window.cancelAnimationFrame(followScrollRaf);
      followScrollRaf = 0;
    }

    const startTs = performance.now();
    const step = (ts) => {
      const progress = Math.min(1, (ts - startTs) / durationMs);
      const eased = easeInOutCubic(progress);
      window.scrollTo(0, startY + distance * eased);
      if (progress < 1) {
        followScrollRaf = window.requestAnimationFrame(step);
      } else {
        followScrollRaf = 0;
      }
    };
    followScrollRaf = window.requestAnimationFrame(step);
  };

  const snapshotBlockPositions = () => {
    const map = new Map();
    getBlocks().forEach((el) => map.set(el, el.getBoundingClientRect()));
    return map;
  };

  const animateReorder = (beforePositions) => {
    if (!beforePositions || !beforePositions.size) return;
    getBlocks().forEach((el) => {
      const before = beforePositions.get(el);
      if (!before) return;
      const after = el.getBoundingClientRect();
      const deltaY = before.top - after.top;
      if (Math.abs(deltaY) < 1) return;

      el.style.transition = "none";
      el.style.transform = `translateY(${deltaY}px)`;
      el.classList.add("module-reorder-active");
      void el.offsetHeight;
      el.style.transition = `transform ${REORDER_ANIM_MS}ms cubic-bezier(0.22, 0.61, 0.36, 1)`;
      el.style.transform = "";

      const cleanup = () => {
        el.style.transition = "";
        el.classList.remove("module-reorder-active");
      };
      el.addEventListener("transitionend", cleanup, { once: true });
      window.setTimeout(cleanup, REORDER_ANIM_MS + 40);
    });
  };

  const followMovedBlock = (block) => {
    if (!block) return;
    const rect = block.getBoundingClientRect();
    const vh = window.innerHeight || document.documentElement.clientHeight;
    const targetViewportTop = vh * 0.24;
    const delta = rect.top - targetViewportTop;
    // Umbral pequeño para evitar micro-ajustes en cada click.
    if (Math.abs(delta) < 32) return;

    const targetTop = window.scrollY + delta;
    smoothScrollWindowTo(targetTop, FOLLOW_SCROLL_MS);
  };

  const moveBlock = (block, dir) => {
    const beforePositions = snapshotBlockPositions();
    const blocks = getBlocks();
    const idx = blocks.indexOf(block);
    if (idx < 0) return;

    if (dir === "up") {
      if (idx === 0) return;
      const prev = blocks[idx - 1];
      container.insertBefore(block, prev);
    } else if (dir === "down") {
      if (idx >= blocks.length - 1) return;
      const next = blocks[idx + 1];
      const nextNext = next.nextElementSibling;
      if (nextNext) container.insertBefore(block, nextNext);
      else container.appendChild(block);
    }

    syncOrderToHiddenInput();
    syncInternalModuleOrder();
    updateMoveButtonsState();
    followMovedBlock(block);
    animateReorder(beforePositions);
  };

  // Delegación (sirve también para módulos agregados dinámicamente)
  container.addEventListener("click", (ev) => {
    const btn = ev.target && ev.target.closest ? ev.target.closest("[data-move]") : null;
    if (!btn) return;

    const dir = btn.getAttribute("data-move");
    const block = btn.closest(".module-block[data-module-key]");
    if (!block || !isMovable(block)) return;

    ev.preventDefault();
    moveBlock(block, dir);
  });

  // API para que otros flujos puedan sincronizar orden/botones tras cambios
  window.__trufadocs_reorder = {
    sync: () => {
      syncOrderToHiddenInput();
      syncInternalModuleOrder();
      updateMoveButtonsState();
    },
  };

  applyOrderFromHiddenInput();
  window.__trufadocs_reorder.sync();
})();;
// --- End core modules reorder
