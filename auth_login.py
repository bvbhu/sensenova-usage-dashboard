#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SenseNova 自动登录模块

复现浏览器登录流程，用账号密码自动换取控制台 JWT（Bearer Token）：

  1. 访问 oauth2/auth（带 PKCE 挑战）拿到 login_challenge
  2. 用平台 JWKS 里的 RSA 公钥（kid=public:hydra.openid.id-token）
     以 JWE(RSA-OAEP + A256GCM) 加密密码
  3. POST /iam/authn/v1/auth/nova/login 登录，拿到 oauth2 回调地址
  4. 跟随回调拿到 authorization_code
  5. 用 code + PKCE verifier 在 token 端点换 access_token（即控制台 JWT）

依赖: requests, jwcrypto
"""

import base64
import hashlib
import html
import json
import os
import re
import secrets
import time

import requests
from jwcrypto import jwk, jwe
from jwcrypto.common import json_encode

# ============================================================
# 常量（均来自对平台前端代码的反编译与 OIDC 元数据）
# ============================================================
IAM_BASE = "https://iam.sensecoreapi.cn"
# 注意：授权端点必须用 platform.sensenova.cn 域名，不能直接用 OIDC 元数据里的
# signin.sensecore.cn。两者都代理到同一套 Hydra，但 CSRF cookie（oauth2_authentication_csrf）
# 的域会随入口域名走：用 signin.sensecore.cn 发起 → cookie 落在 signin.sensecore.cn，
# 而 nova/login 回调的兑换地址是 platform.sensenova.cn/oauth2/auth，跨域拿不到 cookie，
# 会报 "No CSRF value available in the session cookie"。用 platform.sensenova.cn 发起即可。
OIDC_AUTH = "https://platform.sensenova.cn/oauth2/auth"
OIDC_TOKEN = "https://signin.sensecore.cn/oauth2/token"
JWKS_URL = "https://signin.sensecore.cn/.well-known/jwks.json"
CLIENT_ID = "nova"
REDIRECT_URI = "https://platform.sensenova.cn"
SCOPE = "openid offline offline_access"

_USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")

# 缓存的公钥（首次获取后复用，避免每次登录都拉 JWKS）
_pubkey_cache = {"key": None, "ts": 0}
_PUBKEY_TTL = 3600

# 登录失败时写入的诊断日志路径（写入当前工作目录，桌面应用即 exe 同级目录）
_DEBUG_LOG = os.path.join(os.getcwd(), "auth_login_last_error.log")

def _write_debug_log(hops, redirect=None, extra=""):
    try:
        with open(_DEBUG_LOG, "w", encoding="utf-8") as f:
            f.write(f"# SenseNova auth login debug log\n")
            f.write(f"# 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# 调试文件路径: {_DEBUG_LOG}\n\n")
            if redirect:
                f.write(f"nova/login 返回的 redirect: {redirect}\n\n")
            if extra:
                f.write(f"额外信息: {extra}\n\n")
            for hop in hops:
                f.write(f"--- Hop {hop.get('n')} ---\n")
                f.write(f"URL: {hop.get('url')}\n")
                f.write(f"Method: {hop.get('method')}\n")
                f.write(f"Status: {hop.get('status')}\n")
                f.write(f"Location header: {hop.get('location')}\n")
                f.write(f"Body snippet:\n{hop.get('body_snippet')}\n\n")
    except Exception:
        pass


def _b64url_decode(s):
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


def get_enc_pubkey():
    """获取用于加密密码的 RSA 公钥（JWKS 中的 public:hydra.openid.id-token）。"""
    now = time.time()
    if _pubkey_cache["key"] and now - _pubkey_cache["ts"] < _PUBKEY_TTL:
        return _pubkey_cache["key"]
    jwks = requests.get(JWKS_URL, headers={"User-Agent": _USER_AGENT}, timeout=20).json()
    k = next(x for x in jwks["keys"] if x.get("kid") == "public:hydra.openid.id-token")
    # 只取 n/e 重建公钥，去掉 use/alg 约束，避免 jwcrypto 报 "Invalid usage"
    pub = jwk.JWK(kty="RSA", n=k["n"], e=k["e"])
    _pubkey_cache["key"] = pub
    _pubkey_cache["ts"] = now
    return pub


def encrypt_password(password: str) -> str:
    """用 RSA-OAEP + A256GCM 加密密码，返回紧凑型 JWE 字符串。"""
    pub = get_enc_pubkey()
    return jwe.JWE(
        password.encode("utf-8"),
        recipient=pub,
        protected=json_encode({"alg": "RSA-OAEP", "enc": "A256GCM"}),
    ).serialize(compact=True)


def _pkce():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def _follow_until(loc, session, predicate, max_hops=6, hops=None):
    """
    手动跟随重定向，直到 predicate(location) 为真，返回命中的 location。
    若 Location 头里没有 code，也尝试从响应体里解析 JS/HTML 跳转或 JSON 中的 code。
    hops 列表会记录每一跳供排查看用。
    """
    if hops is None:
        hops = []

    def _extract_next_from_body(r):
        """从 200 响应体里找下一个跳转目标或 code。"""
        text = r.text
        if not text:
            return None
        # 1) 直接包含 code= 的 URL
        for m in re.finditer(r"(https?://[^\"'\s<>]+[?&]code=[^&\"'\s<>]+)", text):
            if predicate(m.group(1)):
                return m.group(1)
        # 2) HTML meta refresh
        m = re.search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+url=["\']([^"\']+)', text, re.I)
        if m:
            return html.unescape(m.group(1))
        # 3) JS 跳转
        for pattern in [
            r"window\.location\.replace\([\"']([^\"']+)[\"']",
            r"window\.location\.href\s*=\s*[\"']([^\"']+)[\"']",
            r"location\.href\s*=\s*[\"']([^\"']+)[\"']",
            r"window\.location\s*=\s*[\"']([^\"']+)[\"']",
        ]:
            m = re.search(pattern, text)
            if m:
                return html.unescape(m.group(1))
        return None

    for idx in range(max_hops):
        if not loc:
            break
        if predicate(loc):
            return loc
        r = session.get(loc, headers={"User-Agent": _USER_AGENT, "Accept": "*/*"},
                        allow_redirects=False, timeout=30)
        hop = {
            "n": idx + 1,
            "url": loc,
            "method": "GET",
            "status": r.status_code,
            "location": r.headers.get("Location", ""),
            "body_snippet": r.text[:2000],
        }
        hops.append(hop)
        new_loc = r.headers.get("Location")
        # 200 响应体里可能藏着跳转
        if not new_loc and r.status_code in (200, 201):
            new_loc = _extract_next_from_body(r)
        loc = new_loc
    return None


def login(username: str, password: str, timeout: int = 30) -> dict:
    """
    用账号密码登录，返回 {"access_token", "refresh_token", "expires_in"}。
    access_token 即控制台 API 所需的 Bearer JWT。
    """
    if not username or not password:
        raise ValueError("用户名和密码不能为空")

    s = requests.Session()
    s.headers.update({"User-Agent": _USER_AGENT, "Accept": "*/*"})

    # ---- 1) 拿 login_challenge（带自己的 PKCE） ----
    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(16)
    auth_params = {
        "client_id": CLIENT_ID,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "state": state,
    }
    r = s.get(OIDC_AUTH, params=auth_params, allow_redirects=False, timeout=timeout)
    loc = r.headers.get("Location")
    hops = []
    challenge_loc = _follow_until(
        loc, s, lambda u: "login_challenge=" in u, hops=hops
    )
    if not challenge_loc:
        _write_debug_log(hops, extra=f"OIDC_AUTH response Location={loc}")
        raise RuntimeError(f"未能获取 login_challenge（登录流程中断），诊断日志：{_DEBUG_LOG}")
    login_challenge = re.search(r"login_challenge=([^&]+)", challenge_loc).group(1)

    # ---- 2) 加密密码并提交登录 ----
    enc = encrypt_password(password)
    resp = s.post(
        f"{IAM_BASE}/iam/authn/v1/auth/nova/login",
        json={"username": username, "password": enc,
              "challenge": login_challenge, "is_encrypt": True},
        headers={
            "Content-Type": "application/json",
            "Origin": "https://platform.sensenova.cn",
            "Referer": "https://platform.sensenova.cn/",
        },
        timeout=timeout,
    )
    # 记录 nova/login 响应，便于排查
    hops.insert(0, {
        "n": 0,
        "url": f"{IAM_BASE}/iam/authn/v1/auth/nova/login",
        "method": "POST",
        "status": resp.status_code,
        "location": "",
        "body_snippet": resp.text[:2000],
    })
    try:
        body = resp.json()
    except Exception:
        _write_debug_log(hops, extra=f"nova/login HTTP {resp.status_code}，非 JSON 响应")
        raise RuntimeError(f"登录接口返回异常（HTTP {resp.status_code}），诊断日志：{_DEBUG_LOG}")
    redirect = body.get("redirect")
    if not redirect:
        # 登录失败：把后端给的错误信息透传出来
        msg = body.get("message") or body.get("error") or json.dumps(body, ensure_ascii=False)
        _write_debug_log(hops, extra=f"nova/login 未返回 redirect，msg={msg}")
        raise RuntimeError(f"登录失败：{msg}")

    # ---- 3) 跟随回调拿 authorization_code ----
    code_loc = _follow_until(redirect, s, lambda u: "code=" in u, hops=hops)
    if not code_loc:
        _write_debug_log(hops, redirect=redirect,
                         extra="已尝试从 Location 头和响应体（meta refresh/JS 跳转）中解析 code")
        raise RuntimeError(f"未能获取 authorization code（回调流程中断），诊断日志：{_DEBUG_LOG}")
    try:
        authorization_code = re.search(r"[?&]code=([^&]+)", code_loc).group(1)
    except (AttributeError, IndexError):
        _write_debug_log(hops, redirect=redirect,
                         extra=f"从 code_loc 解析 code 失败：{code_loc}")
        raise RuntimeError(f"未能从回调地址解析 authorization code，诊断日志：{_DEBUG_LOG}")

    # ---- 4) 用 code + PKCE verifier 换 token ----
    token_resp = s.post(
        OIDC_TOKEN,
        data={
            "grant_type": "authorization_code",
            "code": authorization_code,
            "code_verifier": verifier,
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=timeout,
    )
    try:
        tok = token_resp.json()
    except Exception:
        raise RuntimeError(f"token 接口返回异常（HTTP {token_resp.status_code}）")
    access_token = tok.get("access_token")
    if not access_token:
        msg = tok.get("error_description") or tok.get("error") or json.dumps(tok, ensure_ascii=False)
        raise RuntimeError(f"未返回 access_token：{msg}")

    return {
        "access_token": access_token,
        "refresh_token": tok.get("refresh_token", ""),
        "expires_in": int(tok.get("expires_in", 10800)),
    }


if __name__ == "__main__":
    # 简单自测：仅验证加密与 challenge 获取（不提交真实凭据）
    print("公钥可用，样例 JWE：")
    sample = encrypt_password("demo")
    print(sample[:60], "... (段数=%d)" % len(sample.split(".")))
    print("模块导入与加密链路 OK")
