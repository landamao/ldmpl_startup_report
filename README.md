# 启动报告 (Startup Report)

> ldmbot 启动完成后自动发送启动报告，支持框架发送和 NapCat HTTP API 直发双通道。
>
> 本插件仅兼容[ldmbot](https://github.com/landamao/ldm_AstrBot) 版本v4.26.27以上

## 功能

- **自动发送启动报告** — ldmbot 全部加载完成后，向指定群聊或私聊发送启动通知
- **双通道发送** — 优先通过 ldmbot 框架发送，失败时自动回退到 NapCat HTTP API 直发
- **重启耗时统计** — 通过 `/重启框架` 指令重启后，下次启动报告自动包含重启耗时
- **消息模板** — 支持 `{time}` `{date}` `{restart}` 占位符自定义消息内容
- **发送延迟** — 可配置启动后延迟几秒再发送，避免初始化未完成时发送失败

## 指令

| 指令 | 别名 | 说明 |
| --- | --- | --- |
| `/重启框架` | `/重启ldm` `/重启ldmbot` | 重启 ldmbot 框架，记录重启耗时 |
| `/测试启动报告` | — | 手动触发一次启动报告发送，用于测试配置 |

## 配置

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| 发送目标 | 选项 | 群聊 | 启动报告发到群聊还是私聊 |
| 目标ID | 字符串 | 空 | 群号或QQ号，重启时自动记录群ID |
| 消息模板 | 文本 | `ldmbot 启动完成！\n时间：{time}\n状态：运行中 ✓\n{restart}` | 支持 {time} {date} {restart} |
| 延迟发送 | 整数 | 0 | 启动后延迟几秒发送 |
| NapCat地址 | 字符串 | 空 | 如 `http://127.0.0.1:5700` |
| API Token | 字符串 | 空 | NapCat 的 token，没设置可留空 |
| HTTP回退 | 布尔 | true | 框架发送失败时用 HTTP 直发 |

## 发送机制

报告发送按优先级依次尝试：

1. **重启记录的会话来源 (UMO)** — 如果通过 `/重启框架` 触发，优先发回触发重启的会话
2. **框架发送** — 通过 ldmbot 框架按群/私聊类型 + 目标ID发送
3. **HTTP 回退** — 框架发送失败且开启 HTTP 回退时，通过 NapCat HTTP API 直接发送

## 安装

1. 打开 ldmbot WebUI → 插件 → ldm 插件
2. 点击右下角 ➕ 号 → 从链接安装
3. 填入仓库地址：`https://github.com/landamao/ldmpl_startup_report`
4. 点「测试代理」确认网络可达（国内网络环境需要代理）
5. 点「安装」

## 信息

- **作者**: 纳西妲
- **版本**: v1.1.0
- **仓库**: https://github.com/landamao/ldmpl_startup_report
- **适用平台**: aiocqhttp (OneBot)
