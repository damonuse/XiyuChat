# 戏语 · XiyuChat

一个跑在自己电脑上的 AI 角色扮演聊天软件。创建角色、写人设、拉群聊，让几个 AI 角色在同一场景里各自说话。

纯 Python 标准库实现（Tkinter + urllib），无需安装任何第三方运行时依赖，打包后是一个可直接双击的 Windows 程序。

> A local AI role-play chat app for Windows. Multiple characters, group scenes, custom personas, local encrypted storage.

## 功能

- **角色**：名字、开场白、人设提示词；勾选「高级权限」可填写世界背景（世界观、地点、规则）。
- **群聊**：把多个角色放进同一个房间，每个角色单独回复、独立成条，用头像和名字区分说话人。
- **格式约定**：台词写正文，动作、神态、心理、旁白一律用中文全角括号（）标注在台词前后，例如：
  `（端起杯子抿了一口，眼神瞥向门口）这事儿你最好别再提了。`
- **长期记忆**：每聊若干条自动把关键剧情摘要成一份 `memory/<会话>.md`，之后每次请求都带上；也可以手动编辑。
- **接口**：内置 DeepSeek、OpenAI 兼容接口预设，也可自定义 Base URL / 模型名。
- **密钥安全**：API Key 用 Windows DPAPI 加密后保存（`secret.bin`），不写死在代码里，不上传任何服务器。
- **数据目录**：默认在 `%APPDATA%\XiyuChat\Data`，可在 F2 →「数据目录」改到任意盘符；更换时可以把现有角色和聊天记录一起复制过去。
- **用量统计**：F2 →「用量余额」可查询 DeepSeek 账户余额，并显示本机累计的 token 用量。

## 安装

从 [Releases](../../releases) 下载 `XiyuSetup.exe`，双击运行，按向导选择安装位置与数据目录即可。安装完成后桌面会有一个「戏语」快捷方式。

首次启动会要求填写 API Key 并选择接口预设；之后随时按 `F2` 修改。

## 从源码运行

```bash
python main.py
```

要求 Python 3.9+（Tkinter 为 Python 自带组件）。没有任何 `pip` 依赖。

## 打包

```bash
pip install pyinstaller

# 主程序（onedir）
pyinstaller --noconfirm --clean --onedir --windowed --name Xiyu \
  --icon assets/icon.ico --distpath App --workpath build --specpath build main.py

# 安装向导（单文件，把上面打好的 App/Xiyu 一起嵌进去）
pyinstaller --noconfirm --clean --onefile --windowed --name XiyuSetup \
  --icon assets/icon.ico \
  --add-data "App/Xiyu;app" --add-data "assets/icon.ico;." \
  --distpath dist --workpath build_setup --specpath build_setup installer/installer.py
```

## 目录结构

```
main.py                 启动入口
xiyu_core/
  paths.py              数据目录解析与切换（location.json 指针）
  secure.py             API Key 加密（Windows DPAPI）
  storage.py            配置 / 角色 / 会话 / 聊天记录的 JSON 读写
  llm.py                OpenAI 兼容接口客户端、余额查询
  engine.py             提示词组装（人设、世界背景、长期记忆、格式规范）
  memory.py             长期记忆的生成与存储
  usage.py              token 用量统计
xiyu_ui/
  app.py                主窗口、会话切换、发送与回复调度
  chat_view.py          Canvas 自绘的聊天气泡
  dialogs.py            设置窗口、角色创建、长期记忆窗口
  theme.py / widgets.py 配色与圆角按钮
installer/installer.py  安装向导
assets/                 图标
```

## 数据与隐私

所有数据都在本机：

```
<数据目录>/
  config.json           接口、模型、温度等（不含密钥）
  characters.json       角色
  sessions.json         会话列表
  chats/<id>.json       每个会话的聊天记录
  memory/<id>.md        长期记忆
  secret.bin            DPAPI 加密的 API Key（绑定当前 Windows 用户）
  usage.json            token 用量统计
```

软件只会访问你自己填写的接口地址（默认 DeepSeek），不会向其它服务器发送任何内容。

## 已知限制

- 只有 DeepSeek 提供余额查询接口；OpenAI 兼容接口下余额一栏会提示不支持。
- token 统计是本机累加，不跨设备同步。
- API Key 用用户级 DPAPI 加密，换电脑需要在设置里重新填写。

## License

[MIT](LICENSE)
