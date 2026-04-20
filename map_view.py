
import os
import sys
import requests
import pandas as pd
import folium
from dotenv import load_dotenv


# ============================================================
# 1. 配置加载
# ============================================================
# 从项目根目录的 .env 文件读取环境变量
# 如果 .env 不存在也不会报错,只是拿不到值
load_dotenv()

OPENSKY_USER = os.getenv("OPENSKY_USER", "")
OPENSKY_PASS = os.getenv("OPENSKY_PASS", "")

# 有账号就用,没填就传 None(等于匿名访问,配额较低)
AUTH = (OPENSKY_USER, OPENSKY_PASS) if OPENSKY_USER and OPENSKY_PASS else None

# 东亚空域范围(北纬 20°-45°, 东经 100°-140°)
# 覆盖中国东部、日本、韩国、台湾、菲律宾北部
BBOX = {
    "lamin": 20,
    "lomin": 100,
    "lamax": 45,
    "lomax": 140,
}

API_URL = "https://opensky-network.org/api/states/all"
OUTPUT_HTML = "airspace_map.html"

# OpenSky states/all 接口返回的字段顺序(官方文档定义)
STATE_COLS = [
    'icao24', 'callsign', 'origin_country', 'time_position',
    'last_contact', 'longitude', 'latitude', 'baro_altitude',
    'on_ground', 'velocity', 'true_track', 'vertical_rate',
    'sensors', 'geo_altitude', 'squawk', 'spi', 'position_source'
]

# 航司呼号前缀 -> 中文名映射(用于地图弹窗显示)
AIRLINE_MAPPING = {
    "CCA": "中国国航", "CES": "东方航空", "CSN": "南方航空",
    "CHH": "海南航空", "CXA": "厦门航空", "CSZ": "深圳航空",
    "CPA": "国泰航空", "HDA": "国泰港龙", "HKE": "香港快运",
    "CAL": "中华航空", "EVA": "长荣航空",
    "JAL": "日本航空", "ANA": "全日空",
    "KAL": "大韩航空", "AAR": "韩亚航空",
}
# ============================================================
# 2. 数据获取
# ============================================================
def fetch_states():
    """调用 OpenSky API,返回原始 JSON。网络或 API 出错时抛异常。"""
    print("📡 正在向 OpenSky 请求东亚空域实时状态...")
    try:
        resp = requests.get(API_URL, params=BBOX, auth=AUTH, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        sys.exit("❌ 请求超时,请检查网络或稍后重试")
    except requests.exceptions.HTTPError as e:
        sys.exit(f"❌ API 返回错误: {e}")
    except requests.exceptions.RequestException as e:
        sys.exit(f"❌ 网络异常: {e}")

    data = resp.json()
    if not data.get('states'):
        sys.exit("⚠️  当前空域内未获取到任何航班数据,请稍后重试")
    return data
# ============================================================
# 3. 数据清洗
# ============================================================
def build_dataframe(raw):
    """把 OpenSky 的原始数据转成清洗后的 DataFrame。"""
    df = pd.DataFrame(raw['states'], columns=STATE_COLS)

    # 地图渲染至少需要经纬度和高度,缺一不可
    df = df.dropna(subset=['latitude', 'longitude', 'baro_altitude'])

    # 呼号字段有尾部空格,清掉
    df['callsign'] = df['callsign'].str.strip()

    # 单位换算:米 -> 英尺(航空行业通用高度单位)
    df['altitude_ft'] = df['baro_altitude'] * 3.28084
    # 单位换算:米/秒 -> 千米/小时
    df['velocity_kmh'] = df['velocity'] * 3.6

    # 从呼号提取航司代码(前 3 位字母,如 CCA1234 -> CCA)
    df['operator'] = df['callsign'].str[:3]

    return df
# ============================================================
# 4. 可视化逻辑
# ============================================================
def color_by_altitude(alt_ft):
    """
    按飞行阶段粗分染色:
      红 - 低空(<10k ft),通常是起飞/降落/进近阶段
      橙 - 中空(10k-25k ft),爬升或下降过渡阶段
      绿 - 高空(≥25k ft),巡航阶段
    """
    if pd.isna(alt_ft):
        return 'gray'
    if alt_ft < 10000:
        return 'red'
    elif alt_ft < 25000:
        return 'orange'
    else:
        return 'green'
def build_popup_html(row):
    """生成鼠标点击标记点时显示的 HTML 弹窗。"""
    callsign = row['callsign'] if row['callsign'] else 'N/A'
    airline = AIRLINE_MAPPING.get(row['operator'], '其他/未识别')
    altitude = row['altitude_ft']
    speed = row['velocity_kmh'] if pd.notna(row['velocity_kmh']) else 0
    heading = row['true_track'] if pd.notna(row['true_track']) else 0
    country = row['origin_country']

    return f"""
    <div style="font-family: sans-serif; font-size: 13px;">
      <b style="font-size: 15px;">{callsign}</b><br>
      <span style="color:#666;">{airline}</span><br>
      <hr style="margin: 4px 0;">
      🌐 国籍: {country}<br>
      📏 高度: {altitude:,.0f} ft<br>
      💨 地速: {speed:.0f} km/h<br>
      🧭 航向: {heading:.0f}°
    </div>
    """
def render_map(df):
    """把 DataFrame 渲染成 folium 交互地图,保存为 HTML。"""
    print(f"🗺️  正在绘制 {len(df)} 架航班的态势地图...")

    # CartoDB positron 是浅灰色底图,航迹点更突出
    m = folium.Map(
        location=[30, 120],
        zoom_start=5,
        tiles='CartoDB positron'
    )

    # 添加图例(手工拼 HTML,folium 没有内置图例组件)
    legend_html = """
    <div style="
        position: fixed; bottom: 30px; left: 30px; z-index: 9999;
        background: white; padding: 10px 14px; border-radius: 6px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.15); font-family: sans-serif;
        font-size: 13px;">
      <b>Altitude Legend</b><br>
      <span style="color:red;">●</span> &lt; 10,000 ft (低空)<br>
      <span style="color:orange;">●</span> 10k - 25k ft (中空)<br>
      <span style="color:green;">●</span> ≥ 25,000 ft (巡航)
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # 每架飞机画一个圆点
    for _, row in df.iterrows():
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=4,
            popup=folium.Popup(build_popup_html(row), max_width=240),
            tooltip=row['callsign'] if row['callsign'] else None,
            color=color_by_altitude(row['altitude_ft']),
            fill=True,
            fill_opacity=0.75,
            weight=1,
        ).add_to(m)

    m.save(OUTPUT_HTML)
    print(f"✅ 地图已保存: {OUTPUT_HTML}")
    print(f"   用浏览器打开即可查看交互效果")
# ============================================================
# 5. 主流程
# ============================================================
def main():
    if AUTH is None:
        print("⚠️  未配置 OpenSky 账号,将使用匿名访问(配额较低)")
        print("   如需提升配额,请在 .env 文件中配置 OPENSKY_USER / OPENSKY_PASS\n")

    raw = fetch_states()
    df = build_dataframe(raw)

    # 打印一行概要,方便运行时确认数据
    ground = df[df['on_ground'] == True].shape[0]
    cruise = df[(df['altitude_ft'] >= 30000) & (df['altitude_ft'] <= 40000)].shape[0]
    print(f"📊 捕获 {len(df)} 架航班 | 巡航层 {cruise} 架 | 地面 {ground} 架\n")

    render_map(df)
if __name__ == "__main__":
    main()