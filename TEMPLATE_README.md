# XHS Automation 模板项目

这是一个去除个人敏感信息的模板项目，用于作为开源或共享的基础。

## 使用方法

1. **克隆或拷贝此项目**
2. **创建虚拟环境**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **配置环境变量**
   ```bash
   cp .env .env.local
   # 编辑 .env.local 填入自己的 API Keys
   ```
4. **运行配置向导**
   ```bash
   python3 main.py setup
   ```

## 已清理的内容

- ❌ API Keys (需要自行配置)
- ❌ Cookies 数据
- ❌ 数据库
- ❌ 个人图片
- ❌ 个人笔记草稿
- ❌ 虚拟环境

## 项目结构

```
xhs-automation/
├── config/              # 配置文件模板
├── content/drafts/      # 笔记草稿模板
├── images/              # 图片目录 (空)
├── data/                # 数据目录 (空)
├── scripts/             # 脚本
├── src/                 # 源代码
├── main.py              # CLI 入口
├── manage.sh            # 管理脚本
└── .env                 # 环境变量模板
```

## 配置文件说明

所有配置文件中的敏感信息已替换为占位符，请参考各配置文件中的注释进行配置。
