import logging
import pyotp
import re

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

_log = logging.getLogger(__name__)


def generate_totp(secret: str) -> str:
    try:
        totp = pyotp.TOTP(secret.strip().replace(" ", ""))
        return totp.now()
    except Exception:
        return None


def google_login_and_get_link(
    email: str,
    password: str,
    totp_secret: str,
    backup_code: str | None = None,
) -> dict:
    """
    Log into Google with a real browser and return a partner link.

    Parameters
    ----------
    email        : Google account email
    password     : Account password
    totp_secret  : TOTP authenticator secret (base-32).  Pass None if using backup_code only.
    backup_code  : Optional 8-digit Google backup code.  Used when TOTP is rejected or
                   when the user has no TOTP secret (totp_secret is None).

    Returns
    -------
    {"success": True,  "link": "https://..."}
    {"success": False, "error": "human-readable message"}
    """
    otp_code = None
    if totp_secret:
        otp_code = generate_totp(totp_secret)
        if not otp_code:
            return {"success": False, "error": "Invalid 2FA secret key. Please check and try again."}

    if not otp_code and not backup_code:
        return {"success": False, "error": "No 2FA credentials provided. Supply a TOTP secret or a backup code."}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--window-size=1280,800",
                ],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
            )
            page = context.new_page()

            try:
                result = _do_login(page, email, password, otp_code, totp_secret, backup_code)
            finally:
                context.close()
                browser.close()

            return result

    except PWTimeout:
        return {"success": False, "error": "Login timed out. Google may be slow — please try again."}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error during login: {str(e)[:120]}"}


def _do_login(
    page, email: str, password: str,
    otp_code: str | None, totp_secret: str | None, backup_code: str | None,
) -> dict:
    page.goto(
        "https://accounts.google.com/signin/v2/identifier"
        "?flowName=GlifWebSignIn&flowEntry=ServiceLogin"
        "&continue=https://one.google.com/u/0/partner-eft-onboard",
        wait_until="domcontentloaded",
        timeout=30_000,
    )

    if _is_captcha_page(page):
        return {"success": False, "error": "Google is showing a CAPTCHA. Please try again in a few minutes."}

    try:
        email_input = page.wait_for_selector('input[type="email"]', timeout=15_000)
        email_input.fill(email)
        page.keyboard.press("Enter")
    except PWTimeout:
        return {"success": False, "error": "Could not find the email field. Google may have changed its login page."}

    try:
        page.wait_for_selector('input[type="password"]', timeout=15_000)
    except PWTimeout:
        if _is_captcha_page(page):
            return {"success": False, "error": "Google is showing a CAPTCHA after email entry. Try again later."}
        return {"success": False, "error": "Gmail address not found. Please check your email and try again."}

    if _is_captcha_page(page):
        return {"success": False, "error": "Google is showing a CAPTCHA. Please try again in a few minutes."}

    page.fill('input[type="password"]', password)
    page.keyboard.press("Enter")

    try:
        page.wait_for_load_state("domcontentloaded", timeout=20_000)
    except PWTimeout:
        pass

    if _is_captcha_page(page):
        return {"success": False, "error": "Google is showing a CAPTCHA after password entry. Try again later."}

    page_text = page.inner_text("body").lower() if page.query_selector("body") else ""
    if any(ind in page_text for ind in ("wrong password", "incorrect password", "didn't recognize")):
        return {"success": False, "error": "Incorrect password. Please check your password and try again."}

    two_fa_result = _handle_2fa(page, otp_code, totp_secret, backup_code)
    if two_fa_result is not None:
        return two_fa_result

    if "accounts.google.com" in page.url and "signin" in page.url:
        return {"success": False, "error": "Login failed. Check your email, password, and 2FA credentials."}

    link = _generate_partner_link(page)
    if link:
        return {"success": True, "link": link}
    return {
        "success": False,
        "error": "Login succeeded but could not generate the partner link. Please try again.",
    }


def _handle_2fa(
    page, otp_code: str | None, totp_secret: str | None, backup_code: str | None,
) -> dict | None:
    """
    Handle Google's 2-step verification screen.
    Returns an error dict on failure, None if 2FA passed or was not required.

    Priority order
    ──────────────
    1. If a method-selection page appears, try to pick the right option first.
    2. If a TOTP field is present and otp_code is available, submit it.
       On rejection, retry once with a freshly-generated code.
       If still rejected (or no TOTP), fall back to the backup-code path.
    3. If a backup_code is supplied, navigate to the backup-code entry and submit it.
    """
    totp_field_css = (
        'input[name="totpPin"], '
        'input[aria-label*="code" i], '
        'input[aria-label*="authenticator" i], '
        'input[aria-label*="verification" i], '
        'input[type="tel"]'
    )
    backup_only = otp_code is None and backup_code is not None

    any_2fa_visible = False

    if backup_only and _find_backup_input(page) is not None:
        any_2fa_visible = True
    else:
        try:
            page.wait_for_selector(totp_field_css, timeout=8_000)
            any_2fa_visible = True
        except PWTimeout:
            if _find_backup_input(page) is not None:
                any_2fa_visible = True
            elif _is_method_selection_page(page):
                _choose_2fa_method(page, prefer_backup=backup_only)
                try:
                    page.wait_for_selector(totp_field_css, timeout=8_000)
                    any_2fa_visible = True
                except PWTimeout:
                    if _find_backup_input(page) is not None:
                        any_2fa_visible = True

    if not any_2fa_visible:
        return None

    if _is_captcha_page(page):
        return {"success": False, "error": "Google is showing a CAPTCHA during 2FA. Please try again later."}

    if otp_code is not None:
        totp_error = _submit_totp(page, otp_code, totp_secret)
        if totp_error is None:
            return None
        if backup_code is None:
            return totp_error

    if backup_code is not None:
        return _submit_backup_code(page, backup_code)

    return None


def _submit_totp(page, otp_code: str, totp_secret: str | None) -> dict | None:
    """Fill and submit a TOTP code. Returns error dict if rejected, None on success."""
    otp_selectors = [
        'input[name="totpPin"]',
        'input[aria-label*="code" i]',
        'input[aria-label*="authenticator" i]',
        'input[aria-label*="verification" i]',
        'input[type="tel"]',
    ]

    def find_otp_field():
        for sel in otp_selectors:
            field = page.query_selector(sel)
            if field:
                return field
        return None

    otp_field = find_otp_field()
    if not otp_field:
        return {"success": False, "error": "2FA field not found. Google may have changed its flow."}

    otp_field.fill(otp_code)
    page.keyboard.press("Enter")
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15_000)
    except PWTimeout:
        pass

    if not _is_otp_rejected(page):
        return None

    if totp_secret:
        fresh_otp = generate_totp(totp_secret)
        if fresh_otp and fresh_otp != otp_code:
            otp_field = find_otp_field()
            if otp_field:
                try:
                    otp_field.fill("")
                    otp_field.fill(fresh_otp)
                    page.keyboard.press("Enter")
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=15_000)
                    except PWTimeout:
                        pass
                    if not _is_otp_rejected(page):
                        return None
                except Exception as exc:
                    _log.debug("TOTP retry failed: %s", exc)

    return {
        "success": False,
        "error": "2FA authenticator code was rejected. Make sure your clock is synced.",
    }


def _submit_backup_code(page, backup_code: str) -> dict | None:
    """
    Navigate to Google's backup-code entry screen and submit the code.
    Returns error dict on failure, None on success.
    """
    backup_input = _find_backup_input(page)

    if backup_input is None:
        navigated = _navigate_to_backup_screen(page)
        if not navigated:
            return {
                "success": False,
                "error": (
                    "Could not find the backup code entry screen. "
                    "Google may not be offering backup codes at this time."
                ),
            }
        backup_input = _find_backup_input(page)

    if backup_input is None:
        return {
            "success": False,
            "error": "Backup code field not found even after navigating to the backup-code screen.",
        }

    try:
        backup_input.fill(backup_code.strip().replace(" ", ""))
        page.keyboard.press("Enter")
        try:
            page.wait_for_load_state("domcontentloaded", timeout=15_000)
        except PWTimeout:
            pass

        page_text = page.inner_text("body").lower() if page.query_selector("body") else ""
        if (
            "invalid" in page_text and "code" in page_text
            or "incorrect backup code" in page_text
            or ("wrong" in page_text and "code" in page_text)
        ):
            return {
                "success": False,
                "error": "Backup code was rejected. Please check the code and try again.",
            }

        return None
    except Exception as e:
        return {"success": False, "error": f"Error submitting backup code: {str(e)[:80]}"}


def _find_backup_input(page):
    """Return the backup-code input element if it is currently visible, else None."""
    selectors = [
        'input[name="backupCodePin"]',
        'input[aria-label*="backup" i]',
        'input[aria-label*="recovery" i]',
    ]
    for sel in selectors:
        el = page.query_selector(sel)
        if el:
            return el
    return None


def _navigate_to_backup_screen(page) -> bool:
    """
    Click 'Try another way' and then select the backup-code option.
    Returns True if the backup-code input is now visible.
    """
    try_another = _find_element_by_text(
        page,
        ["Try another way", "Use another method", "More options"],
        tags=["a", "button", "span[role='link']"],
    )
    if try_another:
        try:
            try_another.click()
            page.wait_for_load_state("domcontentloaded", timeout=10_000)
        except PWTimeout:
            _log.debug("Timed out waiting for page after clicking 'Try another way'")
        except Exception as exc:
            _log.debug("Could not click 'Try another way': %s", exc)

    backup_option = _find_element_by_text(
        page,
        ["backup code", "Backup code", "recovery code", "Recovery code"],
        tags=["li", "div", "span", "button"],
    )
    if backup_option:
        try:
            backup_option.click()
            page.wait_for_load_state("domcontentloaded", timeout=10_000)
        except PWTimeout:
            _log.debug("Timed out after clicking backup-code option")
            return False
        except Exception as exc:
            _log.debug("Could not click backup-code option: %s", exc)
            return False
        return _find_backup_input(page) is not None

    return False


def _choose_2fa_method(page, prefer_backup: bool = False) -> None:
    """
    On Google's method-selection page, click the appropriate 2FA option.
    prefer_backup=True selects backup codes; False selects Authenticator app.
    """
    if prefer_backup:
        labels = ["backup code", "Backup code", "recovery code"]
    else:
        labels = ["Google Authenticator", "Authenticator app", "Authenticator"]

    option = _find_element_by_text(page, labels, tags=["li", "div", "span", "button"])
    if option:
        try:
            option.click()
            page.wait_for_load_state("domcontentloaded", timeout=10_000)
        except PWTimeout:
            _log.debug("Timed out after selecting 2FA method")
        except Exception as exc:
            _log.debug("Could not select 2FA method: %s", exc)


def _find_element_by_text(page, texts: list, tags: list):
    """Return the first element matching any tag that contains any of the given texts."""
    for tag in tags:
        for text in texts:
            el = page.query_selector(f'{tag}:has-text("{text}")')
            if el:
                return el
    return None


def _is_method_selection_page(page) -> bool:
    url = page.url.lower()
    if "challengeselection" in url or "selectchallenge" in url:
        return True
    try:
        text = page.inner_text("body").lower()
        return (
            "choose how you want to sign in" in text
            or "choose another option" in text
        )
    except Exception as exc:
        _log.debug("Could not read page text in _is_method_selection_page: %s", exc)
        return False


def _is_otp_rejected(page) -> bool:
    try:
        text = page.inner_text("body").lower()
        return (
            "wrong code" in text
            or "incorrect code" in text
            or "code is wrong" in text
            or ("try again" in text and "code" in text)
        )
    except Exception as exc:
        _log.debug("Could not read page text in _is_otp_rejected: %s", exc)
        return False


def _generate_partner_link(page) -> str | None:
    try:
        if "one.google.com" not in page.url:
            page.goto(
                "https://one.google.com/u/0/partner-eft-onboard",
                wait_until="domcontentloaded",
                timeout=30_000,
            )

        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except PWTimeout:
            pass

        token = _extract_token_from_url(page.url)
        if token:
            return f"https://one.google.com/partner-eft-onboard/{token}"

        token = _extract_token_from_content(page.content())
        if token:
            return f"https://one.google.com/partner-eft-onboard/{token}"

        try:
            with page.expect_response(
                lambda r: "partner-eft-onboard" in r.url and r.status == 200,
                timeout=10_000,
            ) as resp_info:
                page.reload(wait_until="domcontentloaded")

            resp = resp_info.value
            try:
                data = resp.json()
                token = data.get("token") or data.get("redemptionToken")
                if token:
                    return f"https://one.google.com/partner-eft-onboard/{token}"
            except Exception as exc:
                _log.debug("Could not parse partner API JSON response: %s", exc)
        except Exception as exc:
            _log.debug("Network interception for partner link failed: %s", exc)

        token = _extract_token_from_url(page.url)
        if token:
            return f"https://one.google.com/partner-eft-onboard/{token}"

        token = _extract_token_from_content(page.content())
        if token:
            return f"https://one.google.com/partner-eft-onboard/{token}"

        return None

    except Exception as exc:
        _log.warning("Error generating partner link: %s", exc)
        return None


def _extract_token_from_url(url: str) -> str | None:
    m = re.search(r'partner-eft-onboard[/\\]([A-Za-z0-9_\-]{10,})', url)
    return m.group(1) if m else None


def _extract_token_from_content(html: str) -> str | None:
    m = re.search(r'"redemptionToken":\s*"([A-Za-z0-9_\-]{10,})"', html)
    if m:
        return m.group(1)
    m = re.search(r'partner-eft-onboard[/\\]([A-Za-z0-9_\-]{10,})', html)
    return m.group(1) if m else None


def _is_captcha_page(page) -> bool:
    """
    Detect a CAPTCHA page.  Deliberately avoids checking for 'challenge' in the URL
    because Google's legitimate 2FA pages use /signin/challenge/... paths.
    """
    url = page.url.lower()
    explicit_captcha_paths = (
        "/recaptcha",
        "recaptcha.google.com",
        "google.com/sorry",
    )
    if any(p in url for p in explicit_captcha_paths):
        return True
    try:
        content = page.content().lower()
        return (
            "g-recaptcha" in content
            or 'id="captcha"' in content
            or "verify you&#39;re not a robot" in content
            or "verify you're not a robot" in content
            or "unusual traffic from your computer" in content
        )
    except Exception as exc:
        _log.debug("Could not read page content in _is_captcha_page: %s", exc)
        return False
