# GameMaster

GameMaster 是一个《血染钟楼》AI 说书人 agent。当前优先实现本地 Test Mode：服务自带一个网页，在同一个浏览器页面里模拟多个微信对话框，让你单机测试玩家群聊、私聊说书人、身份分发、夜晚行动、投票和 LLM 结算。

正式 Channel Gateway 以后可以复用同一套事件接口接入；现在先把 agent 逻辑和本地测试体验跑顺。

> 角色说明是便于程序运行的概括版，不替代官方规则书或官方角色文本。

## API 设置放哪里

API key 不写进代码。把仓库根目录的 `.env.example` 复制成 `.env`，然后填你的模型配置：

```powershell
cd C:\Users\LX034\Code\GameMaster
Copy-Item .env.example .env
```

`.env` 示例：

```env
GAMEMASTER_LLM_BASE_URL=https://api.openai.com/v1
GAMEMASTER_LLM_API_KEY=your-api-key
GAMEMASTER_LLM_MODEL=your-model-name
GAMEMASTER_LLM_TEMPERATURE=0.4
GAMEMASTER_LLM_TIMEOUT_SECONDS=30
```

这个 client 使用 OpenAI-compatible `/chat/completions` 接口。接本地模型时，把 `GAMEMASTER_LLM_BASE_URL` 改成本地服务地址即可；如果本地服务不需要 key，可以留空 `GAMEMASTER_LLM_API_KEY`，但必须设置 `GAMEMASTER_LLM_MODEL`。

DeepSeek 可用类似配置：

```env
GAMEMASTER_LLM_BASE_URL=https://api.deepseek.com
GAMEMASTER_LLM_API_KEY=your-deepseek-key
GAMEMASTER_LLM_MODEL=deepseek-chat
```

`.env` 已经在 `.gitignore` 里，不会被提交。

## 快速启动本地测试模式

```powershell
cd C:\Users\LX034\Code\GameMaster
$env:PYTHONPATH="src"
python -m gamemaster serve --host 127.0.0.1 --port 8787
```

默认是内存模式，重启后游戏状态会清空。需要落盘时加：

```powershell
python -m gamemaster serve --host 127.0.0.1 --port 8787 --data data/local-games.json
```

新 core 会使用独立存档 `data/local-games.core.json`，避免和旧 engine 的 JSON 结构互相覆盖。

然后打开：

```text
http://127.0.0.1:8787/test
```

默认 `/test` 现在连接新 core agent / pipeline；旧版页面保留在 `/legacy/test`。页面里可以：

- 点“一键建 5 人局”让 5 个模拟玩家加入；游戏由 agent pipeline 自动创建和倒计时开始。
- 公开消息进入群聊，私密身份进入每个玩家自己的窗口。
- 在任意玩家窗口里切换“私聊/群聊”，模拟微信里私聊说书人或群内发言。
- 夜晚私聊任意文本会被记录为行动。
- 夜晚倒计时结束后，agent 可以自动调用 LLM 读取魔典和夜间行动，生成公开/私密结算建议并应用死亡/复活。

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8787/health
```

返回里会包含 LLM 配置状态：

```json
{
  "ok": true,
  "llm": {
    "configured": true,
    "base_url": "https://api.openai.com/v1",
    "model": "your-model-name",
    "has_api_key": true
  }
}
```

## Memory 设计

GameMaster 不把整局聊天直接塞进 LLM context。每个游戏会保存两层 memory：

- `memory_events`：结构化事件日志。每条事件都有 `event_type`、`created_at`、`actor_id`、`visibility`、`recipient_id`、`phase`、`day`、`text`、`payload` 和 `tags`。
- `memory_summary`：长期摘要。当事件太多时，旧的关键事件会压缩进摘要，最近事件保留为结构化明细。

LLM 每次只拿：

- 当前公开状态或完整魔典，取决于是玩家交互还是说书人结算。
- `memory_summary`。
- 最近少量相关事件。玩家私聊只会拿该玩家可见的私密事件和公开事件；`/resolve` 才会拿完整私密上下文。

调试 memory：

```text
GET /games/<game_id>/memory
```

## Agent Pipeline

主持流程由 agent 主导，不依赖玩家房主。本地网页会按 `GAMEMASTER_TICK_SECONDS` 调用：

```text
POST /agent/tick
```

pipeline 当前是 hard-coded 的基础流程：

1. 频道没有游戏时，自动创建默认剧本。
2. lobby 阶段等待玩家加入。
3. 达到 `GAMEMASTER_MIN_PLAYERS_TO_START` 后，进入开局倒计时。
4. 倒计时结束后自动 `/start`，分发身份并进入首夜。
5. 夜晚开始行动倒计时，玩家私聊行动会进入 memory。
6. 夜晚倒计时结束后，如果 `GAMEMASTER_AUTO_RESOLVE_NIGHT=true`，自动 `/resolve`。
7. 结算后自动进入白天讨论。
8. 白天倒计时结束后，默认等待说书人继续；如果 `GAMEMASTER_AUTO_ADVANCE_DAY=true`，会自动进入下一夜。

统一配置在 `.env`：

```env
GAMEMASTER_DEFAULT_CHANNEL_ID=local-table
GAMEMASTER_DEFAULT_SCRIPT=tb
GAMEMASTER_MIN_PLAYERS_TO_START=5
GAMEMASTER_AUTO_CREATE_GAME=true
GAMEMASTER_AUTO_START_GAME=true
GAMEMASTER_AUTO_RESOLVE_NIGHT=true
GAMEMASTER_AUTO_ADVANCE_DAY=false
GAMEMASTER_LOBBY_COUNTDOWN_SECONDS=30
GAMEMASTER_NIGHT_ACTION_SECONDS=90
GAMEMASTER_DAY_DISCUSSION_SECONDS=300
GAMEMASTER_TICK_SECONDS=1
```

查看当前配置：

```text
GET /agent/config
```

运行时控制当前局：

```text
POST /agent/action
```

示例：

```json
{
  "channel_id": "local-table",
  "action": "extend",
  "params": { "seconds": 60 }
}
```

可用 action：

- `extend`：延长当前阶段倒计时，参数 `seconds`，可选 `timer`
- `shorten`：缩短当前阶段倒计时
- `set_timer`：把当前阶段倒计时设置为指定秒数
- `pause`：暂停 pipeline
- `resume`：恢复 pipeline
- `set_override`：覆盖当前局的某个配置，例如 `night_action_seconds`
- `clear_override`：清除当前局配置覆盖
- `force_stage`：强制设置当前 pipeline stage

说书人 agent 也可以通过聊天命令执行同样动作：

```text
/pipeline extend 60
/pipeline set_timer 120 night_deadline
/pipeline set_override night_action_seconds 180
/pipeline pause
/pipeline resume
/pipeline force_stage day_discussion
```

这些是“当前局覆盖”，不会改 `.env` 的默认值。适合中途加人、玩家掉线、讨论太热烈、夜晚行动没收齐等情况。

## 本地网页背后的事件接口

POST `/gateway/events`

```json
{
  "channel_id": "table-1",
  "user_id": "alice",
  "display_name": "Alice",
  "text": "/join Alice",
  "is_private": false
}
```

本地网页就是调用这个接口，并把返回的 `messages` 分发到群聊或玩家私聊窗口。

说书人控制命令由测试控制台使用系统用户发送：

```json
{
  "channel_id": "table-1",
  "user_id": "__storyteller__",
  "display_name": "GameMaster",
  "text": "/start fixed-seed",
  "metadata": { "storyteller": true }
}
```

以后接正式 Channel Gateway 时，玩家消息仍然用普通 `user_id`；说书人内部调度可以继续用 `__storyteller__` 或 `metadata.storyteller=true`。

## 命令

玩家命令：

- `/join [昵称]` 加入当前频道的游戏。
- `/role` 私聊查看自己的身份。
- `/status` 查看公开状态。
- `/sheet` 查看当前剧本角色表。
- `/action <内容>` 私聊提交夜间行动；夜晚直接发私聊文本也会被记录为行动。
- `/nominate <玩家名|座位号>` 提名。
- `/vote yes|no` 投票。
- `/closevote` 关闭当前投票，达到门槛时执行处决。

说书人 agent / 测试控制台命令：

- `/new [tb|bmr|sv]` 创建一局。
- `/start [seed]` 分配身份并进入首夜。
- `/day`、`/night` 切换白天/夜晚。
- `/actions` 查看最近行动。
- `/resolve` 使用 LLM 自动生成夜晚结算。
- `/execute <玩家>`、`/kill <玩家>`、`/revive <玩家>`、`/info <玩家> <文本>` 是结算工具。

## 剧本范围

当前内置了三个基础剧本的角色名、阵营、类型、简要效果、基础人数分布，以及部分设置规则：

- Trouble Brewing / 暗流涌动
- Bad Moon Rising / 黯月初升
- Sects & Violets / 梦殒春宵

已支持的自动化：

- 5 到 15 名普通玩家人数分布。
- 随机抽取镇民、外来者、爪牙、恶魔。
- 恶魔伪装角色。
- 酒鬼显示为镇民。
- 男爵、方古、维格莫提斯等基础外来者数量调整。
- 邪恶阵营首夜私聊信息。
- 圣徒被处决、恶魔死亡、仅剩两名存活玩家等基础胜负条件。
- 猩红女郎在满足条件时接任恶魔。

复杂角色能力现在分两步处理：规则引擎维护确定性状态，LLM 读取魔典和玩家行动生成结算。遇到不确定规则时，LLM 会把备注写回说书人窗口，而不是擅自强行结算。

## 测试

```powershell
python -m unittest discover -s tests
```

## Core Rewrite

当前新增进度：

- RoleAllocator 支持 5-15 人 Trouble Brewing 人数分布。
- Baron setup 已接入：抽到 `baron` 时自动减少 2 个 Townsfolk，并增加 2 个 Outsider。
- Drunk setup 已接入：真实身份保留为 `drunk`，玩家可见身份会显示为一个 Townsfolk，且优先选择未在场镇民。
- Trouble Brewing outsider 池已补齐到 Drunk / Saint / Recluse / Butler，便于 Baron 修正规则在大人数局生效。
- 新 core 已接入白天提名、投票、关闭投票和处决流程。
- 新 core 已接入基础胜负判断：恶魔死亡善良胜利、仅剩 2 名存活且恶魔仍在场邪恶胜利、Saint 被处决邪恶胜利。
- Scarlet Woman 已接入恶魔转移：恶魔死亡且仍有至少 5 名存活玩家时，活着且清醒健康的 Scarlet Woman 会秘密变成 Imp。
- Slayer 已接入白天射击：真 Slayer 射中恶魔会杀死目标；酒鬼/中毒 Slayer 会消耗能力但不生效。
- Undertaker 已接入普通夜信息：得知当天被处决者的角色，醉酒/中毒时走 false_information 裁量。
- Monk 已接入夜晚保护：健康 Monk 的保护可以阻止恶魔造成的死亡。
- Ravenkeeper 已接入夜死信息：夜晚死亡后按夜间选择得知目标角色。
- Mayor 已接入三人生存无人处决胜利，以及恶魔夜杀时的 optional_death 转移裁量。
- Virgin 已接入首次被镇民提名时处决提名者。
- Soldier 已接入免疫恶魔死亡。
- Trouble Brewing 角色池已补齐到官方 22 角色：新增 Librarian / Investigator / Spy / Recluse / Butler。
- Librarian / Investigator 已接入首夜信息；Spy 可在夜晚获得魔典摘要；Butler 已接入夜选 master 和白天赞成票限制；Recluse 先以真实角色卡和误登记能力文本进入系统。
- ActionValidator 已接入新 core 夜间行动提交：校验阶段、角色匹配、目标数量、重复提交、死亡状态和 Monk 自保限制。
- LLMDecisionProvider 已接入新 core：复用 OpenAI-compatible/DeepSeek client，把 `DecisionRequest` 转成 JSON prompt，并把模型 JSON 转回 `DecisionProposal`；失败时自动 fallback。
- Setup visibility 已接入新 core：身份私信、邪恶阵营互认、恶魔伪装角色都会作为可见性受控事件写入魔典。
- MemoryCompactor 已接入新 core：结构化事件不删除，旧事件可折叠进 `grimoire.summary`，LLM context 默认只取最近可见事件。
- Registration override 已接入新 core：`grimoire.pipeline_state["registration_overrides"]` 可让 Recluse / Spy 在 Empath、Chef、Fortune Teller 等登记敏感能力里临时登记为不同阵营或角色类型。
- CoreGameStore 已接入新 core：使用 `--data data/local-games.json` 启动时，core 状态会落盘到 `data/local-games.core.json`，包含玩家、座位、身份、事件流、pipeline_state、night_actions 和 channel 映射。
- CoreAgent 已支持常见自然语言输入：夜晚私聊可写“我毒 3 号”“今晚查 P3 和 P7”，白天群聊可写“我提名 4 号”“赞成/反对”，系统会先解析为 player_id 再交给 ActionValidator。
- CorePipeline 已支持夜晚行动提醒：夜晚倒计时过半后，会私信提醒仍需要行动且尚未提交的玩家。
- Core recap 已接入：`/core/games/<game_id>/recap?player_id=<viewer>` 会按玩家可见性生成复盘；`__storyteller__` 视角可看全量事件。
- CorePlayerResponder 已接入防泄密回复上下文：玩家私聊问规则/状态时，只把该玩家可见的 `llm_context_for(player_id)` 交给 LLM；如果模型回复包含该玩家不可见的身份信息，会自动 fallback 到安全模板。

新的核心框架先放在 `src/gamemaster/core`，不直接破坏旧的本地测试服务。当前已落地的基础类：

- `GameFlow`：新的游戏流程主体，负责等待玩家、setup、首夜等状态推进。
- `Grimoire`：append-only 魔典，保存玩家、座位、身份实例、事件流，并提供玩家视角可见性过滤。
- `RoleCard`：角色卡基类，角色通过 hooks 产生确定性 effect 或 `DecisionRequest`。
- `DecisionRequest` / `DecisionProposal` / `StorytellerDecision`：LLM 自动裁量协议。
- `StorytellerDecisionEngine`：调用裁量 provider，校验合法选项，非法时自动 fallback。
- `ActionExecutor`：唯一写入魔典和发出消息的执行层。
- `RoleAllocator`：按人数分配 Trouble Brewing 最小角色池，并生成恶魔伪装。
- `NightOrderResolver`：按首夜/其他夜行动顺序执行角色 hook。
- `RulesEngine`：集中处理白天提名、投票、处决、基础胜负判断和部分行动合法性。

已实现的最小示例覆盖了 Trouble Brewing 的几种关键能力形态：

- 清醒健康 Empath：代码直接计算邻居邪恶数量。
- 酒鬼/中毒 Empath：生成 `false_information` 裁量请求。
- Washerwoman：生成 `setup_selection` 裁量请求，选择信息候选人。
- Chef：代码直接计算相邻邪恶玩家对数。
- Fortune Teller：读取夜间行动，给 yes/no 信息；酒鬼/中毒时走裁量。
- Poisoner：读取夜间行动并写入 `poisoned` 状态。
- Imp：读取夜间行动并写入死亡事件。
- RoleAllocator：目前覆盖 5-15 人 TB 分布。
- RulesEngine：支持白天提名、投票、关闭投票、处决、鬼票消耗、每日提名限制。
- 基础胜负判断：恶魔死亡、两人生存、Saint 被处决。
- Scarlet Woman：在胜负判断前接任恶魔，避免误判善良胜利。
- Slayer：支持一次性白天公开射击，并复用死亡后的胜负/恶魔转移检查。
- Undertaker / Ravenkeeper：支持夜间角色信息，并在醉酒/中毒时生成裁量请求。
- Monk / Soldier：支持阻止恶魔死亡。
- Mayor：支持三人生存无人处决胜利与死亡转移裁量。
- Virgin：支持首次被镇民提名立即处决提名者。
- Librarian / Investigator：支持首夜角色信息。
- Spy：支持夜晚查看魔典摘要。
- Butler：支持夜选 master，并限制白天赞成票。
- Recluse：已作为真实 Outsider 角色卡进入脚本，并可通过 registration override 在需要时登记为邪恶或恶魔。
- ActionValidator：支持新 core 夜间行动提交校验，并提供 `GameFlow.submit_night_action(...)` 入口。
- LLMDecisionProvider：支持 `DecisionRequest -> OpenAI-compatible/DeepSeek -> DecisionProposal`，并由 DecisionValidator 二次校验。
- Setup visibility：支持 `GameFlow.send_setup_info()`，分发玩家身份、evil_team 信息和 demon bluffs。
- MemoryCompactor：支持 `GameFlow.compact_memory(...)`，保留完整事件流并维护短 summary。
- NightOrderResolver：能保证 Poisoner 在 Fortune Teller 前执行，Imp 后执行。
- LLM/provider 返回合法数字后自动执行。
- LLM/provider 返回非法数字时自动 fallback。
- 玩家视角不能看到 storyteller-only 的身份分配事件。

对应测试在：

```text
tests/test_core_rewrite.py
tests/test_core_allocator_night.py
tests/test_core_day_rules.py
tests/test_core_action_validator.py
tests/test_core_llm_provider.py
tests/test_core_memory.py
```

新 core HTTP 入口已开始接入旧 server，并与旧 `/test` 并存：

```text
POST /core/games
POST /core/games/<game_id>/join
POST /core/games/<game_id>/start
POST /core/games/<game_id>/night-action
POST /core/games/<game_id>/resolve-night
POST /core/games/<game_id>/compact-memory
POST /core/events
POST /core/agent/tick
POST /core/agent/action
GET  /core/games/<game_id>
GET  /core/games/<game_id>/events?player_id=<player_id>
```

Core chat command notes:
- `/gm <question>` or `/ask <question>` talks directly to the AI Storyteller. It works during night without being parsed as a night action.

这些入口现在由新 core 驱动默认 `/test`；旧页面保留在 `/legacy/test`。`/core/events` 使用和旧 gateway 相同的 payload 形状，但交给新的 `CoreAgent` 处理 `/new`、`/join`、`/start`、`/role`、`/action`、`/resolve`、`/nominate`、`/vote` 等命令，也支持常见自然语言行动、提名和投票。`/core/agent/tick` 使用新的 `CorePipeline` 自动建局、倒计时开局、夜晚提醒、夜晚结算和白天推进；`/core/agent/action` 支持 pause/resume、set_timer、extend、shorten、set_override、clear_override、force_phase。使用 `--data` 启动时，core 状态会保存到独立 `.core.json` 文件。

新 core 也有独立测试页：

```text
http://127.0.0.1:8787/core/test
```

该页面直接调用 `/core/games...`，可创建 core game、加入 5 名玩家、开始 setup、切换玩家视角查看可见事件。
页面也提供 Core Tick / Pause / Resume 控件，可测试新 core pipeline。
