"""
启动报告 ldmbot 插件

ldmbot 启动完成后，发送启动报告到指定群或私聊。
支持两种发送方式：
1. 通过 ldmbot 框架发送（需要框架已连接平台）
2. 通过 NapCat HTTP API 直接发送（框架未连接时的备选方案）
支持 /重启框架 指令，通过框架内置重启机制重启并记录重启耗时。
"""

import asyncio
import json
import os
from datetime import datetime

import aiohttp
from astrbot.api.all import AstrBotConfig, Context, MessageChain, Star, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import StarTools
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent


class StartupReportPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.record_file = os.path.join(str(StarTools.get_data_dir()), "restart_record.json")

        self.send_target = config.get("send_target", "群聊")
        self.target_id = config.get("target_id", "")
        self.message_template = config.get(
            "message_template",
            "ldmbot 启动完成！\n时间：{time}\n状态：运行中 ✓"
        )
        self.delay_seconds = config.get("delay_seconds", 3)

        # NapCat HTTP API 配置
        self.napcat_url = config.get("napcat_url", "").rstrip("/")
        self.napcat_token = config.get("napcat_token", "")
        self.http_fallback = config.get("http_fallback", True)

        logger.info(
            f"[启动报告] 配置: target={self.send_target}:{self.target_id}, "
            f"delay={self.delay_seconds}s, "
            f"napcat_http={'已配置' if self.napcat_url else '未配置'}, "
            f"http_fallback={'开启' if self.http_fallback else '关闭'}"
        )

    @filter.on_astrbot_loaded()
    async def on_loaded(self):
        """ldmbot 全部加载完成后触发"""
        if self.delay_seconds > 0:
            logger.info(f"[启动报告] 等待 {self.delay_seconds}s 后发送...")
            await asyncio.sleep(self.delay_seconds)

        await self._send_report()

    def _read_restart_record(self) -> dict | None:
        """读取重启记录，返回 None 表示没有记录"""
        try:
            if not os.path.exists(self.record_file):
                return None
            with open(self.record_file, 'r') as f:
                record = json.load(f)
            # 读取后删除记录，避免下次启动重复报告
            os.remove(self.record_file)
            return record
        except Exception as e:
            logger.warning(f"[启动报告] 读取重启记录失败: {e}")
            return None

    def _write_restart_record(self, group_id: int = None, umo: str = None):
        """写入重启记录，可选记录触发重启的群ID和会话来源"""
        try:
            os.makedirs(os.path.dirname(self.record_file), exist_ok=True)
            record = {"restart_time": datetime.now().isoformat()}
            if group_id:
                record["group_id"] = group_id
            if umo:
                record["umo"] = umo
            with open(self.record_file, 'w') as f:
                json.dump(record, f, ensure_ascii=False)
            logger.info(f"[启动报告] 重启记录已写入: {self.record_file}, group_id={group_id}, umo={umo}")
        except Exception as e:
            logger.error(f"[启动报告] 写入重启记录失败: {e}", exc_info=True)

    async def _send_via_napcat_http(self, target_id: str, is_group: bool, message: str) -> bool:
        """通过 NapCat HTTP API 直接发送消息

        Args:
            target_id: 群号或QQ号
            is_group: 是否群聊
            message: 消息内容

        Returns:
            是否发送成功
        """
        if not self.napcat_url:
            logger.warning("[启动报告] NapCat HTTP API 地址未配置，无法使用 HTTP 直发")
            return False

        if is_group:
            endpoint = f"{self.napcat_url}/send_group_msg"
            payload = {"group_id": int(target_id), "message": message}
        else:
            endpoint = f"{self.napcat_url}/send_private_msg"
            payload = {"user_id": int(target_id), "message": message}

        headers = {"Content-Type": "application/json"}
        if self.napcat_token:
            headers["Authorization"] = f"Bearer {self.napcat_token}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("status") == "ok" or data.get("retcode") == 0:
                            logger.info(f"[启动报告] HTTP 直发成功 → {'群' if is_group else '私聊'}:{target_id}")
                            return True
                        else:
                            logger.warning(f"[启动报告] HTTP 直发返回异常: {data}")
                            return False
                    else:
                        text = await resp.text()
                        logger.warning(f"[启动报告] HTTP 直发失败: HTTP {resp.status}, {text[:200]}")
                        return False
        except Exception as e:
            logger.warning(f"[启动报告] HTTP 直发异常: {e}")
            return False

    async def _send_report(self, override_group_id: int = None):
        """发送启动报告，优先使用框架发送，失败时回退到 HTTP 直发

        Args:
            override_group_id: 优先发送到此群ID（来自重启记录），为None时使用配置默认值
        """
        now = datetime.now()
        message = self.message_template
        message = message.replace("{time}", now.strftime("%Y-%m-%d %H:%M:%S"))
        message = message.replace("{date}", now.strftime("%Y-%m-%d"))

        # 检查重启记录
        record = self._read_restart_record()
        actual_target_id = self.target_id
        actual_send_target = self.send_target
        restart_umo = None

        if record and "restart_time" in record:
            try:
                restart_time = datetime.fromisoformat(record["restart_time"])
                elapsed = (now - restart_time).total_seconds()
                restart_line = f"重启耗时：{elapsed:.1f} 秒"
            except Exception:
                restart_line = "重启耗时：计算失败"
            message = message.replace("{restart}", restart_line)
            logger.info(f"[启动报告] 检测到重启记录，{restart_line}")

            # 如果重启记录中有群ID，优先使用
            if record.get("group_id"):
                actual_target_id = str(record["group_id"])
                actual_send_target = "群聊"
                logger.info(f"[启动报告] 使用重启记录中的群ID: {actual_target_id}")
            # 记录了 umo（私聊或群聊的会话来源），优先用于精确发送
            if record.get("umo"):
                restart_umo = record["umo"]
                logger.info(f"[启动报告] 使用重启记录中的会话来源: {restart_umo}")
        else:
            message = message.replace("{restart}", "")

        # override_group_id 优先级最高
        if override_group_id:
            actual_target_id = str(override_group_id)
            actual_send_target = "群聊"

        if not actual_target_id and not restart_umo:
            logger.warning("[启动报告] 未配置目标 ID 且无重启记录，跳过发送")
            return

        # 清理多余的空行
        while "\n\n\n" in message:
            message = message.replace("\n\n\n", "\n\n")
        message = message.strip()

        is_group = actual_send_target == "群聊"

        # 方式0：如果有重启记录的 umo，优先用 send_message 精确发送（支持私聊）
        framework_success = False
        if restart_umo:
            try:
                framework_success = await StarTools.send_message(
                    restart_umo,
                    MessageChain().message(message),
                )
                if framework_success:
                    logger.info(f"[启动报告] 框架发送成功 → {restart_umo}")
                else:
                    logger.warning(f"[启动报告] 框架发送未找到匹配平台: {restart_umo}")
            except Exception as e:
                logger.warning(f"[启动报告] 框架发送失败(umo): {e}")

        # 方式1：通过框架按 type + id 发送
        if not framework_success and actual_target_id:
            msg_type = "GroupMessage" if is_group else "PrivateMessage"
            try:
                await StarTools.send_message_by_id(
                    type=msg_type,
                    id=str(actual_target_id),
                    message_chain=MessageChain().message(message),
                    platform="aiocqhttp"
                )
                framework_success = True
                logger.info(f"[启动报告] 框架发送成功 → {actual_send_target}:{actual_target_id}")
            except Exception as e:
                logger.warning(f"[启动报告] 框架发送失败: {e}")

        # 方式2：框架发送失败且开启 HTTP 回退时，尝试 HTTP 直发
        if not framework_success and self.http_fallback:
            logger.info("[启动报告] 框架发送失败，尝试 NapCat HTTP API 直发...")
            http_success = await self._send_via_napcat_http(actual_target_id, is_group, message)
            if http_success:
                logger.info(f"[启动报告] HTTP 回退发送成功 → {actual_send_target}:{actual_target_id}")
            else:
                logger.error(f"[启动报告] 框架和 HTTP 直发均失败，消息未送达 → {actual_send_target}:{actual_target_id}")
        elif not framework_success:
            logger.error(f"[启动报告] 框架发送失败且 HTTP 回退已关闭，消息未送达")

    @filter.command("重启框架", alias={"重启ldm", "重启ldmbot"})
    async def restart_framework(self, event: AiocqhttpMessageEvent):
        """重启 ldmbot 框架"""
        event.stop_event()

        # 获取当前群ID并写入重启记录
        group_id = None
        try:
            group_id = int(event.get_group_id())
        except Exception:
            pass
        self._write_restart_record(
            group_id=group_id,
            umo=event.unified_msg_origin,
        )

        await event.send(event.plain_result("正在重启框架..."))

        # 延迟一下让消息发出去，再执行重启
        await asyncio.sleep(2)

        await self.context._core_lifecycle.restart()

    @filter.command("测试启动报告")
    async def test_report(self, event: AiocqhttpMessageEvent):
        """手动测试发送启动报告"""
        event.stop_event()
        await self._send_report()
        yield event.plain_result("启动报告已发送，请检查目标位置")

    async def terminate(self) -> None:
        logger.info("[启动报告] 插件已卸载")
