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

然后打开：

```text
http://127.0.0.1:8787/test
```

页面里可以：

- 点“一键建 5 人局”创建本地频道并让 5 个模拟玩家加入。
- 点“开始”分配身份；公开消息进入群聊，私密身份进入每个玩家自己的窗口。
- 在任意玩家窗口里切换“私聊/群聊”，模拟微信里私聊说书人或群内发言。
- 夜晚私聊任意文本会被记录为行动。
- 点“结算”会让 LLM 读取魔典和夜间行动，生成公开/私密结算建议并应用死亡/复活。

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
