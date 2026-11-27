"""API Key 的安全存储。

优先使用 Windows DPAPI（CryptProtectData），密文与当前用户账户绑定，
拷到别的机器或别的账户都解不开。非 Windows 或调用失败时，退化为
带 HMAC 校验的本地派生密钥加密（仍不是明文）。
"""
import base64
import ctypes
import hashlib
import hmac
import os
import sys
from ctypes import wintypes

_MAGIC = b"XIYU1"


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char))]


def _to_blob(data: bytes):
    buf = ctypes.create_string_buffer(bytes(data), len(data))
    blob = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    return blob, buf


def _dpapi(data: bytes, protect: bool) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    blob_in, _buf = _to_blob(data)
    blob_out = _Blob()
    if protect:
        ok = crypt32.CryptProtectData(ctypes.byref(blob_in), None, None, None,
                                      None, 0, ctypes.byref(blob_out))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None,
                                        None, 0, ctypes.byref(blob_out))
    if not ok:
        raise OSError("DPAPI 调用失败")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _local_key() -> bytes:
    seed = ("xiyu|" + os.environ.get("USERNAME", "user") + "|"
            + os.environ.get("COMPUTERNAME", "pc") + "|local-fallback")
    return hashlib.sha256(seed.encode("utf-8")).digest()


def _fallback_encrypt(data: bytes) -> bytes:
    key = _local_key()
    stream = b"".join(hashlib.sha256(key + bytes([i])).digest() for i in range(4))
    ct = bytes(b ^ stream[i % len(stream)] for i, b in enumerate(data))
    return hmac.new(key, ct, hashlib.sha256).digest() + ct


def _fallback_decrypt(payload: bytes) -> bytes:
    key = _local_key()
    mac, ct = payload[:32], payload[32:]
    if not hmac.compare_digest(mac, hmac.new(key, ct, hashlib.sha256).digest()):
        raise OSError("密钥校验失败，配置可能被外部修改")
    stream = b"".join(hashlib.sha256(key + bytes([i])).digest() for i in range(4))
    return bytes(b ^ stream[i % len(stream)] for i, b in enumerate(ct))


def _encrypt(text: str) -> bytes:
    raw = text.encode("utf-8")
    if sys.platform == "win32":
        try:
            return _MAGIC + b"D" + _dpapi(raw, True)
        except Exception:
            pass
    return _MAGIC + b"F" + _fallback_encrypt(raw)


def _decrypt(blob: bytes) -> str:
    if not blob.startswith(_MAGIC) or len(blob) < 6:
        raise OSError("密钥文件格式异常")
    mode, payload = blob[5:6], blob[6:]
    if mode == b"D":
        return _dpapi(payload, False).decode("utf-8")
    if mode == b"F":
        return _fallback_decrypt(payload).decode("utf-8")
    raise OSError("密钥文件格式异常")


def save_api_key(path: str, api_key: str) -> None:
    blob = _encrypt(api_key or "")
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(blob)
    os.replace(tmp, path)
    try:
        if sys.platform == "win32":
            import subprocess
            subprocess.run(["attrib", "+H", path], shell=False,
                           capture_output=True, check=False)
    except Exception:
        pass


def load_api_key(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        blob = f.read()
    try:
        return _decrypt(blob)
    except Exception:
        return ""


def has_api_key(path: str) -> bool:
    return bool(load_api_key(path))
