import asyncio
import base64
import json
import os
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from astrbot.api.all import AstrBotConfig, Context, Image, Reply, Star, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import StarTools


class MemeGeneratorApiPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.base_url = self.config.get("base_url", "https://memes.ikechan8370.com").rstrip("/")
        self.reply_result = bool(self.config.get("reply", True))
        self.force_sharp = bool(self.config.get("force_sharp", False))
        self.master_protect_do = bool(self.config.get("master_protect_do", True))
        self.max_file_size_mb = int(self.config.get("max_file_size_mb", 10))
        self.max_file_size_bytes = self.max_file_size_mb * 1024 * 1024
        self.protect_list = set(self.config.get("protect_list", ["lash", "do", "beat_up", "little_do"]))
        self.reply_image_pick_mode = str(self.config.get("reply_image_pick_mode", "all")).lower()
        self.template_filter_mode = str(self.config.get("template_filter_mode", "blacklist")).lower()
        self.template_filter_list = [str(x).strip() for x in self.config.get("template_filter_list", []) if str(x).strip()]

        self.key_map: Dict[str, str] = {}
        self.infos: Dict[str, Any] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache_dir = self._resolve_cache_dir()
        self._infos_file = self._cache_dir / "infos.json"
        self._key_map_file = self._cache_dir / "key_map.json"
        self._list_cache_file = self._cache_dir / "render_list.jpg"
        self._lock = asyncio.Lock()

    def _resolve_cache_dir(self) -> Path:
        try:
            data_dir = StarTools.get_data_dir()
            return data_dir if isinstance(data_dir, Path) else Path(str(data_dir))
        except Exception:
            return Path(os.getcwd()) / "data" / "meme_generator_api"

    async def initialize(self) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        await self._load_or_sync_data()

    async def terminate(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    @filter.command("meme_ping", alias={"meme状态"})
    async def meme_ping(self, event: AstrMessageEvent):
        """检查插件是否正常加载。"""
        yield event.plain_result("表情包插件已就绪")

    @filter.command("meme帮助", alias={"memes帮助", "表情包帮助"})
    async def meme_help(self, event: AstrMessageEvent):
        """
        查看插件帮助信息。

        用法:
        - meme帮助
        """
        yield event.plain_result(
            "使用说明:\n"
            "1) meme列表\n"
            "2) 随机meme\n"
            "3) meme搜索 关键词\n"
            "4) meme更新\n"
            "5) 直接发送: <模板关键词> 文本1/文本2#参数"
        )

    @filter.command("meme更新", alias={"memes更新", "表情包更新"})
    async def meme_update(self, event: AstrMessageEvent):
        """
        更新模板缓存（infos/key_map）。

        用法:
        - meme更新
        """
        yield event.plain_result("正在更新模板缓存...")
        await self._load_or_sync_data(force_remote=True)
        if self._list_cache_file.exists():
            self._list_cache_file.unlink(missing_ok=True)
        yield event.plain_result("模板缓存更新完成")

    @filter.command("meme搜索", alias={"memes搜索", "表情包搜索"})
    async def meme_search(self, event: AstrMessageEvent, keyword: str = ""):
        """
        按关键词搜索可用模板。

        参数:
        - keyword: 搜索词

        用法:
        - meme搜索 摸
        """
        keyword = keyword.strip()
        if not keyword:
            yield event.plain_result("请输入要搜索的关键词")
            return
        hits = [k for k in self.key_map.keys() if keyword in k and self._is_keyword_allowed(k)]
        if not hits:
            yield event.plain_result("未找到匹配关键词")
            return
        yield event.plain_result("搜索结果:\n" + "\n".join([f"{i + 1}. {k}" for i, k in enumerate(hits[:50])]))

    @filter.command("meme列表", alias={"memes列表", "表情包列表"})
    async def meme_list(self, event: AstrMessageEvent):
        """
        获取并发送模板总览图。

        用法:
        - meme列表
        """
        try:
            image_bytes = await self._get_render_list_image()
            yield event.chain_result([Image.fromBytes(image_bytes)])
        except Exception as exc:
            logger.error("meme_list failed: %s", exc, exc_info=True)
            yield event.plain_result(f"获取列表失败: {exc}")

    @filter.command("随机meme", alias={"随机表情包"})
    async def random_meme(self, event: AstrMessageEvent):
        """
        随机选择一个模板并生成图片。

        生成后会额外返回本次使用的模板名称。

        用法:
        - 随机meme
        """
        keys = [
            k for k, v in self.infos.items()
            if v.get("params", {}).get("min_images", 0) == 1
            and v.get("params", {}).get("min_texts", 0) == 0
            and self._is_template_code_allowed(k)
        ]
        if not keys:
            yield event.plain_result("当前无可用随机模板")
            return
        info = self.infos[random.choice(keys)]
        keyword = (info.get("keywords") or [info.get("key")])[0]
        await self._run_meme_generation(event, keyword)
        await event.send(event.plain_result(f"本次模板：{keyword}"))

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听表情包关键词"""
        msg = (event.get_message_str() or "").strip()
        if not msg:
            return
        if msg.startswith(("meme", "memes", "表情包", "随机meme", "meme列表", "meme搜索", "meme更新", "meme帮助")):
            return
        normalized = msg[1:] if msg.startswith("#") else msg
        target = self._find_longest_matching_key(normalized)
        if not target:
            return
        if self.force_sharp and not msg.startswith("#"):
            return
        await self._run_meme_generation(event, normalized)

    async def _run_meme_generation(self, event: AstrMessageEvent, normalized_msg: str) -> None:
        target = self._find_longest_matching_key(normalized_msg)
        if not target:
            return
        target_code = self.key_map.get(target)
        if not target_code or target_code not in self.infos:
            await event.send(event.plain_result("未找到对应模板"))
            return

        tail = normalized_msg[len(target):].strip()
        if tail in {"详情", "帮助"}:
            await event.send(event.plain_result(self._detail_text(target_code)))
            return

        text_part, _, args_part = tail.partition("#")
        info = self.infos[target_code]

        image_ids = await self._prepare_image_ids(event, target_code, info)
        if image_ids is None:
            return

        texts = self._prepare_texts(event, text_part, info)
        if texts is None:
            await event.send(event.plain_result("文本参数不足"))
            return

        options = self._handle_args(target_code, args_part)
        payload = {"images": image_ids, "texts": texts, "options": options}

        async with self._session.post(f"{self.base_url}/memes/{target_code}", json=payload) as resp:
            if resp.status >= 300:
                await event.send(event.plain_result(f"生成失败: {await resp.text()}"))
                return
            result = await resp.json()

        image_id = result.get("image_id")
        if not image_id:
            await event.send(event.plain_result("生成失败: 未返回图片ID"))
            return

        image_bytes = await self._download_image(image_id)
        chain = []
        if self.reply_result and hasattr(event, "message_obj") and getattr(event.message_obj, "message_id", None):
            chain.append(Reply(id=event.message_obj.message_id))
        chain.append(Image.fromBytes(image_bytes))
        await event.send(event.chain_result(chain))

    def _find_longest_matching_key(self, msg: str) -> Optional[str]:
        candidates = [k for k in self.key_map.keys() if msg.startswith(k) and self._is_keyword_allowed(k)]
        return max(candidates, key=len) if candidates else None

    async def _prepare_image_ids(self, event: AstrMessageEvent, target_code: str, info: Dict[str, Any]) -> Optional[List[Dict[str, str]]]:
        params = info.get("params", {})
        max_images = int(params.get("max_images", 0))
        min_images = int(params.get("min_images", 0))
        if max_images <= 0:
            return []

        img_urls = await self._collect_image_urls(event)
        if not img_urls:
            img_urls = [await self._get_avatar_url(event)]
        if len(img_urls) < min_images:
            img_urls = [await self._get_avatar_url(event)] + img_urls

        if self.master_protect_do and target_code in self.protect_list:
            img_urls = await self._apply_master_protect(event, img_urls)

        img_urls = img_urls[:max_images]
        image_ids = []
        for idx, url in enumerate(img_urls):
            image_id = await self._upload_image_from_url(event, url)
            if not image_id:
                return None
            image_ids.append({"name": f"image_{idx}", "id": image_id})
        return image_ids

    async def _collect_image_urls(self, event: AstrMessageEvent) -> List[str]:
        urls: List[str] = []
        segs = event.get_messages()
        for seg in segs:
            if isinstance(seg, Image) and seg.url:
                urls.append(seg.url)
        for seg in segs:
            if isinstance(seg, Reply):
                reply_urls = self._extract_urls_from_reply(seg)
                if self.reply_image_pick_mode == "first":
                    if reply_urls:
                        urls.append(reply_urls[0])
                else:
                    urls.extend(reply_urls)
        for seg in segs:
            if seg.__class__.__name__ == "At" and getattr(seg, "qq", None):
                urls.append(f"https://q1.qlogo.cn/g?b=qq&s=160&nk={seg.qq}")
        return urls

    def _extract_urls_from_reply(self, reply_seg: Reply) -> List[str]:
        urls: List[str] = []
        chain = getattr(reply_seg, "chain", None) or []
        for item in chain:
            if isinstance(item, Image) and item.url:
                urls.append(item.url)
                continue
            for key in ("url", "file"):
                value = getattr(item, key, None)
                if isinstance(value, str) and value.startswith(("http://", "https://")):
                    urls.append(value)
                    break
            item_data = getattr(item, "data", None)
            if isinstance(item_data, dict):
                for key in ("url", "file"):
                    value = item_data.get(key)
                    if isinstance(value, str) and value.startswith(("http://", "https://")):
                        urls.append(value)
                        break
        return urls

    def _prepare_texts(self, event: AstrMessageEvent, text_part: str, info: Dict[str, Any]) -> Optional[List[str]]:
        params = info.get("params", {})
        max_texts = int(params.get("max_texts", 0))
        min_texts = int(params.get("min_texts", 0))
        raw_text = (text_part or "").strip()
        if max_texts == 0:
            return []
        if not raw_text and min_texts > 0:
            raw_text = event.get_sender_name() or ""
        texts = [x.strip() for x in raw_text.split("/") if x.strip()] if raw_text else []
        texts = texts[:max_texts] if max_texts > 0 else texts
        return texts if len(texts) >= min_texts else None

    def _handle_args(self, key: str, args: str) -> Dict[str, Any]:
        args = (args or "").strip()
        if not args:
            return {}
        info = self.infos.get(key, {})
        args_type = info.get("params", {}).get("args_type")
        if not args_type:
            return {}
        args_model = args_type.get("args_model", {})
        parser_options = args_type.get("parser_options", [])
        options: Dict[str, Any] = {}

        for prop, prop_info in args_model.get("properties", {}).items():
            if prop == "user_infos":
                continue
            related = [opt for opt in parser_options if opt.get("dest") == prop]
            if prop_info.get("enum") and related:
                value_map: Dict[str, Any] = {}
                for opt in related:
                    action = opt.get("action", {})
                    if action.get("type") == 0:
                        for name in opt.get("names", []):
                            if name.startswith("--"):
                                value_map[name[2:]] = action.get("value")
                            elif not name.startswith("-"):
                                value_map[name] = action.get("value")
                if args in value_map:
                    options[prop] = value_map[args]
            elif prop_info.get("type") in {"integer", "number"} and args.isdigit():
                options[prop] = int(args)
        return options

    def _detail_text(self, code: str) -> str:
        d = self.infos.get(code, {})
        p = d.get("params", {})
        return (
            f"【代码】{d.get('key', code)}\n"
            f"【名称】{'、'.join(d.get('keywords', []))}\n"
            f"【最大图片】{p.get('max_images', 0)}\n"
            f"【最小图片】{p.get('min_images', 0)}\n"
            f"【最大文本】{p.get('max_texts', 0)}\n"
            f"【最小文本】{p.get('min_texts', 0)}"
        )

    async def _upload_image_from_url(self, event: AstrMessageEvent, url: str) -> Optional[str]:
        async with self._session.get(url) as resp:
            if resp.status >= 300:
                await event.send(event.plain_result(f"下载图片失败: {resp.status}"))
                return None
            data = await resp.read()
        if len(data) >= self.max_file_size_bytes:
            await event.send(event.plain_result(f"图片超过限制，最大 {self.max_file_size_mb}MB"))
            return None
        payload = {"type": "data", "data": base64.b64encode(data).decode("utf-8")}
        async with self._session.post(f"{self.base_url}/image/upload", json=payload) as resp:
            if resp.status >= 300:
                await event.send(event.plain_result(f"上传图片失败: {await resp.text()}"))
                return None
            body = await resp.json()
        return body.get("image_id")

    async def _download_image(self, image_id: str) -> bytes:
        async with self._session.get(f"{self.base_url}/image/{image_id}") as resp:
            resp.raise_for_status()
            return await resp.read()

    async def _get_render_list_image(self) -> bytes:
        if self._list_cache_file.exists():
            return self._list_cache_file.read_bytes()
        async with self._session.post(f"{self.base_url}/tools/render_list", json={"sort_by": "date_created"}) as resp:
            resp.raise_for_status()
            data = await resp.json()
        image_bytes = await self._download_image(data["image_id"])
        self._list_cache_file.write_bytes(image_bytes)
        return image_bytes

    async def _load_or_sync_data(self, force_remote: bool = False) -> None:
        async with self._lock:
            infos = {}
            key_map = {}
            if not force_remote:
                infos = self._read_json(self._infos_file)
                key_map = self._read_json(self._key_map_file)
            if not infos or not key_map:
                infos, key_map = await self._fetch_infos_and_keymap()
                self._write_json(self._infos_file, infos)
                self._write_json(self._key_map_file, key_map)
            self.infos = infos
            self.key_map = key_map

    async def _fetch_infos_and_keymap(self) -> Tuple[Dict[str, Any], Dict[str, str]]:
        infos: Dict[str, Any] = {}
        key_map: Dict[str, str] = {}
        try:
            async with self._session.get(f"{self.base_url}/memes/static/infos.json") as resp:
                if resp.status == 200:
                    infos = await resp.json()
            async with self._session.get(f"{self.base_url}/memes/static/keyMap.json") as resp:
                if resp.status == 200:
                    key_map = await resp.json()
        except Exception:
            logger.warning("静态资源拉取失败，尝试 /meme/infos", exc_info=True)
        if infos and key_map:
            return infos, key_map

        async with self._session.get(f"{self.base_url}/meme/infos") as resp:
            resp.raise_for_status()
            data = await resp.json()
        infos_tmp: Dict[str, Any] = {}
        key_map_tmp: Dict[str, str] = {}
        for meme_info in data:
            key = meme_info.get("key")
            if not key:
                continue
            infos_tmp[key] = meme_info
            for keyword in meme_info.get("keywords", []):
                key_map_tmp[keyword] = key
        return infos_tmp, key_map_tmp

    async def _get_avatar_url(self, event: AstrMessageEvent, user_id: Optional[str] = None) -> str:
        uid = user_id or event.get_sender_id()
        return f"https://q1.qlogo.cn/g?b=qq&s=160&nk={uid}"

    async def _apply_master_protect(self, event: AstrMessageEvent, img_urls: List[str]) -> List[str]:
        masters = {str(x) for x in self.config.get("master_qq_list", [])}
        if not masters:
            return img_urls
        me = await self._get_avatar_url(event)

        def extract_qq(url: str) -> Optional[str]:
            if "q1.qlogo.cn" not in url or "nk=" not in url:
                return None
            return url.split("nk=")[-1]

        if len(img_urls) == 1:
            target = extract_qq(img_urls[0])
            return [me] if target in masters else img_urls

        if len(img_urls) > 1:
            target = extract_qq(img_urls[1])
            if target in masters:
                return [img_urls[1], me]
        return img_urls

    def _is_keyword_allowed(self, keyword: str) -> bool:
        code = self.key_map.get(keyword)
        return self._is_template_code_allowed(code) if code else False

    def _is_template_code_allowed(self, code: str) -> bool:
        info = self.infos.get(code, {})
        keywords = [str(x) for x in info.get("keywords", [])]
        haystack = [code] + keywords

        if self.template_filter_mode == "whitelist":
            if not self.template_filter_list:
                return False
            return any(any(token in name for name in haystack) for token in self.template_filter_list)

        if not self.template_filter_list:
            return True
        return not any(any(token in name for name in haystack) for token in self.template_filter_list)

    @staticmethod
    def _read_json(file_path: Path) -> Dict[str, Any]:
        if not file_path.exists():
            return {}
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @staticmethod
    def _write_json(file_path: Path, data: Dict[str, Any]) -> None:
        file_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
