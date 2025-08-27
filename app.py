import os
import subprocess
import sys

import pymysql
import chardet
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import datetime
from multiprocessing import Pool, cpu_count, Manager
from functools import partial
from queue import Queue


def resource_path(relative_path):
    """
    获取资源文件的路径，兼容打包前和打包后
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


favicon = resource_path("icon.ico")

idb_exe = resource_path("ibd_to_sql.exe")
def on_button_click():
    subprocess.Popen([idb_exe])   # 打开真正的 ibd_to_sql.exe

def execute_sql_command(input_file, output_file):
    """执行 ibd_to_sql 命令（确保路径格式正确）"""
    # 标准化输入输出文件路径
    input_file = os.path.normpath(input_file)
    output_file = os.path.normpath(output_file)

    # 构建命令（路径用双引号包裹，避免路径含空格等特殊字符）
    command = [idb_exe,
               f'"{input_file}"',  # 路径带引号，处理含空格的情况
               '--ddl',
               '--sql',
               '>',
               f'"{output_file}"'
               ]
    # 拼接为字符串命令（因涉及重定向>，用字符串形式更稳妥）
    command_str = ' '.join(command)

    # 执行命令
    try:
        subprocess.run(command_str, check=True, shell=True)
        return True, f"SQL 输出已保存到 {output_file}"
    except subprocess.CalledProcessError as e:
        return False, f"执行命令时出错: {e}"
    except Exception as e:
        return False, f"发生了其他错误: {e}"


def _split_sql_statements(sql):
    """
    使用更健壮的方法分割SQL语句，处理引号和注释中的分号
    """
    statements = []
    current_statement = ""
    in_quote = None
    in_comment = False
    quote_escape = False

    for char in sql:
        # 处理转义字符
        if in_quote and char == '\\':
            quote_escape = not quote_escape  # 反转义状态
        else:
            quote_escape = False

        # 处理注释
        if not in_quote and not quote_escape:
            if char == '-' and len(sql) > sql.index(char) + 1 and sql[sql.index(char) + 1] == '-':
                in_comment = True
            elif char == '\n' and in_comment:
                in_comment = False
                char = ' '  # 将注释替换为空格
            elif char == '/' and len(sql) > sql.index(char) + 1 and sql[sql.index(char) + 1] == '*':
                in_comment = True
                char = ' '  # 忽略注释开始
            elif char == '*' and len(sql) > sql.index(char) + 1 and sql[sql.index(char) + 1] == '/' and in_comment:
                in_comment = False
                char = ' '  # 忽略注释结束，继续处理下一个字符
                continue

        if in_comment:
            continue  # 忽略注释内容

        # 处理引号
        if char in ["'", '"', '`'] and not quote_escape:
            if in_quote == char:
                in_quote = None
            elif not in_quote:
                in_quote = char

        # 处理语句分隔符
        if char == ';' and not in_quote:
            statements.append(current_statement.strip())
            current_statement = ""
        else:
            current_statement += char

    # 添加最后一个语句（如果有）
    if current_statement.strip():
        statements.append(current_statement.strip())

    return statements


def _execute_sequentially(host, port, user, password, db, statements):
    """顺序执行SQL语句"""
    global connection
    try:
        # 尝试连接数据库，如果不存在则创建
        try:
            connection = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=db,
                charset='utf8mb4',
                autocommit=False
            )
        except pymysql.err.OperationalError as e:
            if e.args[0] == 1049:  # Unknown database error
                # 创建数据库
                create_conn = pymysql.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    charset='utf8mb4'
                )
                with create_conn.cursor() as create_cursor:
                    create_cursor.execute(
                        f"CREATE DATABASE IF NOT EXISTS {db} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                create_conn.close()

                # 再次尝试连接
                connection = pymysql.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    database=db,
                    charset='utf8mb4',
                    autocommit=False
                )
            else:
                raise

        with connection.cursor() as cursor:
            for stmt in statements:
                if not stmt.strip():
                    continue

                try:
                    cursor.execute(stmt)
                except Exception as e:
                    error_msg = f"语句执行失败: {str(e)}"
                    error_stmt = f"错误语句: {stmt[:500]}..."
                    raise Exception(f"{error_msg}\n{error_stmt}")

        connection.commit()
        return True, "语句执行成功"
    except Exception as e:
        if 'connection' in locals():
            connection.rollback()
        return False, str(e)
    finally:
        if 'connection' in locals():
            connection.close()


def _execute_in_parallel(host, port, user, password, db, statements, max_threads):
    """使用多线程并行执行SQL语句"""
    # 创建工作队列
    work_queue = Queue()
    for stmt in statements:
        work_queue.put(stmt)

    # 创建结果队列
    result_queue = Queue()

    # 创建并启动工作线程
    threads = []

    def _thread_worker(work_queue, result_queue):
        """工作线程函数，从队列中获取SQL语句并执行"""
        try:
            connection = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=db,
                charset='utf8mb4',
                autocommit=True  # 每个INSERT语句单独提交
            )

            with connection.cursor() as cursor:
                while not work_queue.empty():
                    try:
                        stmt = work_queue.get(block=False)
                    except:
                        break

                    try:
                        cursor.execute(stmt)
                        result_queue.put((True, stmt, None))
                    except Exception as e:
                        result_queue.put((False, stmt, str(e)))
                    finally:
                        work_queue.task_done()

        except Exception as e:
            result_queue.put((False, "", f"线程执行出错: {str(e)}"))
        finally:
            if 'connection' in locals():
                connection.close()

    for _ in range(min(max_threads, len(statements))):
        thread = threading.Thread(
            target=_thread_worker,
            args=(work_queue, result_queue)
        )
        thread.daemon = True
        thread.start()
        threads.append(thread)

    # 等待所有线程完成
    for thread in threads:
        thread.join()

    # 处理结果
    successes = 0
    failures = 0
    error_messages = []

    while not result_queue.empty():
        success, stmt, error = result_queue.get()
        if success:
            successes += 1
        else:
            failures += 1
            error_messages.append(f"失败语句: {stmt[:200]}... 错误: {error}")

    if failures > 0:
        return False, f"并行执行完成: 成功={successes}, 失败={failures}\n" + "\n".join(error_messages[:5])

    return True, f"并行执行完成: 成功={successes}, 失败={failures}"


def execute_sql_file(host, port, user, password, db, sql_file_path, max_threads, log_queue=None):
    """执行SQL文件（确保路径格式正确）"""
    # 标准化SQL文件路径
    sql_file_path = os.path.normpath(sql_file_path)
    if log_queue:
        log_queue.put(f"开始执行SQL文件: {sql_file_path}")

    try:
        # 读取并解析SQL文件
        with open(sql_file_path, 'rb') as f:
            raw_data = f.read()

        result = chardet.detect(raw_data)
        encoding = result['encoding'] or 'utf-8'
        if log_queue:
            log_queue.put(f"检测到文件编码: {encoding}")

        sql = raw_data.decode(encoding)

        statements = _split_sql_statements(sql)
        if not statements:
            if log_queue:
                log_queue.put("SQL文件中没有可执行的语句")
            return True, "SQL文件中没有可执行的语句"

        # 分类语句：将INSERT语句与其他语句分开
        insert_statements = []
        other_statements = []

        for stmt in statements:
            if stmt.upper().startswith('INSERT '):
                insert_statements.append(stmt)
            else:
                other_statements.append(stmt)

        if log_queue:
            log_queue.put(f"文件包含 {len(other_statements)} 条非INSERT语句和 {len(insert_statements)} 条INSERT语句")

        # 先执行非INSERT语句（如CREATE TABLE等）
        if other_statements:
            success, message = _execute_sequentially(host, port, user, password, db, other_statements)
            if not success:
                if log_queue:
                    log_queue.put(message)
                return False, message

        # 再执行INSERT语句
        if insert_statements:
            if len(insert_statements) > 10 and max_threads > 1:  # 只有当INSERT语句足够多时才使用并行
                if log_queue:
                    log_queue.put(f"使用 {max_threads} 个线程并行执行 {len(insert_statements)} 条INSERT语句")
                success, message = _execute_in_parallel(host, port, user, password, db, insert_statements, max_threads)
                if not success:
                    if log_queue:
                        log_queue.put(message)
                    return False, message
            else:
                # 语句较少时，顺序执行更简单
                success, message = _execute_sequentially(host, port, user, password, db, insert_statements)
                if not success:
                    if log_queue:
                        log_queue.put(message)
                    return False, message

        if log_queue:
            log_queue.put(f"SQL 文件 '{sql_file_path}' 执行成功!")
        return True, f"SQL 文件 '{sql_file_path}' 执行成功!"

    except Exception as e:
        error_msg = f"执行 SQL 文件时发生错误: {str(e)}"
        if log_queue:
            log_queue.put(error_msg)
        return False, error_msg


def process_file_worker(task_tuple):
    """处理单个文件的工作函数，供进程池使用"""
    file_index, total_files, file_name, input_folder, output_folder, db_config, max_threads, log_queue = task_tuple

    host = db_config['host']
    port = db_config['port']
    user = db_config['user']
    password = db_config['password']
    db = db_config['db']

    try:
        log_queue.put(f"处理文件 {file_index}/{total_files}: {file_name}.ibd")

        # 拼接文件路径
        input_file = os.path.join(input_folder, f"{file_name}.ibd")
        output_file = os.path.join(output_folder, f"{file_name}.sql")

        # 执行 ibd_to_sql 命令
        success, message = execute_sql_command(input_file, output_file)
        log_queue.put(message)

        result = {
            'file_name': file_name,
            'sql_generated': success,
            'sql_executed': False,
            'message': message
        }

        if success:
            # 执行 SQL 文件
            sql_success, sql_message = execute_sql_file(
                host, port, user, password, db, output_file, max_threads, log_queue
            )
            log_queue.put(sql_message)

            result['sql_executed'] = sql_success
            result['message'] = sql_message

        return result

    except Exception as e:
        error_msg = f"处理文件 {file_name}.ibd 时发生错误: {str(e)}"
        log_queue.put(error_msg)
        return {
            'file_name': file_name,
            'sql_generated': False,
            'sql_executed': False,
            'message': error_msg
        }


class MySQLIBDConverterApp:
    def __init__(self, root):
        self.root = root

        self.root.title("IBD数据恢复ForMySQL-v1.0")
        self.root.geometry("800x600")
        # 添加窗口居中代码
        self.center_window()
        # 设置图标
        self.root.iconbitmap(default=favicon)
        # 设置中文字体
        self.style = ttk.Style()
        # 保持原有代码不变...
        self.root.minsize(700, 500)

        # 设置中文字体
        self.style = ttk.Style()
        self.style.configure("TLabel", font=("SimHei", 10))
        self.style.configure("TButton", font=("SimHei", 10))
        self.style.configure("TEntry", font=("SimHei", 10))
        self.style.configure("TCombobox", font=("SimHei", 10))

        # 创建主框架
        self.main_frame = ttk.Frame(root, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 输入文件夹选择
        ttk.Label(self.main_frame, text="输入文件夹:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.input_folder_var = tk.StringVar()
        ttk.Entry(self.main_frame, textvariable=self.input_folder_var, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(self.main_frame, text="浏览...", command=self.select_input_folder).grid(row=0, column=2, padx=5,
                                                                                           pady=5)

        # 输出文件夹信息
        ttk.Label(self.main_frame, text="输出文件夹:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.output_folder_var = tk.StringVar()
        self.output_folder_var.set("(自动生成)")
        ttk.Entry(self.main_frame, textvariable=self.output_folder_var, width=50, state="readonly").grid(row=1,
                                                                                                         column=1,
                                                                                                         padx=5, pady=5)

        # 并行处理设置
        parallel_frame = ttk.LabelFrame(self.main_frame, text="并行处理设置", padding="10")
        parallel_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(parallel_frame, text="进程数:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.processes_var = tk.IntVar(value=cpu_count())
        ttk.Entry(parallel_frame, textvariable=self.processes_var, width=10).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(parallel_frame, text="线程数:").grid(row=0, column=2, sticky=tk.W, pady=5)
        self.threads_var = tk.IntVar(value=5)
        ttk.Entry(parallel_frame, textvariable=self.threads_var, width=10).grid(row=0, column=3, padx=5, pady=5)

        # 数据库连接信息
        db_frame = ttk.LabelFrame(self.main_frame, text="数据库连接信息", padding="10")
        db_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        # 主机和端口
        ttk.Label(db_frame, text="主机:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.host_var = tk.StringVar(value="localhost")
        ttk.Entry(db_frame, textvariable=self.host_var, width=20).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(db_frame, text="端口:").grid(row=0, column=2, sticky=tk.W, pady=5)
        self.port_var = tk.IntVar(value=3306)
        ttk.Entry(db_frame, textvariable=self.port_var, width=10).grid(row=0, column=3, padx=5, pady=5)

        # 用户名和密码
        ttk.Label(db_frame, text="用户名:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.user_var = tk.StringVar(value="root")
        ttk.Entry(db_frame, textvariable=self.user_var, width=20).grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(db_frame, text="密码:").grid(row=1, column=2, sticky=tk.W, pady=5)
        self.password_var = tk.StringVar()
        ttk.Entry(db_frame, textvariable=self.password_var, show="*", width=20).grid(row=1, column=3, padx=5, pady=5)

        # 数据库名
        ttk.Label(db_frame, text="数据库名:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.db_var = tk.StringVar()
        ttk.Entry(db_frame, textvariable=self.db_var, width=20).grid(row=2, column=1, padx=5, pady=5)
        # 数据库说明
        ttk.Label(db_frame, text="<-原ibd文件所属数据库:").grid(row=2, column=2, sticky=tk.W, pady=5)
        self.db_info_var = tk.StringVar()

        # 进度条
        ttk.Label(self.main_frame, text="处理进度:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.main_frame, variable=self.progress_var, length=500)
        self.progress_bar.grid(row=4, column=1, padx=5, pady=5)

        # 日志区域
        ttk.Label(self.main_frame, text="处理日志:").grid(row=5, column=0, sticky=tk.NW, pady=5)
        self.log_text = tk.Text(self.main_frame, height=15, width=70)
        self.log_text.grid(row=5, column=1, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar = ttk.Scrollbar(self.main_frame, command=self.log_text.yview)
        scrollbar.grid(row=5, column=2, sticky=(tk.N, tk.S))
        self.log_text.config(yscrollcommand=scrollbar.set)
        self.log_text.config(state=tk.DISABLED)

        # 按钮区域
        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.grid(row=6, column=0, columnspan=3, pady=20)

        self.start_btn = ttk.Button(btn_frame, text="开始处理", command=self.start_processing, style='Accent.TButton')
        self.start_btn.pack(side=tk.LEFT, padx=10)

        self.clear_btn = ttk.Button(btn_frame, text="清除日志", command=self.clear_log)
        self.clear_btn.pack(side=tk.LEFT, padx=10)

        # 配置按钮样式
        self.style.configure('Accent.TButton', font=('SimHei', 10, 'bold'))

        # 设置网格权重，使日志区域可扩展
        self.main_frame.grid_rowconfigure(5, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)

        # 初始化变量
        self.total_files = 0
        self.processed_files = 0
        self.process_results = []

    def center_window(self):
        """将窗口居中显示"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry('{}x{}+{}+{}'.format(width, height, x, y))

    def select_input_folder(self):
        folder = filedialog.askdirectory(title="选择包含.ibd文件的文件夹")
        if folder:
            # 标准化路径（将斜杠统一为系统默认格式）
            normalized_folder = os.path.normpath(folder)
            self.input_folder_var.set(normalized_folder)
            # 自动生成输出文件夹路径（使用os.path.join确保路径格式正确）
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_folder = os.path.join(os.path.dirname(normalized_folder), f"sql_output_{timestamp}")
            self.output_folder_var.set(output_folder)

    def log(self, message):
        """向日志区域添加消息"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def clear_log(self):
        """清除日志区域"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

    def update_progress(self, value):
        """更新进度条"""
        self.progress_var.set(value)

    def get_ibd_filenames_without_extension(self, folder_path):
        """获取指定文件夹下所有 .ibd 文件的文件名（不包含后缀）"""
        # 标准化输入文件夹路径，避免斜杠问题
        folder_path = os.path.normpath(folder_path)
        filenames = []
        for file in os.listdir(folder_path):
            full_path = os.path.join(folder_path, file)  # 关键：用os.path.join拼接路径
            # 检查文件是否是 .ibd 文件
            if os.path.isfile(full_path) and file.endswith('.ibd'):
                name_without_ext = os.path.splitext(file)[0]
                filenames.append(name_without_ext)

        # set 去重
        filenames = list(set(filenames))
        return filenames

    def log_listener(self, log_queue):
        """监听日志队列并更新GUI"""
        while True:
            message = log_queue.get()
            if message is None:  # 退出信号
                break
            self.root.after(0, self.log, message)
            log_queue.task_done()

    def process_files(self):
        """处理文件的主函数（在线程中运行）"""
        try:
            # 获取输入文件夹路径
            input_folder = self.input_folder_var.get()
            if not input_folder:
                messagebox.showerror("错误", "请选择输入文件夹")
                return

            # 标准化输入文件夹路径
            input_folder = os.path.normpath(input_folder)

            # 检查输入文件夹是否存在
            if not os.path.exists(input_folder):
                messagebox.showerror("错误", f"输入文件夹不存在: {input_folder}")
                return

            # 创建输出文件夹
            output_folder = self.output_folder_var.get()
            if output_folder == "(自动生成)":
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                output_folder = os.path.join(os.path.dirname(input_folder), f"sql_output_{timestamp}")
                self.output_folder_var.set(output_folder)

            # 标准化输出文件夹路径并创建
            output_folder = os.path.normpath(output_folder)
            os.makedirs(output_folder, exist_ok=True)
            self.log(f"输出文件夹已创建: {output_folder}")

            # 获取所有 .ibd 文件
            file_names = self.get_ibd_filenames_without_extension(input_folder)
            self.total_files = len(file_names)

            if self.total_files == 0:
                messagebox.showinfo("提示", "在指定文件夹中未找到 .ibd 文件")
                return

            self.log(f"找到 {self.total_files} 个 .ibd 文件")

            # 获取数据库连接信息
            db_config = {
                'host': self.host_var.get(),
                'port': self.port_var.get(),
                'user': self.user_var.get(),
                'password': self.password_var.get(),
                'db': self.db_var.get()
            }

            # 获取并行处理设置
            max_processes = max(1, self.processes_var.get())
            max_threads = max(1, self.threads_var.get())

            self.log(f"并行处理设置: 进程数={max_processes}, 线程数={max_threads}")

            # 创建进程间共享的日志队列
            with Manager() as manager:
                log_queue = manager.Queue()

                # 启动日志监视线程
                log_thread = threading.Thread(target=self.log_listener, args=(log_queue,))
                log_thread.daemon = True
                log_thread.start()

                # 创建工作任务列表
                tasks = [
                    (i + 1, self.total_files, file_name, input_folder, output_folder, db_config, max_threads, log_queue)
                    for i, file_name in enumerate(file_names)
                ]

                # 使用进程池并行处理文件
                with Pool(processes=max_processes) as pool:
                    self.process_results = pool.map(process_file_worker, tasks)

                # 停止日志监视线程
                log_queue.put(None)
                log_thread.join()

            # 汇总结果
            total_success = sum(1 for r in self.process_results if r['sql_generated'] and r['sql_executed'])
            total_failed = self.total_files - total_success

            self.log(f"\n处理结果: 成功={total_success}, 失败={total_failed}")

            if total_failed > 0:
                self.log("失败文件列表:")
                for result in self.process_results:
                    if not result['sql_generated'] or not result['sql_executed']:
                        self.log(f"- {result['file_name']}: {result['message']}")

            messagebox.showinfo("处理完成", f"处理完成!\n成功: {total_success}\n失败: {total_failed}")

        except Exception as e:
            self.log(f"发生错误: {e}")
            messagebox.showerror("错误", f"处理过程中发生错误: {e}")

        finally:
            # 启用按钮
            self.start_btn.config(state=tk.NORMAL)

    def start_processing(self):
        """开始处理按钮的回调函数"""
        # 禁用按钮防止重复点击
        self.start_btn.config(state=tk.DISABLED)

        # 清空日志
        self.clear_log()

        # 在新线程中执行处理，避免界面卡顿
        thread = threading.Thread(target=self.process_files)
        thread.daemon = True
        thread.start()


if __name__ == "__main__":
    root = tk.Tk()
    app = MySQLIBDConverterApp(root)
    root.mainloop()
