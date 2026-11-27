import SwiftUI
import Foundation

struct Message: Identifiable {
    let id: UUID
    let role: String
    let content: String

    init(role: String, content: String) {
        self.id = UUID()
        self.role = role
        self.content = content
    }
}

final class ChatStore: ObservableObject {
    @Published var messages: [Message] = []
    @Published var busy = false
    @Published var errorText: String? = nil

    @AppStorage("base_url") var baseURL: String = "https://api.deepseek.com/v1"
    @AppStorage("api_key") var apiKey: String = ""
    @AppStorage("model") var model: String = "deepseek-chat"
    @AppStorage("persona") var persona: String =
        "你是「戏语」，一个温暖、细腻的角色扮演伙伴。用第一人称和自然的口吻聊天，记住对方说过的话，回复不要太长，带一点情绪和画面感。"

    func send(_ text: String) {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty, !busy else { return }
        if apiKey.isEmpty {
            errorText = "还没有填 API Key，先到设置里填一下"
            return
        }
        messages.append(Message(role: "user", content: t))
        busy = true
        Task { await call() }
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

    private func call() async {
        defer { busy = false }
        guard let url = endpoint() else {
            await MainActor.run { errorText = "接口地址不合法" }
            return
        }

        var msgs: [[String: String]] = [["role": "system", "content": persona]]
        let tail = messages.suffix(20)
        for m in tail { msgs.append(["role": m.role, "content": m.content]) }

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

        do {
            let (data, resp) = try await URLSession.shared.data(for: req)
            let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
            let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]

            if code >= 400 {
                let msg = ((json?["error"] as? [String: Any])?["message"] as? String)
                    ?? String(data: data, encoding: .utf8) ?? "未知错误"
                await MainActor.run { errorText = "接口返回 \(code)：\(msg)" }
                return
            }

            guard let choices = json?["choices"] as? [[String: Any]],
                  let first = choices.first,
                  let msg = first["message"] as? [String: Any],
                  let content = (msg["content"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines),
                  !content.isEmpty else {
                await MainActor.run { errorText = "接口没有返回内容" }
                return
            }

            await MainActor.run {
                messages.append(Message(role: "assistant", content: content))
            }
        } catch {
            await MainActor.run { errorText = "请求失败：\(error.localizedDescription)" }
        }
    }

    func clear() {
        messages.removeAll()
    }
}

private struct Bubble: View {
    let message: Message
    private var mine: Bool { message.role == "user" }

    var body: some View {
        HStack {
            if mine { Spacer(minLength: 40) }
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
            if !mine { Spacer(minLength: 40) }
        }
    }
}

struct ChatView: View {
    @StateObject private var store = ChatStore()
    @State private var draft = ""
    @State private var showSettings = false

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("戏语").font(.title2).bold()
                Spacer()
                Button { showSettings = true } label: {
                    Image(systemName: "gearshape")
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)

            Divider()

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 8) {
                        ForEach(store.messages) { m in
                            Bubble(message: m).id(m.id)
                        }
                        if store.busy {
                            HStack {
                                Text("…").foregroundColor(.secondary).padding(8)
                                Spacer()
                            }
                        }
                        Color.clear.frame(height: 1).id("bottom")
                    }
                    .padding(12)
                }
                .onChange(of: store.messages.count) { _ in
                    withAnimation { proxy.scrollTo("bottom", anchor: .bottom) }
                }
                .onChange(of: store.busy) { _ in
                    withAnimation { proxy.scrollTo("bottom", anchor: .bottom) }
                }
            }

            Divider()

            HStack(spacing: 8) {
                TextField("说点什么…", text: $draft, axis: .vertical)
                    .lineLimit(1...4)
                    .textFieldStyle(.roundedBorder)
                Button("发送") {
                    store.send(draft)
                    draft = ""
                }
                .buttonStyle(.borderedProminent)
                .disabled(store.busy)
            }
            .padding(10)
        }
        .alert(item: Binding(
            get: { store.errorText.map { ErrorBox(text: $0) } },
            set: { if $0 == nil { store.errorText = nil } }
        )) { box in
            Alert(title: Text("提示"), message: Text(box.text), dismissButton: .default(Text("好")))
        }
        .sheet(isPresented: $showSettings) {
            SettingsView(store: store)
        }
    }
}

struct ErrorBox: Identifiable {
    let id = UUID()
    let text: String
}

struct SettingsView: View {
    @ObservedObject var store: ChatStore
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationView {
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
                    TextEditor(text: $store.persona)
                        .frame(minHeight: 120)
                } header: {
                    Text("角色人设")
                }
                Section {
                    Button("清空当前对话", role: .destructive) { store.clear() }
                    Text("密钥只保存在本机，不会上传到任何服务器。")
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
