# astrbot_plugin_meme_generator_api

基于远程 memes API 的 AstrBot 表情包生成插件。

## 模板来源说明
- 模板元数据（`infos`、`key_map`）优先从本地缓存读取。
- 本地缓存不存在或你执行 `meme更新` 时，会从后端拉取：
  - `GET /memes/static/infos.json`
  - `GET /memes/static/keyMap.json`
- 如果静态接口失败，会回退到：
  - `GET /meme/infos`
- 因此模板列表本质上来自后端，并在本地做缓存。

## 指令
- `meme_ping`
- `meme帮助`
- `meme列表`
- `随机meme`
- `meme搜索 <关键词>`
- `meme更新`
- `<模板关键词> 文本1/文本2#参数`

## 配置项
- `base_url`：Meme 服务基础地址
- `reply`：发送结果时是否引用原消息
- `force_sharp`：是否必须使用 `#关键词` 触发
- `reply_image_pick_mode`：引用消息取图策略（`all`/`first`）
- `template_filter_mode`：模板过滤模式（`blacklist`/`whitelist`）
- `template_filter_list`：模板匹配列表（按 code/关键词子串匹配）
- `master_protect_do`：主人保护开关
- `protect_list`：启用主人保护的模板代码列表
- `master_qq_list`：主人 QQ 列表
- `max_file_size_mb`：源图片大小限制（MB）
