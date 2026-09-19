import sqlite3
import csv
import os

# 1. 打印开始信息，确保脚本真的被执行了
print("🚀 脚本开始运行，正在准备导出数据...")

# 2. 获取当前运行的完整路径，方便排查位置错位
current_dir = os.getcwd()
DB_PATH = os.path.join(current_dir, "data", "scan_cases.db")

print(f"🔍 正在尝试读取数据库，路径为: {DB_PATH}")

# 3. 检查文件是否真实存在
if not os.path.exists(DB_PATH):
    print("❌ 致命错误：在这个路径下找不到 dara.db 文件！")
    print("👉 解决办法：请确保你是在项目的根目录下打开的终端。如果你的数据库在别的文件夹，请手动修改代码里的 DB_PATH。")
    exit()

def export_table_to_csv(table_name, csv_filename):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cursor.fetchone():
            print(f"⚠️ 错误：数据库中不存在 '{table_name}' 这个表！")
            return

        # 获取表中所有数据
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        if not rows:
            print(f"⚠️ 警告：表 '{table_name}' 存在，但是里面是空的没有数据。")
            return

        # 获取列名 (Headers)
        col_names = [description[0] for description in cursor.description]
        
        # 写入 CSV 文件
        csv_full_path = os.path.join(current_dir, csv_filename)
        with open(csv_full_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(col_names)
            writer.writerows(rows)
            
        print(f"✅ 成功导出 {len(rows)} 条记录！文件已保存为: {csv_full_path}")
        conn.close()
    except Exception as e:
        print(f"❌ 导出 {table_name} 时发生未知错误: {e}")

# 4. 执行导出
print("----------------------------------------")
export_table_to_csv("scan_cases", "scan_cases.csv")
export_table_to_csv("learning_cases", "learning_cases.csv")
print("----------------------------------------")
print("🏁 脚本运行结束！")