# astrbot_plugin_meme_generator_api

基于 [https://github.com/ikechan8370/yunzai-meme](https://github.com/ikechan8370/yunzai-meme) 迁移而来
基于 [meme-generator](https://github.com/MemeCrafters/meme-generator-rs) API 的 AstrBot 表情包插件。

本插件支持：
- 拉取后端模板并本地缓存
- 关键词直接触发生成表情包
- 随机生成、模板搜索、模板列表
- 引用消息取图、@用户头像取图
- 黑白名单过滤模板
- 主人保护逻辑（可配置）

## 功能特点

- 默认后端：`https://memes.ikechan8370.com`(从[https://github.com/ikechan8370/yunzai-meme](https://github.com/ikechan8370/yunzai-meme)获取)
- 自动缓存模板：`infos.json`、`key_map.json`
- 支持命令和关键词两种触发方式
- 支持模板参数（`#参数`）透传
- 支持图片大小限制

## 安装

将本插件目录放入 AstrBot 插件目录后，在管理面板安装/启用。

目录结构示例：

```text
astrbot_plugin_meme_generator_api/
├─ main.py
├─ metadata.yaml
├─ _conf_schema.json
├─ requirements.txt
└─ astrbot_plugin_meme_generator_api.png
```

## 指令

- `meme_ping`：检查插件是否可用
- `meme帮助`：查看帮助
- `meme列表`：查看模板列表图
- `随机meme`：随机生成一张表情包（会附带模板名称）
- `meme搜索 <关键词>`：搜索模板关键词
- `meme更新`：刷新模板缓存

另外也可直接通过关键词触发：

```text
<模板关键词> 文本1/文本2#参数
```

示例：

```text
摸 文本A/文本B
#摸 文本A/文本B#右
```

## 模板与数据来源

插件启动后会按以下顺序获取模板数据：

1. 本地缓存：
   - `infos.json`
   - `key_map.json`
2. 后端静态接口：
   - `GET /memes/static/infos.json`
   - `GET /memes/static/keyMap.json`
3. 回退接口：
   - `GET /meme/infos`

说明：模板本质来自后端，本地仅做缓存。

## 配置项

在 AstrBot 插件配置页可设置：

- `base_url`：Meme 服务基础地址
- `reply`：发送结果时是否引用原消息
- `force_sharp`：是否必须使用 `#关键词` 触发
- `reply_image_pick_mode`：引用消息取图策略
  - `all`：取全部图片
  - `first`：仅取第一张
- `template_filter_mode`：模板过滤模式
  - `blacklist`：黑名单（留空=启用全部）
  - `whitelist`：白名单（留空=禁用全部）
- `template_filter_list`：模板匹配列表（按模板 code / 关键词子串匹配）
- `master_protect_do`：主人保护开关
- `protect_list`：启用主人保护的模板 code 列表
- `master_qq_list`：主人 QQ 列表
- `max_file_size_mb`：输入图片大小限制（MB）

## 图片来源优先级

生成时，图片来源按以下逻辑收集：

1. 当前消息中的图片
2. 引用消息中的图片（由 `reply_image_pick_mode` 控制取一张或全部）
3. `@`用户头像
4. 发送者头像（兜底）

## 兼容说明

- 依赖 `aiohttp`（已在 `requirements.txt`）
- `astrbot.*` 模块由 AstrBot 运行时提供

## 常见问题

### 1) 插件加载成功但命令无响应

请先发送：

```text
meme_ping
meme帮助
```

若仍无响应，检查：
- 插件是否启用
- 是否有命令前缀限制
- `template_filter_mode=whitelist` 且 `template_filter_list` 为空（会禁用全部模板）

### 2) 生成失败/超时

- 检查 `base_url` 是否可访问
- 后端服务是否正常
- 输入图片是否超过 `max_file_size_mb`
