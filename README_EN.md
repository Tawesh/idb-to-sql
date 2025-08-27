# IBD Data Recovery Tool For MySQL

This is a comprehensive toolkit for MySQL database IBD file data recovery, supporting MySQL 5.7 and 8.0 versions. The tool can recover data from corrupted IBD files and provides both graphical interface and command-line usage options.

## Features

- 🔧 **IBD File Parsing**: Parse MySQL 5.7/8.0 IBD files
- 📊 **Data Recovery**: Recover data from corrupted IBD files
- 🗑️ **Deleted Data Recovery**: Recover data marked as deleted
- 🏗️ **DDL Generation**: Automatically generate table structure (CREATE TABLE statements)
- 💾 **SQL Export**: Export recovered data as INSERT statements
- 🖥️ **Graphical Interface**: User-friendly GUI interface
- ⚡ **Parallel Processing**: Support multi-process and multi-threading
- 🔐 **Encryption Support**: Support encrypted IBD files
- 📁 **Partition Table Support**: Support partition table data recovery
- 🚀 **Batch Processing**: Support batch processing of multiple IBD files

## Project Structure

```
src/
├── app.py                    # GUI main program
├── ibd_to_sql.exe           # Core executable for IBD to SQL conversion
├── icon.ico                 # Application icon
└── ibd2sql-main/            # Core parsing module
    ├── main.py              # Command-line entry point
    ├── ibd2sql/             # Core parsing library
    │   ├── ibd2sql.py       # Main parsing class
    │   ├── innodb_page*.py  # InnoDB page parsing modules
    │   └── ...              # Other parsing modules
    └── docs/                # Documentation directory
        └── USAGE.md         # Detailed usage instructions
```

## Requirements

- Python 3.6+
- MySQL 5.7+ or MySQL 8.0+
- Windows Operating System

### Python Dependencies

**Method 1: Install using requirements.txt (Recommended)**
```bash
pip install -r requirements.txt
```

**Method 2: Manual installation of core dependencies**
```bash
pip install pymysql chardet lz4 pycryptodome
```

**Note**: tkinter usually comes with Python. If you encounter import errors, please install the appropriate tkinter package for your operating system.

## Usage

### 1. Graphical Interface (Recommended)

#### Starting the GUI Program

```bash
python app.py
```

#### Operation Steps

1. **Select Input Folder**: Click the "Browse" button to select the folder containing .ibd files
2. **Configure Database Connection**: Fill in MySQL database connection information
   - Host Address (default: localhost)
   - Port (default: 3306)
   - Username
   - Password
   - Database Name
3. **Set Parallel Parameters**: 
   - Process Count: Recommended to set to CPU core count
   - Thread Count: Recommended to set to 2-4
4. **Start Processing**: Click the "Start Processing" button
5. **View Results**: Check processing progress and results in the log area

#### Processing Workflow

The program automatically executes the following steps:
1. Scan all .ibd files in the input folder
2. Use ibd_to_sql.exe to convert each .ibd file to .sql file
3. Automatically execute the generated SQL files to import data into the specified MySQL database
4. Display processing result statistics

### 2. Command Line Usage

#### Basic Syntax

```bash
python ibd2sql-main/main.py [options] IBD_FILE_PATH
```

#### Common Command Examples

**1. Generate Table Structure (DDL)**
```bash
python main.py table.ibd --ddl
```

**2. Recover Data (DML)**
```bash
python main.py table.ibd --sql
```

**3. Generate Both DDL and DML**
```bash
python main.py table.ibd --ddl --sql
```

**4. Recover Deleted Data**
```bash
python main.py table.ibd --sql --delete
```

**5. Partition Table Recovery**
```bash
python main.py table#p#p1.ibd --sql --sdi-table table#p#p0.ibd
```

**6. MySQL 5.7 File Recovery**
```bash
python main.py table.ibd --sql --mysql5 --sdi-table metadata.ibd
```

#### Main Parameters

| Parameter | Description |
|-----------|-------------|
| `--ddl` | Output table structure (CREATE TABLE statement) |
| `--sql` | Output data (INSERT statements) |
| `--delete` | Recover data marked as deleted |
| `--complete-insert` | Generate complete INSERT statements (with field names) |
| `--multi-value` | Generate one INSERT statement per page |
| `--replace` | Use REPLACE INTO instead of INSERT INTO |
| `--table TABLE_NAME` | Specify table name |
| `--schema SCHEMA_NAME` | Specify database name |
| `--sdi-table SDI_FILE` | Specify metadata file (for partition tables or 5.7) |
| `--mysql5` | Mark as MySQL 5.7 file |
| `--limit N` | Limit output rows |
| `--force` | Force parsing (ignore error pages) |
| `--debug` | Enable debug mode |

## Use Cases

### 1. Database Crash Recovery
When MySQL database cannot start normally due to hardware failure, file system corruption, etc., this tool can directly recover data from IBD files.

### 2. Accidental Data Deletion Recovery
When data is accidentally deleted but IBD files still exist, you can recover data marked as deleted.

### 3. Lost Table Structure
When you only have IBD files but no table structure, you can extract table structure information from IBD files.

### 4. Cross-Version Data Migration
During MySQL version upgrades, if compatibility issues occur, this tool can be used to extract data.

## Important Notes

1. **Backup Important**: Always backup original IBD files before performing data recovery operations
2. **Permission Requirements**: Ensure sufficient file system permissions to read IBD files
3. **Memory Usage**: Processing large IBD files may require significant memory
4. **MySQL Versions**: IBD file formats may differ between MySQL versions, use appropriate parameters
5. **Partition Tables**: Partition tables require specifying metadata files for correct parsing
6. **Encrypted Files**: Encrypted IBD files require providing corresponding key files

## Troubleshooting

### Common Issues

**1. "Unknown database" Error**
- Solution: Ensure target database exists, or the program will create it automatically

**2. IBD File Parsing Failure**
- Check if the file is corrupted
- Try using the `--force` parameter
- Confirm MySQL version and use appropriate parameters

**3. Partition Table Parsing Failure**
- Ensure using `--sdi-table` parameter to specify metadata file
- Check if the metadata file is correct

**4. Out of Memory**
- Reduce the number of parallel processes and threads
- Process large files in batches

## Technical Support

If you encounter problems during use, please check:
1. Whether Python version and dependencies are correctly installed
2. Whether IBD files are complete and readable
3. Whether MySQL database connection is normal
4. Whether system resources are sufficient

## License

This project is released under an open source license. For specific license information, please check the LICENSE file in the project root directory.

---

**Disclaimer**: This tool is intended for data recovery purposes only. Please ensure important data is backed up before use. The author is not responsible for any data loss or damage caused by using this tool.