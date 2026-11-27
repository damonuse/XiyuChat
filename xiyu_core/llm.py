"""OpenAI 兼容接口的最小客户端（标准库实现，无需第三方依赖）。"""
import json
import socket
import urllib.error
import urllib.parse
import urllib.request

from . import usage


class LLMError(Exception):
    pass


def _endpoint(base_url: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    if not base:
        raise LLMError("接口地址为空，请在设置里填写 Base URL")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1") or base.endswith("/v2") or base.endswith("/v3"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def chat_completion(base_url, api_key, model, messages,
                    temperature=0.8, max_tokens=800, timeout=180):
    if not api_key:
        raise LLMError("没有可用的 API Key，请按 F2 打开设置填写")
    if not model:
        raise LLMError("模型名称为空，请在设置里填写")

    url = _endpoint(base_url)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "stream": False,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + api_key)
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")
            data = json.loads(detail)
            detail = (data.get("error") or {}).get("message") or detail
        except Exception:
            pass
        raise LLMError("接口返回 %s：%s" % (e.code, (detail or e.reason)[:300]))
    except urllib.error.URLError as e:
        raise LLMError("网络连接失败：%s" % (e.reason,))
    except socket.timeout:
        raise LLMError("请求超时，请检查网络或代理设置")
    except Exception as e:
        raise LLMError("请求异常：%s" % (e,))

    try:
        data = json.loads(raw)
        choices = data.get("choices") or []
        if not choices:
            raise LLMError("接口未返回内容：" + raw[:200])
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if isinstance(content, list):   # 少数实现返回分段结构
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        content = (content or "").strip()
        if not content:
            raise LLMError("模型返回了空内容")
        u = data.get("usage") or {}
        try:
            usage.record(u.get("prompt_tokens", 0), u.get("completion_tokens", 0), model)
        except Exception:
            pass
        return content
    except LLMError:
        raise
    except Exception as e:
        raise LLMError("返回内容解析失败：%s" % (e,))


def _api_root(base_url):
    base = (base_url or "").strip()
    if not base:
        raise LLMError("接口地址为空，请先在设置里填写 Base URL")
    if "://" not in base:
        base = "https://" + base
    parsed = urllib.parse.urlparse(base)
    if not parsed.netloc:
        raise LLMError("接口地址不合法")
    return "%s://%s" % (parsed.scheme, parsed.netloc)


def query_balance(base_url, api_key, timeout=25):
    """查询账户余额（DeepSeek 提供 /user/balance）。"""
    if not api_key:
        raise LLMError("没有可用的 API Key，请先填写并保存")
    url = _api_root(base_url) + "/user/balance"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", "Bearer " + api_key)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (404, 405):
            raise LLMError("这个接口没有余额查询（目前只有 DeepSeek 提供 /user/balance）")
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")
            detail = (json.loads(detail).get("error") or {}).get("message") or detail
        except Exception:
            pass
        raise LLMError("余额查询失败 %s：%s" % (e.code, (detail or e.reason)[:200]))
    except urllib.error.URLError as e:
        raise LLMError("网络连接失败：%s" % (e.reason,))
    except socket.timeout:
        raise LLMError("余额查询超时")
    except Exception as e:
        raise LLMError("余额查询异常：%s" % (e,))

    try:
        data = json.loads(raw)
    except Exception:
        raise LLMError("余额返回格式无法解析")
    return {
        "is_available": bool(data.get("is_available", True)),
        "infos": data.get("balance_infos") or [],
    }
