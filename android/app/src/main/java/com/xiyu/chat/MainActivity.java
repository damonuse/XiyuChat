package com.xiyu.chat;

import android.app.Activity;
import android.content.SharedPreferences;
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

/**
 * 戏语 Android 客户端（原生 Java 实现，不依赖任何第三方库）。
 * 对话走 OpenAI 兼容的 /v1/chat/completions 接口，密钥只保存在本机 SharedPreferences。
 */
public class MainActivity extends Activity {

    private static final String DEFAULT_BASE = "https://api.deepseek.com/v1";
    private static final String DEFAULT_MODEL = "deepseek-chat";
    private static final String DEFAULT_PERSONA =
            "你是「戏语」，一个温暖、细腻的角色扮演伙伴。用第一人称和自然的口吻聊天，"
                    + "记住对方说过的话，回复不要太长，带一点情绪和画面感。";

    private SharedPreferences prefs;
    private final List<JSONObject> history = new ArrayList<>();
    private LinearLayout msgBox;
    private ScrollView scroll;
    private EditText input;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private boolean busy = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences("xiyu", MODE_PRIVATE);
        loadHistory();
        if (prefs.getString("api_key", "").isEmpty()) {
            showSettings(true);
        } else {
            showChat();
        }
    }

    // ---------------- 通用小工具 ----------------

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

    private GradientDrawable round(int color) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(dp(14));
        return d;
    }

    // ---------------- 设置页 ----------------

    private void showSettings(boolean firstRun) {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.WHITE);
        root.setPadding(dp(20), dp(28), dp(20), dp(20));

        root.addView(text("戏语", 26, true, Color.BLACK));
        root.addView(text(firstRun ? "第一次使用，先填写接口信息" : "设置", 14, false, Color.GRAY));

        EditText base = field("接口地址 Base URL", prefs.getString("base_url", DEFAULT_BASE),
                InputType.TYPE_TEXT_VARIATION_URI);
        EditText key = field("API Key", prefs.getString("api_key", ""),
                InputType.TYPE_TEXT_VARIATION_PASSWORD);
        EditText model = field("模型名称", prefs.getString("model", DEFAULT_MODEL),
                InputType.TYPE_CLASS_TEXT);
        EditText persona = field("角色人设提示词", prefs.getString("persona", DEFAULT_PERSONA),
                InputType.TYPE_CLASS_TEXT);
        persona.setMinLines(3);
        persona.setGravity(Gravity.TOP);

        root.addView(base);
        root.addView(key);
        root.addView(model);
        root.addView(persona);

        Button save = new Button(this);
        save.setText("保存");
        save.setOnClickListener(v -> {
            String b = base.getText().toString().trim();
            String k = key.getText().toString().trim();
            String m = model.getText().toString().trim();
            String p = persona.getText().toString().trim();
            if (b.isEmpty()) b = DEFAULT_BASE;
            if (m.isEmpty()) m = DEFAULT_MODEL;
            if (p.isEmpty()) p = DEFAULT_PERSONA;
            prefs.edit().putString("base_url", b).putString("api_key", k)
                    .putString("model", m).putString("persona", p).apply();
            Toast.makeText(this, "已保存到本机", Toast.LENGTH_SHORT).show();
            showChat();
        });
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(48));
        lp.topMargin = dp(14);
        root.addView(save, lp);

        if (!firstRun) {
            Button back = new Button(this);
            back.setText("返回聊天");
            back.setOnClickListener(v -> showChat());
            root.addView(back, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, dp(48)));
        }

        ScrollView sc = new ScrollView(this);
        sc.addView(root);
        setContentView(sc);
    }

    private EditText field(String hint, String value, int inputType) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setText(value);
        e.setInputType(inputType);
        e.setTextSize(15);
        e.setSingleLine(inputType != InputType.TYPE_CLASS_TEXT);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(10);
        e.setLayoutParams(lp);
        return e;
    }

    // ---------------- 聊天页 ----------------

    private void showChat() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.WHITE);

        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(16), dp(10), dp(8), dp(10));
        bar.addView(text("戏语", 22, true, Color.BLACK),
                new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        Button gear = new Button(this);
        gear.setText("设置");
        gear.setOnClickListener(v -> showSettings(false));
        bar.addView(gear);
        root.addView(bar);

        scroll = new ScrollView(this);
        msgBox = new LinearLayout(this);
        msgBox.setOrientation(LinearLayout.VERTICAL);
        msgBox.setPadding(dp(12), dp(6), dp(12), dp(6));
        scroll.addView(msgBox);
        root.addView(scroll, new LinearLayout.LayoutParams(
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
        Button send = new Button(this);
        send.setText("发送");
        send.setOnClickListener(v -> onSend());
        bottom.addView(send);
        root.addView(bottom);

        setContentView(root);
        renderHistory();
    }

    private void renderHistory() {
        msgBox.removeAllViews();
        for (JSONObject m : history) {
            String role = m.optString("role");
            String content = m.optString("content");
            msgBox.addView(bubble(content, "user".equals(role)));
        }
        scrollDown();
    }

    private TextView bubble(String content, boolean mine) {
        TextView tv = new TextView(this);
        tv.setText(content);
        tv.setTextSize(15);
        tv.setTextColor(mine ? Color.WHITE : Color.parseColor("#1F1F1F"));
        tv.setBackground(round(mine ? Color.parseColor("#3B6FE0") : Color.parseColor("#EEF1F6")));
        tv.setPadding(dp(12), dp(8), dp(12), dp(8));
        tv.setLineSpacing(dp(3), 1f);

        LinearLayout wrap = new LinearLayout(this);
        wrap.setGravity(mine ? Gravity.END : Gravity.START);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(6);
        wrap.addView(tv);
        LinearLayout.LayoutParams wp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        wp.setMargins(0, 0, 0, dp(6));
        wrap.setLayoutParams(wp);
        // 气泡最大宽度约屏宽的 80%
        int max = (int) (getResources().getDisplayMetrics().widthPixels * 0.8f);
        tv.setMaxWidth(max);
        return tagged(wrap, tv);
    }

    /** 为了让 msgBox.addView 拿到外层包装，这里用一个小技巧：返回包装内的 TextView 但 addView 需要 ViewGroup。 */
    private TextView tagged(LinearLayout wrap, TextView tv) {
        // 记录包装，供 renderHistory / 追加时使用
        tv.setTag(wrap);
        return tv;
    }

    private void addBubble(String content, boolean mine) {
        TextView tv = bubble(content, mine);
        ViewGroup wrap = (ViewGroup) tv.getTag();
        msgBox.addView(wrap);
        scrollDown();
    }

    private void scrollDown() {
        scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
    }

    private void onSend() {
        if (busy) {
            Toast.makeText(this, "上一条还在等回复", Toast.LENGTH_SHORT).show();
            return;
        }
        String s = input.getText().toString().trim();
        if (s.isEmpty()) return;
        input.setText("");
        addBubble(s, true);
        JSONObject user = new JSONObject();
        try {
            user.put("role", "user");
            user.put("content", s);
        } catch (Exception ignored) {
        }
        history.add(user);
        saveHistory();
        request();
    }

    private void request() {
        final String base = prefs.getString("base_url", DEFAULT_BASE);
        final String key = prefs.getString("api_key", "");
        final String model = prefs.getString("model", DEFAULT_MODEL);
        final String persona = prefs.getString("persona", DEFAULT_PERSONA);

        busy = true;
        TextView typing = bubble("…", false);
        ViewGroup typingWrap = (ViewGroup) typing.getTag();
        msgBox.addView(typingWrap);
        scrollDown();

        new Thread(() -> {
            String reply = null;
            String error = null;
            try {
                JSONObject body = new JSONObject();
                body.put("model", model);
                JSONArray arr = new JSONArray();
                JSONObject sys = new JSONObject();
                sys.put("role", "system");
                sys.put("content", persona);
                arr.put(sys);
                int from = Math.max(0, history.size() - 20);
                for (int i = from; i < history.size(); i++) arr.put(history.get(i));
                body.put("messages", arr);
                body.put("temperature", 0.8);
                body.put("max_tokens", 800);
                body.put("stream", false);

                URL url = new URL(endpoint(base));
                HttpURLConnection c = (HttpURLConnection) url.openConnection();
                c.setRequestMethod("POST");
                c.setConnectTimeout(20000);
                c.setReadTimeout(180000);
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                c.setRequestProperty("Authorization", "Bearer " + key);
                c.setRequestProperty("Accept", "application/json");
                byte[] out = body.toString().getBytes(StandardCharsets.UTF_8);
                try (OutputStream os = c.getOutputStream()) {
                    os.write(out);
                }
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
                if (code >= 400) {
                    String msg = raw;
                    try {
                        msg = new JSONObject(raw).optJSONObject("error").optString("message", raw);
                    } catch (Exception ignored) {
                    }
                    error = "接口返回 " + code + "：" + msg;
                } else {
                    JSONObject data = new JSONObject(raw);
                    JSONArray choices = data.optJSONArray("choices");
                    if (choices == null || choices.length() == 0) {
                        error = "接口没有返回内容";
                    } else {
                        reply = choices.getJSONObject(0).optJSONObject("message")
                                .optString("content", "").trim();
                        if (reply.isEmpty()) error = "模型返回了空内容";
                    }
                }
            } catch (Exception e) {
                error = "请求失败：" + e.getMessage();
            }

            final String r = reply;
            final String err = error;
            ui.post(() -> {
                msgBox.removeView(typingWrap);
                busy = false;
                if (r != null) {
                    addBubble(r, false);
                    try {
                        JSONObject a = new JSONObject();
                        a.put("role", "assistant");
                        a.put("content", r);
                        history.add(a);
                    } catch (Exception ignored) {
                    }
                    saveHistory();
                } else {
                    Toast.makeText(this, err == null ? "未知错误" : err, Toast.LENGTH_LONG).show();
                }
            });
        }).start();
    }

    private String endpoint(String base) {
        String b = base == null ? "" : base.trim();
        while (b.endsWith("/")) b = b.substring(0, b.length() - 1);
        if (b.endsWith("/chat/completions")) return b;
        if (b.endsWith("/v1") || b.endsWith("/v2") || b.endsWith("/v3")) return b + "/chat/completions";
        if (!b.contains("://")) b = "https://" + b;
        return b + "/v1/chat/completions";
    }

    // ---------------- 会话持久化 ----------------

    private void loadHistory() {
        history.clear();
        String raw = prefs.getString("history", "");
        if (raw == null || raw.isEmpty()) return;
        try {
            JSONArray arr = new JSONArray(raw);
            for (int i = 0; i < arr.length(); i++) {
                JSONObject m = arr.optJSONObject(i);
                if (m != null) history.add(m);
            }
        } catch (Exception ignored) {
        }
    }

    private void saveHistory() {
        while (history.size() > 60) history.remove(0);
        JSONArray arr = new JSONArray();
        for (JSONObject m : history) arr.put(m);
        prefs.edit().putString("history", arr.toString()).apply();
    }
}
