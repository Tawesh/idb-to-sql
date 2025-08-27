# IBD数据恢复工具 For MySQL

[English](README_EN.md) | 中文

这是一个用于MySQL数据库IBD文件数据恢复的工具集，支持MySQL 5.7和8.0版本。该工具可以从损坏的IBD文件中恢复数据，并提供图形界面和命令行两种使用方式。

## 功能特性

- 🔧 **IBD文件解析**: 解析MySQL 5.7/8.0的IBD文件
- 📊 **数据恢复**: 从损坏的IBD文件中恢复数据
- 🗑️ **删除数据恢复**: 恢复被标记为删除的数据
- 🏗️ **DDL生成**: 自动生成表结构(CREATE TABLE语句)
- 💾 **SQL导出**: 将恢复的数据导出为INSERT语句
- 🖥️ **图形界面**: 提供友好的GUI界面
- ⚡ **并行处理**: 支持多进程和多线程并行处理
- 🔐 **加密支持**: 支持加密的IBD文件
- 📁 **分区表支持**: 支持分区表的数据恢复
- 🚀 **批量处理**: 支持批量处理多个IBD文件

## 项目结构

```
src/
├── app.py                    # GUI主程序
├── ibd_to_sql.exe           # IBD转SQL的核心可执行文件
├── icon.ico                 # 应用图标
└── ibd2sql-main/            # 核心解析模块
    ├── main.py              # 命令行入口
    ├── ibd2sql/             # 核心解析库
    │   ├── ibd2sql.py       # 主解析类
    │   ├── innodb_page*.py  # InnoDB页面解析模块
    │   └── ...              # 其他解析模块
    └── docs/                # 文档目录
        └── USAGE.md         # 详细使用说明
```

## 环境要求

- Python 3.6+
- MySQL 5.7+ 或 MySQL 8.0+
- Windows操作系统

### Python依赖包

**方法一：使用requirements.txt安装（推荐）**
```bash
pip install -r requirements.txt
```

**方法二：手动安装核心依赖**
```bash
pip install pymysql chardet lz4 pycryptodome
```

**注意**: tkinter通常随Python自带，如果遇到导入错误，请根据您的操作系统安装相应的tkinter包。

## 使用方法

### 1. 图形界面使用(推荐)

#### 启动GUI程序

```bash
python app.py
```

#### 操作步骤

1. **选择输入文件夹**: 点击"浏览"按钮，选择包含.ibd文件的文件夹
2. **配置数据库连接**: 填写MySQL数据库连接信息
   - 主机地址 (默认: localhost)
   - 端口 (默认: 3306)
   - 用户名
   - 密码
   - 数据库名
3. **设置并行参数**: 
   - 进程数: 建议设置为CPU核心数
   - 线程数: 建议设置为2-4
4. **开始处理**: 点击"开始处理"按钮
5. **查看结果**: 在日志区域查看处理进度和结果

#### 处理流程

程序会自动执行以下步骤：
1. 扫描输入文件夹中的所有.ibd文件
2. 使用ibd_to_sql.exe将每个.ibd文件转换为.sql文件
3. 自动执行生成的SQL文件，将数据导入到指定的MySQL数据库
4. 显示处理结果统计

### 2. 命令行使用

#### 基本语法

```bash
python ibd2sql-main/main.py [选项] IBD文件路径
```

#### 常用命令示例

**1. 生成表结构(DDL)**
```bash
python main.py table.ibd --ddl
```

**2. 恢复数据(DML)**
```bash
python main.py table.ibd --sql
```

**3. 同时生成DDL和DML**
```bash
python main.py table.ibd --ddl --sql
```

**4. 恢复被删除的数据**
```bash
python main.py table.ibd --sql --delete
```

**5. 分区表恢复**
```bash
python main.py table#p#p1.ibd --sql --sdi-table table#p#p0.ibd
```

**6. MySQL 5.7文件恢复**
```bash
python main.py table.ibd --sql --mysql5 --sdi-table metadata.ibd
```

#### 主要参数说明

| 参数 | 说明 |
|------|------|
| `--ddl` | 输出表结构(CREATE TABLE语句) |
| `--sql` | 输出数据(INSERT语句) |
| `--delete` | 恢复被标记为删除的数据 |
| `--complete-insert` | 生成完整的INSERT语句(包含字段名) |
| `--multi-value` | 每页数据生成一个INSERT语句 |
| `--replace` | 使用REPLACE INTO代替INSERT INTO |
| `--table TABLE_NAME` | 指定表名 |
| `--schema SCHEMA_NAME` | 指定数据库名 |
| `--sdi-table SDI_FILE` | 指定元数据文件(用于分区表或5.7) |
| `--mysql5` | 标记为MySQL 5.7文件 |
| `--limit N` | 限制输出行数 |
| `--force` | 强制解析(忽略错误页面) |
| `--debug` | 启用调试模式 |

## 使用场景

### 1. 数据库崩溃恢复
当MySQL数据库因为硬件故障、文件系统损坏等原因无法正常启动时，可以使用此工具直接从IBD文件中恢复数据。

### 2. 误删数据恢复
当数据被误删除但IBD文件还存在时，可以恢复被标记为删除的数据。

### 3. 表结构丢失
当只有IBD文件但没有表结构时，可以从IBD文件中提取表结构信息。

### 4. 跨版本数据迁移
在MySQL版本升级过程中，如果遇到兼容性问题，可以使用此工具提取数据。

## 注意事项

1. **备份重要**: 在进行数据恢复操作前，请务必备份原始IBD文件
2. **权限要求**: 确保有足够的文件系统权限读取IBD文件
3. **内存使用**: 处理大型IBD文件时可能需要较多内存
4. **MySQL版本**: 不同MySQL版本的IBD文件格式可能有差异，请使用对应的参数
5. **分区表**: 分区表需要指定元数据文件才能正确解析
6. **加密文件**: 加密的IBD文件需要提供相应的密钥文件

## 故障排除

### 常见问题

**1. "Unknown database" 错误**
- 解决方案: 确保目标数据库存在，或者程序会自动创建

**2. IBD文件解析失败**
- 检查文件是否损坏
- 尝试使用 `--force` 参数
- 确认MySQL版本并使用相应参数

**3. 分区表解析失败**
- 确保使用了 `--sdi-table` 参数指定元数据文件
- 检查元数据文件是否正确

**4. 内存不足**
- 减少并行进程数和线程数
- 分批处理大型文件

## 技术支持

如果在使用过程中遇到问题，请检查：
1. Python版本和依赖包是否正确安装
2. IBD文件是否完整且可读
3. MySQL数据库连接是否正常
4. 系统资源是否充足

## 许可证

本项目基于开源许可证发布，具体许可证信息请查看项目根目录的LICENSE文件。

---

**免责声明**: 此工具仅用于数据恢复目的，使用前请确保已备份重要数据。作者不对使用此工具造成的任何数据丢失或损坏承担责任。