# graveyard/ · 墓地

被"埋葬"的记忆条目放这里。它们**物理上还在，但不参与检索**。

## 三条语义

1. **移入不销毁**：`memory bury` 只是把条目从 `facts.jsonl` 挪到
   `graveyard/YYYY-MM/facts-YYYY-MM.jsonl`，原文一个字都不改。
2. **退出检索**：`memory search` 不扫墓地，旧内容不再挤占上下文。
3. **可恢复**：`memory restore --id <id>` 原样搬回 `facts.jsonl`。

## 目录结构

```
graveyard/
├── index.json                      # 索引：每条被埋记忆的 id / 文件 / 时间 / 摘要
├── README.md                       # 本文件
└── YYYY-MM/
    └── facts-YYYY-MM.jsonl         # 当月被埋的条目正文
```

`index.json` 只存指针和摘要，正文永远在月份文件里——这样索引坏了也能靠文件重建。

## 什么时候才真的"焚毁"

只有两种情况该动第三级（清墓地 + 清备份）：**明确的敏感信息**，或者本人明确要求。
执行前要问，并且先备份。其余情况停在第 1、2 级就够了：降权或移入墓地，
都是可逆的，半年后想起来还能捞回来。

## 常用命令

```bash
memory graveyard            # 列出现有墓地条目
memory bury --id <id>       # 把某条移进墓地
memory bury --query 关键词   # 按关键词批量移入
memory restore --id <id>    # 捞回
```

墓地本身也可以整目录备份：它就是个普通文件夹，不需要特殊工具。
