import pandas as pd
from sqlalchemy import create_engine

# 填入你刚才从 Supabase 复制的数据库链接，并将 [YOUR-PASSWORD] 替换为你的真实密码
SUPABASE_URL = "postgresql://postgres:dHym7RXB7OAdjKnV@db.vszqcefyhirpzqkmrilh.supabase.co:5432/postgres"

print("🔄 正在连接 Supabase 并导入数据...")
engine = create_engine(SUPABASE_URL)

# 1. 导入 scan_cases
df_scan = pd.read_csv("scan_cases.csv")
df_scan.to_sql("scan_cases", engine, if_exists="replace", index=False)
print("✅ scan_cases 122 条记录全部导入成功！")

# 2. 导入 learning_cases
df_learning = pd.read_csv("learning_cases.csv")
df_learning.to_sql("learning_cases", engine, if_exists="replace", index=False)
print("✅ learning_cases 记录全部导入成功！")

print("🎉 所有历史数据已成功同步到云端数据库！")