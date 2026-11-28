import SwiftUI
import Foundation
import UniformTypeIdentifiers

struct Actor: Identifiable, Codable, Hashable {
    var id: UUID = UUID()
    var name: String
    var greeting: String = ""
    var persona: String = ""
    var world: String = ""
}

struct Message: Identifiable, Codable, Hashable {
    var id: UUID = UUID()
    var role: String      // user / character
    var speaker: String
    var content: String
}

/// 从 AI 给的 JSON 里认出角色，兼容常见字段别名与批量格式。
func actorsFromJSON(_ raw: String) -> [Actor] {
    var text = raw.trimmingCharacters(in: .whitespacesAndNewlines)
    if text.hasPrefix("```") {
        var lines = text.components(separatedBy: .newlines)
        lines.removeFirst()
        if let last = lines.last, last.hasPrefix("```") { lines.removeLast() }
        text = lines.joined(separator: "\n")
    }
    guard let data = text.data(using: .utf8),
          let any = try? JSONSerialization.jsonObject(with: data) else { return [] }
    var dicts: [[String: Any]] = []
    if let arr = any as? [[String: Any]] {
        dicts = arr
    } else if let d = any as? [String: Any] {
        if let arr = d["characters"] as? [[String: Any]] { dicts = arr }
        else if let arr = d["roles"] as? [[String: Any]] { dicts = arr }
        else if let arr = d["data"] as? [[String: Any]] { dicts = arr }
        else { dicts = [d] }
    }
    var out: [Actor] = []
    for d in dicts {
        let name = (d["name"] as? String) ?? (d["名字"] as? String) ?? ""
        guard !name.isEmpty else { continue }
        let greeting = (d["greeting"] as? String) ?? (d["开场白"] as? String) ?? ""
        let persona = (d["persona"] as? String) ?? (d["prompt"] as? String)
            ?? (d["人设"] as? String) ?? (d["设定"] as? String) ?? ""
        let world = (d["world"] as? String) ?? (d["世界"] as? String) ?? (d["背景"] as? String) ?? ""
        out.append(Actor(name: name, greeting: greeting, persona: persona, world: world))
    }
    return out
}

struct Session: Identifiable, Codable, Hashable {
    var id: UUID = UUID()
    var name: String
    var type: String      // single / group
    var members: [UUID]
    var messages: [Message]
}

let formatRule = """
【输出格式规范（必须严格遵守）】
1. 角色说出口的台词就是正文，直接写，不加引号、不加“旁白：”之类的前缀、不加自己的名字。
2. 一切与对话无关的内容——动作、表情、神态、心理活动、场景描写、旁白、环境变化等——一律用中文全角括号（）包起来，放在对应台词的前面或后面。
3. 不使用 Markdown、列表、标题、代码块；不解释你在扮演；不跳出角色；不提“我是 AI”或“作为语言模型”。
4. 只输出你这一条回复的内容，不要替用户或其他角色写台词。
示例：（端起杯子抿了一口，眼神瞥向门口）这事儿你最好别再提了。
"""

let defaultGlobal = "你是一个沉浸式角色扮演引擎。始终以角色身份说话，不要提及自己是 AI，不要跳出设定。"

let termsVersion = "1"

final class Store: ObservableObject {
    @Published var actors: [Actor] = [] { didSet { save() } }
    @Published var sessions: [Session] = [] { didSet { save() } }
    @Published var busy = false
    @Published var typingName: String? = nil
    @Published var errorText: String? = nil

    @AppStorage("base_url") var baseURL: String = "https://api.deepseek.com/v1"
    @AppStorage("api_key") var apiKey: String = ""
    @AppStorage("model") var model: String = "deepseek-chat"
    @AppStorage("global_prompt") var globalPrompt: String = defaultGlobal

    init() {
        let d = UserDefaults.standard
        if let raw = d.string(forKey: "actors"), let data = raw.data(using: .utf8),
           let list = try? JSONDecoder().decode([Actor].self, from: data) {
            actors = list
        }
        if let raw = d.string(forKey: "sessions"), let data = raw.data(using: .utf8),
           let list = try? JSONDecoder().decode([Session].self, from: data) {
            sessions = list
        }
        if actors.isEmpty && !d.bool(forKey: "seeded") {
            let a = Actor(name: "戏语",
                          greeting: "（放下手里的书，抬头笑了笑）你来了，坐吧。今天想聊点什么？",
                          persona: "你是「戏语」，一个温暖、细腻的角色扮演伙伴。用第一人称和自然的口吻聊天，记住对方说过的话，回复不要太长，带一点情绪和画面感。")
            actors = [a]
            var msgs: [Message] = []
            if !a.greeting.isEmpty {
                msgs.append(Message(role: "character", speaker: a.name, content: a.greeting))
            }
            sessions = [Session(name: a.name, type: "single", members: [a.id], messages: msgs)]
            d.set(true, forKey: "seeded")
        }
    }

    private func save() {
        let d = UserDefaults.standard
        if let data = try? JSONEncoder().encode(actors) {
            d.set(String(data: data, encoding: .utf8), forKey: "actors")
        }
        if let data = try? JSONEncoder().encode(sessions) {
            d.set(String(data: data, encoding: .utf8), forKey: "sessions")
        }
    }

    func actorBy(_ id: UUID) -> Actor? { actors.first { $0.id == id } }

    func memberNames(_ s: Session) -> String {
        s.members.compactMap { actorBy($0)?.name }.joined(separator: "、")
    }

    func targets(_ s: Session) -> [Actor] {
        if s.type == "single" {
            return s.members.compactMap { actorBy($0) }
        }
        return s.members.compactMap { actorBy($0) }
    }

    func addSession(name: String, members: [UUID], type: String) {
        var msgs: [Message] = []
        for id in members {
            if let a = actorBy(id), !a.greeting.isEmpty {
                msgs.append(Message(role: "character", speaker: a.name, content: a.greeting))
            }
        }
        let title: String
        if type == "group" {
            title = name.isEmpty ? "群聊" : name
        } else {
            title = name.isEmpty ? (actorBy(members.first ?? UUID())?.name ?? "会话") : name
        }
        sessions.insert(Session(name: title, type: type, members: members, messages: msgs), at: 0)
    }

    var groups: [Session] {
        sessions.filter { $0.type == "group" }
    }

    func openSingle(actorID: UUID) -> UUID {
        if let s = sessions.first(where: { $0.type == "single" && $0.members.first == actorID }) {
            return s.id
        }
        let a = actorBy(actorID)
        var msgs: [Message] = []
        if let a = a, !a.greeting.isEmpty {
            msgs.append(Message(role: "character", speaker: a.name, content: a.greeting))
        }
        let s = Session(name: a?.name ?? "会话", type: "single", members: [actorID], messages: msgs)
        sessions.insert(s, at: 0)
        return s.id
    }

    func deleteActors(_ ids: [UUID]) {
        actors.removeAll { ids.contains($0.id) }
        sessions = sessions.compactMap { s in
            if s.type == "single" {
                return ids.contains(s.members.first ?? UUID()) ? nil : s
            }
            var s2 = s
            s2.members = s.members.filter { !ids.contains($0) }
            return s2.members.count >= 2 ? s2 : nil
        }
    }

    func removeGroup(atOffsets idx: IndexSet) {
        let ids = idx.map { groups[$0].id }
        sessions.removeAll { ids.contains($0.id) }
    }

    /// 查询 DeepSeek 的账户余额（只读，不产生费用）。
    func balance() async -> String {
        guard !apiKey.isEmpty else { return "请先填写并保存 API Key" }
        var comps = URLComponents(string: baseURL)
        guard let scheme = comps?.scheme, let host = comps?.host,
              let url = URL(string: "\(scheme)://\(host)/user/balance") else {
            return "Base URL 不合法"
        }
        var req = URLRequest(url: url)
        req.setValue("Bearer " + apiKey, forHTTPHeaderField: "Authorization")
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        req.timeoutInterval = 20
        do {
            let (data, resp) = try await URLSession.shared.data(for: req)
            let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
            if code == 404 || code == 405 {
                return "这个接口没有余额查询（目前只有 DeepSeek 提供 /user/balance）"
            }
            guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else {
                return "余额返回格式无法解析（HTTP \(code)）"
            }
            if code != 200 {
                let msg = ((obj["error"] as? [String: Any])?["message"] as? String) ?? "HTTP \(code)"
                return "查询失败：" + msg
            }
            let available = (obj["is_available"] as? Bool) ?? true
            var parts: [String] = []
            if let infos = obj["balance_infos"] as? [[String: Any]] {
                for i in infos {
                    let cur = (i["currency"] as? String) ?? ""
                    let total = (i["total_balance"] as? String) ?? "0"
                    let topped = (i["topped_up_balance"] as? String) ?? "-"
                    let granted = (i["granted_balance"] as? String) ?? "-"
                    parts.append("\(total) \(cur)（充值 \(topped) · 赠送 \(granted)）")
                }
            }
            let body = parts.isEmpty ? "接口未返回余额信息" : parts.joined(separator: "；")
            return body + "｜账户状态：" + (available ? "可用" : "不可用（余额可能不足）")
        } catch {
            return "查询失败：" + error.localizedDescription
        }
    }

    func send(_ text: String, sessionID: UUID) {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty, !busy else { return }
        guard let idx = sessions.firstIndex(where: { $0.id == sessionID }) else { return }
        if apiKey.isEmpty {
            errorText = "还没有填 API Key，先到设置里填一下"
            return
        }
        sessions[idx].messages.append(Message(role: "user", speaker: "我", content: t))
        let targets = self.targets(sessions[idx])
        if targets.isEmpty {
            errorText = "这个会话没有可用角色"
            return
        }
        busy = true
        Task {
            for a in targets {
                let payload = await MainActor.run { () -> (String, [[String: String]])? in
                    self.typingName = a.name
                    guard let i = self.sessions.firstIndex(where: { $0.id == sessionID }) else { return nil }
                    return (self.buildSystem(a, session: self.sessions[i]),
                            self.buildMessages(a, session: self.sessions[i]))
                }
                guard let p = payload else { break }
                do {
                    let reply = try await self.complete(system: p.0, messages: p.1)
                    let trimmed = reply.trimmingCharacters(in: .whitespacesAndNewlines)
                    if trimmed.isEmpty { throw CallError.empty }
                    await MainActor.run {
                        if let j = self.sessions.firstIndex(where: { $0.id == sessionID }) {
                            self.sessions[j].messages.append(Message(role: "character", speaker: a.name, content: trimmed))
                        }
                    }
                } catch {
                    await MainActor.run { self.errorText = "\(error.localizedDescription)" }
                    break
                }
            }
            await MainActor.run {
                self.typingName = nil
                self.busy = false
            }
        }
    }

    struct CallError: LocalizedError {
        static let empty = CallError()
        var errorDescription: String? { "模型返回了空内容" }
    }

    private func clip(_ s: String, _ n: Int) -> String {
        let one = s.replacingOccurrences(of: "\n", with: " ").trimmingCharacters(in: .whitespaces)
        return one.count > n ? String(one.prefix(n)) + "…" : one
    }

    func buildSystem(_ c: Actor, session: Session) -> String {
        var parts: [String] = []
        let gp = globalPrompt.trimmingCharacters(in: .whitespacesAndNewlines)
        if !gp.isEmpty { parts.append("【全局规则】\n" + gp) }
        let world = c.world.trimmingCharacters(in: .whitespacesAndNewlines)
        if !world.isEmpty { parts.append("【世界背景】\n" + world) }
        parts.append("【你的身份】\n你叫「\(c.name)」。你的角色设定：\n\(c.persona)")
        if session.type == "group" {
            let others = session.members.compactMap { actorBy($0) }.filter { $0.id != c.id }
            var lines: [String] = ["【同场角色】这轮对话里还有：\(others.isEmpty ? "无" : others.map { $0.name }.joined(separator: "、"))。"]
            for o in others {
                lines.append("- \(o.name)：\(clip(o.persona, 60))")
            }
            lines.append("你要始终清楚自己是谁，只以「\(c.name)」的身份说话和行动，绝不代替其他角色发言，也不要合并多个角色的话。")
            parts.append(lines.joined(separator: "\n"))
        }
        parts.append(formatRule)
        return parts.joined(separator: "\n\n")
    }

    func buildMessages(_ c: Actor, session: Session) -> [[String: String]] {
        let group = session.type == "group"
        var out: [[String: String]] = []
        let trimmed = session.messages.suffix(40)
        for m in trimmed {
            let content = m.content.trimmingCharacters(in: .whitespacesAndNewlines)
            if content.isEmpty { continue }
            if m.role == "user" {
                out.append(["role": "user", "content": group ? "用户：\(content)" : content])
            } else if m.role == "character" {
                out.append(["role": "assistant",
                            "content": group ? "\(m.speaker)：\(content)" : content])
            }
        }
        if group {
            let last = session.messages.last
            let tail = (last?.role == "user") ? (last?.content ?? "") : ""
            let hint = "【现在轮到你（\(c.name)）回应刚才的对话。只写你自己的一条回复：台词用正文，动作/神态/心理/场景一律用（）包住。不要写其他角色的台词，不要写用户的话。】"
            out.append(["role": "user", "content": tail.isEmpty ? hint : tail + "\n\n" + hint])
        }
        return out
    }

    private func endpoint() -> URL? {
        var b = baseURL.trimmingCharacters(in: .whitespacesAndNewlines)
        while b.hasSuffix("/") { b.removeLast() }
        if b.isEmpty { return nil }
        if !b.contains("://") { b = "https://" + b }
        if b.hasSuffix("/chat/completions") { return URL(string: b) }
        if b.hasSuffix("/v1") || b.hasSuffix("/v2") || b.hasSuffix("/v3") {
            return URL(string: b + "/chat/completions")
        }
        return URL(string: b + "/v1/chat/completions")
    }

    private func complete(system: String, messages: [[String: String]]) async throws -> String {
        guard let url = endpoint() else { throw CallError.empty }
        var msgs: [[String: String]] = [["role": "system", "content": system]]
        msgs.append(contentsOf: messages)
        let payload: [String: Any] = [
            "model": model,
            "messages": msgs,
            "temperature": 0.8,
            "max_tokens": 800,
            "stream": false
        ]
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.timeoutInterval = 180
        req.setValue("application/json; charset=utf-8", forHTTPHeaderField: "Content-Type")
        req.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        req.httpBody = try? JSONSerialization.data(withJSONObject: payload)

        let (data, resp) = try await URLSession.shared.data(for: req)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        if code >= 400 {
            let msg = ((json?["error"] as? [String: Any])?["message"] as? String)
                ?? String(data: data, encoding: .utf8) ?? "未知错误"
            throw NSError(domain: "xiyu", code: code,
                          userInfo: [NSLocalizedDescriptionKey: "接口返回 \(code)：\(msg)"])
        }
        guard let choices = json?["choices"] as? [[String: Any]],
              let first = choices.first,
              let msg = first["message"] as? [String: Any],
              let content = msg["content"] as? String else {
            throw CallError.empty
        }
        return content
    }
}

private struct Bubble: View {
    let message: Message
    private var mine: Bool { message.role == "user" }

    var body: some View {
        HStack {
            if mine { Spacer(minLength: 40) }
            VStack(alignment: mine ? .trailing : .leading, spacing: 3) {
                if !mine && !message.speaker.isEmpty {
                    Text(message.speaker)
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(.secondary)
                }
                Text(message.content)
                    .font(.system(size: 15))
                    .foregroundColor(mine ? .white : Color(red: 0.12, green: 0.12, blue: 0.12))
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(
                        RoundedRectangle(cornerRadius: 14, style: .continuous)
                            .fill(mine ? Color(red: 0.23, green: 0.44, blue: 0.88)
                                       : Color(red: 0.93, green: 0.94, blue: 0.96))
                    )
            }
            if !mine { Spacer(minLength: 40) }
        }
    }
}

struct ChatDetail: View {
    @ObservedObject var store: Store
    let sessionID: UUID
    @State private var draft = ""

    private var session: Session? {
        store.sessions.first { $0.id == sessionID }
    }

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 8) {
                        if let s = session {
                            ForEach(s.messages) { m in
                                Bubble(message: m).id(m.id)
                            }
                            if let t = store.typingName {
                                HStack {
                                    Text("（\(t) 正在回应…）")
                                        .font(.system(size: 13))
                                        .foregroundColor(.secondary)
                                        .padding(6)
                                    Spacer()
                                }
                            }
                        }
                        Color.clear.frame(height: 1).id("bottom")
                    }
                    .padding(12)
                }
                .onChange(of: session?.messages.count ?? 0) { _ in
                    withAnimation { proxy.scrollTo("bottom", anchor: .bottom) }
                }
                .onChange(of: store.typingName) { _ in
                    withAnimation { proxy.scrollTo("bottom", anchor: .bottom) }
                }
            }
            if let t = store.typingName {
                Text("\(t) 正在回应…")
                    .font(.footnote)
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 14)
            }
            Divider()
            HStack(spacing: 8) {
                TextField("说点什么…", text: $draft, axis: .vertical)
                    .lineLimit(1...4)
                    .textFieldStyle(.roundedBorder)
                Button("发送") {
                    store.send(draft, sessionID: sessionID)
                    draft = ""
                }
                .buttonStyle(.borderedProminent)
                .disabled(store.busy)
            }
            .padding(10)
        }
        .navigationTitle(session?.name ?? "会话")
        .navigationBarTitleDisplayMode(.inline)
        .alert(item: Binding(
            get: { store.errorText.map { Box(text: $0) } },
            set: { if $0 == nil { store.errorText = nil } }
        )) { box in
            Alert(title: Text("提示"), message: Text(box.text), dismissButton: .default(Text("好")))
        }
    }
}

struct Box: Identifiable {
    let id = UUID()
    let text: String
}

let termsText = """
戏语（XiyuChat）用户协议

欢迎使用戏语。请在使用前完整阅读下面的条款；点击「我已阅读并同意」表示你接受全部内容，否则程序不会进入主界面。

一、软件性质
1. 戏语是运行在你自己设备上的 AI 角色扮演聊天工具，本身不提供模型服务。
2. 对话内容由你自行配置的第三方大模型接口生成，你需要自备接口地址、模型名称和 API Key，并遵守该服务商的条款。
3. 本软件不收集、不上传你的聊天记录、角色设定与密钥；所有数据只保存在本机应用私有存储。

二、内容与使用规范
1. AI 生成的内容由模型产生，可能存在错误、偏见或不准确之处，不代表开发者观点，也不构成任何建议。
2. 你不得利用本软件制作、传播违反法律法规的内容，包括但不限于危害国家安全、暴力恐怖、违法犯罪、色情低俗、侵犯他人隐私与名誉、诈骗与冒充他人等内容。
3. 你不得利用角色扮演功能冒充真实人物骗取信任、实施欺诈，或诱导他人做出财产、人身方面的决定。
4. 你对使用本软件产生的一切行为与后果负责。

三、未成年人
未成年人应在监护人的知情与指导下使用，监护人应妥善保管 API Key 并设置合理的消费额度。

四、免责
1. 软件按「现状」提供，不承诺无错误、不中断或适用于特定目的。
2. 因第三方接口故障、网络问题、模型输出或你的操作造成的任何损失，开发者不承担责任。
3. 你应自行承担使用第三方接口产生的费用。

五、其他
1. 本协议可能随版本更新而调整，更新后会在启动时再次展示。
2. 你若不同意本协议的任何内容，请停止使用并删除本软件。
"""

struct TermsView: View {
    let onAgree: () -> Void
    @State private var showDecline = false

    var body: some View {
        VStack(spacing: 10) {
            Text("用户协议").font(.title2).bold().padding(.top, 20)
            Text("使用前请阅读并同意以下条款")
                .font(.footnote)
                .foregroundColor(.secondary)
            ScrollView {
                Text(termsText)
                    .font(.system(size: 14))
                    .lineSpacing(4)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(14)
                    .background(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(Color(red: 0.93, green: 0.94, blue: 0.96))
                    )
                    .padding(.horizontal, 16)
            }
            Button("我已阅读并同意") { onAgree() }
                .buttonStyle(.borderedProminent)
                .padding(.horizontal, 20)
            Button("不同意并退出") { showDecline = true }
                .foregroundColor(.red)
                .padding(.bottom, 16)
        }
        .alert("提示", isPresented: $showDecline) {
            Button("好", role: .cancel) {}
        } message: {
            Text("不同意用户协议则无法使用戏语，请退出应用。")
        }
    }
}

struct ChatView: View {
    @StateObject private var store = Store()
    @State private var showNew = false
    @State private var showSettings = false
    @AppStorage("terms_version") private var agreedVersion = ""

    var body: some View {
        if agreedVersion == termsVersion {
            mainBody
        } else {
            TermsView(onAgree: { agreedVersion = termsVersion })
        }
    }

    private var mainBody: some View {
        NavigationStack {
            List {
                Section {
                    ForEach(store.actors) { a in
                        NavigationLink {
                            ChatDetail(store: store, sessionID: store.openSingle(actorID: a.id))
                        } label: {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(a.name).font(.system(size: 17, weight: .semibold))
                                Text(a.persona.isEmpty ? "（还没有人设）" : a.persona)
                                    .font(.system(size: 12))
                                    .foregroundColor(.secondary)
                                    .lineLimit(1)
                            }
                            .padding(.vertical, 3)
                        }
                    }
                    .onDelete { idx in
                        store.deleteActors(idx.map { store.actors[$0].id })
                    }
                } header: {
                    HStack {
                        Text("角色")
                        Spacer()
                        Text("点进角色直接单聊")
                    }
                }
                if !store.groups.isEmpty {
                    Section {
                        ForEach(store.groups) { s in
                            NavigationLink {
                                ChatDetail(store: store, sessionID: s.id)
                            } label: {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(s.name).font(.system(size: 17, weight: .semibold))
                                    Text("群聊 · \(s.members.count) 位角色 · \(store.memberNames(s))")
                                        .font(.system(size: 12))
                                        .foregroundColor(.secondary)
                                        .lineLimit(1)
                                }
                                .padding(.vertical, 3)
                            }
                        }
                        .onDelete { idx in store.removeGroup(atOffsets: idx) }
                    } header: {
                        Text("群聊")
                    }
                }
            }
            .navigationTitle("戏语")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    NavigationLink { ActorsView(store: store) } label: { Text("角色") }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("设置") { showSettings = true }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("＋ 群聊") {
                        if store.actors.count < 2 { showSettings = true } else { showNew = true }
                    }
                }
            }
            .sheet(isPresented: $showNew) { NewSessionView(store: store) }
            .sheet(isPresented: $showSettings) { SettingsView(store: store) }
            .overlay {
                if store.actors.isEmpty {
                    Text("点左上角「角色」新建一个角色").foregroundColor(.secondary)
                }
            }
        }
    }
}

struct NewSessionView: View {
    @ObservedObject var store: Store
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var selected: Set<UUID> = []

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("群聊名称（可留空）", text: $name)
                } header: {
                    Text("名称")
                }
                Section {
                    ForEach(store.actors) { a in
                        Toggle(a.name, isOn: Binding(
                            get: { selected.contains(a.id) },
                            set: { on in
                                if on { selected.insert(a.id) } else { selected.remove(a.id) }
                            }
                        ))
                    }
                } header: {
                    Text("选择角色（至少 2 个，构成群聊）")
                }
            }
            .navigationTitle("新建群聊")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("创建") {
                        let ids = store.actors.filter { selected.contains($0.id) }.map { $0.id }
                        if ids.count < 2 { return }
                        store.addSession(name: name, members: ids, type: "group")
                        dismiss()
                    }
                    .disabled(selected.count < 2)
                }
            }
        }
    }
}

struct ActorsView: View {
    @ObservedObject var store: Store
    @State private var editing: Actor? = nil
    @State private var showImport = false

    var body: some View {
        List {
            ForEach(store.actors) { a in
                Button {
                    editing = a
                } label: {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(a.name).font(.system(size: 16, weight: .semibold))
                            .foregroundColor(.primary)
                        Text(a.persona)
                            .font(.system(size: 12))
                            .foregroundColor(.secondary)
                            .lineLimit(2)
                    }
                    .padding(.vertical, 2)
                }
            }
            .onDelete { idx in
                let ids = idx.map { store.actors[$0].id }
                store.actors.remove(atOffsets: idx)
                store.sessions = store.sessions.filter { s in
                    if s.type == "single" { return !ids.contains(s.members.first ?? UUID()) }
                    let rest = s.members.filter { !ids.contains($0) }
                    return rest.count >= 2
                }
            }
        }
        .navigationTitle("角色")
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("导入 JSON") { showImport = true }
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("＋ 角色") { editing = Actor(name: "", greeting: "", persona: "") }
            }
        }
        .sheet(item: $editing) { a in
            ActorEditView(store: store, actor: a)
        }
        .sheet(isPresented: $showImport) {
            ImportActorsView(store: store)
        }
    }
}

struct ImportActorsView: View {
    @ObservedObject var store: Store
    @Environment(\.dismiss) private var dismiss
    @State private var raw = ""
    @State private var message = ""
    @State private var showPicker = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Button("从文件选择 .json") { showPicker = true }
                    TextEditor(text: $raw)
                        .frame(minHeight: 240)
                        .disableAutocorrection(true)
                        .autocapitalization(.none)
                } header: {
                    Text("把 AI 生成的 JSON 粘贴到这里")
                } footer: {
                    Text("支持单个角色，也支持 characters 数组或直接数组。字段可用 name/名字、persona/prompt/人设、greeting/开场白、world/世界。")
                }
                if !message.isEmpty {
                    Section {
                        Text(message).font(.footnote).foregroundColor(.red)
                    }
                }
            }
            .navigationTitle("导入角色")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("导入") {
                        let list = actorsFromJSON(raw)
                        if list.isEmpty {
                            message = "没认出角色，检查一下 JSON（至少要有一个 name 字段）"
                            return
                        }
                        for a in list { store.actors.append(a) }
                        dismiss()
                    }
                }
            }
            .fileImporter(isPresented: $showPicker, allowedContentTypes: [.json, .text, .plainText],
                          allowsMultipleSelection: false) { result in
                guard case .success(let urls) = result, let url = urls.first else { return }
                let ok = url.startAccessingSecurityScopedResource()
                defer { if ok { url.stopAccessingSecurityScopedResource() } }
                if let s = try? String(contentsOf: url, encoding: .utf8) {
                    raw = s
                } else {
                    message = "这个文件读不出来，换一个 UTF-8 的 .json 试试"
                }
            }
        }
    }
}

struct ActorEditView: View {
    @ObservedObject var store: Store
    let actor: Actor
    @Environment(\.dismiss) private var dismiss

    @State private var name = ""
    @State private var greeting = ""
    @State private var persona = ""
    @State private var world = ""

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("名字", text: $name)
                    TextField("开场白（可留空）", text: $greeting, axis: .vertical)
                        .lineLimit(2...4)
                } header: {
                    Text("基本信息")
                }
                Section {
                    TextEditor(text: $persona).frame(minHeight: 100)
                } header: {
                    Text("人设提示词")
                }
                Section {
                    TextEditor(text: $world).frame(minHeight: 70)
                } header: {
                    Text("世界背景（可留空）")
                }
            }
            .navigationTitle("角色")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("保存") {
                        let n = name.trimmingCharacters(in: .whitespaces)
                        if n.isEmpty { return }
                        var fresh = actor
                        fresh.name = n
                        fresh.greeting = greeting
                        fresh.persona = persona
                        fresh.world = world
                        if let i = store.actors.firstIndex(where: { $0.id == actor.id }) {
                            store.actors[i] = fresh
                        } else {
                            store.actors.append(fresh)
                        }
                        dismiss()
                    }
                }
            }
            .onAppear {
                if name.isEmpty { name = actor.name }
                if greeting.isEmpty { greeting = actor.greeting }
                if persona.isEmpty { persona = actor.persona }
                if world.isEmpty { world = actor.world }
            }
        }
    }
}

struct SettingsView: View {
    @ObservedObject var store: Store
    @Environment(\.dismiss) private var dismiss
    @State private var balanceText = "点「查询余额」试试（仅 DeepSeek 支持）"
    @State private var balanceBusy = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Base URL", text: $store.baseURL)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                    TextField("API Key", text: $store.apiKey)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                    TextField("模型名称", text: $store.model)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                } header: {
                    Text("接口")
                }
                Section {
                    Text(balanceText).font(.system(size: 14))
                    Button(balanceBusy ? "查询中…" : "查询余额") {
                        balanceBusy = true
                        balanceText = "查询中…"
                        Task {
                            let r = await store.balance()
                            await MainActor.run {
                                balanceText = r
                                balanceBusy = false
                            }
                        }
                    }
                    .disabled(balanceBusy)
                } header: {
                    Text("账户余额")
                } footer: {
                    Text("来自 DeepSeek 的 /user/balance 接口，只读取、不产生费用。")
                }
                Section {
                    TextEditor(text: $store.globalPrompt)
                        .frame(minHeight: 110)
                } header: {
                    Text("全局提示词")
                }
                Section {
                    Text("密钥只保存在本机应用私有存储，不会上传到任何服务器。")
                        .font(.footnote)
                        .foregroundColor(.secondary)
                }
            }
            .navigationTitle("设置")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("完成") { dismiss() }
                }
            }
        }
    }
}
