# astrbot_plugin_meme_generator_api

基于远端 `memes API` 的 AstrBot 表情包插件。

插件会从后端拉取模板元数据，在 AstrBot 内完成消息解析、参数提取、图片来源收集，然后调用远端接口生成表情包图片并回传。

## 功能特性

- 支持命令方式使用：`meme帮助`、`meme列表`、`meme搜索`、`meme更新`、`随机meme`
- 支持被动关键词触发
- 支持模板黑白名单
- 支持引用消息取图、直接图片取图、`@` 头像取图
- 对需要图片的模板提供“触发者头像保底”
- 支持 HTTP 超时与重试配置

## 安装

将插件目录放入 AstrBot 插件目录后启用。

目录结构示例：

```text
astrbot_plugin_meme_generator_api/
├─ main.py
├─ metadata.yaml
├─ _conf_schema.json
├─ requirements.txt
└─ logo.png
```

## 依赖

当前插件额外依赖：

```text
aiohttp>=3.9.0
```

`astrbot.*` 相关模块由 AstrBot 运行环境提供，不需要额外安装。

## 指令

- `meme_ping`
  - 检查插件是否正常加载

- `meme帮助`
  - 查看插件帮助信息

- `meme列表`
  - 获取模板总览图

- `随机meme`
  - 随机选择一个模板生成图片
  - 生成后会额外返回本次使用的模板名称

- `meme搜索 <关键词>`
  - 搜索模板关键词

- `meme更新`
  - 重新拉取模板缓存

## 被动触发规则

插件支持直接发送模板关键词触发，但为了减少聊天误触，当前规则比“只要包含关键词就触发”更严格。

触发要求：

- 关键词必须出现在消息开头
- 如果开启了 `force_sharp`，则必须以 `#关键词` 开头
- 如果模板需要文字输入：
  - 必须写成 `关键词 + 空格 + 文本`
  - 多段文本使用 `/` 分隔
- 如果模板不需要文字输入：
  - 关键词后面不能再跟普通文本
- 如果模板需要图片输入：
  - 可使用当前消息图片、引用消息图片、`@` 用户头像
  - 如果仍不足，会自动使用触发者头像补足最小图片数量

示例：

```text
摸头 小明
结婚 张三/李四
#打
```

## 图片来源优先级

生成时会按下面的顺序收集图片输入：

1. 当前消息直接发送的图片
2. 引用消息中的图片
3. `@` 到的用户头像
4. 触发者头像（保底补足）

## 模板来源

插件启动后会优先读取本地缓存：

- `infos.json`
- `key_map.json`

如果本地缓存不存在，或执行了 `meme更新`，则会从后端拉取：

- `GET /memes/static/infos.json`
- `GET /memes/static/keyMap.json`

如果静态接口失败，会回退到：

- `GET /meme/infos`

## 配置项

- `base_url`
  - Meme 服务基础地址

- `reply`
  - 发送结果时是否引用原消息

- `force_sharp`
  - 是否必须使用 `#关键词` 触发

- `http_timeout_seconds`
  - HTTP 请求超时秒数

- `http_retry_times`
  - HTTP 超时重试次数

- `reply_image_pick_mode`
  - 引用消息取图策略
  - 可选值：`all`、`first`

- `template_filter_mode`
  - 模板过滤模式
  - 可选值：`blacklist`、`whitelist`

- `template_filter_list`
  - 模板匹配列表
  - 按模板 `code` 或关键词做子串匹配

- `master_protect_do`
  - 是否启用主人保护逻辑

- `protect_list`
  - 启用主人保护的模板代码列表

- `master_qq_list`
  - 主人 QQ 列表

- `max_file_size_mb`
  - 输入图片大小限制（MB）

## 常见问题

### 1. 命令无响应

先发送：

```text
meme_ping
meme帮助
```

如果这两个命令无响应，请检查：

- 插件是否已启用
- AstrBot 是否设置了命令前缀限制
- `force_sharp` 是否启用

### 2. 被动触发没有生效

请确认：

- 关键词是否在消息开头
- 需要文字的模板是否写成了 `关键词 + 空格 + 文本`
- 模板是否被黑名单禁用，或不在白名单内

### 3. 图片模板没有传图也生成了

这是当前设计行为。对于需要图片的模板，插件会在显式图片不足时使用触发者头像补足。

### 4. 请求超时或生成失败

可以尝试：

- 提高 `http_timeout_seconds`
- 提高 `http_retry_times`
- 检查 `base_url` 是否可访问

## 仓库

GitHub:

- [kyuphoenix/astrbot_plugin_meme_generator_api](https://github.com/kyuphoenix/astrbot_plugin_meme_generator_api)
