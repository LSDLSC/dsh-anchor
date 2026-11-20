# 事故复盘 001：会话列表被清空三次

## 症状

UI 里只剩 3 条会话，磁盘上有 9～10 个会话目录，文件完好。

## 第一次：没登记

DSH 的会话索引只来自 `storages/workspace.json` 的 `tables.workspaces[].sessionIds`，
不扫描 `sessions/` 目录。工作区搬迁、手动拷贝会话目录之后，注册表里没有对应 id，
UI 就不显示。

**修法**：补登记。但补完立刻遇到第二次。

## 第二次：内存快照覆盖

同一份 storage 被两个宿主进程使用（不同端口、不同 profile），各自在内存里维护
sessionIds 清单，退出时整体写回。A 进程写 9 条，B 进程写回它内存里的 3 条，
注册表被覆盖。

**修法**：
- 只留一个宿主；
- 守卫脚本在写回前比对磁盘，补漏；
- 补登记后立刻重启宿主，避免运行中的旧实例再把旧清单写回。

## 第三次：类型错误

注册表的 `updatedAt` 被旧版本或外部脚本写成毫秒数字 `1794152228979`。
新版 schema 是 `updatedAt: z.string()`，于是：

```
DomainError: stored record '...' in table 'workspaces' does not match its schema
ZodError: expected string, received number  path ["updatedAt"]
```

整个 workspace 域加载失败，列表空白。

**修法**：守卫把 12 位以上的数字时间戳转成 ISO 字符串。

## 三条可复用的结论

1. **文件在 ≠ 数据在**。索引、格式、schema 任一环坏掉，用户体验上就是"数据丢了"。
2. **多进程共写同一份状态，必须假设会互相覆盖**。要么单写者，要么合并策略，要么守卫。
3. **格式错误要从加载日志里找**，`expected string, received number` 比"列表空白"信息量大得多。
