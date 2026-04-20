import requests
import pandas as pd
import matplotlib.pyplot as plt
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

print("正在向 OpenSky 发送请求，获取东亚空域实时数据...")
try:
    # 加上 auth 认证，增加稳定性
    resp = requests.get(url, params=params, auth=(USERNAME, PASSWORD), timeout=30)
    resp.raise_for_status()
    raw = resp.json()
    
    if raw['states'] is None:
        print("当前范围内未获取到航班数据，请稍后重试。")
        exit()

    # 2. 数据清洗与计算
    cols = ['icao24', 'callsign', 'origin_country', 'time_position',
            'last_contact', 'longitude', 'latitude', 'baro_altitude',
            'on_ground', 'velocity', 'true_track', 'vertical_rate',
            'sensors', 'geo_altitude', 'squawk', 'spi', 'position_source']
    
    df = pd.DataFrame(raw['states'], columns=cols)
    df = df.dropna(subset=['latitude', 'longitude', 'baro_altitude'])
    df['altitude_ft'] = df['baro_altitude'] * 3.28084
    df['velocity_kmh'] = df['velocity'] * 3.6
    
    print(f"\n成功！当前东亚空域捕捉到有效状态飞机数: {len(df)}")
    print("\n航班所属国籍 TOP 5:")
    print(df['origin_country'].value_counts().head(5))

    # 3. 基础可视化
    print("\n正在生成图表...")
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # 高度分布直方图
    axes[0].hist(df['altitude_ft'].dropna(), bins=50, edgecolor='black', color='skyblue')
    axes[0].set_xlabel('Altitude (ft)')
    axes[0].set_ylabel('Aircraft count')
    axes[0].set_title('Real-time Altitude Distribution')

    # 地理分布散点图
    sc = axes[1].scatter(df['longitude'], df['latitude'],
                         c=df['altitude_ft'], s=10, cmap='viridis', alpha=0.7)
    axes[1].set_xlabel('Longitude')
    axes[1].set_ylabel('Latitude')
    axes[1].set_title('Aircraft Positions (colored by altitude)')
    plt.colorbar(sc, ax=axes[1], label='Altitude (ft)')

    plt.tight_layout()
    plt.savefig('airspace_snapshot.png', dpi=120)
    print("图表已保存为 airspace_snapshot.png，请在左侧文件列表中查看！")

except Exception as e:
    print(f"出错了: {e}")
