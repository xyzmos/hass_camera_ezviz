"""Constants for the EZVIZ CN (萤石云开放平台) integration."""

DOMAIN = "hass_camera_ezviz"

# Config entry data keys
CONF_APP_KEY = "appkey"
CONF_APP_SECRET = "appsecret"
CONF_DEVICES = "devices"

# Options keys
CONF_DEVICE_SERIAL = "deviceserial"
CONF_UPDATE_INTERVAL = "update_interval_seconds"
CONF_CAMERA_INTERVAL = "update_camera_seconds"
CONF_SWITCHS = "switchs"
CONF_ENABLE_WEBHOOK = "enable_webhook"
CONF_WEBHOOK_URL = "webhook_url"

DEFAULT_UPDATE_INTERVAL = 30
DEFAULT_CAMERA_INTERVAL = 120

ATTRIBUTION = "Data provided by EZVIZ Open Platform"

# Ezviz open platform API
API_BASE = "https://open.ys7.com"
API_TOKEN = f"{API_BASE}/api/lapp/token/get"
API_DEVICE_LIST = f"{API_BASE}/api/lapp/device/list"
API_CAMERA_LIST = f"{API_BASE}/api/lapp/camera/list"
API_DEVICE_CAPACITY = f"{API_BASE}/api/lapp/device/capacity"
API_DEVICE_INFO = f"{API_BASE}/api/lapp/device/info"
API_SCENE_SWITCH_STATUS = f"{API_BASE}/api/lapp/device/scene/switch/status"
API_SCENE_SWITCH_SET = f"{API_BASE}/api/lapp/device/scene/switch/set"
API_SOUND_STATUS = f"{API_BASE}/api/lapp/camera/video/sound/status"
API_SOUND_SET = f"{API_BASE}/api/lapp/camera/video/sound/set"
API_DEFENCE_SET = f"{API_BASE}/api/lapp/device/defence/set"
API_PTZ_START = f"{API_BASE}/api/lapp/device/ptz/start"
API_PTZ_STOP = f"{API_BASE}/api/lapp/device/ptz/stop"
API_CAPTURE = f"{API_BASE}/api/lapp/device/capture"
API_ALARM_LIST = f"{API_BASE}/api/lapp/alarm/device/list"
API_LIVE_ADDRESS = f"{API_BASE}/api/lapp/v2/live/address/get"
API_VEHICLE_PROPS = f"{API_BASE}/api/lapp/intelligence/vehicle/analysis/props"
API_HUMAN_DETECT = f"{API_BASE}/api/lapp/intelligence/human/analysis/detect"
API_HUMAN_BODY = f"{API_BASE}/api/lapp/intelligence/human/analysis/body"
API_FACE_DETECT = f"{API_BASE}/api/lapp/intelligence/face/analysis/detect"

API_TIMEOUT = 10
# accessToken 有效期约 7 天，提前 10 分钟刷新
TOKEN_REFRESH_MARGIN_MS = 10 * 60 * 1000
PAGE_SIZE = 50

# Ezviz API 错误码 -> 认证类错误（appKey/appSecret 或账号问题，触发 reauth）
# 注意：49999(数据异常)/10002(token过期) 为瞬时或服务端错误，应重试而非 reauth
AUTH_ERROR_CODES = {"10004", "10005", "10017", "10030"}

EVENT_WEBHOOK = f"{DOMAIN}_webhook_event"
EVENT_INTELLIGENCE = f"{DOMAIN}_intelligence_event"

# 可选开关类型：kind -> (translation_key, icon)
SWITCH_TYPES = {
    "on_off": ("ezviz_onoff", "mdi:toggle-switch"),
    "soundswitch": ("ezviz_soundswitch", "mdi:microphone"),
    "defence": ("ezviz_defence", "mdi:alarm-light"),
}

# 选项流中可供用户启用的开关（defence 由设备能力自动创建）
OPTIONAL_SWITCH_TYPES = ["on_off", "soundswitch"]

# kind -> (translation_key, icon, direction, action)
BUTTON_TYPES = {
    "stop": ("stop", "mdi:stop", None, "stop"),
    "capture": ("capture", "mdi:camera", None, "capture"),
    "up": ("up", "mdi:arrow-up-thick", 0, "move"),
    "down": ("down", "mdi:arrow-down-thick", 1, "move"),
    "left": ("left", "mdi:arrow-left-thick", 2, "move"),
    "right": ("right", "mdi:arrow-right-thick", 3, "move"),
    "upleft": ("upleft", "mdi:arrow-top-left-thick", 4, "move"),
    "downleft": ("downleft", "mdi:arrow-bottom-left-thick", 5, "move"),
    "upright": ("upright", "mdi:arrow-top-right-thick", 6, "move"),
    "downright": ("downright", "mdi:arrow-bottom-right-thick", 7, "move"),
    "zoombig": ("zoombig", "mdi:magnify-plus", 8, "move"),
    "zoomsmall": ("zoomsmall", "mdi:magnify-minus", 9, "move"),
    "zoomnear": ("zoomnear", "mdi:magnify-minus-cursor", 10, "move"),
    "zoomfar": ("zoomfar", "mdi:magnify-plus-cursor", 11, "move"),
    "zoomauto": ("zoomauto", "mdi:autorenew", 16, "move"),
    "vehicleprops": ("vehicleprops", "mdi:car-search", None, "vehicleprops"),
    "humandetect": ("humandetect", "mdi:human", None, "humandetect"),
    "humanbody": ("humanbody", "mdi:human-male-female-child", None, "humanbody"),
    "facedetect": ("facedetect", "mdi:face-agent", None, "facedetect"),
    "liveget": ("liveget", "mdi:monitor-eye", None, "liveget"),
}

PTZ_BUTTONS = [
    "stop", "up", "down", "left", "right",
    "upleft", "downleft", "upright", "downright",
]
PTZ_DIAGONAL_BUTTONS = ["upleft", "downleft", "upright", "downright"]
PTZ_VERTICAL_BUTTONS = ["up", "down"]
PTZ_HORIZONTAL_BUTTONS = ["left", "right"]
ZOOM_BUTTONS = ["zoombig", "zoomsmall"]
INTELLIGENCE_BUTTONS = ["vehicleprops", "humandetect", "humanbody", "facedetect"]

# kind -> (api 字段名, translation_key, icon, 状态标签列表, 默认启用)
SENSOR_TYPES = {
    "status": ("status", "onlinestatus", "mdi:check-network-outline", "ONLINESTATUS", True),
    "defence": ("defence", "alarmstatus", "mdi:alarm-light-outline", "DEFENCE", True),
    "alarmSoundMode": ("alarmSoundMode", "alarm_sound_mod", "mdi:surround-sound", "ALARMSOUNDMODE", True),
    "offlineNotify": ("offlineNotify", "offlinenotify", "mdi:message-alert", "OFFLINENOTIFY", False),
    "netAddress": ("netAddress", "wan_ip", "mdi:wan", None, False),
}

ALARMSOUNDMODE = ["短叫", "长叫", "静音"]
DEFENCE = ["撤防", "布防"]
ON_OFF = ["启用遮蔽", "关闭遮蔽"]
OFFLINENOTIFY = ["设备下线通知已关闭", "设备下线通知已开启"]
ONLINESTATUS = ["不在线", "在线"]

STATE_LABELS = {
    "ALARMSOUNDMODE": ALARMSOUNDMODE,
    "DEFENCE": DEFENCE,
    "ON_OFF": ON_OFF,
    "OFFLINENOTIFY": OFFLINENOTIFY,
    "ONLINESTATUS": ONLINESTATUS,
}
