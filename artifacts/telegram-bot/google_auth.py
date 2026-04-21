import requests
import pyotp
import re
import json
import time


def generate_totp(secret: str) -> str:
    try:
        totp = pyotp.TOTP(secret.strip().replace(" ", ""))
        return totp.now()
    except Exception:
        return None


def google_login_and_get_link(email: str, password: str, totp_secret: str) -> dict:
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; Pixel 4) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    })

    try:
        otp_code = generate_totp(totp_secret)
        if not otp_code:
            return {"success": False, "error": "Invalid 2FA secret key. Please check and try again."}

        r = session.get(
            "https://accounts.google.com/signin/v2/identifier",
            params={"flowName": "GlifWebSignIn", "flowEntry": "ServiceLogin"},
            timeout=15,
        )

        action_url = "https://accounts.google.com/signin/v2/identifier"
        hidden = _extract_hidden_fields(r.text)

        data = {**hidden, "identifier": email, "continue": "https://myaccount.google.com/"}
        r = session.post(action_url, data=data, timeout=15)

        if "password" not in r.text.lower() and "signin" not in r.url.lower():
            return {"success": False, "error": "Gmail not found or incorrect. Please check your email."}

        hidden = _extract_hidden_fields(r.text)
        data = {**hidden, "Passwd": password}
        r = session.post(
            "https://accounts.google.com/signin/v2/sl/pwd",
            data=data,
            timeout=15,
        )

        if "challenge" in r.url or "totp" in r.text.lower() or "2-step" in r.text.lower():
            hidden = _extract_hidden_fields(r.text)
            data = {**hidden, "totpPin": otp_code}
            challenge_url = r.url
            r = session.post(challenge_url, data=data, timeout=15)

        if "myaccount.google.com" not in r.url and "accounts.google.com" in r.url:
            return {"success": False, "error": "Login failed. Check your password or 2FA code."}

        link = _generate_partner_link(session)
        if link:
            return {"success": True, "link": link}
        else:
            return {"success": False, "error": "Login succeeded but could not generate the partner link. Try again."}

    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timed out. Google servers are slow. Try again."}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {str(e)[:100]}"}


def _extract_hidden_fields(html: str) -> dict:
    fields = {}
    for match in re.finditer(r'<input[^>]+type=["\']hidden["\'][^>]*>', html):
        tag = match.group(0)
        name_m = re.search(r'name=["\']([^"\']+)["\']', tag)
        value_m = re.search(r'value=["\']([^"\']*)["\']', tag)
        if name_m:
            fields[name_m.group(1)] = value_m.group(1) if value_m else ""
    return fields


def _generate_partner_link(session: requests.Session) -> str:
    try:
        r = session.get(
            "https://one.google.com/u/0/partner-eft-onboard",
            timeout=15,
            allow_redirects=True,
        )

        token_match = re.search(
            r'partner-eft-onboard[/\\]([A-Za-z0-9_\-]{10,})', r.url + " " + r.text
        )
        if token_match:
            token = token_match.group(1)
            return f"https://one.google.com/partner-eft-onboard/{token}"

        js_match = re.search(r'"redemptionToken":\s*"([A-Za-z0-9_\-]{10,})"', r.text)
        if js_match:
            token = js_match.group(1)
            return f"https://one.google.com/partner-eft-onboard/{token}"

        api_url = "https://one.google.com/u/0/partner-eft-onboard/generate"
        api_r = session.post(api_url, json={}, timeout=15)
        if api_r.status_code == 200:
            try:
                data = api_r.json()
            except (ValueError, json.JSONDecodeError):
                return None
            token = data.get("token") or data.get("redemptionToken") or data.get("link", "").split("/")[-1]
            if token:
                return f"https://one.google.com/partner-eft-onboard/{token}"

        return None

    except Exception:
        return None
