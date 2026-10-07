# 萤石摄像头-开放平台（hass_camera_ezviz）

[![通过 HACS 添加此仓库](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=xyzmos&repository=hass_camera_ezviz&category=integration)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/xyzmos/hass_camera_ezviz)](https://github.com/xyzmos/hass_camera_ezviz/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

通过**萤石开放平台 API**（open.ys7.com）将萤石摄像头接入 Home Assistant 的自定义集成。支持摄像头抓图、云台控制、隐私遮蔽、布撤防、麦克风、告警 Webhook 推送、AI 智能分析（车牌/人形/人脸）等能力。

> 本项目基于 [@dscao](https://github.com/dscao) 的 [ezviz](https://github.com/dscao/ezviz) 插件二次修改而来，特此感谢原作者 dscao 的开源贡献。本仓库在其基础上做了大量重构与修复，详见「与原版差异」一节。

---

## 功能特性

- **摄像头（camera）**：定时抓图（云端快照）生成监控画面；猫眼/门铃类设备（CS-DP*）自动改用「最近告警图片」
- **按钮（button）**：云台方向控制、变倍变焦、抓拍、AI 分析、获取直播地址
- **开关（switch）**：隐私遮蔽开关、布撤防（移动侦测）、设备麦克风
- **传感器（sensor）**：在线状态、布防状态、告警声音模式、下线通知、外网地址
- **服务（action）**：`capture`（抓拍）、`humandetect`（人形检测，返回响应数据）
- **Webhook**：接收萤石云**告警消息推送**，触发 Home Assistant 事件供自动化使用
- **配置流**：UI 一键配置 appKey/appSecret，选项可调刷新间隔、设备过滤、开关类型等
- **诊断**：支持下载诊断信息（自动脱敏密钥）

## 前置条件

1. 一台已绑定到萤石云账号的摄像头/猫眼/门铃设备。
2. 在[萤石开放平台](https://open.ys7.com)注册开发者账号，进入[控制台 - 应用管理](https://open.ys7.com/console/application.html)**创建应用**，获得：
   - `appKey`
   - `appSecret`
3. Home Assistant **2025.1.0** 或更高版本。
4. （可选，Webhook 推送）Home Assistant 可被萤石云从公网访问（配置了外部访问 URL，如域名/NABU CASA 等）。

## 安装

### 方式一：HACS（推荐）

**一键添加**：点击 [![通过 HACS 添加此仓库](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=xyzmos&repository=hass_camera_ezviz&category=integration) 会自动跳转到你的 Home Assistant 并把本仓库添加为 HACS 自定义仓库，然后在 HACS 中搜索下载即可。

**手动添加**：

1. 打开 HACS → 右上角菜单 → **自定义存储库**
2. 添加仓库：`https://github.com/xyzmos/hass_camera_ezviz`，类别选择 **Integration**
3. 在 HACS 中搜索「萤石摄像头-开放平台」并下载
4. **重启 Home Assistant**

### 方式二：手动安装

1. 下载本仓库，将 `custom_components/hass_camera_ezviz` 整个目录复制到 HA 配置目录的 `custom_components/` 下
2. 重启 Home Assistant

```
config/
└── custom_components/
    └── hass_camera_ezviz/
        ├── __init__.py
        ├── manifest.json
        └── ...
```

## 配置

1. 进入 **设置 → 设备与服务 → 添加集成**，搜索「萤石摄像头-开放平台」
2. 填入 `appKey` 和 `appSecret`，提交。集成会自动拉取账号下的设备列表并创建实体。

### 集成选项（集成卡片 → 配置）

| 选项 | 说明 | 默认值 |
|---|---|---|
| 刷新间隔时间 | 设备状态轮询间隔（秒），范围 3-600 | 30 |
| 摄像头自动抓图间隔 | camera 实体画面刷新间隔（秒），范围 3-3600 | 120 |
| 只显示以下设备 | 按序列号过滤设备，不选则显示所有设备 | 全部 |
| 启用的开关实体 | 勾选后才会创建/刷新对应开关（每次刷新各消耗 1 次 API） | 开关（隐私遮蔽） |
| 启用 Webhook 回调 | 注册本机接收萤石云告警推送的地址 | 开 |
| Webhook URL | **只读**。启用后自动生成，需复制到开放平台配置 | — |

修改选项后集成会自动重载。

## 实体说明

> 同一账号下每台设备创建为一个「设备」，下列实体均挂在对应设备下。实际创建的实体取决于设备能力（`capacity`）与选项配置。

### Camera（每个可用通道一个）

| 实体 | 说明 |
|---|---|
| 监控画面 | 普通摄像头：按「自动抓图间隔」定时调用抓图接口刷新画面 |
| 告警画面 | CS-DP* 猫眼/门铃：展示最近一条告警消息的图片 |

多通道设备实体名带通道号前缀（如 `2 监控画面`）。

### Sensor

| 实体 | 说明 | 默认启用 |
|---|---|---|
| 在线状态 | 在线 / 不在线 | ✅ |
| 布防状态 | 布防 / 撤防 | ✅ |
| 告警声音模式 | 短叫 / 长叫 / 静音 | ✅ |
| 下线通知 | 设备下线通知是否开启 | ❌ |
| 外网地址 | 设备公网 IP:端口 | ❌ |

### Switch

| 实体 | 说明 | 前置条件 |
|---|---|---|
| 摄像头开关 | 隐私遮蔽：开 = 监控中，关 = 已遮蔽 | 设备支持 `support_privacy`，且在选项中启用「开关（隐私遮蔽）」 |
| 移动侦测 | 布防 / 撤防 | 设备支持 `support_defence`，自动创建 |
| 设备麦克风 | 摄像头拾音开关 | 在选项中启用「麦克风」 |

### Button（按设备能力创建）

| 分类 | 实体 | 说明 |
|---|---|---|
| 云台 | 上/下/左/右/左上/左下/右上/右下/停止 | 点动控制（按下转动约 0.5 秒），需 `support_ptz` |
| 变倍 | 放大/缩小/近焦距/远焦距/自动控制 | 需 `ptz_zoom` |
| 抓拍 | 抓拍 | 立即抓拍，图片 URL 存入实体属性 `capture_pic`，需 `support_capture` |
| AI | 车牌识别/人形检测/人体属性识别/人脸检测 | 先抓拍再调用云端 AI 接口，结果存入实体属性并触发 `hass_camera_ezviz_intelligence_event` 事件 |
| 直播 | 获取直播地址 | 返回 5 分钟有效的 HLS 地址，存入实体属性 `liveaddress` |

## 服务（Action）

### `hass_camera_ezviz.capture`

立即抓拍并刷新摄像头画面。

```yaml
action: hass_camera_ezviz.capture
target:
  entity_id: camera.ke_ting_jian_kong_hua_mian
```

### `hass_camera_ezviz.humandetect`

对指定图片做人形检测，**返回响应数据**（可在自动化中读取）。

| 字段 | 必填 | 说明 |
|---|---|---|
| `picurl` | 是 | 待检测图片 URL（可先用抓拍服务/按钮获取） |
| `operation` | 否 | `number`（人数统计，默认）或 `rect`（人形框） |

```yaml
action: hass_camera_ezviz.humandetect
target:
  entity_id: camera.ke_ting_jian_kong_hua_mian
data:
  picurl: "{{ state_attr('button.ke_ting_zhua_pai', 'capture_pic') }}"
  operation: number
response_variable: result
```

## Webhook 告警推送

1. 集成选项中启用 **Webhook 回调**（默认开启），加载后日志会打印 Webhook URL，也可以在选项表单中直接复制；
2. 进入[萤石开放平台](https://open.ys7.com) → 控制台 → **消息推送**（或对应应用的消息订阅配置），将回调地址填写为：
   `https://<你的HA外部地址>/api/hass_camera_ezviz/webhook/<webhook_id>`
3. 萤石云推送告警消息后，集成会触发事件：

```yaml
trigger:
  - platform: event
    event_type: hass_camera_ezviz_webhook_event
    event_data:
      message_type: "alarm"   # 按消息类型过滤
action:
  - action: notify.notify
    data:
      message: "摄像头告警：{{ trigger.event.data.body }}"
```

事件字段：`webhook_id`（即 config entry id）、`message_id`、`device_id`（设备序列号）、`message_type`、`channel_no`、`message_time`、`body`。

> 注意：该端点无需认证，URL 中的 `webhook_id` 即为密钥，请勿泄露。

## 自动化示例

```yaml
automation:
  - alias: "有人按门铃时抓拍并通知"
    trigger:
      - platform: event
        event_type: hass_camera_ezviz_webhook_event
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.device_id == 'C12345678' }}"
    action:
      - action: hass_camera_ezviz.capture
        target:
          entity_id: camera.men_ling_gao_jing_hua_mian
      - action: notify.mobile_app_iphone
        data:
          message: "门口有动静"
          data:
            image: "{{ state_attr('camera.men_ling_gao_jing_hua_mian', 'pic_url') }}"
```

## API 配额说明

萤石开放平台免费账号限制（以官方为准）：API 总调用约 **10000 次/天**、抓图 **1000 次/天**、AI 接口 **50-200 次/天**。

- 每多启用一个开关实体、每多一台设备，每次刷新都会增加 API 调用；请根据设备数量调整刷新间隔；
- camera 画面刷新单独消耗「抓图」配额，间隔建议 ≥ 60 秒；
- 告警推送走 Webhook 不消耗轮询配额，建议开启。

## 从旧版（dscao/ezviz）迁移

本集成的 domain 为 `hass_camera_ezviz`，与原 `ezviz` 插件及 HA 官方 EZVIZ 集成**互不冲突、可同时存在**；但由于 domain 不同，属于全新集成：

1. 删除（或先停用）旧的 `custom_components/ezviz` 目录与对应配置项；
2. 安装本集成，重新用 appKey/appSecret 添加；
3. 实体 unique_id 保持 `ezviz_xxx_序列号` 形式，若此前自动生成的实体 ID 一致则自动化无需修改。

## 常见问题

- **认证错误**：检查 appKey/appSecret 是否正确、应用是否已启用、设备是否已绑定到同一账号。
- **画面不更新**：确认设备在线且「抓图」配额未耗尽；拉大「自动抓图间隔」。
- **没有云台按钮**：该设备不支持 PTZ 或通道无权限（`permission` ≠ -1）。
- **Webhook 收不到**：HA 需具备公网可达的外部 URL（设置 → 网络 → 外部地址）。

## 与原版差异（本仓库主要改动）

- domain 调整为 `hass_camera_ezviz`，避免与 HA 官方 EZVIZ 集成冲突
- 修复选项流写入错误位置导致**选项不生效**的问题（原写入 `entry.data`，现写入 `entry.options`）
- 修复开关状态不随轮询刷新、实体状态属性中**泄露 accessToken** 的问题
- accessToken 统一管理：自动续期、接口失败自动重试一次、认证失败触发**重新认证流程（reauth）**
- 设备列表/通道列表支持分页（每页 50）
- Webhook 增加 webhook_id 校验（未注册 ID 返回 404），URL 使用 `get_url(prefer_external)` 生成
- 全部实体改为 `CoordinatorEntity`/`translation_key`/`icons.json` 现代化写法；`humandetect` 服务支持响应数据
- 新增 `strings.json`、`diagnostics.py`（脱敏）、`hacs.json`、CI 校验与自动发版工作流
- 修复 `mdi:mdi:` 图标笔误、`utcnow()` 弃用、按钮 device_class 误用等问题

## 致谢

- 原作者 [@dscao](https://github.com/dscao) —— [dscao/ezviz](https://github.com/dscao/ezviz)，本集成在其代码基础上二次开发，感谢原作者的开源工作。
- [萤石开放平台](https://open.ys7.com) 提供的开放 API。

## 免责说明

本项目为个人开源项目，与杭州萤石网络有限公司无关；"萤石"、"EZVIZ" 等商标归属其权利人。使用本集成请遵守萤石开放平台服务条款与 API 配额限制。
