from __future__ import annotations


TEST_CLIENT_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GameMaster Test Mode</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7f4;
      --panel: #ffffff;
      --panel-soft: #edf6ef;
      --line: #d8e1da;
      --text: #172018;
      --muted: #637268;
      --green: #1aad19;
      --green-dark: #0d7f12;
      --amber: #a05a00;
      --blue: #2767a8;
      --danger: #b3261e;
      --shadow: 0 10px 26px rgba(23, 32, 24, 0.08);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, "Microsoft YaHei", sans-serif;
      letter-spacing: 0;
    }

    button,
    input,
    select {
      font: inherit;
    }

    button {
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      border-radius: 6px;
      min-height: 34px;
      padding: 0 10px;
      cursor: pointer;
    }

    button.primary {
      border-color: var(--green);
      background: var(--green);
      color: #fff;
    }

    button.icon {
      width: 34px;
      padding: 0;
      font-weight: 700;
    }

    button:disabled {
      cursor: not-allowed;
      opacity: 0.6;
    }

    .app {
      display: grid;
      grid-template-columns: 280px minmax(420px, 1fr);
      min-height: 100vh;
    }

    .sidebar {
      border-right: 1px solid var(--line);
      background: #ffffff;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }

    .brand {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    .brand h1 {
      margin: 0;
      font-size: 20px;
      line-height: 1.2;
    }

    .badge {
      border: 1px solid #b9d7bd;
      background: #effaf1;
      color: var(--green-dark);
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 12px;
      white-space: nowrap;
    }

    .field {
      display: grid;
      gap: 6px;
    }

    .field label {
      color: var(--muted);
      font-size: 12px;
    }

    .field input,
    .field select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      min-height: 34px;
      padding: 6px 8px;
      background: #fff;
    }

    .quick {
      display: grid;
      gap: 8px;
    }

    .quick-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }

    .players {
      display: grid;
      gap: 8px;
      overflow: auto;
      padding-right: 2px;
    }

    .player-row {
      display: grid;
      grid-template-columns: 1fr auto;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px;
      background: #fbfdfb;
    }

    .player-name {
      font-weight: 700;
      overflow-wrap: anywhere;
    }

    .player-id {
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }

    .main {
      display: grid;
      grid-template-rows: auto 1fr;
      min-width: 0;
    }

    .toolbar {
      min-height: 62px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.9);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 16px;
    }

    .toolbar-title {
      min-width: 0;
    }

    .toolbar-title strong {
      display: block;
      font-size: 16px;
    }

    .toolbar-title span {
      color: var(--muted);
      font-size: 12px;
    }

    .command-bank {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
    }

    .workspace {
      display: grid;
      grid-template-columns: minmax(320px, 0.8fr) minmax(520px, 1.2fr);
      gap: 14px;
      padding: 14px;
      min-height: 0;
      overflow: hidden;
    }

    .phone,
    .group {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      min-height: 0;
      box-shadow: var(--shadow);
      display: grid;
      grid-template-rows: auto 1fr auto;
    }

    .group {
      height: calc(100vh - 90px);
    }

    .phone {
      height: 390px;
    }

    .chat-head {
      border-bottom: 1px solid var(--line);
      padding: 10px 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-width: 0;
    }

    .chat-head strong {
      overflow-wrap: anywhere;
    }

    .chat-head small {
      color: var(--muted);
      white-space: nowrap;
    }

    .feed {
      padding: 12px;
      overflow: auto;
      background: #f0f4ef;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .bubble {
      max-width: 88%;
      border-radius: 8px;
      padding: 8px 10px;
      line-height: 1.45;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      border: 1px solid rgba(0, 0, 0, 0.05);
    }

    .bubble .meta {
      display: block;
      color: var(--muted);
      font-size: 11px;
      margin-bottom: 3px;
    }

    .bubble.user {
      align-self: flex-end;
      background: #d9fdd3;
    }

    .bubble.agent {
      align-self: flex-start;
      background: #fff;
    }

    .bubble.system {
      align-self: center;
      max-width: 96%;
      background: #fff8e6;
      color: var(--amber);
    }

    .composer {
      border-top: 1px solid var(--line);
      padding: 10px;
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 8px;
      background: #fff;
    }

    .composer input {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 6px 8px;
      min-height: 34px;
    }

    .player-grid {
      min-height: 0;
      overflow: auto;
      display: grid;
      grid-template-columns: repeat(2, minmax(250px, 1fr));
      gap: 14px;
      align-content: start;
      padding-right: 2px;
    }

    .mode-switch {
      display: inline-grid;
      grid-template-columns: 1fr 1fr;
      border: 1px solid var(--line);
      border-radius: 6px;
      overflow: hidden;
      min-width: 94px;
      height: 30px;
    }

    .mode-switch button {
      min-height: 28px;
      border: 0;
      border-radius: 0;
      padding: 0 8px;
      font-size: 12px;
      background: #fff;
    }

    .mode-switch button.active {
      background: var(--green);
      color: #fff;
    }

    .status {
      color: var(--muted);
      font-size: 12px;
      min-height: 18px;
    }

    .error {
      color: var(--danger);
    }

    @media (max-width: 980px) {
      .app {
        grid-template-columns: 1fr;
      }

      .sidebar {
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }

      .workspace {
        grid-template-columns: 1fr;
        overflow: visible;
      }

      .group {
        height: 420px;
      }

      .player-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="brand">
        <h1>GameMaster</h1>
        <span class="badge">Test Mode</span>
      </div>

      <div class="field">
        <label for="channelId">本地频道</label>
        <input id="channelId" value="local-table" />
      </div>

      <div class="field">
        <label for="scriptName">默认剧本</label>
        <select id="scriptName">
          <option value="tb">暗流涌动 / TB</option>
          <option value="bmr">黯月初升 / BMR</option>
          <option value="sv">梦殒春宵 / SV</option>
        </select>
      </div>

      <div class="quick">
        <button class="primary" id="setupDemo">一键建 5 人局</button>
        <div class="quick-row">
          <button data-command="/start fixed-seed">开始</button>
          <button data-command="/day">白天</button>
        </div>
        <div class="quick-row">
          <button data-command="/night">夜晚</button>
          <button data-command="/resolve">结算</button>
        </div>
        <div class="quick-row">
          <button data-command="/actions">行动</button>
          <button data-command="/status">状态</button>
        </div>
      </div>

      <div class="field">
        <label>模拟玩家</label>
        <div class="players" id="players"></div>
      </div>

      <div class="quick-row">
        <button id="addPlayer">添加玩家</button>
        <button id="clearFeeds">清屏</button>
      </div>

      <div class="status" id="statusLine">准备好了。</div>
    </aside>

    <main class="main">
      <header class="toolbar">
        <div class="toolbar-title">
          <strong>本地微信模拟器</strong>
          <span>公开消息进群聊，私密消息只出现在对应玩家窗口。</span>
        </div>
        <div class="command-bank">
          <button data-fill="/new tb">/new</button>
          <button data-fill="/join">/join</button>
          <button data-fill="/role">/role</button>
          <button data-fill="/gm ">Ask GM</button>
          <button data-fill="/action ">行动</button>
          <button data-fill="/nominate ">提名</button>
          <button data-fill="/vote yes">赞成</button>
        </div>
      </header>

      <section class="workspace">
        <section class="group">
          <div class="chat-head">
            <strong>群聊：钟楼镇广场</strong>
            <small>public room</small>
          </div>
          <div class="feed" id="groupFeed"></div>
          <form class="composer" id="groupComposer">
            <select id="groupSender"></select>
            <input id="groupText" autocomplete="off" placeholder="以所选玩家身份发送群聊，例如 /new tb" />
            <button class="primary" type="submit">发送</button>
          </form>
        </section>

        <section class="player-grid" id="playerGrid"></section>
      </section>
    </main>
  </div>

  <template id="playerTemplate">
    <article class="phone">
      <div class="chat-head">
        <div>
          <strong data-name></strong>
          <small data-user></small>
        </div>
        <div class="mode-switch">
          <button type="button" data-mode="private" class="active">私聊</button>
          <button type="button" data-mode="public">群聊</button>
        </div>
      </div>
      <div class="feed" data-feed></div>
      <form class="composer">
        <input autocomplete="off" placeholder="给说书人私聊，例如 今晚查 3 号" />
        <button type="button" class="icon" title="填入 /role" data-role>身</button>
        <button class="primary" type="submit">发送</button>
      </form>
    </article>
  </template>

  <script>
    const state = {
      storyteller: { user_id: "__storyteller__", display_name: "GameMaster" },
      players: [
        { user_id: "alice", display_name: "Alice" },
        { user_id: "bob", display_name: "Bob" },
        { user_id: "chen", display_name: "Chen" },
        { user_id: "dana", display_name: "Dana" },
        { user_id: "eli", display_name: "Eli" }
      ],
      modes: new Map(),
      feeds: new Map()
    };

    const $ = (selector, root = document) => root.querySelector(selector);
    const groupFeed = $("#groupFeed");
    const playerGrid = $("#playerGrid");
    const playersBox = $("#players");
    const groupSender = $("#groupSender");
    const statusLine = $("#statusLine");

    function channelId() {
      return $("#channelId").value.trim() || "local-table";
    }

    function setStatus(text, error = false) {
      statusLine.textContent = text;
      statusLine.className = error ? "status error" : "status";
    }

    function appendBubble(feed, kind, meta, text) {
      const bubble = document.createElement("div");
      bubble.className = `bubble ${kind}`;
      const metaNode = document.createElement("span");
      metaNode.className = "meta";
      metaNode.textContent = meta;
      bubble.append(metaNode, document.createTextNode(text));
      feed.appendChild(bubble);
      feed.scrollTop = feed.scrollHeight;
    }

    function feedFor(userId) {
      return state.feeds.get(userId) || groupFeed;
    }

    function renderPlayers() {
      playersBox.replaceChildren();
      playerGrid.replaceChildren();
      groupSender.replaceChildren();

      for (const player of state.players) {
        state.modes.set(player.user_id, state.modes.get(player.user_id) || "private");

        const option = document.createElement("option");
        option.value = player.user_id;
        option.textContent = player.display_name;
        groupSender.appendChild(option);

        const row = document.createElement("div");
        row.className = "player-row";
        row.innerHTML = `<div><div class="player-name"></div><div class="player-id"></div></div>`;
        $(".player-name", row).textContent = player.display_name;
        $(".player-id", row).textContent = player.user_id;
        const fill = document.createElement("button");
        fill.textContent = "选中";
        fill.addEventListener("click", () => { groupSender.value = player.user_id; });
        row.appendChild(fill);
        playersBox.appendChild(row);

        const node = $("#playerTemplate").content.firstElementChild.cloneNode(true);
        $("[data-name]", node).textContent = `${player.display_name} 的微信`;
        $("[data-user]", node).textContent = player.user_id;
        const feed = $("[data-feed]", node);
        state.feeds.set(player.user_id, feed);

        const input = $("input", node);
        const privateButton = $('[data-mode="private"]', node);
        const publicButton = $('[data-mode="public"]', node);
        const syncMode = () => {
          const mode = state.modes.get(player.user_id);
          privateButton.classList.toggle("active", mode === "private");
          publicButton.classList.toggle("active", mode === "public");
          input.placeholder = mode === "private"
            ? "给说书人私聊，例如 今晚查 3 号"
            : "发送群聊，例如 /vote yes";
        };
        privateButton.addEventListener("click", () => {
          state.modes.set(player.user_id, "private");
          syncMode();
        });
        publicButton.addEventListener("click", () => {
          state.modes.set(player.user_id, "public");
          syncMode();
        });
        syncMode();

        $("[data-role]", node).addEventListener("click", () => {
          input.value = "/role";
          input.focus();
        });

        $("form", node).addEventListener("submit", async (event) => {
          event.preventDefault();
          const text = input.value.trim();
          if (!text) return;
          input.value = "";
          const isPrivate = state.modes.get(player.user_id) === "private";
          if (isPrivate) {
            appendBubble(feed, "user", `${player.display_name} -> 说书人`, text);
          } else {
            appendBubble(groupFeed, "user", player.display_name, text);
          }
          await sendEvent(player, text, isPrivate);
        });

        playerGrid.appendChild(node);
      }
    }

    async function sendEvent(player, text, isPrivate = false) {
      setStatus("发送中...");
      try {
        const response = await fetch("/gateway/events", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            channel_id: channelId(),
            user_id: player.user_id,
            display_name: player.display_name,
            text,
            is_private: isPrivate,
            metadata: player.user_id === "__storyteller__" ? { storyteller: true } : {}
          })
        });
        const data = await response.json();
        if (!response.ok || data.ok === false) {
          throw new Error(data.error || data.gateway_error || `HTTP ${response.status}`);
        }
        routeMessages(data.messages || []);
        setStatus(`已处理 ${data.messages?.length || 0} 条 agent 消息。`);
      } catch (error) {
        appendBubble(isPrivate ? feedFor(player.user_id) : groupFeed, "system", "本地测试器", error.message);
        setStatus(error.message, true);
      }
    }

    function routeMessages(messages) {
      for (const message of messages) {
        if (message.visibility === "private" && message.recipient_id) {
          appendBubble(feedFor(message.recipient_id), "agent", "说书人", message.text);
        } else {
          appendBubble(groupFeed, "agent", "说书人", message.text);
        }
      }
    }

    async function tickAgent() {
      try {
        const response = await fetch("/agent/tick", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ channel_id: channelId() })
        });
        const data = await response.json();
        if (!response.ok || data.ok === false) {
          throw new Error(data.error || data.gateway_error || `HTTP ${response.status}`);
        }
        const messages = data.messages || [];
        if (messages.length > 0) {
          routeMessages(messages);
          setStatus(`Pipeline tick: ${messages.length} message(s).`);
        }
      } catch (error) {
        setStatus(`Pipeline stopped: ${error.message}`, true);
      }
    }

    function startAgentLoop(config) {
      const tickSeconds = Math.max(1, Number(config?.tick_seconds || 1));
      tickAgent();
      window.setInterval(tickAgent, tickSeconds * 1000);
    }

    async function setupDemo() {
      clearFeeds();
      await tickAgent();
      for (const player of state.players.slice(0, 5)) {
        await sendEvent(player, `/join ${player.display_name}`, false);
      }
    }

    async function sendSystemEvent(text) {
      appendBubble(groupFeed, "user", state.storyteller.display_name, text);
      await sendEvent(state.storyteller, text, false);
    }

    function clearFeeds() {
      groupFeed.replaceChildren();
      for (const feed of state.feeds.values()) {
        feed.replaceChildren();
      }
      setStatus("已清屏。");
    }

    $("#groupComposer").addEventListener("submit", async (event) => {
      event.preventDefault();
      const userId = groupSender.value;
      const player = state.players.find((item) => item.user_id === userId);
      const input = $("#groupText");
      const text = input.value.trim();
      if (!player || !text) return;
      input.value = "";
      appendBubble(groupFeed, "user", player.display_name, text);
      await sendEvent(player, text, false);
    });

    $("#setupDemo").addEventListener("click", setupDemo);
    $("#clearFeeds").addEventListener("click", clearFeeds);
    $("#addPlayer").addEventListener("click", () => {
      const index = state.players.length + 1;
      const userId = `player${index}`;
      state.players.push({ user_id: userId, display_name: `玩家${index}` });
      renderPlayers();
      setStatus(`已添加 玩家${index}。`);
    });

    document.querySelectorAll("[data-command]").forEach((button) => {
      button.addEventListener("click", async () => {
        const text = button.dataset.command;
        await sendSystemEvent(text);
      });
    });

    document.querySelectorAll("[data-fill]").forEach((button) => {
      button.addEventListener("click", () => {
        $("#groupText").value = button.dataset.fill;
        $("#groupText").focus();
      });
    });

    renderPlayers();
    appendBubble(groupFeed, "system", "本地测试器", "先点“一键建 5 人局”，再点“开始”。私密身份会进入每个玩家自己的窗口。");
    fetch("/health")
      .then((response) => response.json())
      .then((data) => {
        const llm = data.llm || {};
        startAgentLoop(data.config || {});
        if (llm.configured) {
          setStatus(`LLM 已配置：${llm.model}`);
        } else {
          setStatus("LLM 未配置：可先用命令模式测试，配置 .env 后启用 AI 说书人。");
        }
      })
      .catch((error) => setStatus(error.message, true));
  </script>
</body>
</html>
"""


CORE_CHAT_CLIENT_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GameMaster Core Chat Test</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f6f8;
      --panel: #ffffff;
      --soft: #eef3f7;
      --line: #d5dde5;
      --text: #18212b;
      --muted: #647181;
      --accent: #1769c2;
      --agent: #ffffff;
      --user: #dcf8c6;
      --system: #fff4d6;
      --danger: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, "Microsoft YaHei", sans-serif;
      letter-spacing: 0;
    }
    button, input, select { font: inherit; }
    button {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      min-height: 34px;
      padding: 0 10px;
      cursor: pointer;
    }
    button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
    }
    input, select {
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 6px 8px;
      background: #fff;
      color: var(--text);
      min-width: 0;
    }
    .app {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 300px minmax(0, 1fr);
    }
    aside {
      border-right: 1px solid var(--line);
      background: var(--panel);
      padding: 16px;
      display: grid;
      gap: 12px;
      align-content: start;
    }
    h1 { margin: 0; font-size: 20px; }
    .hint, label, .status {
      color: var(--muted);
      font-size: 12px;
    }
    label { display: grid; gap: 6px; }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }
    .players {
      display: grid;
      gap: 6px;
      max-height: 260px;
      overflow: auto;
      padding-right: 2px;
    }
    .player-row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 7px;
      background: #fbfcfd;
    }
    .player-row strong, .phone strong { overflow-wrap: anywhere; }
    main {
      min-width: 0;
      display: grid;
      grid-template-rows: auto 1fr;
    }
    .topbar {
      min-height: 58px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.92);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 14px;
    }
    .commands {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }
    .workspace {
      min-height: 0;
      padding: 14px;
      display: grid;
      grid-template-columns: minmax(320px, 0.78fr) minmax(480px, 1.22fr);
      gap: 14px;
      overflow: hidden;
    }
    .group, .phone {
      min-height: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      display: grid;
      grid-template-rows: auto 1fr auto;
    }
    .group { height: calc(100vh - 86px); }
    .phone { height: 360px; }
    .head {
      min-height: 46px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 8px 10px;
    }
    .head small { color: var(--muted); white-space: nowrap; }
    .feed {
      min-height: 0;
      overflow: auto;
      padding: 10px;
      background: var(--soft);
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .bubble {
      max-width: 88%;
      border: 1px solid rgba(0, 0, 0, 0.06);
      border-radius: 8px;
      padding: 7px 9px;
      line-height: 1.42;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .bubble small {
      display: block;
      color: var(--muted);
      font-size: 11px;
      margin-bottom: 3px;
    }
    .bubble.user { align-self: flex-end; background: var(--user); }
    .bubble.agent { align-self: flex-start; background: var(--agent); }
    .bubble.system { align-self: center; background: var(--system); color: #76510c; max-width: 96%; }
    .composer {
      border-top: 1px solid var(--line);
      padding: 9px;
      display: grid;
      grid-template-columns: 118px minmax(0, 1fr) auto;
      gap: 8px;
      background: #fff;
    }
    .phone .composer {
      grid-template-columns: minmax(0, 1fr) auto auto;
    }
    .grid {
      min-height: 0;
      overflow: auto;
      display: grid;
      grid-template-columns: repeat(2, minmax(250px, 1fr));
      gap: 14px;
      align-content: start;
      padding-right: 2px;
    }
    .mode {
      display: inline-grid;
      grid-template-columns: 1fr 1fr;
      border: 1px solid var(--line);
      border-radius: 6px;
      overflow: hidden;
    }
    .mode button {
      border: 0;
      border-radius: 0;
      min-height: 28px;
      font-size: 12px;
      padding: 0 8px;
    }
    .mode button.active { background: var(--accent); color: #fff; }
    .status.error { color: var(--danger); }
    @media (max-width: 980px) {
      .app { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
      .workspace { grid-template-columns: 1fr; overflow: visible; }
      .group { height: 420px; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside>
      <div>
        <h1>GameMaster</h1>
        <div class="hint">Core Chat Test Mode</div>
      </div>
      <label>Channel <input id="channelId" value="local-table" /></label>
      <div class="row">
        <button class="primary" id="joinAll">Join 12</button>
        <button id="tickNow">Core Tick</button>
      </div>
      <div class="row">
        <button id="loadCurrent">Load Game</button>
        <button id="showRecap">Recap</button>
      </div>
      <div class="row">
        <button data-system="/start fixed-seed">Start</button>
        <button data-system="/resolve">Resolve</button>
      </div>
      <div class="row">
        <button data-system="/status">Status</button>
        <button data-system="/day">Day</button>
      </div>
      <div class="row">
        <button data-action="pause">Pause</button>
        <button data-action="resume">Resume</button>
      </div>
      <label>Sender <select id="groupSender"></select></label>
      <div class="players" id="players"></div>
      <div class="status" id="status">Ready.</div>
    </aside>
    <main>
      <header class="topbar">
        <div>
          <strong>本地微信模拟器</strong>
          <div class="hint">群聊走公开消息，玩家窗口默认私聊说书人。</div>
        </div>
        <div class="commands">
          <button data-fill="/role">/role</button>
          <button data-fill="/gm ">Ask GM</button>
          <button data-fill="/action ">夜间行动</button>
          <button data-fill="/nominate ">提名</button>
          <button data-fill="/vote yes">赞成</button>
          <button data-fill="/closevote">关票</button>
          <button id="clearFeeds">清屏</button>
        </div>
      </header>
      <section class="workspace">
        <section class="group">
          <div class="head">
            <strong>群聊：钟楼镇广场</strong>
            <small>public</small>
          </div>
          <div class="feed" id="groupFeed"></div>
          <form class="composer" id="groupComposer">
            <select id="groupSenderInline"></select>
            <input id="groupText" autocomplete="off" placeholder="公开发言或命令，例如 /join P1" />
            <button class="primary" type="submit">发送</button>
          </form>
        </section>
        <section class="grid" id="playerGrid"></section>
      </section>
    </main>
  </div>

  <template id="phoneTemplate">
    <article class="phone">
      <div class="head">
        <div>
          <strong data-name></strong>
          <small data-id></small>
        </div>
        <div class="mode">
          <button type="button" data-mode="private" class="active">私聊</button>
          <button type="button" data-mode="public">群聊</button>
        </div>
      </div>
      <div class="feed" data-feed></div>
      <form class="composer">
        <input autocomplete="off" placeholder="给说书人私聊，例如 /role" />
        <button type="button" data-role>身份</button>
        <button class="primary" type="submit">发送</button>
      </form>
    </article>
  </template>

  <script>
    const storyteller = { user_id: "__storyteller__", display_name: "GameMaster" };
    const players = Array.from({ length: 12 }, (_, index) => ({
      user_id: `u${index + 1}`,
      display_name: `P${index + 1}`
    }));
    const modes = new Map(players.map((player) => [player.user_id, "private"]));
    const feeds = new Map();
    const $ = (selector, root = document) => root.querySelector(selector);
    const statusEl = $("#status");
    const groupFeed = $("#groupFeed");
    const playerGrid = $("#playerGrid");
    const playersBox = $("#players");
    const groupSender = $("#groupSender");
    const groupSenderInline = $("#groupSenderInline");
    let currentGameId = null;

    function channelId() {
      return $("#channelId").value.trim() || "local-table";
    }
    function setStatus(text, error = false) {
      statusEl.textContent = text;
      statusEl.className = error ? "status error" : "status";
    }
    function addBubble(feed, kind, meta, text) {
      const bubble = document.createElement("div");
      bubble.className = `bubble ${kind}`;
      const small = document.createElement("small");
      small.textContent = meta;
      bubble.append(small, document.createTextNode(text));
      feed.appendChild(bubble);
      feed.scrollTop = feed.scrollHeight;
    }
    function privateFeed(userId) {
      return feeds.get(userId) || groupFeed;
    }
    function routeMessages(messages) {
      for (const message of messages || []) {
        if (message.visibility === "private" && message.recipient_id) {
          addBubble(privateFeed(message.recipient_id), "agent", "说书人", message.text);
        } else {
          addBubble(groupFeed, "agent", "说书人", message.text);
        }
      }
    }
    async function postJson(path, body) {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {})
      });
      const data = await response.json();
      if (!response.ok || data.ok === false) {
        throw new Error(data.error || data.gateway_error || `HTTP ${response.status}`);
      }
      return data;
    }
    async function sendEvent(player, text, isPrivate) {
      const data = await postJson("/core/events", {
        channel_id: channelId(),
        user_id: player.user_id,
        display_name: player.display_name,
        text,
        is_private: Boolean(isPrivate),
        metadata: player.user_id === "__storyteller__" ? { storyteller: true } : {}
      });
      routeMessages(data.messages);
      setStatus(`处理了 ${(data.messages || []).length} 条 core 消息。`);
      return data;
    }
    async function tick() {
      const data = await postJson("/core/agent/tick", { channel_id: channelId() });
      routeMessages(data.messages);
      if ((data.messages || []).length > 0) {
        setStatus(`Core tick: ${data.messages.length} 条消息。`);
      }
      return data;
    }
    async function pipelineAction(action) {
      const data = await postJson("/core/agent/action", {
        channel_id: channelId(),
        action,
        params: {}
      });
      routeMessages(data.messages);
      setStatus(data.messages?.[0]?.text || "Pipeline action done.");
    }
    async function loadCurrentGame() {
      const response = await fetch(`/core/games?channel_id=${encodeURIComponent(channelId())}`);
      const data = await response.json();
      if (!response.ok || data.ok === false) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }
      const current = (data.games || []).find((game) => game.game_id === data.current_game_id);
      if (!current) {
        setStatus("当前频道还没有 core game。");
        return;
      }
      currentGameId = current.game_id;
      setStatus(`已加载 ${current.game_id}: ${current.phase}, day ${current.day}, players ${current.players.length}.`);
      addBubble(groupFeed, "system", "本地测试器", `已连接当前局：${current.game_id} / ${current.phase} / day ${current.day}`);
    }
    async function showRecap() {
      if (!currentGameId) {
        await loadCurrentGame();
      }
      if (!currentGameId) return;
      const viewerId = groupSender.value || "__storyteller__";
      const response = await fetch(`/core/games/${encodeURIComponent(currentGameId)}/recap?player_id=${encodeURIComponent(viewerId)}&mode=llm`);
      const data = await response.json();
      if (!response.ok || data.ok === false) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }
      addBubble(privateFeed(viewerId), "system", "复盘", data.recap.text);
      setStatus(`已生成 ${viewerId} 视角复盘。`);
    }
    function renderPlayers() {
      playersBox.replaceChildren();
      playerGrid.replaceChildren();
      groupSender.replaceChildren();
      groupSenderInline.replaceChildren();
      for (const player of players) {
        for (const select of [groupSender, groupSenderInline]) {
          const option = document.createElement("option");
          option.value = player.user_id;
          option.textContent = `${player.display_name} (${player.user_id})`;
          select.appendChild(option);
        }
        const row = document.createElement("div");
        row.className = "player-row";
        const text = document.createElement("div");
        text.innerHTML = `<strong>${player.display_name}</strong><div class="hint">${player.user_id}</div>`;
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = "选中";
        button.addEventListener("click", () => {
          groupSender.value = player.user_id;
          groupSenderInline.value = player.user_id;
        });
        row.append(text, button);
        playersBox.appendChild(row);

        const node = $("#phoneTemplate").content.firstElementChild.cloneNode(true);
        $("[data-name]", node).textContent = `${player.display_name} 的微信`;
        $("[data-id]", node).textContent = player.user_id;
        const feed = $("[data-feed]", node);
        feeds.set(player.user_id, feed);
        const input = $("input", node);
        const privateButton = $('[data-mode="private"]', node);
        const publicButton = $('[data-mode="public"]', node);
        function syncMode() {
          const mode = modes.get(player.user_id);
          privateButton.classList.toggle("active", mode === "private");
          publicButton.classList.toggle("active", mode === "public");
          input.placeholder = mode === "private" ? "私聊说书人，例如 /role" : "公开发言，例如 /vote yes";
        }
        privateButton.addEventListener("click", () => { modes.set(player.user_id, "private"); syncMode(); });
        publicButton.addEventListener("click", () => { modes.set(player.user_id, "public"); syncMode(); });
        $("[data-role]", node).addEventListener("click", () => { input.value = "/role"; input.focus(); });
        $("form", node).addEventListener("submit", async (event) => {
          event.preventDefault();
          const text = input.value.trim();
          if (!text) return;
          input.value = "";
          const isPrivate = modes.get(player.user_id) === "private";
          addBubble(isPrivate ? feed : groupFeed, "user", player.display_name, text);
          try {
            await sendEvent(player, text, isPrivate);
          } catch (error) {
            addBubble(isPrivate ? feed : groupFeed, "system", "本地测试器", error.message);
            setStatus(error.message, true);
          }
        });
        syncMode();
        playerGrid.appendChild(node);
      }
    }
    async function joinAll() {
      try {
        await tick();
        for (const player of players) {
          addBubble(groupFeed, "user", player.display_name, `/join ${player.display_name}`);
          await sendEvent(player, `/join ${player.display_name}`, false);
        }
        setStatus("12 名玩家已加入 core game。");
      } catch (error) {
        addBubble(groupFeed, "system", "本地测试器", error.message);
        setStatus(error.message, true);
      }
    }
    $("#groupComposer").addEventListener("submit", async (event) => {
      event.preventDefault();
      const player = players.find((item) => item.user_id === groupSenderInline.value) || players[0];
      const input = $("#groupText");
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      addBubble(groupFeed, "user", player.display_name, text);
      try {
        await sendEvent(player, text, false);
      } catch (error) {
        addBubble(groupFeed, "system", "本地测试器", error.message);
        setStatus(error.message, true);
      }
    });
    $("#joinAll").addEventListener("click", joinAll);
    $("#tickNow").addEventListener("click", () => tick().catch((error) => setStatus(error.message, true)));
    $("#loadCurrent").addEventListener("click", () => loadCurrentGame().catch((error) => setStatus(error.message, true)));
    $("#showRecap").addEventListener("click", () => showRecap().catch((error) => setStatus(error.message, true)));
    $("#clearFeeds").addEventListener("click", () => {
      groupFeed.replaceChildren();
      for (const feed of feeds.values()) feed.replaceChildren();
      setStatus("已清屏。");
    });
    document.querySelectorAll("[data-system]").forEach((button) => {
      button.addEventListener("click", async () => {
        const text = button.dataset.system;
        addBubble(groupFeed, "user", storyteller.display_name, text);
        try {
          await sendEvent(storyteller, text, false);
        } catch (error) {
          addBubble(groupFeed, "system", "本地测试器", error.message);
          setStatus(error.message, true);
        }
      });
    });
    document.querySelectorAll("[data-action]").forEach((button) => {
      button.addEventListener("click", () => pipelineAction(button.dataset.action).catch((error) => setStatus(error.message, true)));
    });
    document.querySelectorAll("[data-fill]").forEach((button) => {
      button.addEventListener("click", () => {
        $("#groupText").value = button.dataset.fill;
        $("#groupText").focus();
      });
    });
    groupSender.addEventListener("change", () => { groupSenderInline.value = groupSender.value; });
    groupSenderInline.addEventListener("change", () => { groupSender.value = groupSenderInline.value; });
    renderPlayers();
    addBubble(groupFeed, "system", "本地测试器", "默认页面已连接新 core：先一键加入 12 人，再点击开始。玩家私聊 /role 可查看自己的身份。");
    fetch("/health")
      .then((response) => response.json())
      .then((data) => {
        const tickSeconds = Math.max(1, Number(data.config?.tick_seconds || 1));
        window.setInterval(() => tick().catch(() => {}), tickSeconds * 1000);
        setStatus(data.llm?.configured ? `LLM 已配置：${data.llm.model}` : "LLM 未配置，core 会使用 fallback 裁量。");
      })
      .catch((error) => setStatus(error.message, true));
  </script>
</body>
</html>
"""


CORE_TEST_CLIENT_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GameMaster Core Test</title>
  <style>
    :root {
      --bg: #f7f8fa;
      --panel: #ffffff;
      --line: #d6dbe1;
      --text: #18212b;
      --muted: #647181;
      --accent: #1868db;
      --danger: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, "Microsoft YaHei", sans-serif;
      letter-spacing: 0;
    }
    button, input, select { font: inherit; }
    button {
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      cursor: pointer;
      padding: 0 10px;
    }
    button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
    }
    .app {
      display: grid;
      grid-template-columns: 320px 1fr;
      min-height: 100vh;
    }
    aside {
      padding: 16px;
      border-right: 1px solid var(--line);
      background: var(--panel);
      display: grid;
      align-content: start;
      gap: 12px;
    }
    main {
      padding: 16px;
      display: grid;
      grid-template-rows: auto 1fr;
      gap: 12px;
      min-width: 0;
    }
    h1 {
      font-size: 20px;
      margin: 0 0 4px;
    }
    label {
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
    }
    input, select {
      width: 100%;
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 6px 8px;
      background: #fff;
      color: var(--text);
    }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }
    .status {
      min-height: 20px;
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }
    .status.error { color: var(--danger); }
    .panel {
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      min-height: 0;
      display: grid;
      grid-template-rows: auto 1fr;
    }
    .panel-head {
      min-height: 48px;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .panel-head strong { font-size: 15px; }
    .events {
      padding: 12px;
      overflow: auto;
      display: grid;
      gap: 8px;
      align-content: start;
    }
    .event {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      padding: 8px;
      overflow-wrap: anywhere;
    }
    .event small {
      display: block;
      color: var(--muted);
      margin-bottom: 4px;
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      font-size: 12px;
    }
    @media (max-width: 820px) {
      .app { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside>
      <div>
        <h1>Core Test Mode</h1>
        <div class="status">Runs against /core APIs.</div>
      </div>
      <label>Game ID <input id="gameId" value="core-local" /></label>
      <label>Channel ID <input id="channelId" value="core-local" /></label>
      <label>Player view
        <select id="viewer">
          <option value="__storyteller__">Storyteller</option>
          <option value="u1">P1</option>
          <option value="u2">P2</option>
          <option value="u3">P3</option>
          <option value="u4">P4</option>
          <option value="u5">P5</option>
        </select>
      </label>
      <button class="primary" id="createGame">Create Game</button>
      <button id="joinFive">Join 5 Players</button>
      <button id="startGame">Start Setup</button>
      <button id="refreshGame">Refresh</button>
      <div class="row">
        <button id="viewEvents">View Events</button>
        <button id="compact">Compact</button>
      </div>
      <div class="row">
        <button id="coreTick">Core Tick</button>
        <button id="pausePipeline">Pause</button>
      </div>
      <button id="resumePipeline">Resume Pipeline</button>
      <div class="status" id="status">Ready.</div>
    </aside>
    <main>
      <section class="panel">
        <div class="panel-head">
          <strong>Game State</strong>
          <span class="status" id="phase">No game loaded.</span>
        </div>
        <div class="events"><pre id="gameState">{}</pre></div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <strong>Visible Events</strong>
          <span class="status" id="eventCount">0 events</span>
        </div>
        <div class="events" id="events"></div>
      </section>
    </main>
  </div>
  <script>
    const players = [
      ["u1", "P1"],
      ["u2", "P2"],
      ["u3", "P3"],
      ["u4", "P4"],
      ["u5", "P5"]
    ];
    const statusEl = document.querySelector("#status");
    const phaseEl = document.querySelector("#phase");
    const gameStateEl = document.querySelector("#gameState");
    const eventsEl = document.querySelector("#events");
    const eventCountEl = document.querySelector("#eventCount");

    function gameId() {
      return document.querySelector("#gameId").value.trim() || "core-local";
    }
    function channelId() {
      return document.querySelector("#channelId").value.trim() || "core-local";
    }
    function viewer() {
      return document.querySelector("#viewer").value;
    }
    function status(text, error = false) {
      statusEl.textContent = text;
      statusEl.className = error ? "status error" : "status";
    }
    async function request(path, body) {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {})
      });
      const data = await response.json();
      if (!response.ok || data.ok === false) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }
      return data;
    }
    function renderGame(game) {
      phaseEl.textContent = game ? `${game.phase} day ${game.day}` : "No game loaded.";
      gameStateEl.textContent = JSON.stringify(game || {}, null, 2);
    }
    function renderEvents(events) {
      eventsEl.replaceChildren();
      for (const event of events) {
        const node = document.createElement("div");
        node.className = "event";
        const meta = document.createElement("small");
        meta.textContent = `${event.event_type} | ${event.phase} | actor: ${event.actor_id || "system"}`;
        const text = document.createElement("div");
        text.textContent = event.text || JSON.stringify(event.payload);
        node.append(meta, text);
        eventsEl.appendChild(node);
      }
      eventCountEl.textContent = `${events.length} events`;
    }
    async function refreshGame() {
      const response = await fetch(`/core/games/${encodeURIComponent(gameId())}`);
      const data = await response.json();
      if (!response.ok || data.ok === false) throw new Error(data.error || `HTTP ${response.status}`);
      renderGame(data.game);
      return data.game;
    }
    async function refreshEvents() {
      const response = await fetch(`/core/games/${encodeURIComponent(gameId())}/events?player_id=${encodeURIComponent(viewer())}`);
      const data = await response.json();
      if (!response.ok || data.ok === false) throw new Error(data.error || `HTTP ${response.status}`);
      renderEvents(data.events || []);
    }
    document.querySelector("#createGame").addEventListener("click", async () => {
      try {
        const data = await request("/core/games", { game_id: gameId(), min_players: 5 });
        renderGame(data.game);
        status("Created.");
      } catch (error) { status(error.message, true); }
    });
    document.querySelector("#joinFive").addEventListener("click", async () => {
      try {
        for (const [player_id, display_name] of players) {
          await request(`/core/games/${encodeURIComponent(gameId())}/join`, { player_id, display_name });
        }
        await refreshGame();
        status("Joined 5 players.");
      } catch (error) { status(error.message, true); }
    });
    document.querySelector("#startGame").addEventListener("click", async () => {
      try {
        const data = await request(`/core/games/${encodeURIComponent(gameId())}/start`, { seed: "core-ui" });
        renderGame(data.game);
        await refreshEvents();
        status("Started.");
      } catch (error) { status(error.message, true); }
    });
    document.querySelector("#refreshGame").addEventListener("click", async () => {
      try { await refreshGame(); status("Refreshed."); } catch (error) { status(error.message, true); }
    });
    document.querySelector("#viewEvents").addEventListener("click", async () => {
      try { await refreshEvents(); status("Events loaded."); } catch (error) { status(error.message, true); }
    });
    document.querySelector("#compact").addEventListener("click", async () => {
      try {
        await request(`/core/games/${encodeURIComponent(gameId())}/compact-memory`, { keep_last: 20 });
        await refreshGame();
        status("Compacted.");
      } catch (error) { status(error.message, true); }
    });
    document.querySelector("#coreTick").addEventListener("click", async () => {
      try {
        const data = await request("/core/agent/tick", { channel_id: channelId() });
        if (data.game) {
          document.querySelector("#gameId").value = data.game.game_id;
          renderGame(data.game);
        }
        await refreshEvents().catch(() => {});
        status(`Tick returned ${(data.messages || []).length} message(s).`);
      } catch (error) { status(error.message, true); }
    });
    document.querySelector("#pausePipeline").addEventListener("click", async () => {
      try {
        await request("/core/agent/action", { channel_id: channelId(), action: "pause", params: {} });
        status("Pipeline paused.");
      } catch (error) { status(error.message, true); }
    });
    document.querySelector("#resumePipeline").addEventListener("click", async () => {
      try {
        await request("/core/agent/action", { channel_id: channelId(), action: "resume", params: {} });
        status("Pipeline resumed.");
      } catch (error) { status(error.message, true); }
    });
    document.querySelector("#viewer").addEventListener("change", () => refreshEvents().catch((error) => status(error.message, true)));
  </script>
</body>
</html>
"""
