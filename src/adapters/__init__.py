"""注册表适配器：把"注册表在哪、怎么读写"与"守卫怎么修"分开。

核心（registry_guard）只依赖这个模块暴露的协议：

    load()            -> dict          读注册表（已做格式修正）
    registered(data)  -> list[str]     注册表里已登记的 id
    disk_ids()        -> list[str]     磁盘上实际存在的 id
    merge(data, ids)  -> list[str]     把缺失的并进 data，返回新增
    save(data)        -> str           写回，返回备份路径
    registry_path()   -> Path          用于加锁/判断存在

换成别的 agent / 别的文件格式，只需实现一个新的 adapter。
"""
