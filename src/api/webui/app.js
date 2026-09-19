const state = {
  sessionToken: localStorage.getItem("privatedock_admin_session") || "",
  csrfToken: sessionStorage.getItem("privatedock_admin_csrf") || "",
  authDisabled: false,
  authMode: "login",
  selectedPlayer: null,
  category: "item",
  catalogItems: [],
  attachments: new Map(),
};

const dom = {
  toast: document.getElementById("toast"),
  authView: document.getElementById("auth-view"),
  appView: document.getElementById("app-view"),
  authTitle: document.getElementById("auth-title"),
  authSubtitle: document.getElementById("auth-subtitle"),
  authForm: document.getElementById("auth-form"),
  authUsername: document.getElementById("auth-username"),
  authPassword: document.getElementById("auth-password"),
  authSubmit: document.getElementById("auth-submit"),
  authError: document.getElementById("auth-error"),
  sessionUser: document.getElementById("session-user"),
  logoutButton: document.getElementById("logout-button"),
  playerSearch: document.getElementById("player-search"),
  playerResults: document.getElementById("player-results"),
  selectedPlayer: document.getElementById("selected-player"),
  mailTitle: document.getElementById("mail-title"),
  mailSender: document.getElementById("mail-sender"),
  mailBody: document.getElementById("mail-body"),
  catalogTabs: document.getElementById("catalog-tabs"),
  catalogSearchWrap: document.getElementById("catalog-search-wrap"),
  catalogSearch: document.getElementById("catalog-search"),
  manualEntry: document.getElementById("manual-entry"),
  manualType: document.getElementById("manual-type"),
  manualId: document.getElementById("manual-id"),
  manualAdd: document.getElementById("manual-add"),
  catalogResults: document.getElementById("catalog-results"),
  attachmentList: document.getElementById("attachment-list"),
  attachmentEmpty: document.getElementById("attachment-empty"),
  attachmentCount: document.getElementById("attachment-count"),
  sendSummary: document.getElementById("send-summary"),
  sendButton: document.getElementById("send-button"),
};

const resourceNames = {
  1: "金币",
  2: "石油",
  3: "功勋",
  4: "钻石",
  6: "家具币",
  8: "舰队币",
  11: "游戏币",
  12: "游戏券",
  14: "免费钻石",
  15: "声音故事卡",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showToast(message, isError = false) {
  dom.toast.textContent = message;
  dom.toast.classList.toggle("error", isError);
  dom.toast.classList.add("visible");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => dom.toast.classList.remove("visible"), 2800);
}

function authHeaders(write = false) {
  const headers = {};
  if (state.sessionToken) headers.Authorization = `Bearer ${state.sessionToken}`;
  if (write && state.csrfToken) headers["X-CSRF-Token"] = state.csrfToken;
  return headers;
}

async function request(path, options = {}, handleAuth = true) {
  const method = options.method || "GET";
  const headers = { Accept: "application/json", ...authHeaders(method !== "GET"), ...(options.headers || {}) };
  if (options.body !== undefined && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, { ...options, headers });
  let payload = null;
  try {
    payload = await response.json();
  } catch (_error) {
    payload = null;
  }
  const body = payload && typeof payload === "object" && "ok" in payload ? payload : { ok: false, error: { message: `HTTP ${response.status}` } };
  if (!response.ok || !body.ok) {
    const code = body.error?.code || "";
    if (handleAuth && (response.status === 401 || code === "auth.session_missing")) {
      clearSession();
      await showAuth();
    }
    const error = new Error(body.error?.message || `HTTP ${response.status}`);
    error.status = response.status;
    error.code = code;
    throw error;
  }
  return body.data;
}

function clearSession() {
  state.sessionToken = "";
  state.csrfToken = "";
  localStorage.removeItem("privatedock_admin_session");
  sessionStorage.removeItem("privatedock_admin_csrf");
}

function saveSession(sessionId, csrfToken) {
  state.sessionToken = sessionId || "";
  state.csrfToken = csrfToken || "";
  if (state.sessionToken) localStorage.setItem("privatedock_admin_session", state.sessionToken);
  if (state.csrfToken) sessionStorage.setItem("privatedock_admin_csrf", state.csrfToken);
}

function setAuthMode(mode) {
  state.authMode = mode;
  const setup = mode === "setup";
  dom.authTitle.textContent = setup ? "初始化管理员" : "管理员登录";
  dom.authSubtitle.textContent = setup
    ? "当前没有管理员账号，创建首个管理账号后即可使用。"
    : "使用管理账号进入邮件发放控制台。";
  dom.authSubmit.textContent = setup ? "创建并进入" : "登录";
  dom.authPassword.autocomplete = setup ? "new-password" : "current-password";
  dom.authPassword.value = "";
  dom.authError.hidden = true;
  dom.authUsername.focus();
}

async function showAuth() {
  dom.appView.hidden = true;
  dom.authView.hidden = false;
  try {
    const status = await request("/api/v1/auth/bootstrap/status", {}, false);
    setAuthMode(status.can_bootstrap ? "setup" : "login");
  } catch (error) {
    setAuthMode("login");
    dom.authError.textContent = error.message;
    dom.authError.hidden = false;
  }
}

async function showApp(data) {
  state.authDisabled = Boolean(data?.auth_disabled);
  dom.authView.hidden = true;
  dom.appView.hidden = false;
  dom.sessionUser.textContent = state.authDisabled ? "API 未启用登录" : `${data?.user?.username || "admin"} · Administrator`;
  dom.logoutButton.hidden = state.authDisabled;
  dom.playerSearch.focus();
}

async function initialiseAuth() {
  try {
    const data = await request("/api/v1/auth/session", {}, false);
    await showApp(data);
  } catch (_error) {
    clearSession();
    await showAuth();
  }
}

dom.authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  dom.authError.hidden = true;
  const endpoint = state.authMode === "setup" ? "/api/v1/auth/bootstrap" : "/api/v1/auth/login";
  try {
    const data = await request(endpoint, {
      method: "POST",
      body: JSON.stringify({
        username: dom.authUsername.value.trim(),
        password: dom.authPassword.value,
      }),
    }, false);
    saveSession(data.session?.id, data.csrf_token);
    await showApp(data);
  } catch (error) {
    dom.authError.textContent = error.message;
    dom.authError.hidden = false;
  }
});

dom.logoutButton.addEventListener("click", async () => {
  try {
    await request("/api/v1/auth/logout", { method: "POST" });
  } catch (_error) {
    // The local session is cleared even if the server session already expired.
  }
  clearSession();
  await showAuth();
});

function renderSelectedPlayer() {
  if (!state.selectedPlayer) {
    dom.selectedPlayer.hidden = true;
    updateSendState();
    return;
  }
  const player = state.selectedPlayer;
  dom.selectedPlayer.textContent = `${player.name || "未命名"} · UID ${player.commander_id}`;
  dom.selectedPlayer.hidden = false;
  updateSendState();
}

function selectPlayer(player) {
  state.selectedPlayer = player;
  dom.playerSearch.value = `${player.name || ""} (${player.commander_id})`.trim();
  dom.playerResults.hidden = true;
  renderSelectedPlayer();
}

let playerSearchTimer = null;
dom.playerSearch.addEventListener("input", () => {
  clearTimeout(playerSearchTimer);
  state.selectedPlayer = null;
  renderSelectedPlayer();
  const query = dom.playerSearch.value.trim();
  if (!query) {
    dom.playerResults.hidden = true;
    return;
  }
  playerSearchTimer = setTimeout(async () => {
    try {
      const data = await request(`/api/v1/mail-admin/players/search?q=${encodeURIComponent(query)}&limit=12`);
      if (!data.players.length) {
        dom.playerResults.innerHTML = '<p class="empty-state">没有匹配的指挥官。</p>';
        dom.playerResults.hidden = false;
        return;
      }
      dom.playerResults.innerHTML = data.players.map((player) => `
        <button type="button" data-player-id="${player.commander_id}">
          <span class="player-avatar">${escapeHtml((player.name || "?").slice(0, 1).toUpperCase())}</span>
          <span class="result-title">
            <strong>${escapeHtml(player.name || "未命名")}</strong>
            <small>UID ${player.commander_id} · Lv.${player.level} · 账号 ${player.account_id}</small>
          </span>
          <span class="muted">选择</span>
        </button>
      `).join("");
      dom.playerResults.hidden = false;
    } catch (error) {
      showToast(error.message, true);
    }
  }, 240);
});

dom.playerResults.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-player-id]");
  if (!button) return;
  const playerId = Number(button.dataset.playerId);
  const text = button.querySelector("strong")?.textContent || "";
  selectPlayer({ commander_id: playerId, name: text, level: 0, account_id: 0 });
  dom.playerSearch.value = `${text} (${playerId})`;
  renderSelectedPlayer();
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".search-wrap")) dom.playerResults.hidden = true;
});

function rarityClass(rarity) {
  const value = Math.max(0, Math.min(Number(rarity) || 0, 6));
  return `rarity-${value}`;
}

const resourceIconIds = {
  1: "coin",
  2: "oil",
  3: "medal",
  4: "gem",
  6: "furniture",
  8: "flag",
  11: "gamecoin",
  12: "ticket",
  14: "gem",
  15: "music",
};

function itemIconId(item) {
  const attachmentType = Number(item.attachment_type) || 0;
  if (attachmentType === 1) return resourceIconIds[Number(item.item_id)] || "coin";
  if (attachmentType === 3) return "equipment";
  if (attachmentType === 4) return "ship";
  if (attachmentType === 5) return "furniture";
  if (attachmentType === 7) return "skin";
  if (attachmentType === 9) return "cube";
  if (attachmentType === 17) return "cube";

  const icon = String(item.icon || "").toLowerCase();
  if (icon.startsWith("equips/")) return "equipment";
  if (icon.startsWith("chargeicon/")) return "gift";
  if (icon.includes("blueprint")) return "blueprint";

  const itemType = Number(item.item_type) || 0;
  if (itemType === 9) return "blueprint";
  if (itemType === 15 || itemType === 16) return "quick";
  if (itemType === 17) return "gift";
  if (itemType === 98 || itemType === 99) return "cube";
  if (Number(item.virtual_type) || 0) return "cube";
  return "box";
}

function attachmentTypeLabel(item) {
  const attachmentType = Number(item.attachment_type) || 0;
  return {
    1: "资源",
    2: "物品",
    3: "装备",
    4: "舰船",
    5: "家具",
    6: "策略",
    7: "皮肤",
    8: "虚拟物品",
    9: "装备外观",
    14: "头像框",
    15: "聊天气泡",
  }[attachmentType] || `附件 ${attachmentType}`;
}

function renderItemIcon(item, extraClass = "") {
  const iconId = itemIconId(item);
  return `<span class="item-art ${rarityClass(item.rarity)} ${extraClass}" title="${escapeHtml(catalogName(item))}"><svg class="item-symbol" aria-hidden="true"><use href="/admin/icons.svg#icon-${iconId}"></use></svg></span>`;
}

function catalogName(item) {
  if (item.attachment_type === 1) return resourceNames[item.item_id] || item.name || `资源 ${item.item_id}`;
  return item.name || `ID ${item.item_id}`;
}

function renderCatalog() {
  if (!state.catalogItems.length) {
    dom.catalogResults.innerHTML = '<p class="empty-state">没有匹配结果。</p>';
    return;
  }
  dom.catalogResults.innerHTML = state.catalogItems.map((item, index) => `
    <button class="catalog-item" type="button" data-index="${index}">
      ${renderItemIcon(item)}
      <span class="catalog-copy">
        <strong>${escapeHtml(catalogName(item))}</strong>
        <small>${attachmentTypeLabel(item)} · ID ${item.item_id}</small>
      </span>
      <span class="add-mark">+</span>
    </button>
  `).join("");
}

let catalogSearchTimer = null;
async function performCatalogSearch() {
  const query = dom.catalogSearch.value.trim();
  if (!query) {
    state.catalogItems = [];
    dom.catalogResults.innerHTML = '<p class="empty-state">输入名称或 ID 开始搜索。</p>';
    return;
  }
  try {
    const data = await request(`/api/v1/mail-admin/catalog?category=${encodeURIComponent(state.category)}&q=${encodeURIComponent(query)}&limit=50`);
    state.catalogItems = data.items;
    renderCatalog();
  } catch (error) {
    showToast(error.message, true);
  }
}

dom.catalogSearch.addEventListener("input", () => {
  clearTimeout(catalogSearchTimer);
  catalogSearchTimer = setTimeout(performCatalogSearch, 220);
});

dom.catalogTabs.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-category]");
  if (!button) return;
  state.category = button.dataset.category;
  for (const tab of dom.catalogTabs.querySelectorAll("button")) tab.classList.toggle("active", tab === button);
  const manual = state.category === "manual";
  dom.catalogSearchWrap.hidden = manual;
  dom.manualEntry.hidden = !manual;
  state.catalogItems = [];
  if (manual) {
    dom.catalogResults.innerHTML = '<p class="empty-state">输入附件类型和物品 ID，然后添加到清单。</p>';
  } else {
    dom.catalogResults.innerHTML = '<p class="empty-state">输入名称或 ID 开始搜索。</p>';
  }
});

dom.catalogResults.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-index]");
  if (!button) return;
  addAttachment(state.catalogItems[Number(button.dataset.index)]);
});

dom.manualAdd.addEventListener("click", () => {
  const attachmentType = Number(dom.manualType.value);
  const itemId = Number(dom.manualId.value);
  if (!Number.isInteger(attachmentType) || attachmentType <= 0 || !Number.isInteger(itemId) || itemId <= 0) {
    showToast("请输入有效的附件类型和物品 ID。", true);
    return;
  }
  addAttachment({ attachment_type: attachmentType, item_id: itemId, name: `手动项目 ${itemId}`, rarity: 0 });
});

function addAttachment(item) {
  if (!item) return;
  const key = `${item.attachment_type}:${item.item_id}`;
  const existing = state.attachments.get(key);
  if (existing) {
    existing.quantity += 1;
  } else {
    state.attachments.set(key, { ...item, display_name: catalogName(item), quantity: 1 });
  }
  renderAttachments();
  showToast(`已添加 ${catalogName(item)}`);
}

function renderAttachments() {
  const entries = [...state.attachments.values()];
  dom.attachmentEmpty.hidden = entries.length > 0;
  dom.attachmentCount.textContent = `${entries.length} 项`;
  dom.attachmentList.innerHTML = entries.map((item) => `
    <tr data-key="${item.attachment_type}:${item.item_id}">
      <td>
        <div class="attachment-name">
          ${renderItemIcon(item)}
          <span><strong>${escapeHtml(item.display_name || item.name || item.item_id)}</strong><small>${attachmentTypeLabel(item)} · ID ${item.item_id}</small></span>
        </div>
      </td>
      <td>${attachmentTypeLabel(item)}</td>
      <td><input class="quantity-input" type="number" min="1" max="999999999" value="${item.quantity}" data-quantity></td>
      <td><button class="remove-button" type="button" data-remove>移除</button></td>
    </tr>
  `).join("");
  updateSendState();
}

dom.attachmentList.addEventListener("input", (event) => {
  const input = event.target.closest("input[data-quantity]");
  if (!input) return;
  const row = input.closest("tr");
  const item = state.attachments.get(row.dataset.key);
  if (item) item.quantity = Math.max(1, Number(input.value) || 1);
});

dom.attachmentList.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-remove]");
  if (!button) return;
  state.attachments.delete(button.closest("tr").dataset.key);
  renderAttachments();
});

function updateSendState() {
  const attachmentCount = state.attachments.size;
  const ready = Boolean(state.selectedPlayer && attachmentCount > 0);
  dom.sendButton.disabled = !ready;
  if (!state.selectedPlayer) {
    dom.sendSummary.textContent = "请先选择收件玩家。";
  } else if (!attachmentCount) {
    dom.sendSummary.textContent = "至少添加一项附件。";
  } else {
    dom.sendSummary.textContent = `发送给 ${state.selectedPlayer.name || state.selectedPlayer.commander_id}，共 ${attachmentCount} 项附件。`;
  }
}

dom.sendButton.addEventListener("click", async () => {
  if (!state.selectedPlayer || !state.attachments.size) return;
  const attachments = [...state.attachments.values()].map((item) => ({
    type: item.attachment_type,
    item_id: item.item_id,
    quantity: item.quantity,
  }));
  dom.sendButton.disabled = true;
  try {
    const data = await request("/api/v1/mail-admin/send", {
      method: "POST",
      body: JSON.stringify({
        commander_id: state.selectedPlayer.commander_id,
        title: dom.mailTitle.value.trim(),
        body: dom.mailBody.value.trim(),
        sender: dom.mailSender.value.trim(),
        attachments,
      }),
    });
    state.attachments.clear();
    renderAttachments();
    showToast(`邮件 #${data.mail_id} 已发送。`);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    updateSendState();
  }
});

initialiseAuth();
