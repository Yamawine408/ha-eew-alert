"""Constants for the EEW Alert integration."""

DOMAIN = "eew_alert"

CONF_MIN_SCALE = "min_scale"
CONF_CAST_DEVICE = "cast_device"
CONF_IGNORE_TEST = "ignore_test"
CONF_TARGET_PREFS = "target_prefs"
CONF_TARGET_LIGHTS = "target_lights"
CONF_TARGET_LOCKS = "target_locks"
CONF_PRESENCE_ENTITIES = "presence_entities"

DEFAULT_MIN_SCALE = 45  # 震度5弱
DEFAULT_IGNORE_TEST = True
DEFAULT_TARGET_PREFS: list[str] = []  # 空 = 全国対象(現在の全国最大震度で判定)
DEFAULT_TARGET_LIGHTS: list[str] = []
DEFAULT_TARGET_LOCKS: list[str] = []
DEFAULT_PRESENCE_ENTITIES: list[str] = []  # 空 = 在宅検知しない(常に実行)

# 都道府県名(短縮形)。config_flowの選択肢および都道府県マッチングに使用
PREFECTURES = [
    "北海道", "青森", "岩手", "宮城", "秋田", "山形",
    "福島", "茨城", "栃木", "群馬", "埼玉", "千葉",
    "東京", "神奈川", "新潟", "富山", "石川", "福井",
    "山梨", "長野", "岐阜", "静岡", "愛知", "三重",
    "滋賀", "京都", "大阪", "兵庫", "奈良", "和歌山",
    "鳥取", "島根", "岡山", "広島", "山口", "徳島",
    "香川", "愛媛", "高知", "福岡", "佐賀", "長崎",
    "熊本", "大分", "宮崎", "鹿児島", "沖縄",
]

WS_URL = "wss://api.p2pquake.net/v2/ws"

EVENT_EEW_TRIGGERED = f"{DOMAIN}_triggered"
EVENT_EEW_CANCELLED = f"{DOMAIN}_cancelled"

# P2P地震情報の震度コード -> 表示ラベル
SCALE_LABEL = {
    10: "1", 20: "2", 30: "3", 40: "4", 45: "5弱",
    50: "5強", 55: "6弱", 60: "6強", 70: "7",
}

SERVICE_CAST_ALERT = "cast_alert"
ATTR_LABEL = "label"
ATTR_HYPOCENTER = "hypocenter"
ATTR_SCALE = "scale"
ATTR_PREFS = "prefs"
ATTR_DEVICE_NAME = "device_name"
