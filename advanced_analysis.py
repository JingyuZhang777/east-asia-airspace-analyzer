import requests
import pandas as pd
import os
from dotenv import load_dotenv

# 加载 .env 文件中的隐藏环境变量
load_dotenv()

# 1. 设置 API 请求参数
url = "https://opensky-network.org/api/states/all"
params = {"lamin": 20, "lomin": 100, "lamax": 45, "lomax": 140} 

# 从环境变量中安全提取账号密码
USERNAME = os.getenv("OPENSKY_USER")
PASSWORD = os.getenv("OPENSKY_PASS")

print("📡 正在获取东亚空域实时报文...")
try:
    resp = requests.get(url, params=params, auth=(USERNAME, PASSWORD), timeout=30)
    raw = resp.json()
    
    cols = ['icao24', 'callsign', 'origin_country', 'time_position',
            'last_contact', 'longitude', 'latitude', 'baro_altitude',
            'on_ground', 'velocity', 'true_track', 'vertical_rate',
            'sensors', 'geo_altitude', 'squawk', 'spi', 'position_source']
    df = pd.DataFrame(raw['states'], columns=cols)
    
    # 基础清洗
    df['callsign'] = df['callsign'].str.strip()
    df['altitude_ft'] = df['baro_altitude'] * 3.28084
    df['velocity_kmh'] = df['velocity'] * 3.6

    print("-" * 50)
    print(f"📊 实时态势分析报告 (捕获总量: {len(df)})")
    print("-" * 50)

    # --- 任务 1：高空巡航分析 ---
    cruise_df = df[(df['altitude_ft'] >= 30000) & (df['altitude_ft'] <= 40000)]
    avg_speed = cruise_df['velocity_kmh'].mean()
    print(f"✈️  巡航阶段 (30k-40k ft):")
    print(f"   - 数量: {len(cruise_df)} 架")
    print(f"   - 平均地速: {avg_speed:.2f} km/h" if not pd.isna(avg_speed) else "   - 平均地速: 暂无有效数据")

    # --- 任务 2：地面态势监控 ---
    ground_count = df[df['on_ground'] == True].shape[0]
    print(f"\n🚜 地面状态监控:")
    print(f"   - 当前机场内 (滑行/停机): {ground_count} 架")

    # --- 任务 3：航司运力分布 ---
    # 提取呼号前三位，排除空值和 Unknown
    df['operator'] = df['callsign'].str[:3]
    valid_ops = df[df['operator'].str.isalpha() & (df['on_ground'] == False)]
    top_airlines = valid_ops['operator'].value_counts().head(5)
    
    print(f"\n🏆 当前活跃航司 TOP 5 (在飞):")
    for code, count in top_airlines.items():
        mapping = {
    "CCA": "中国国航", "CES": "东方航空", "CSN": "南方航空", 
    "CPA": "国泰航空", "JAL": "日本航空", "ANA": "全日空",
    "KAL": "大韩航空", "AAR": "韩亚航空", "CAL": "中华航空", "EVA":"长荣航空"
}
        name = mapping.get(code, "其他/国际")
        print(f"   - {code} ({name}): {count} 架")

except Exception as e:
    print(f"❌ 分析中断: {e}")

"""
2026.4.20 21:00
--------------------------------------------------
📊 实时态势分析报告 (捕获总量: 301)
--------------------------------------------------
✈️  巡航阶段 (30k-40k ft):
   - 数量: 105 架
   - 平均地速: 819.35 km/h

🚜 地面状态监控:
   - 当前机场内 (滑行/停机): 42 架

🏆 当前活跃航司 TOP 5 (在飞):
   - CCA (中国国航): 16 架
   - CSN (南方航空): 13 架
   - CPA (国泰航空): 11 架
   - EVA (其他/国际): 11 架
   - ANA (全日空): 10 架
"""