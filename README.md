# 戏语 · XiyuChat

一个跑在自己设备上的 AI 角色扮演聊天软件。创建角色、写人设、拉群聊，让几个 AI 角色在同一场景里各自说话。

桌面端纯 Python 标准库实现（Tkinter + urllib），无需安装任何第三方运行时依赖，已适配 Windows（x64 / x86 / ARM64）、Linux（x64 / ARM64）与 macOS（Intel / Apple Silicon）。移动端是独立的原生实现：Android 用 Java，iOS 用 SwiftUI，都不依赖 Python 运行时，功能与桌面端保持一致（多角色、单聊与群聊）。

> A local AI role-play chat app. Multiple characters, group scenes, custom personas, local encrypted storage. Runs on Windows, Linux, macOS, plus native Android / iOS clients.

## 功能

- **角色**：名字、开场白、人设提示词；「高级权限」可填写世界背景（世界观、地点、规则）。
- **批量导入角色**：把 AI 生成的角色 JSON 粘贴进来，或直接选一个 `.json` 文件，名字、开场白、人设、世界背景自动填好；群聊里也能一次导入多个成员。
- **单聊**：只和一个角色对话，角色有开场白时自动作为第一条消息。
- **群聊**：把多个角色放进同一个房间，每个角色依次单独回复、各自成条，用名字区分说话人；提示词里会列出同场其他角色的设定，避免抢戏、串戏。
- **格式约定**：台词写正文，动作、神态、心理、旁白一律用中文全角括号（）标注在台词前后，例如：
  `（端起杯子抿了一口，眼神瞥向门口）这事儿你最好别再提了。`
- **长期记忆**（桌面端）：每聊若干条自动把关键剧情摘要成一份 `memory/<会话>.md`，之后每次请求都带上；也可以手动编辑。
- **接口**：内置 DeepSeek、OpenAI 兼容接口预设，也可自定义 Base URL / 模型名。
- **密钥安全**：API Key 加密后保存（`secret.bin`），不写死在代码里，不上传任何服务器。Windows 用 DPAPI（绑定当前用户），Linux / macOS 用 PBKDF2 派生密钥（文件权限 600），移动端只存在本机应用私有存储。
- **数据目录**：Windows 默认 `%APPDATA%\XiyuChat\Data`，macOS 默认 `~/Library/Application Support/XiyuChat/Data`，Linux 默认 `$XDG_DATA_HOME/XiyuChat/Data`（无则 `~/.local/share`）。可在 F2 →「数据目录」改到任意位置；更换时可以把现有角色和聊天记录一起复制过去。
- **用量统计**：F2 →「用量余额」可查询 DeepSeek 账户余额，并显示本机累计的 token 用量；移动端在「设置 → 账户余额」里。

## 用 AI 帮你写角色

不想手敲人设的话，把下面这段发给任意大模型，它会回一段可以直接导入的 JSON：

```text
你是一个角色设计助手。请按下面的要求输出一个角色，只输出 JSON，不要解释。

- name：角色名字，2～6 个字，好念
- greeting：开场白，1～2 句，带一个中文括号里的动作或神态，例如（放下手里的书，抬头笑了笑）
- persona：人设提示词，150～300 字，写清身份、性格、说话方式、与用户的关系、说话节奏
- world：世界背景，80～150 字，写清时代、地点、规则、当下的处境

输出格式：
{"name": "…", "greeting": "…", "persona": "…", "world": "…"}

要多个角色就输出：{"characters": [{"…"}, {"…"}]}
```

把回的内容整段粘进来就行，带不带 ````json` 包裹都能认。字段写成中文（名字 / 开场白 / 人设 / 设定 / 世界 / 背景）也认。

导入入口：

- 桌面端：「＋ 创建角色」→「粘贴 JSON」或「从文件导入」；群聊窗口里是「粘贴 JSON 加成员」/「从文件加成员」，一次建好并自动选中。
- Android：「角色管理」→「导入 JSON」，可以粘贴，也能「从文件选择 .json」。
- iOS：「角色」页右上「导入 JSON」，可以粘贴，也能从文件里选。


## 下载

到 [Releases](../../releases) 按系统选一个，全部是同一版本 `1.0.0`：

| 平台 | 文件 | 说明 |
| --- | --- | --- |
| Windows 64 位 | `XiyuSetup.exe` | 安装向导，可选安装位置与数据目录 |
| Windows 32 位 | `XiyuSetup-x86.exe` | 同上，32 位系统用 |
| Windows 64 位便携 | `Xiyu-1.0.0-windows-x64.zip` | 解压即用 |
| Windows 32 位便携 | `Xiyu-1.0.0-windows-x86.zip` | 解压即用 |
| Windows ARM64 | `Xiyu-1.0.0-windows-arm64.zip` | 解压即用，骁龙本 / ARM 版 Windows |
| Linux x64 | `Xiyu-1.0.0-linux-x64.tar.gz` | 解压后 `./Xiyu`，需系统有 `libtk8.6` |
| Linux ARM64 | `Xiyu-1.0.0-linux-arm64.tar.gz` | 64 位 ARM 架构的 Linux 发行版，同上 |
| macOS Apple Silicon | `Xiyu-1.0.0-macos-arm64.dmg` | 打开镜像，把 `Xiyu.app` 拖进「应用程序」 |
| macOS Intel | `Xiyu-1.0.0-macos-x64.dmg` | 同上 |
| Android（64 位 ARM） | `Xiyu-1.0.0-android-arm64-v8a.apk` | 现在绝大多数手机，首选 |
| Android（32 位 ARM） | `Xiyu-1.0.0-android-armeabi-v7a.apk` | 较老的 32 位安卓设备 |
| Android（x86_64） | `Xiyu-1.0.0-android-x86_64.apk` | 模拟器 / x86 平板 |
| Android（x86 / 32 位） | `Xiyu-1.0.0-android-x86.apk` | 同上，32 位 x86 环境 |
| Android（通用） | `Xiyu-1.0.0-android-universal.apk` | 不确定架构时用这个，一个包兼容全部 |
| iOS | `Xiyu-1.0.0-ios-unsigned.ipa` | **未签名**，需用 Sideloadly / AltStore / 自签工具配合自己的证书安装 |

Android 的安装包按 CPU 架构拆开了：不确定选哪个就下载 `universal`。所有 APK 都自带应用图标，直接安装（需允许未知来源）。

macOS 首次打开若提示「无法验证开发者」，右键 `Xiyu.app` →「打开」，或执行：

```bash
xattr -dr com.apple.quarantine /Applications/Xiyu.app
```

iOS 的 ipa 未做 Apple 签名（签名需要自己的开发者证书），可以用 Sideloadly 之类的工具配上自己的证书和描述文件安装，或者用 Xcode 直接编译到设备。

首次启动会要求填写 API Key 并选择接口预设；之后随时按 `F2`（桌面端）/ 设置按钮（移动端）修改。

## 移动端

Android 与 iOS 客户端与桌面端功能对齐：

- 会话列表：单聊与群聊都在这里，长按 / 左滑可删除。
- 角色管理：新建、编辑（名字、开场白、人设、世界背景）、删除，支持粘贴 JSON 或从文件导入。
- 群聊：选中多个角色创建房间，发言后每个角色按顺序各回复一条，界面按名字区分。
- 设置：接口地址、API Key、模型名、全局提示词、账户余额。

数据与会话只保存在本机应用私有目录，卸载即清除。

首次启动会弹一次用户协议，点同意后不再重复出现；只有协议内容更新时才会再弹。

## 从源码运行

桌面端：

```bash
python main.py
```

要求 Python 3.9+（Tkinter 为 Python 自带组件）。没有任何 `pip` 依赖。

Android（需要 JDK 17 + Android SDK 34）：

```bash
cd android && ./gradlew assembleRelease
```

产物在 `android/app/build/outputs/apk/release/`，按 ABI 拆分；`universal` 为全架构包。

iOS（需要 macOS + Xcode，工程文件由 XcodeGen 生成）：

```bash
cd ios && xcodegen generate && open Xiyu.xcodeproj
```

App 图标是构建时从 `assets/icon256.png` 生成进 `Assets.xcassets` 的（见 `.github/workflows/build.yml`），本地构建前需要自己跑一次同样的转换。

## 打包

Windows（安装版）：

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

Linux / macOS（便携版 / 镜像）：

```bash
pyinstaller --noconfirm --clean --onefile --windowed --name Xiyu main.py

# macOS 生成 dmg
hdiutil create -volname "Xiyu 1.0.0" -srcfolder pkg -ov -format UDZO Xiyu-1.0.0-macos-arm64.dmg
```

各平台安装包由 GitHub Actions 构建，配置见 `.github/workflows/build.yml`（9 个 job：Windows x64 / x86 / ARM64、Linux x64 / ARM64、macOS arm64 / Intel、Android、iOS；Android 一个 job 出 5 个 ABI 包）。

## 目录结构

```
main.py                 启动入口
xiyu_core/
  paths.py              数据目录解析与切换（location.json 指针，三平台根目录）
  secure.py             API Key 加密（Windows DPAPI / 其它平台 PBKDF2）
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
assets/                 图标（icon.ico / icon256.png，移动端图标由构建时生成）
android/                Android 原生客户端（Java + Gradle，按 ABI 拆分）
ios/                    iOS 原生客户端（SwiftUI + XcodeGen 工程描述）
.github/workflows/      全平台自动构建
```

## 数据与隐私

桌面端所有数据都在本机：

```
<数据目录>/
  config.json           接口、模型、温度等（不含密钥）
  characters.json       角色
  sessions.json         会话列表
  chats/<id>.json       每个会话的聊天记录
  memory/<id>.md        长期记忆
  secret.bin            加密的 API Key（Windows 为 DPAPI，绑定当前用户；Linux / macOS 为 PBKDF2，权限 600）
  usage.json            token 用量统计
```

软件只会访问你自己填写的接口地址（默认 DeepSeek），不会向其它服务器发送任何内容。仓库里没有任何密钥、配置或聊天数据。

## 已知限制

- 只有 DeepSeek 提供余额查询接口；OpenAI 兼容接口下余额一栏会提示不支持（三端都有入口，桌面端还多一项本机 token 统计）。
- token 统计是本机累加，不跨设备同步。
- Windows 下 API Key 用用户级 DPAPI 加密，换电脑需要在设置里重新填写。
- Linux 需要系统装有 Tk（Debian / Ubuntu：`sudo apt install python3-tk libtk8.6`）。
- macOS 包未做公证（notarization），首次运行需要手动放行。
- iOS ipa 未签名，必须自签后安装；iOS 端长期记忆与 token 统计尚未实现。
- 移动端不包含长期记忆摘要（会话历史存在本机，够用但不会自动摘要）。
- Linux ARM64、Windows ARM64、macOS Intel 构建在 CI 中标记为容错，若 runner 不可用则该产物可能缺失。

## License

[MIT](LICENSE)
