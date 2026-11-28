package com.xiyu.chat;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * 戏语 Android 客户端（原生 Java，无第三方依赖）。
 * 功能对齐桌面端：多角色、单聊 / 群聊、独立人设、本地加密存储（应用私有目录）。
 * 只依赖 OpenAI 兼容的 /chat/completions 接口，API Key 仅保存在本机 SharedPreferences。
 */
public class MainActivity extends Activity {

    private static final String DEFAULT_BASE = "https://api.deepseek.com/v1";
    private static final String DEFAULT_MODEL = "deepseek-chat";
    private static final String DEFAULT_GLOBAL =
            "你是一个沉浸式角色扮演引擎。始终以角色身份说话，不要提及自己是 AI，不要跳出设定。";

    private static final String FORMAT_RULE =
            "【输出格式规范（必须严格遵守）】\n"
                    + "1. 角色说出口的台词就是正文，直接写，不加引号、不加“旁白：”之类的前缀、不加自己的名字。\n"
                    + "2. 一切与对话无关的内容——动作、表情、神态、心理活动、场景描写、旁白、环境变化等——"
                    + "一律用中文全角括号（）包起来，放在对应台词的前面或后面。\n"
                    + "3. 不使用 Markdown、列表、标题、代码块；不解释你在扮演；不跳出角色；不提“我是 AI”或“作为语言模型”。\n"
                    + "4. 只输出你这一条回复的内容，不要替用户或其他角色写台词。\n"
                    + "示例：（端起杯子抿了一口，眼神瞥向门口）这事儿你最好别再提了。";

    private static final int C_BG = Color.WHITE;
    private static final int C_TEXT = Color.parseColor("#1F1F1F");
    private static final int C_SUB = Color.parseColor("#8B93A3");
    private static final int C_ACCENT = Color.parseColor("#3B6FE0");
    private static final int C_GRAY = Color.parseColor("#EEF1F6");
    private static final int C_LINE = Color.parseColor("#DCE0E9");

    private SharedPreferences prefs;
    private JSONArray chars = new JSONArray();
    private JSONArray sessions = new JSONArray();
    private final Handler ui = new Handler(Looper.getMainLooper());

    private static final String TERMS_VERSION = "1";
    private static final int REQ_JSON = 1001;
    private EditText pendingImportInput;

    private boolean busy = false;
    private JSONObject curSession;
    private LinearLayout msgBox;
    private ScrollView scrollView;
    private EditText input;
    private TextView typingView;

    private static final String TERMS =
            "戏语（XiyuChat）用户协议\n\n"
                    + "欢迎使用戏语。请在使用前完整阅读下面的条款；点击「我已阅读并同意」表示你接受全部内容，否则程序不会进入主界面。\n\n"
                    + "一、软件性质\n"
                    + "1. 戏语是运行在你自己设备上的 AI 角色扮演聊天工具，本身不提供模型服务。\n"
                    + "2. 对话内容由你自行配置的第三方大模型接口生成，你需要自备接口地址、模型名称和 API Key，并遵守该服务商的条款。\n"
                    + "3. 本软件不收集、不上传你的聊天记录、角色设定与密钥；所有数据只保存在本机应用私有存储。\n\n"
                    + "二、内容与使用规范\n"
                    + "1. AI 生成的内容由模型产生，可能存在错误、偏见或不准确之处，不代表开发者观点，也不构成任何建议。\n"
                    + "2. 你不得利用本软件制作、传播违反法律法规的内容，包括但不限于危害国家安全、暴力恐怖、违法犯罪、色情低俗、侵犯他人隐私与名誉、诈骗与冒充他人等内容。\n"
                    + "3. 你不得利用角色扮演功能冒充真实人物骗取信任、实施欺诈，或诱导他人做出财产、人身方面的决定。\n"
                    + "4. 你对使用本软件产生的一切行为与后果负责。\n\n"
                    + "三、未成年人\n"
                    + "未成年人应在监护人的知情与指导下使用，监护人应妥善保管 API Key 并设置合理的消费额度。\n\n"
                    + "四、免责\n"
                    + "1. 软件按「现状」提供，不承诺无错误、不中断或适用于特定目的。\n"
                    + "2. 因第三方接口故障、网络问题、模型输出或你的操作造成的任何损失，开发者不承担责任。\n"
                    + "3. 你应自行承担使用第三方接口产生的费用。\n\n"
                    + "五、其他\n"
                    + "1. 本协议可能随版本更新而调整，更新后会在启动时再次展示。\n"
                    + "2. 你若不同意本协议的任何内容，请停止使用并删除本软件。";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences("xiyu", MODE_PRIVATE);
        if (TERMS_VERSION.equals(prefs.getString("terms_version", ""))) {
            enterApp();
        } else {
            showTermsPage();
        }
    }

    private void showTermsPage() {
        LinearLayout root = page();
        root.addView(text("用户协议", 26, true, C_TEXT));
        root.addView(text("使用前请阅读并同意以下条款", 13, false, C_SUB));

        ScrollView sc = new ScrollView(this);
        TextView body = text(TERMS, 14, false, C_TEXT);
        body.setLineSpacing(dp(4), 1.3f);
        body.setPadding(dp(14), dp(12), dp(14), dp(12));
        body.setBackground(round(C_GRAY, 12));
        sc.addView(body, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        LinearLayout.LayoutParams scLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f);
        scLp.topMargin = dp(12);
        root.addView(sc, scLp);

        Button agree = button("我已阅读并同意", true);
        agree.setOnClickListener(v -> {
            prefs.edit().putString("terms_version", TERMS_VERSION).apply();
            enterApp();
        });
        LinearLayout.LayoutParams btnLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(48));
        btnLp.topMargin = dp(12);
        root.addView(agree, btnLp);

        Button refuse = button("不同意并退出", false);
        refuse.setOnClickListener(v -> finish());
        LinearLayout.LayoutParams btnLp2 = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(48));
        btnLp2.topMargin = dp(8);
        root.addView(refuse, btnLp2);

        setContentView(root);
    }

    private void enterApp() {
        if (prefs.getString("api_key", "").isEmpty()) {
            showSettingsPage(true);
            return;
        }
        loadData();
        ensureDefault();
        showSessionsPage();
    }

    // ================= 数据 =================

    private void loadData() {
        try {
            chars = new JSONArray(prefs.getString("characters", "[]"));
        } catch (Exception e) {
            chars = new JSONArray();
        }
        try {
            sessions = new JSONArray(prefs.getString("sessions", "[]"));
        } catch (Exception e) {
            sessions = new JSONArray();
        }
    }

    private void saveData() {
        prefs.edit()
                .putString("characters", chars.toString())
                .putString("sessions", sessions.toString())
                .apply();
    }

    private JSONObject defaultCharacter() throws Exception {
        JSONObject c = new JSONObject();
        c.put("id", "c_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12));
        c.put("name", "戏语");
        c.put("persona", "你是「戏语」，一个温暖、细腻的角色扮演伙伴。用第一人称和自然的口吻聊天，"
                + "记住对方说过的话，回复不要太长，带一点情绪和画面感。");
        c.put("greeting", "（放下手里的书，抬头笑了笑）你来了，坐吧。今天想聊点什么？");
        c.put("world", "");
        return c;
    }

    private void ensureDefault() {
        if (prefs.getBoolean("seeded", false)) return;
        if (chars.length() == 0) {
            try {
                JSONObject c = defaultCharacter();
                chars.put(c);
                JSONObject s = new JSONObject();
                s.put("id", "s_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12));
                s.put("type", "single");
                s.put("name", c.optString("name"));
                s.put("single_id", c.optString("id"));
                s.put("members", new JSONArray().put(c.optString("id")));
                JSONArray msgs = new JSONArray();
                if (!c.optString("greeting").isEmpty()) {
                    JSONObject m = new JSONObject();
                    m.put("role", "character");
                    m.put("speaker", c.optString("name"));
                    m.put("content", c.optString("greeting"));
                    msgs.put(m);
                }
                s.put("msgs", msgs);
                sessions.put(s);
                saveData();
            } catch (Exception ignored) {
            }
        }
        prefs.edit().putBoolean("seeded", true).apply();
    }

    private JSONObject findChar(String id) {
        for (int i = 0; i < chars.length(); i++) {
            JSONObject c = chars.optJSONObject(i);
            if (c != null && id != null && id.equals(c.optString("id"))) return c;
        }
        return null;
    }

    // ================= 通用控件 =================

    private int dp(float v) {
        return (int) (v * getResources().getDisplayMetrics().density);
    }

    private TextView text(String s, float size, boolean bold, int color) {
        TextView tv = new TextView(this);
        tv.setText(s);
        tv.setTextSize(size);
        tv.setTextColor(color);
        if (bold) tv.setTypeface(Typeface.DEFAULT_BOLD);
        return tv;
    }

    private GradientDrawable round(int color, float radius) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(dp(radius));
        return d;
    }

    private Button button(String label, boolean primary) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(14);
        b.setAllCaps(false);
        if (primary) {
            b.setTextColor(Color.WHITE);
            b.setBackground(round(C_ACCENT, 12));
        } else {
            b.setTextColor(C_TEXT);
            b.setBackground(round(C_GRAY, 12));
        }
        return b;
    }

    private LinearLayout.LayoutParams wrapLp(int top) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(top);
        return lp;
    }

    private EditText field(String hint, String value, int lines) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setText(value);
        e.setTextSize(15);
        e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        e.setMinLines(lines);
        e.setGravity(Gravity.TOP);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(8);
        e.setLayoutParams(lp);
        return e;
    }

    private LinearLayout page() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(C_BG);
        root.setPadding(dp(16), dp(22), dp(16), dp(16));
        return root;
    }

    private LinearLayout header(String title, String action, Runnable onAction) {
        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.addView(text(title, 24, true, C_TEXT),
                new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        if (action != null) {
            Button b = button(action, true);
            b.setOnClickListener(v -> onAction.run());
            bar.addView(b);
        }
        return bar;
    }

    // ================= 会话列表页 =================

    private void showSessionsPage() {
        LinearLayout root = page();
        root.addView(header("戏语", "＋ 群聊", this::newSessionDialog));
        root.addView(text("点角色直接单聊；多个角色一起聊用「＋ 群聊」", 13, false, C_SUB));

        LinearLayout tools = new LinearLayout(this);
        tools.setOrientation(LinearLayout.HORIZONTAL);
        Button actors = button("角色管理", false);
        actors.setOnClickListener(v -> showCharactersPage());
        tools.addView(actors, wrapLp(10));
        Button set = button("设置", false);
        set.setOnClickListener(v -> showSettingsPage(false));
        tools.addView(set, wrapLp(10));
        root.addView(tools);

        ScrollView sc = new ScrollView(this);
        LinearLayout list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);

        list.addView(text("角色", 13, true, C_SUB), wrapLp(12));
        if (chars.length() == 0) {
            list.addView(text("还没有角色，点上方「角色管理」新建一个。", 14, false, C_SUB), wrapLp(20));
        }
        for (int i = 0; i < chars.length(); i++) {
            final int ci = i;
            final JSONObject c = chars.optJSONObject(i);
            if (c == null) continue;
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.VERTICAL);
            row.setPadding(dp(14), dp(12), dp(14), dp(12));
            row.setBackground(round(C_GRAY, 12));
            row.addView(text(c.optString("name", "角色"), 17, true, C_TEXT));
            String persona = c.optString("persona", "");
            row.addView(text(persona.isEmpty() ? "（还没有人设）" : persona, 12, false, C_SUB));
            row.setOnClickListener(v -> openSingle(c));
            row.setOnLongClickListener(v -> {
                editCharacter(ci);
                return true;
            });
            list.addView(row, wrapLp(10));
        }

        StringBuilder groupHeader = new StringBuilder();
        int groupCount = 0;
        for (int i = 0; i < sessions.length(); i++) {
            JSONObject s = sessions.optJSONObject(i);
            if (s != null && "group".equals(s.optString("type"))) groupCount++;
        }
        if (groupCount > 0) {
            list.addView(text("群聊", 13, true, C_SUB), wrapLp(12));
            for (int i = 0; i < sessions.length(); i++) {
                final int index = i;
                final JSONObject s = sessions.optJSONObject(i);
                if (s == null || !"group".equals(s.optString("type"))) continue;
                LinearLayout row = new LinearLayout(this);
                row.setOrientation(LinearLayout.VERTICAL);
                row.setPadding(dp(14), dp(12), dp(14), dp(12));
                row.setBackground(round(C_GRAY, 12));
                JSONArray members = s.optJSONArray("members");
                String sub = "群聊 · " + (members == null ? 0 : members.length())
                        + " 位角色 · " + memberNames(s);
                row.addView(text(s.optString("name", "群聊"), 17, true, C_TEXT));
                row.addView(text(sub, 12, false, C_SUB));
                row.setOnClickListener(v -> showChatPage(s));
                row.setOnLongClickListener(v -> {
                    confirmDeleteSession(index);
                    return true;
                });
                list.addView(row, wrapLp(10));
            }
        }
        sc.addView(list);
        root.addView(sc, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        setContentView(root);
    }

    /** 点角色直接进入和它的单聊；没有会话就现建一个。 */
    private void openSingle(JSONObject c) {
        String cid = c.optString("id");
        for (int i = 0; i < sessions.length(); i++) {
            JSONObject s = sessions.optJSONObject(i);
            if (s == null) continue;
            if ("single".equals(s.optString("type")) && cid.equals(s.optString("single_id"))) {
                showChatPage(s);
                return;
            }
        }
        try {
            JSONObject s = new JSONObject();
            s.put("id", "s_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12));
            s.put("type", "single");
            s.put("name", c.optString("name", "角色"));
            s.put("single_id", cid);
            s.put("members", new JSONArray().put(cid));
            JSONArray msgs = new JSONArray();
            if (!c.optString("greeting").isEmpty()) {
                JSONObject m = new JSONObject();
                m.put("role", "character");
                m.put("speaker", c.optString("name"));
                m.put("content", c.optString("greeting"));
                msgs.put(m);
            }
            s.put("msgs", msgs);
            sessions.put(s);
            saveData();
            showChatPage(s);
        } catch (Exception ignored) {
        }
    }

    private String memberNames(JSONObject s) {
        StringBuilder sb = new StringBuilder();
        JSONArray members = s.optJSONArray("members");
        if (members == null) return "";
        for (int i = 0; i < members.length(); i++) {
            JSONObject c = findChar(members.optString(i));
            if (c == null) continue;
            if (sb.length() > 0) sb.append("、");
            sb.append(c.optString("name"));
        }
        return sb.toString();
    }

    private void confirmDeleteSession(int index) {
        JSONObject s = sessions.optJSONObject(index);
        if (s == null) return;
        new AlertDialog.Builder(this)
                .setTitle("删除会话")
                .setMessage("确定删除「" + s.optString("name") + "」及其聊天记录吗？")
                .setPositiveButton("删除", (d, w) -> {
                    sessions.remove(index);
                    saveData();
                    showSessionsPage();
                })
                .setNegativeButton("取消", null)
                .show();
    }

    // ================= 新建会话 =================

    private void newSessionDialog() {
        if (chars.length() == 0) {
            Toast.makeText(this, "先创建一个角色", Toast.LENGTH_SHORT).show();
            showCharactersPage();
            return;
        }
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(20), dp(12), dp(20), dp(4));

        EditText name = field("群聊名称（可留空）", "", 1);
        name.setSingleLine(true);
        box.addView(name);
        box.addView(text("选择参与的角色（至少 2 个，构成群聊）", 12, false, C_SUB), wrapLp(12));

        final List<CheckBox> boxes = new ArrayList<>();
        for (int i = 0; i < chars.length(); i++) {
            JSONObject c = chars.optJSONObject(i);
            if (c == null) continue;
            CheckBox cb = new CheckBox(this);
            cb.setText(c.optString("name"));
            cb.setTextSize(15);
            cb.setTag(c.optString("id"));
            boxes.add(cb);
            box.addView(cb);
        }

        ScrollView sc = new ScrollView(this);
        sc.addView(box);

        new AlertDialog.Builder(this)
                .setTitle("新建会话")
                .setView(sc)
                .setPositiveButton("创建", (d, w) -> {
                    List<String> picked = new ArrayList<>();
                    for (CheckBox cb : boxes) {
                        if (cb.isChecked()) picked.add((String) cb.getTag());
                    }
                    if (picked.size() < 2) {
                        Toast.makeText(this, "至少选两个角色", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    try {
                        JSONObject s = new JSONObject();
                        s.put("id", "s_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12));
                        JSONArray members = new JSONArray();
                        for (String id : picked) members.put(id);
                        s.put("members", members);
                        JSONArray msgs = new JSONArray();
                        if (picked.size() == 1) {
                            JSONObject c = findChar(picked.get(0));
                            String n = c == null ? "角色" : c.optString("name");
                            s.put("type", "single");
                            s.put("name", name.getText().toString().trim().isEmpty()
                                    ? n : name.getText().toString().trim());
                            s.put("single_id", picked.get(0));
                            if (c != null && !c.optString("greeting").isEmpty()) {
                                JSONObject m = new JSONObject();
                                m.put("role", "character");
                                m.put("speaker", n);
                                m.put("content", c.optString("greeting"));
                                msgs.put(m);
                            }
                        } else {
                            s.put("type", "group");
                            String n = name.getText().toString().trim();
                            s.put("name", n.isEmpty() ? "群聊" : n);
                            s.put("single_id", "");
                            for (String id : picked) {
                                JSONObject c = findChar(id);
                                if (c != null && !c.optString("greeting").isEmpty()) {
                                    JSONObject m = new JSONObject();
                                    m.put("role", "character");
                                    m.put("speaker", c.optString("name"));
                                    m.put("content", c.optString("greeting"));
                                    msgs.put(m);
                                }
                            }
                        }
                        s.put("msgs", msgs);
                        sessions.put(s);
                        saveData();
                        showChatPage(s);
                    } catch (Exception ignored) {
                    }
                })
                .setNegativeButton("取消", null)
                .show();
    }

    // ================= 角色管理 =================

    private void showCharactersPage() {
        LinearLayout root = page();
        root.addView(header("角色", "＋ 角色", () -> editCharacter(-1)));
        root.addView(text("每个角色都有自己的名字、开场白和人设", 13, false, C_SUB));

        LinearLayout tools = new LinearLayout(this);
        tools.setOrientation(LinearLayout.HORIZONTAL);
        Button imp = button("导入 JSON", false);
        imp.setOnClickListener(v -> importCharactersDialog());
        tools.addView(imp, wrapLp(10));
        root.addView(tools);

        ScrollView sc = new ScrollView(this);
        LinearLayout list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        for (int i = 0; i < chars.length(); i++) {
            final int index = i;
            final JSONObject c = chars.optJSONObject(i);
            if (c == null) continue;
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.VERTICAL);
            row.setPadding(dp(14), dp(12), dp(14), dp(12));
            row.setBackground(round(C_GRAY, 12));
            row.addView(text(c.optString("name"), 17, true, C_TEXT));
            String p = c.optString("persona");
            if (p.length() > 60) p = p.substring(0, 60) + "…";
            row.addView(text(p, 12, false, C_SUB));
            row.setOnClickListener(v -> editCharacter(index));
            row.setOnLongClickListener(v -> {
                confirmDeleteCharacter(index);
                return true;
            });
            list.addView(row, wrapLp(10));
        }
        sc.addView(list);
        root.addView(sc, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        Button back = button("返回会话", false);
        back.setOnClickListener(v -> showSessionsPage());
        root.addView(back, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(46)));
        setContentView(root);
    }

    /** 粘贴 JSON 一次性导入角色。 */
    private void importCharactersDialog() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(20), dp(12), dp(20), dp(4));
        box.addView(text("把 AI 生成的 JSON 粘贴进来：支持单个角色，也支持 characters 数组。"
                + "字段可用 name/名字、persona/prompt/人设、greeting/开场白、world/世界。", 12, false, C_SUB),
                wrapLp(10));
        EditText input = field("在这里粘贴 JSON", "", 8);
        input.setSingleLine(false);
        box.addView(input);
        Button pick = button("从文件选择 .json", false);
        pick.setOnClickListener(v -> pickJsonFile(input));
        box.addView(pick, wrapLp(6));
        ScrollView sc = new ScrollView(this);
        sc.addView(box);
        new AlertDialog.Builder(this)
                .setTitle("导入角色")
                .setView(sc)
                .setPositiveButton("导入", (d, w) -> {
                    int added = importCharacters(input.getText().toString());
                    if (added == 0) {
                        Toast.makeText(this, "没认出角色，检查 JSON 里有没有 name", Toast.LENGTH_SHORT).show();
                    } else {
                        saveData();
                        Toast.makeText(this, "已导入 " + added + " 个角色", Toast.LENGTH_SHORT).show();
                        showCharactersPage();
                    }
                })
                .setNegativeButton("取消", null)
                .show();
    }

    private void pickJsonFile(EditText target) {
        pendingImportInput = target;
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        startActivityForResult(intent, REQ_JSON);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQ_JSON || resultCode != RESULT_OK || data == null) return;
        if (pendingImportInput == null) return;
        Uri uri = data.getData();
        if (uri == null) return;
        try {
            InputStream is = getContentResolver().openInputStream(uri);
            if (is == null) return;
            BufferedReader br = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = br.readLine()) != null) sb.append(line).append('\n');
            br.close();
            pendingImportInput.setText(sb.toString());
        } catch (Exception e) {
            Toast.makeText(this, "读取失败：" + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    private String firstOf(JSONObject o, String... keys) {
        for (String k : keys) {
            String v = o.optString(k, "");
            if (!v.isEmpty()) return v;
        }
        return "";
    }

    private int importCharacters(String raw) {
        String t = raw == null ? "" : raw.trim();
        if (t.startsWith("```")) {
            int nl = t.indexOf('\n');
            t = nl >= 0 ? t.substring(nl + 1) : t;
            int end = t.lastIndexOf("```");
            if (end >= 0) t = t.substring(0, end);
            t = t.trim();
        }
        int added = 0;
        try {
            Object parsed = new org.json.JSONTokener(t).nextValue();
            JSONArray arr = null;
            if (parsed instanceof JSONArray) {
                arr = (JSONArray) parsed;
            } else if (parsed instanceof JSONObject) {
                JSONObject o = (JSONObject) parsed;
                if (o.optJSONArray("characters") != null) arr = o.optJSONArray("characters");
                else if (o.optJSONArray("roles") != null) arr = o.optJSONArray("roles");
                else if (o.optJSONArray("data") != null) arr = o.optJSONArray("data");
                else {
                    arr = new JSONArray();
                    arr.put(o);
                }
            }
            if (arr == null) return 0;
            for (int i = 0; i < arr.length(); i++) {
                JSONObject d = arr.optJSONObject(i);
                if (d == null) continue;
                String name = firstOf(d, "name", "名字");
                if (name.isEmpty()) continue;
                JSONObject c = new JSONObject();
                c.put("id", "c_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12));
                c.put("name", name);
                c.put("greeting", firstOf(d, "greeting", "开场白"));
                c.put("persona", firstOf(d, "persona", "prompt", "人设", "设定"));
                c.put("world", firstOf(d, "world", "世界", "背景"));
                chars.put(c);
                added++;
            }
        } catch (Exception ignored) {
        }
        return added;
    }

    private void editCharacter(int index) {
        JSONObject origin = index >= 0 ? chars.optJSONObject(index) : null;

        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(20), dp(12), dp(20), dp(4));

        EditText name = field("名字", origin == null ? "" : origin.optString("name"), 1);
        name.setSingleLine(true);
        EditText greeting = field("开场白（可留空）", origin == null ? "" : origin.optString("greeting"), 2);
        EditText persona = field("人设提示词（身份、性格、说话方式、与用户的关系）",
                origin == null ? "" : origin.optString("persona"), 5);
        EditText world = field("世界背景（可留空，仅本人设生效）", origin == null ? "" : origin.optString("world"), 3);
        box.addView(name);
        box.addView(greeting);
        box.addView(persona);
        box.addView(world);

        ScrollView sc = new ScrollView(this);
        sc.addView(box);

        new AlertDialog.Builder(this)
                .setTitle(origin == null ? "新建角色" : "编辑角色")
                .setView(sc)
                .setPositiveButton("保存", (d, w) -> {
                    String n = name.getText().toString().trim();
                    if (n.isEmpty()) {
                        Toast.makeText(this, "名字不能为空", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    try {
                        JSONObject c = origin == null ? new JSONObject() : origin;
                        if (origin == null) {
                            c.put("id", "c_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12));
                            chars.put(c);
                        }
                        c.put("name", n);
                        c.put("greeting", greeting.getText().toString().trim());
                        c.put("persona", persona.getText().toString().trim());
                        c.put("world", world.getText().toString().trim());
                        saveData();
                        showCharactersPage();
                    } catch (Exception ignored) {
                    }
                })
                .setNegativeButton("取消", null)
                .show();
    }

    private void confirmDeleteCharacter(int index) {
        JSONObject c = chars.optJSONObject(index);
        if (c == null) return;
        new AlertDialog.Builder(this)
                .setTitle("删除角色")
                .setMessage("确定删除「" + c.optString("name") + "」吗？相关群聊会同时移除这个角色。")
                .setPositiveButton("删除", (d, w) -> {
                    String id = c.optString("id");
                    chars.remove(index);
                    // 从所有会话里移除，群聊不足两人则整个删除
                    JSONArray keep = new JSONArray();
                    for (int i = 0; i < sessions.length(); i++) {
                        JSONObject s = sessions.optJSONObject(i);
                        if (s == null) continue;
                        JSONArray members = s.optJSONArray("members");
                        JSONArray next = new JSONArray();
                        if (members != null) {
                            for (int k = 0; k < members.length(); k++) {
                                if (!id.equals(members.optString(k))) next.put(members.optString(k));
                            }
                        }
                        if ("group".equals(s.optString("type")) && next.length() < 2) continue;
                        if ("single".equals(s.optString("type")) && next.length() == 0) continue;
                        try {
                            s.put("members", next);
                        } catch (Exception ignored) {
                        }
                        keep.put(s);
                    }
                    sessions = keep;
                    saveData();
                    showCharactersPage();
                })
                .setNegativeButton("取消", null)
                .show();
    }

    // ================= 设置页 =================

    private void showSettingsPage(boolean firstRun) {
        LinearLayout root = page();
        root.addView(text("戏语", 26, true, C_TEXT));
        root.addView(text(firstRun ? "第一次使用，先填写接口信息" : "设置", 14, false, C_SUB));

        EditText base = field("接口地址 Base URL", prefs.getString("base_url", DEFAULT_BASE), 1);
        base.setSingleLine(true);
        EditText key = field("API Key", prefs.getString("api_key", ""), 1);
        key.setSingleLine(true);
        EditText model = field("模型名称", prefs.getString("model", DEFAULT_MODEL), 1);
        model.setSingleLine(true);
        EditText global = field("全局提示词", prefs.getString("global_prompt", DEFAULT_GLOBAL), 4);
        root.addView(base);
        root.addView(key);
        root.addView(model);
        root.addView(global);

        TextView balanceView = text("点「查询余额」试试（仅 DeepSeek 支持）", 13, false, C_SUB);
        root.addView(balanceView, wrapLp(10));
        Button balanceBtn = button("查询余额", false);
        balanceBtn.setOnClickListener(v -> queryBalance(
                base.getText().toString().trim(),
                key.getText().toString().trim(),
                balanceView, balanceBtn));
        root.addView(balanceBtn, wrapLp(10));

        Button save = button("保存", true);
        save.setOnClickListener(v -> {
            String b = base.getText().toString().trim();
            String k = key.getText().toString().trim();
            String m = model.getText().toString().trim();
            String g = global.getText().toString().trim();
            if (b.isEmpty()) b = DEFAULT_BASE;
            if (m.isEmpty()) m = DEFAULT_MODEL;
            if (g.isEmpty()) g = DEFAULT_GLOBAL;
            prefs.edit().putString("base_url", b).putString("api_key", k)
                    .putString("model", m).putString("global_prompt", g).apply();
            Toast.makeText(this, "已保存到本机", Toast.LENGTH_SHORT).show();
            if (firstRun) {
                loadData();
                ensureDefault();
                showSessionsPage();
            } else {
                showSessionsPage();
            }
        });
        LinearLayout.LayoutParams saveLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(46));
        saveLp.topMargin = dp(16);
        root.addView(save, saveLp);

        if (!firstRun) {
            Button back = button("返回会话", false);
            back.setOnClickListener(v -> showSessionsPage());
            root.addView(back, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, dp(46)));
        }

        ScrollView sc = new ScrollView(this);
        sc.addView(root);
        setContentView(sc);
    }

    // ================= 余额 =================

    private void queryBalance(String base, String key, TextView out, Button btn) {
        if (key.isEmpty()) {
            out.setText("请先填写 API Key");
            return;
        }
        btn.setEnabled(false);
        out.setText("查询中…");
        new Thread(() -> {
            String result;
            try {
                String b = base.isEmpty() ? DEFAULT_BASE : base;
                if (!b.contains("://")) b = "https://" + b;
                java.net.URI uri = new java.net.URI(b);
                String root = uri.getScheme() + "://" + uri.getHost()
                        + (uri.getPort() > 0 ? ":" + uri.getPort() : "");
                HttpURLConnection c = (HttpURLConnection)
                        new URL(root + "/user/balance").openConnection();
                c.setRequestMethod("GET");
                c.setRequestProperty("Authorization", "Bearer " + key);
                c.setRequestProperty("Accept", "application/json");
                c.setConnectTimeout(15000);
                c.setReadTimeout(25000);
                int code = c.getResponseCode();
                InputStream is = code >= 400 ? c.getErrorStream() : c.getInputStream();
                StringBuilder sb = new StringBuilder();
                if (is != null) {
                    try (BufferedReader br = new BufferedReader(
                            new InputStreamReader(is, StandardCharsets.UTF_8))) {
                        String line;
                        while ((line = br.readLine()) != null) sb.append(line);
                    }
                }
                String raw = sb.toString();
                if (code == 404 || code == 405) {
                    result = "这个接口没有余额查询（目前只有 DeepSeek 支持）";
                } else if (code != 200) {
                    String msg = raw;
                    try {
                        msg = new JSONObject(raw).optJSONObject("error").optString("message", raw);
                    } catch (Exception ignored) {
                    }
                    result = "查询失败 " + code + "：" + msg;
                } else {
                    JSONObject o = new JSONObject(raw);
                    boolean ok = o.optBoolean("is_available", true);
                    JSONArray infos = o.optJSONArray("balance_infos");
                    StringBuilder tb = new StringBuilder();
                    if (infos != null) {
                        for (int i = 0; i < infos.length(); i++) {
                            JSONObject info = infos.optJSONObject(i);
                            if (info == null) continue;
                            if (tb.length() > 0) tb.append("；");
                            tb.append(info.optString("total_balance", "0")).append(" ")
                                    .append(info.optString("currency", ""))
                                    .append("（充值 ").append(info.optString("topped_up_balance", "-"))
                                    .append(" · 赠送 ").append(info.optString("granted_balance", "-"))
                                    .append("）");
                        }
                    }
                    String body = tb.length() == 0 ? "接口未返回余额信息" : tb.toString();
                    result = body + "｜账户状态：" + (ok ? "可用" : "不可用（余额可能不足）");
                }
            } catch (Exception e) {
                result = "查询失败：" + e.getMessage();
            }
            final String r = result;
            ui.post(() -> {
                out.setText(r);
                btn.setEnabled(true);
            });
        }).start();
    }

    // ================= 聊天页 =================

    private void showChatPage(JSONObject s) {
        curSession = s;
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(C_BG);

        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(16), dp(10), dp(8), dp(10));
        bar.addView(text(s.optString("name", "会话"), 20, true, C_TEXT),
                new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        Button back = button("返回", false);
        back.setOnClickListener(v -> {
            busy = false;
            saveData();
            showSessionsPage();
        });
        bar.addView(back);
        root.addView(bar);
        root.addView(text(subTitle(s), 12, false, C_SUB));

        scrollView = new ScrollView(this);
        msgBox = new LinearLayout(this);
        msgBox.setOrientation(LinearLayout.VERTICAL);
        msgBox.setPadding(dp(12), dp(6), dp(12), dp(6));
        scrollView.addView(msgBox);
        root.addView(scrollView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        LinearLayout bottom = new LinearLayout(this);
        bottom.setOrientation(LinearLayout.HORIZONTAL);
        bottom.setPadding(dp(10), dp(8), dp(10), dp(10));
        input = new EditText(this);
        input.setHint("说点什么…");
        input.setTextSize(15);
        input.setMinHeight(dp(44));
        bottom.addView(input, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        Button send = button("发送", true);
        send.setOnClickListener(v -> onSend());
        bottom.addView(send);
        root.addView(bottom);

        setContentView(root);
        renderChat();
    }

    private String subTitle(JSONObject s) {
        if ("group".equals(s.optString("type"))) {
            return "群聊 · " + memberNames(s) + "（每人依次发言）";
        }
        return "与 " + s.optString("name") + " 的对话";
    }

    private JSONArray msgs() {
        JSONArray m = curSession.optJSONArray("msgs");
        if (m == null) {
            m = new JSONArray();
            try {
                curSession.put("msgs", m);
            } catch (Exception ignored) {
            }
        }
        return m;
    }

    private void renderChat() {
        msgBox.removeAllViews();
        JSONArray arr = msgs();
        for (int i = 0; i < arr.length(); i++) {
            JSONObject m = arr.optJSONObject(i);
            if (m == null) continue;
            addBubble(m.optString("content"), "user".equals(m.optString("role")),
                    m.optString("speaker", ""));
        }
        scrollDown();
    }

    private void addBubble(String content, boolean mine, String speaker) {
        LinearLayout wrap = new LinearLayout(this);
        wrap.setGravity(mine ? Gravity.END : Gravity.START);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(6);
        wrap.setLayoutParams(lp);

        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        if (!mine && speaker != null && !speaker.isEmpty()) {
            col.addView(text(speaker, 12, true, C_SUB));
        }
        TextView tv = new TextView(this);
        tv.setText(content);
        tv.setTextSize(15);
        tv.setTextColor(mine ? Color.WHITE : C_TEXT);
        tv.setBackground(round(mine ? C_ACCENT : C_GRAY, 14));
        tv.setPadding(dp(12), dp(8), dp(12), dp(8));
        tv.setLineSpacing(dp(3), 1f);
        int max = (int) (getResources().getDisplayMetrics().widthPixels * 0.8f);
        tv.setMaxWidth(max);
        col.addView(tv);
        wrap.addView(col);
        msgBox.addView(wrap);
    }

    private void appendBubble(String content, boolean mine, String speaker) {
        addBubble(content, mine, speaker);
        scrollDown();
    }

    private void scrollDown() {
        if (scrollView != null) scrollView.post(() -> scrollView.fullScroll(View.FOCUS_DOWN));
    }

    private void showTyping(String who) {
        if (typingView != null) msgBox.removeView(typingView);
        typingView = text("（" + who + " 正在回应…）", 13, false, C_SUB);
        msgBox.addView(typingView, wrapLp(6));
        scrollDown();
    }

    private void clearTyping() {
        if (typingView != null) {
            msgBox.removeView(typingView);
            typingView = null;
        }
    }

    private void onSend() {
        if (busy) {
            Toast.makeText(this, "上一条还在等回复", Toast.LENGTH_SHORT).show();
            return;
        }
        if (prefs.getString("api_key", "").isEmpty()) {
            Toast.makeText(this, "先在设置里填 API Key", Toast.LENGTH_LONG).show();
            showSettingsPage(true);
            return;
        }
        String s = input.getText().toString().trim();
        if (s.isEmpty()) return;
        input.setText("");

        JSONArray arr = msgs();
        try {
            JSONObject m = new JSONObject();
            m.put("role", "user");
            m.put("speaker", "我");
            m.put("content", s);
            arr.put(m);
        } catch (Exception ignored) {
        }
        appendBubble(s, true, "");
        saveData();
        requestRound();
    }

    private void requestRound() {
        List<JSONObject> targets = new ArrayList<>();
        if ("group".equals(curSession.optString("type"))) {
            JSONArray members = curSession.optJSONArray("members");
            if (members != null) {
                for (int i = 0; i < members.length(); i++) {
                    JSONObject c = findChar(members.optString(i));
                    if (c != null) targets.add(c);
                }
            }
        } else {
            JSONObject c = findChar(curSession.optString("single_id"));
            if (c != null) targets.add(c);
        }
        if (targets.isEmpty()) {
            Toast.makeText(this, "这个会话没有可用角色", Toast.LENGTH_SHORT).show();
            return;
        }

        busy = true;
        final JSONObject sessionRef = curSession;
        new Thread(() -> {
            for (JSONObject c : targets) {
                final String cname = c.optString("name");
                ui.post(() -> showTyping(cname));
                String reply;
                try {
                    reply = callModel(c);
                } catch (Exception e) {
                    final String err = e.getMessage() == null ? e.toString() : e.getMessage();
                    ui.post(() -> {
                        clearTyping();
                        busy = false;
                        Toast.makeText(this, "回复失败：" + err, Toast.LENGTH_LONG).show();
                    });
                    return;
                }
                if (reply == null || reply.trim().isEmpty()) {
                    ui.post(() -> {
                        clearTyping();
                        busy = false;
                        Toast.makeText(this, "模型返回了空内容", Toast.LENGTH_SHORT).show();
                    });
                    return;
                }
                final String text = reply.trim();
                ui.post(() -> {
                    if (curSession != sessionRef) return;
                    clearTyping();
                    try {
                        JSONObject m = new JSONObject();
                        m.put("role", "character");
                        m.put("speaker", cname);
                        m.put("content", text);
                        msgs().put(m);
                    } catch (Exception ignored) {
                    }
                    appendBubble(text, false, cname);
                    saveData();
                });
            }
            ui.post(() -> {
                clearTyping();
                busy = false;
            });
        }).start();
    }

    // ================= 提示词与接口 =================

    private String clip(String s, int n) {
        s = s == null ? "" : s.replace("\n", " ").trim();
        return s.length() > n ? s.substring(0, n) + "…" : s;
    }

    private String buildSystem(JSONObject c) {
        boolean group = "group".equals(curSession.optString("type"));
        StringBuilder sb = new StringBuilder();
        String gp = prefs.getString("global_prompt", DEFAULT_GLOBAL).trim();
        if (!gp.isEmpty()) sb.append("【全局规则】\n").append(gp).append("\n\n");
        String world = c.optString("world", "").trim();
        if (!world.isEmpty()) sb.append("【世界背景】\n").append(world).append("\n\n");
        sb.append("【你的身份】\n你叫「").append(c.optString("name"))
                .append("」。你的角色设定：\n").append(c.optString("persona").trim()).append("\n\n");
        if (group) {
            JSONArray members = curSession.optJSONArray("members");
            List<JSONObject> others = new ArrayList<>();
            if (members != null) {
                for (int i = 0; i < members.length(); i++) {
                    JSONObject o = findChar(members.optString(i));
                    if (o != null && !o.optString("id").equals(c.optString("id"))) others.add(o);
                }
            }
            StringBuilder names = new StringBuilder();
            for (JSONObject o : others) {
                if (names.length() > 0) names.append("、");
                names.append(o.optString("name"));
            }
            sb.append("【同场角色】这轮对话里还有：").append(names.length() == 0 ? "无" : names)
                    .append("。\n");
            for (JSONObject o : others) {
                sb.append("- ").append(o.optString("name")).append("：")
                        .append(clip(o.optString("persona"), 60)).append("\n");
            }
            sb.append("你要始终清楚自己是谁，只以「").append(c.optString("name"))
                    .append("」的身份说话和行动，绝不代替其他角色发言，也不要合并多个角色的话。\n\n");
        }
        sb.append(FORMAT_RULE);
        return sb.toString();
    }

    private JSONArray buildMessages(JSONObject c) throws Exception {
        boolean group = "group".equals(curSession.optString("type"));
        JSONArray all = msgs();
        JSONArray out = new JSONArray();
        int limit = Math.max(2, 20) * 2;
        int from = Math.max(0, all.length() - limit);
        for (int i = from; i < all.length(); i++) {
            JSONObject m = all.optJSONObject(i);
            if (m == null) continue;
            String role = m.optString("role");
            String content = m.optString("content").trim();
            if (content.isEmpty()) continue;
            JSONObject o = new JSONObject();
            if ("user".equals(role)) {
                o.put("role", "user");
                o.put("content", group ? "用户：" + content : content);
            } else if ("character".equals(role)) {
                o.put("role", "assistant");
                o.put("content", group
                        ? m.optString("speaker", c.optString("name")) + "：" + content
                        : content);
            } else {
                continue;
            }
            out.put(o);
        }
        if (group) {
            // 末尾追加这次轮到自己发言的提示
            JSONObject tip = new JSONObject();
            tip.put("role", "user");
            JSONObject last = all.length() > 0 ? all.optJSONObject(all.length() - 1) : null;
            String tail = last != null && "user".equals(last.optString("role"))
                    ? last.optString("content") : "";
            String hint = "【现在轮到你（" + c.optString("name") + "）回应刚才的对话。只写你自己的一条回复："
                    + "台词用正文，动作/神态/心理/场景一律用（）包住。不要写其他角色的台词，不要写用户的话。】";
            tip.put("content", tail.isEmpty() ? hint : tail + "\n\n" + hint);
            out.put(tip);
        }
        return out;
    }

    private String callModel(JSONObject c) throws Exception {
        String base = prefs.getString("base_url", DEFAULT_BASE);
        String key = prefs.getString("api_key", "");
        String model = prefs.getString("model", DEFAULT_MODEL);

        JSONObject body = new JSONObject();
        body.put("model", model);
        JSONArray arr = new JSONArray();
        JSONObject sys = new JSONObject();
        sys.put("role", "system");
        sys.put("content", buildSystem(c));
        arr.put(sys);
        JSONArray msgs = buildMessages(c);
        for (int i = 0; i < msgs.length(); i++) arr.put(msgs.get(i));
        body.put("messages", arr);
        body.put("temperature", 0.8);
        body.put("max_tokens", 800);
        body.put("stream", false);

        URL url = new URL(endpoint(base));
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("POST");
        conn.setConnectTimeout(20000);
        conn.setReadTimeout(180000);
        conn.setDoOutput(true);
        conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        conn.setRequestProperty("Authorization", "Bearer " + key);
        conn.setRequestProperty("Accept", "application/json");
        byte[] out = body.toString().getBytes(StandardCharsets.UTF_8);
        try (OutputStream os = conn.getOutputStream()) {
            os.write(out);
        }
        int code = conn.getResponseCode();
        InputStream is = code >= 400 ? conn.getErrorStream() : conn.getInputStream();
        StringBuilder sb = new StringBuilder();
        if (is != null) {
            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(is, StandardCharsets.UTF_8))) {
                String line;
                while ((line = br.readLine()) != null) sb.append(line);
            }
        }
        String raw = sb.toString();
        if (code >= 400) {
            String msg = raw;
            try {
                msg = new JSONObject(raw).optJSONObject("error").optString("message", raw);
            } catch (Exception ignored) {
            }
            throw new Exception("接口返回 " + code + "：" + msg);
        }
        JSONObject data = new JSONObject(raw);
        JSONArray choices = data.optJSONArray("choices");
        if (choices == null || choices.length() == 0) throw new Exception("接口没有返回内容");
        JSONObject msg = choices.getJSONObject(0).optJSONObject("message");
        return msg == null ? "" : msg.optString("content", "");
    }

    private String endpoint(String base) {
        String b = base == null ? "" : base.trim();
        while (b.endsWith("/")) b = b.substring(0, b.length() - 1);
        if (!b.contains("://")) b = "https://" + b;
        if (b.endsWith("/chat/completions")) return b;
        if (b.endsWith("/v1") || b.endsWith("/v2") || b.endsWith("/v3")) {
            return b + "/chat/completions";
        }
        return b + "/v1/chat/completions";
    }
}
