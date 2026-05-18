import re
import json
import pytest
from playwright.sync_api import Page
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Web_ReKYC_Config import (
    WEB_CLIENT_CODE, WEB_PASSWORD, WEB_YOPMAIL,
    WEB_URL, REKYC_PDF_FILE, REKYC_JPG_FILE
)

step_results = []

def run_step(step_number, step_name, action):
    try:
        action()
        step_results.append({
            "step"  : step_number,
            "name"  : step_name,
            "status": "PASS",
            "reason": ""
        })
        print(f" Step {step_number} PASSED: {step_name}")
    except Exception as e:
        error_msg = str(e).encode("ascii", "ignore").decode("ascii")
        step_results.append({
            "step"  : step_number,
            "name"  : step_name,
            "status": "FAIL",
            "reason": error_msg
        })
        print(f" Step {step_number} FAILED: {step_name} | Reason: {error_msg}")
        raise
    finally:
        with open("web_rekyc_step_results.json", "w") as f:
            json.dump(step_results, f)


class TestWebReKYC:

    def test_web_rekyc_flow(self, page: Page):

        step_results.clear()

        # ── STEP 1: Open Web Login Page ───────────────
        def step1():
            page.context.grant_permissions([])
            page.goto(WEB_URL)
            page.wait_for_timeout(3000)
        run_step(1, "Open Web Login Page", step1)

        # ── STEP 2: Click Login with Client Code ──────
        def step2():
            page.locator("//button[text()='Login with client code']").click()
            page.wait_for_timeout(3000)
        run_step(2, "Click Login with Client Code", step2)

        # ── STEP 3: Enter Client Code ─────────────────
        def step3():
            page.wait_for_selector("//input[@name='clientCode']", state="attached", timeout=10000)
            page.locator("//input[@name='clientCode']").click()
            page.wait_for_timeout(500)
            page.locator("//input[@name='clientCode']").fill(WEB_CLIENT_CODE)
            page.wait_for_timeout(1000)
        run_step(3, f"Enter Client Code: {WEB_CLIENT_CODE}", step3)

        # ── STEP 4: Enter Password ────────────────────
        def step4():
            page.locator("//input[@name='lPassword']").click()
            page.wait_for_timeout(500)
            page.locator("//input[@name='lPassword']").fill(WEB_PASSWORD)
            page.wait_for_timeout(1000)
        run_step(4, "Enter Password", step4)

        # ── STEP 5: Click Get OTP ─────────────────────
        def step5():
            page.wait_for_timeout(2000)
            page.locator("//input[@onclick='GetTOTP()']").click()
            print(" Get OTP clicked!")
            page.wait_for_timeout(5000)
        run_step(5, "Click Get OTP", step5)

        # ── STEP 6: Get OTP from YopMail ─────────────
        def step6():
            page.wait_for_selector("//input[@name='usertotp']", timeout=15000)
            print(" OTP field appeared!")
            page.wait_for_timeout(3000)

            new_page = page.context.new_page()
            new_page.set_default_timeout(60000)

            for attempt in range(3):
                try:
                    print(f" Attempt {attempt+1}: Opening YopMail...")
                    new_page.set_extra_http_headers({
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept-Language": "en-US,en;q=0.9"
                    })
                    new_page.goto("https://yopmail.com/en", timeout=60000, wait_until="domcontentloaded")
                    new_page.wait_for_timeout(10000)
                    break
                except Exception as e:
                    print(f" Attempt {attempt+1} failed: {e}")
                    if attempt == 2:
                        raise Exception("YopMail not loading!")
                    new_page.wait_for_timeout(3000)

            new_page.locator("input[id='login']").fill(WEB_YOPMAIL.split("@")[0])
            new_page.wait_for_timeout(1000)
            new_page.keyboard.press("Enter")
            new_page.wait_for_timeout(10000)

            try:
                new_page.evaluate("""
                    const popup = document.querySelector('#r_parent');
                    if (popup) popup.style.display = 'none';
                """)
                new_page.wait_for_timeout(1000)
            except:
                pass

            try:
                new_page.evaluate("r()")
                new_page.wait_for_timeout(12000)
            except:
                new_page.locator("#refresh").click(force=True)
                new_page.wait_for_timeout(12000)

            try:
                first_email = new_page.locator(".lms div.m").first
                if first_email.is_visible(timeout=5000):
                    first_email.click()
                    new_page.wait_for_timeout(3000)
                    print(" Clicked latest email!")
            except:
                print(" Reading current email...")

            frame = new_page.frame_locator("#ifmail")
            try:
                email_body = frame.locator("body").text_content(timeout=15000)
                print(f" Email body: {email_body[:300]}")
            except:
                email_body = ""

            otp_match = re.search(r"\b\d{6}\b", email_body)
            if otp_match:
                otp = otp_match.group()
            else:
                otp_match = re.search(r"\b\d{4}\b", email_body)
                if otp_match:
                    otp = otp_match.group()
                else:
                    raise Exception(f"OTP not found! Body: {email_body[:200]}")

            print(f" OTP Found: {otp}")
            new_page.close()

            page.bring_to_front()
            page.wait_for_timeout(1000)
            page.locator("//input[@name='usertotp']").clear()
            page.locator("//input[@name='usertotp']").fill(otp)
            page.wait_for_timeout(1000)
            print(f" OTP {otp} entered!")
        run_step(6, f"Get OTP from YopMail: {WEB_YOPMAIL}", step6)

        # ── STEP 7: Click Login ───────────────────────
        def step7():
            page.locator("//button[@id='login_fsmt']").click()
            print(" Login clicked!")
            page.wait_for_timeout(5000)
        run_step(7, "Click Login Button", step7)

        # ── STEP 8: Close Risk Disclosure Popup ───────
        def step8():
            page.wait_for_timeout(3000)
            try:
                page.wait_for_selector("//button[text()='Agree']", timeout=8000)
                page.locator("//button[text()='Agree']").click()
                print(" Risk Disclosure Agree clicked!")
                page.wait_for_timeout(2000)
            except:
                try:
                    page.evaluate("""
                        (() => {
                            const btns = document.querySelectorAll('button');
                            for (let btn of btns) {
                                if (btn.textContent.trim() === 'Agree') {
                                    btn.click();
                                    break;
                                }
                            }
                        })()
                    """)
                    print(" Agree clicked via JavaScript!")
                    page.wait_for_timeout(2000)
                except:
                    print(" Risk Disclosure not found, continuing...")
        run_step(8, "Close Risk Disclosure Popup", step8)

        # ── STEP 9: Close TOTP Popup ──────────────────
        def step9():
            page.wait_for_timeout(2000)
            try:
                for loc in [
                    "//button[@aria-label='close']",
                    "//button[contains(@class,'dhx_button--icon')]",
                    "//button[contains(text(),'Continue With OTP')]",
                ]:
                    try:
                        btn = page.locator(loc).first
                        if btn.is_visible(timeout=2000):
                            btn.click()
                            print(" TOTP popup closed!")
                            page.wait_for_timeout(1000)
                            break
                    except:
                        continue
            except:
                print(" TOTP popup not found, continuing...")
        run_step(9, "Close TOTP Popup", step9)

        # ── STEP 10: Click Re-Ekyc from Left Menu ─────
        def step10():
            page.wait_for_timeout(2000)
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(1000)
            except:
                pass

            try:
                toggle_selectors = [
                    "//button[contains(@class,'sidebar-toggle')]",
                    "//button[contains(@class,'hamburger')]",
                    "//span[contains(@class,'menu-icon')]",
                    "//div[contains(@class,'sidebar')]//button",
                    "//i[contains(@class,'menu')]",
                ]
                for sel in toggle_selectors:
                    try:
                        btn = page.locator(sel).first
                        if btn.is_visible(timeout=2000):
                            btn.click()
                            print(f" Sidebar expanded using: {sel}")
                            page.wait_for_timeout(1500)
                            break
                    except:
                        continue
            except:
                print(" Sidebar toggle not found, continuing...")

            try:
                page.evaluate("""
                    (() => {
                        const sidebar = document.querySelector(
                            '.sidebar, .left-menu, .nav-menu, [class*="sidebar"], [class*="left-nav"]'
                        );
                        if (sidebar) sidebar.scrollTop = sidebar.scrollHeight;
                    })()
                """)
                page.wait_for_timeout(1000)
            except:
                pass

            clicked = page.evaluate("""
                (() => {
                    const spans = document.querySelectorAll('span.m-item');
                    for (let span of spans) {
                        if (span.textContent.trim() === 'Re-Ekyc') {
                            span.scrollIntoView();
                            span.click();
                            return true;
                        }
                    }
                    return false;
                })()
            """)

            if not clicked:
                clicked = page.evaluate("""
                    (() => {
                        const spans = document.querySelectorAll('span');
                        for (let span of spans) {
                            if (span.textContent.trim() === 'Re-Ekyc') {
                                span.scrollIntoView();
                                span.parentElement.click();
                                return true;
                            }
                        }
                        return false;
                    })()
                """)
                if clicked:
                    print(" Re-Ekyc clicked via parent element")
                else:
                    raise Exception("Re-Ekyc menu item not found in DOM!")
            else:
                print(" Re-Ekyc clicked!")

            page.wait_for_timeout(3000)
        run_step(10, "Click Re-Ekyc from Left Menu", step10)

        # ── STEP 11: Check ReKYC Window ───────────────
        def step11():
            print(f" Total pages open: {len(page.context.pages)}")
            for p in page.context.pages:
                print(f" Page URL: {p.url}")
        run_step(11, "Check ReKYC Window", step11)

        # ── Helper: Get ReKYC Page ────────────────────
        def get_rekyc_page():
            for p in page.context.pages:
                if "rekyc.navia.co.in" in p.url:
                    prepare_rekyc_page(p)
                    return p
            raise Exception("ReKYC page not found!")

        def prepare_rekyc_page(rekyc_page):
            rekyc_page.bring_to_front()
            try:
                rekyc_page.set_viewport_size({"width": 1200, "height": 900})
            except:
                pass
            try:
                rekyc_page.evaluate("window.moveTo(0, 0); window.resizeTo(1200, 900);")
            except:
                pass
            try:
                rekyc_page.wait_for_load_state("domcontentloaded", timeout=10000)
            except:
                pass

        # ── Helper: Click menu item by data-key ───────
        def click_rekyc_menu(rekyc_page, data_key):
            prepare_rekyc_page(rekyc_page)
            item = rekyc_page.locator(f"a[data-key='{data_key}']").first
            item.wait_for(state="attached", timeout=15000)
            item.scroll_into_view_if_needed(timeout=10000)
            item.click(force=True, timeout=15000)
            try:
                rekyc_page.wait_for_load_state("networkidle", timeout=15000)
            except:
                try:
                    rekyc_page.wait_for_load_state("domcontentloaded", timeout=5000)
                except:
                    pass
            rekyc_page.wait_for_timeout(2000)
            print(f" Clicked ReKYC menu: {data_key}")

        # ── STEP 12: Switch to ReKYC Page and Click Email ─────
        def step12():
            rekyc_page = get_rekyc_page()
            rekyc_page.bring_to_front()
            rekyc_page.wait_for_timeout(3000)
            page._rekyc_page = rekyc_page

            all_keys = rekyc_page.evaluate("""
                (() => {
                    const links = document.querySelectorAll('a[data-key]');
                    return Array.from(links).map(el => el.getAttribute('data-key'));
                })()
            """)
            print(f" Available data-key values: {all_keys}")

            click_rekyc_menu(rekyc_page, "Email")
        run_step(12, "Click Email Section", step12)

        # ── STEP 13: Click Mobile No ───────────────────
        def step13():
            rekyc_page = page._rekyc_page
            click_rekyc_menu(rekyc_page, "MobileNo")
        run_step(13, "Click Mobile No Section", step13)

        # ── STEP 14: Click Change of Address ──────────
        def step14():
            rekyc_page = page._rekyc_page
            click_rekyc_menu(rekyc_page, "Changeofaddress")
        run_step(14, "Click Change of Address Section", step14)

        # ── STEP 15: Click Nominee ───────────────────
        def step15():
            rekyc_page = page._rekyc_page
            click_rekyc_menu(rekyc_page, "nominee")
        run_step(15, "Click Nominee Section", step15)

        # ── STEP 16: Click Bank ───────────────────────
        def step16():
            rekyc_page = page._rekyc_page
            click_rekyc_menu(rekyc_page, "bank")
        run_step(16, "Click Bank Section", step16)

        # ── STEP 17: Click Segment ────────────────────
        def step17():
            rekyc_page = page._rekyc_page
            click_rekyc_menu(rekyc_page, "segment")
            try:
                btn = rekyc_page.locator("//button[contains(text(),'Agree')]")
                if btn.is_visible(timeout=3000):
                    btn.click()
            except:
                pass
            rekyc_page.wait_for_timeout(2000)
        run_step(17, "Click Segment Section", step17)

        # ── STEP 18: Click Income Declaration ─────────
        def step18():
            rekyc_page = page._rekyc_page
            click_rekyc_menu(rekyc_page, "IncomeDeclaration")
        run_step(18, "Click Income Declaration Section", step18)

        # ── STEP 19: Click Dis Slip Req ───────────────
        def step19():
            rekyc_page = page._rekyc_page
            click_rekyc_menu(rekyc_page, "DISSlipReq")
        run_step(19, "Click Dis Slip Req Section", step19)

        # ── STEP 20: Click Service Status ─────────────
        def step20():
            rekyc_page = page._rekyc_page
            click_rekyc_menu(rekyc_page, "ServiceStatus")
        run_step(20, "Click Service Status Section", step20)

        # ── STEP 21: Click Documents ──────────────────
        def step21():
            rekyc_page = page._rekyc_page
            click_rekyc_menu(rekyc_page, "documents")
            rekyc_page.wait_for_timeout(3000)
        run_step(21, "Click Documents Section", step21)

        # ── STEP 22: Click DDPI ───────────────────────
        def step22():
            rekyc_page = page._rekyc_page
            click_rekyc_menu(rekyc_page, "ddpi")
        run_step(22, "Click DDPI Section", step22)

        # ── STEP 23: Switch back to Dashboard ─────────
        def step23():
            page.bring_to_front()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(3000)
            print(f" Switched back to dashboard: {page.url}")
        run_step(23, "Switch Back to Dashboard", step23)

        # ── STEP 24: Click Profile Icon ───────────────
        def step24():
            page.wait_for_timeout(2000)
            profile_locators = [
                ".profile_sec_head",
                "[class*='profile_sec']",
                "[class*='profile-icon']",
                "[class*='user-icon']",
                "[class*='avatar']",
                "//div[contains(@class,'profile')]",
                "//span[contains(@class,'profile')]",
            ]
            clicked = False
            for loc in profile_locators:
                try:
                    el = page.locator(loc).first
                    if el.is_visible(timeout=2000):
                        el.click()
                        clicked = True
                        print(f" Profile icon clicked using: {loc}")
                        page.wait_for_timeout(2000)
                        break
                except:
                    continue

            if not clicked:
                clicked = page.evaluate("""
                    (() => {
                        const selectors = ['.profile_sec_head','[class*="profile"]','[class*="user-icon"]','[class*="avatar"]'];
                        for (let sel of selectors) {
                            const el = document.querySelector(sel);
                            if (el && typeof el.click === 'function') {
                                el.scrollIntoView();
                                el.click();
                                return sel;
                            }
                        }
                        return null;
                    })()
                """)
                if clicked:
                    print(f" Profile icon clicked via JS: {clicked}")
                    page.wait_for_timeout(2000)
                else:
                    raise Exception("Profile icon not found!")
        run_step(24, "Click Profile Icon", step24)

        # ── STEP 25: Click My Profile ─────────────────
        def step25():
            page.wait_for_timeout(2000)
            my_profile_locators = [
                "//a[contains(text(),'My Profile')]",
                "//span[contains(text(),'My Profile')]",
                "//li[contains(text(),'My Profile')]",
                "//div[contains(text(),'My Profile')]",
                "//*[contains(text(),'My Profile')]",
            ]
            clicked = False
            for loc in my_profile_locators:
                try:
                    el = page.locator(loc).first
                    if el.is_visible(timeout=3000):
                        el.click()
                        clicked = True
                        print(f" My Profile clicked using: {loc}")
                        page.wait_for_timeout(3000)
                        break
                except:
                    continue

            if not clicked:
                clicked = page.evaluate("""
                    (() => {
                        const all = document.querySelectorAll('a, span, li, div');
                        for (let el of all) {
                            if (el.textContent.trim() === 'My Profile' && typeof el.click === 'function') {
                                el.scrollIntoView();
                                el.click();
                                return el.tagName + ':' + el.className;
                            }
                        }
                        return null;
                    })()
                """)
                if clicked:
                    print(f" My Profile clicked via JS: {clicked}")
                    page.wait_for_timeout(3000)
                else:
                    raise Exception("My Profile option not found!")
        run_step(25, "Click My Profile", step25)

        # ── STEP 26: Click Edit Icon on Profile Page ──
        def step26():
            page.wait_for_timeout(3000)
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)
            print(f" Current URL before edit click: {page.url}")

            edit_locators = [
                "//div[contains(@class,'profile')]//input[@type='checkbox']",
                "//label[contains(@class,'edit')]",
                "//i[contains(@class,'edit') or contains(@class,'pencil')]",
                "[class*='edit-icon']",
                "[class*='pencil']",
                "[class*='edit_icon']",
            ]

            clicked = False
            for loc in edit_locators:
                try:
                    el = page.locator(loc).first
                    if el.is_visible(timeout=2000):
                        el.click()
                        clicked = True
                        print(f" Edit icon clicked using locator: {loc}")
                        page.wait_for_timeout(3000)
                        break
                except:
                    continue

            if not clicked:
                clicked = page.evaluate("""
                    (() => {
                        try {
                            const allEls = Array.from(document.querySelectorAll('*'));
                            for (let el of allEls) {
                                const cls = (el.className || '').toString().toLowerCase();
                                if ((cls.includes('edit') || cls.includes('pencil')) && typeof el.click === 'function') {
                                    el.scrollIntoView();
                                    el.click();
                                    return 'class-match:' + cls;
                                }
                            }
                            return null;
                        } catch(e) {
                            return 'error:' + e.message;
                        }
                    })()
                """)
                if clicked and not str(clicked).startswith('error'):
                    print(f" Edit icon clicked via JS class match: {clicked}")
                    page.wait_for_timeout(3000)
                else:
                    clicked2 = page.evaluate("""
                        (() => {
                            try {
                                const walker = document.createTreeWalker(
                                    document.body, NodeFilter.SHOW_TEXT, null, false
                                );
                                let node;
                                while (node = walker.nextNode()) {
                                    if (node.textContent.trim() === 'Email') {
                                        const parent = node.parentElement;
                                        const row = parent.closest('tr, li, div');
                                        if (row) {
                                            const clickables = row.querySelectorAll('button, input, label, a');
                                            for (let c of clickables) {
                                                if (typeof c.click === 'function') {
                                                    c.scrollIntoView();
                                                    c.click();
                                                    return 'near-email:' + c.tagName;
                                                }
                                            }
                                        }
                                        break;
                                    }
                                }
                                return null;
                            } catch(e) {
                                return 'error:' + e.message;
                            }
                        })()
                    """)
                    if clicked2 and not str(clicked2).startswith('error'):
                        print(f" Edit icon clicked near Email text: {clicked2}")
                        page.wait_for_timeout(3000)
                    else:
                        raise Exception(f"Edit icon not found! JS results: {clicked}, {clicked2}")

            page.wait_for_timeout(3000)
            all_pages = page.context.pages
            print(f" Total pages after edit click: {len(all_pages)}")
            for p in all_pages:
                print(f"   URL: {p.url}")
        run_step(26, "Click Edit Icon on Profile Page", step26)

        # ── Helper: Get ReKYC Page (fresh) ────────────
        def get_rekyc_page_fresh():
            page.wait_for_timeout(2000)
            for p in page.context.pages:
                if "rekyc.navia.co.in" in p.url:
                    prepare_rekyc_page(p)
                    return p
            raise Exception("ReKYC page not found after edit click!")

        # ── Helper: Click ReKYC menu by data-key ──────
        def click_profile_rekyc_menu(rekyc_page, data_key):
            prepare_rekyc_page(rekyc_page)
            item = rekyc_page.locator(f"a[data-key='{data_key}']").first
            item.wait_for(state="attached", timeout=15000)
            item.scroll_into_view_if_needed(timeout=10000)
            item.click(force=True, timeout=15000, no_wait_after=True)
            rekyc_page.wait_for_timeout(2000)
            try:
                rekyc_page.wait_for_load_state("domcontentloaded", timeout=5000)
            except:
                pass
            print(f" Clicked profile ReKYC menu: {data_key}")

        # ── Helper: Click menu item by data-key ───────
        def click_rekyc_menu(rekyc_page, data_key):
            click_profile_rekyc_menu(rekyc_page, data_key)

        # ── STEP 27: Switch to ReKYC and Click Email ──
        def step27():
            rekyc_page = get_rekyc_page_fresh()
            rekyc_page.bring_to_front()
            rekyc_page.wait_for_load_state("domcontentloaded")
            rekyc_page.wait_for_timeout(3000)
            page._profile_rekyc_page = rekyc_page
            print(f" ReKYC page URL: {rekyc_page.url}")
            all_keys = rekyc_page.evaluate("""
                (() => {
                    const links = document.querySelectorAll('a[data-key]');
                    return Array.from(links).map(el => el.getAttribute('data-key'));
                })()
            """)
            print(f" Available data-key values: {all_keys}")
            click_profile_rekyc_menu(rekyc_page, "Email")
        run_step(27, "Click Email Section (Profile ReKYC)", step27)

        # ── STEP 28: Click Mobile No ───────────────────
        def step28():
            rekyc_page = page._profile_rekyc_page
            click_profile_rekyc_menu(rekyc_page, "MobileNo")
        run_step(28, "Click Mobile No Section (Profile ReKYC)", step28)

        # ── STEP 29: Click Change of Address ──────────
        def step29():
            rekyc_page = get_rekyc_page_fresh()
            page._profile_rekyc_page = rekyc_page
            click_profile_rekyc_menu(rekyc_page, "Changeofaddress")
        run_step(29, "Click Change of Address Section (Profile ReKYC)", step29)

        # ── STEP 30: Click Nominee ─────────────────────
        def step30():
            rekyc_page = get_rekyc_page_fresh()
            page._profile_rekyc_page = rekyc_page
            click_profile_rekyc_menu(rekyc_page, "nominee")
        run_step(30, "Click Nominee Section (Profile ReKYC)", step30)

        # ── STEP 31: Click Bank ────────────────────────
        def step31():
            rekyc_page = get_rekyc_page_fresh()
            page._profile_rekyc_page = rekyc_page
            click_profile_rekyc_menu(rekyc_page, "bank")
        run_step(31, "Click Bank Section (Profile ReKYC)", step31)

        # ── STEP 32: Click Segment ─────────────────────
        def step32():
            rekyc_page = get_rekyc_page_fresh()
            page._profile_rekyc_page = rekyc_page
            click_profile_rekyc_menu(rekyc_page, "segment")
            try:
                btn = rekyc_page.locator("//button[contains(text(),'Agree')]")
                if btn.is_visible(timeout=3000):
                    btn.click()
                    rekyc_page.wait_for_timeout(1000)
            except:
                pass
        run_step(32, "Click Segment Section (Profile ReKYC)", step32)

        # ── STEP 33: Click Income Declaration ─────────
        def step33():
            rekyc_page = get_rekyc_page_fresh()
            page._profile_rekyc_page = rekyc_page
            click_profile_rekyc_menu(rekyc_page, "IncomeDeclaration")
        run_step(33, "Click Income Declaration Section (Profile ReKYC)", step33)



        # ── STEP 34: Click Dis Slip Req ───────────────
        def step38():
            rekyc_page = get_rekyc_page_fresh()
            page._profile_rekyc_page = rekyc_page
            click_profile_rekyc_menu(rekyc_page, "DISSlipReq")
        run_step(34, "Click Dis Slip Req Section (Profile ReKYC)", step38)

        # ── STEP 35: Click Service Status ─────────────
        def step39():
            rekyc_page = get_rekyc_page_fresh()
            page._profile_rekyc_page = rekyc_page
            click_profile_rekyc_menu(rekyc_page, "ServiceStatus")
        run_step(35, "Click Service Status Section (Profile ReKYC)", step39)


                # ── STEP 36: Click Documents ───────────────────
        def step35():
            rekyc_page = page._profile_rekyc_page
            click_profile_rekyc_menu(rekyc_page, "documents")
            rekyc_page.wait_for_selector("table", timeout=15000)
            rekyc_page.wait_for_timeout(3000)
        run_step(36, "Click Documents Section (Profile ReKYC)", step35)

        def close_proof_modal(rekyc_page):
            close_locators = [
                "button:has-text('Close')",
                ".modal button:has-text('Close')",
                ".modal-header button.close",
                "[data-bs-dismiss='modal']",
                "[data-dismiss='modal']",
                "button[aria-label='Close']",
                "#closeModal",
            ]
            for locator in close_locators:
                try:
                    close_button = rekyc_page.locator(locator).last
                    if close_button.is_visible(timeout=2000):
                        close_button.click(force=True, timeout=5000)
                        rekyc_page.wait_for_timeout(1000)
                        return
                except:
                    continue

            closed = rekyc_page.evaluate("""
                (() => {
                    const closeButtons = Array.from(document.querySelectorAll(
                        "#closeModal, button, [data-bs-dismiss='modal'], [data-dismiss='modal']"
                    ));
                    for (const button of closeButtons) {
                        const text = (button.textContent || "").trim().toLowerCase();
                        const isClose = button.id === "closeModal" ||
                            button.getAttribute("aria-label") === "Close" ||
                            text === "close" ||
                            button.hasAttribute("data-bs-dismiss") ||
                            button.hasAttribute("data-dismiss");
                        if (isClose && typeof button.click === "function") {
                            button.click();
                            return true;
                        }
                    }

                    const visibleModals = Array.from(document.querySelectorAll(".modal, .modal-backdrop"));
                    for (const modal of visibleModals) {
                        modal.style.display = "none";
                        modal.classList.remove("show");
                    }
                    document.body.classList.remove("modal-open");
                    document.body.style.overflow = "";
                    return visibleModals.length > 0;
                })()
            """)
            if not closed:
                rekyc_page.keyboard.press("Escape")
            rekyc_page.wait_for_timeout(1000)


        # ── STEP 37: Click View Proof for first row ─────────
        def scroll_proof_to_last_page(rekyc_page, filename):
            if not filename.lower().endswith(".pdf"):
                return
            try:
                pdf_iframe = rekyc_page.locator("iframe").first
                box = pdf_iframe.bounding_box()
                if box:
                    rekyc_page.mouse.click(
                        box["x"] + box["width"] / 2,
                        box["y"] + box["height"] / 2
                    )
            except:
                pass
            for _ in range(18):
                rekyc_page.mouse.wheel(0, 450)
                rekyc_page.wait_for_timeout(650)

        def step36():
            rekyc_page = page._profile_rekyc_page
            rekyc_page.wait_for_timeout(3000)

            rows = rekyc_page.locator("table tr")
            if rows.count() < 2:
                raise Exception("Not enough rows in documents table")

            row = rows.nth(1)
            filename = (row.locator("td").nth(2).text_content() or "").strip()

            row.locator("td").last.click(force=True)
            print(f" Clicked View Proof for: {filename}")

            rekyc_page.wait_for_timeout(2000)
            scroll_proof_to_last_page(rekyc_page, filename)

            if filename.lower().endswith(".pdf"):
                pdf_iframe = rekyc_page.locator("iframe").first
                box = pdf_iframe.bounding_box()
                if box:
                    rekyc_page.mouse.click(
                        box["x"] + box["width"] / 2,
                        box["y"] + box["height"] / 2
                    )
                    rekyc_page.wait_for_timeout(500)
                    for _ in range(10):
                        rekyc_page.mouse.wheel(0, 500)
                        rekyc_page.wait_for_timeout(500)

            close_proof_modal(rekyc_page)
        run_step(37, "Click View Proof for first row (Profile ReKYC)", step36)


        # ── STEP 38: Click View Proof for second row ─────────
        def step37():
            rekyc_page = page._profile_rekyc_page
            rekyc_page.wait_for_timeout(2000)

            rows = rekyc_page.locator("table tr")
            if rows.count() < 3:
                raise Exception("Second row not available in documents table")

            row = rows.nth(2)
            filename = (row.locator("td").nth(2).text_content() or "").strip()

            row.locator("td").last.click(force=True)
            print(f" Clicked View Proof for: {filename}")

            rekyc_page.wait_for_timeout(2000)
            scroll_proof_to_last_page(rekyc_page, filename)

            if filename.lower().endswith(".pdf"):
                pdf_iframe = rekyc_page.locator("iframe").first
                box = pdf_iframe.bounding_box()
                if box:
                    rekyc_page.mouse.click(
                        box["x"] + box["width"] / 2,
                        box["y"] + box["height"] / 2
                    )
                    rekyc_page.wait_for_timeout(500)
                    for _ in range(10):
                        rekyc_page.mouse.wheel(0, 500)
                        rekyc_page.wait_for_timeout(500)

            close_proof_modal(rekyc_page)
        run_step(38, "Click View Proof for second row (Profile ReKYC)", step37)

                # ── STEP 39: Click DDPI Section ───────────────
        def step38():
            rekyc_page = page._profile_rekyc_page
            click_profile_rekyc_menu(rekyc_page, "ddpi")
        run_step(39, "Click DDPI Section (Profile ReKYC)", step38)

        print("\n All Web ReKYC Steps Completed Successfully!")
