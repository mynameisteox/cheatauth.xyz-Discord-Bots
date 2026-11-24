import re
import time
import requests

class CheatAuthClient:
    LICENSES_URL = "https://cheatauth.xyz/user/?p=licenses"
    APPS_URL = "https://cheatauth.xyz/user/?p=apps"
    BLACKLIST_URL = "https://cheatauth.xyz/user/?p=blacklist"
    DEALERS_URL = "https://cheatauth.xyz/user/?p=dealers"
    
    def __init__(self, session_cookie: str, app_id: str = "popupbypass_ff8a7be0"):
        self.session_cookie = session_cookie.strip()
        self.app_id = app_id
        self._apps_cache = [
            {"name": "Popup Bypass", "app_id": app_id, "status": "Aktif", "license_count": "0", "heartbeat_sec": 300}
        ]
        self._apps_cache_time = 0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Referer": self.LICENSES_URL,
            "Origin": "https://cheatauth.xyz"
        })
        self.session.cookies.set("cgauth_user", self.session_cookie)

    def _get_page(self, url: str = None) -> str:
        target_url = url or self.LICENSES_URL
        res = self.session.get(target_url, timeout=12)
        if "location.href = '/user/login.php'" in res.text or "/user/login.php" in res.url:
            raise Exception("Oturum süresi dolmuş veya geçersiz cookie! Lütfen /cookie-guncelle ile yeni çerezi girin.")
        return res.text

    def _extract_csrf(self, html: str) -> str:
        match = re.search(r'name=["\']_csrf["\']\s+value=["\']([a-f0-9]+)["\']', html)
        if not match:
            raise Exception("CSRF token bulunamadı!")
        return match.group(1)

    def list_licenses(self):
        html = self._get_page()
        licenses = []
        rows = re.findall(r'<tr[\s\S]*?</tr>', html)
        for row in rows:
            lid_m = re.search(r'name=["\']selected_ids\[\]["\']\s+value=["\'](\d+)["\']', row)
            if not lid_m:
                continue
            lid = lid_m.group(1)
            
            key_m = re.search(r'<span class=["\']key-val mono["\']>([^<]+)</span>', row)
            key_val = key_m.group(1) if key_m else "Bilinmiyor"
            
            cells = re.findall(r'<td>([\s\S]*?)</td>', row)
            
            # App Name
            app_name = re.sub(r'<[^>]+>', '', cells[1]).strip() if len(cells) > 1 else "Bilinmiyor"
            
            # HWID
            hwid_raw = cells[2] if len(cells) > 2 else "-"
            hwid = re.sub(r'<[^>]+>', '', hwid_raw).strip()

            # Expiry & Duration
            expiry = re.sub(r'<[^>]+>', '', cells[3]).strip() if len(cells) > 3 else "-"
            duration = re.sub(r'<[^>]+>', '', cells[4]).strip() if len(cells) > 4 else "-"

            # Status (Kullanılmadı / Aktif / Donduruldu / Banlandı)
            status_m = re.search(r'<span class=["\']badge["\'][^>]*>([^<]+)</span>', row)
            status = status_m.group(1) if status_m else "Bilinmiyor"

            # Usage count
            usage = re.sub(r'<[^>]+>', '', cells[6]).strip() if len(cells) > 6 else "0"

            # Note
            note = re.sub(r'<[^>]+>', '', cells[7]).strip() if len(cells) > 7 else ""
            if note == "—":
                note = ""

            licenses.append({
                "lid": lid,
                "app": app_name,
                "key": key_val,
                "hwid": hwid,
                "duration": duration,
                "expiry": expiry,
                "status": status,
                "usage": usage,
                "note": note
            })
        return licenses

    def find_license(self, key_or_lid: str):
        licenses = self.list_licenses()
        search_term = key_or_lid.strip().lower()
        for lic in licenses:
            if lic["key"].lower() == search_term or lic["lid"] == search_term:
                return lic
        return None

    def create_license(self, days: int = 1, hours: int = 0, count: int = 1, note: str = "", app_id: str = None):
        target_app = (app_id or self.app_id).strip()
        html = self._get_page()
        csrf = self._extract_csrf(html)
        old_keys = set(re.findall(r'<span class=["\']key-val mono["\']>([^<]+)</span>', html))

        payload = {
            "_csrf": csrf,
            "do": "create_license",
            "app_id": target_app,
            "count": str(count),
            "days": str(days) if days > 0 else "",
            "hours": str(hours) if hours > 0 else "",
            "note": note
        }

        res = self.session.post(self.LICENSES_URL, data=payload, timeout=12)
        if res.status_code != 200:
            raise Exception(f"HTTP Hata Kodu: {res.status_code}")

        new_html = res.text
        # Error check
        err_m = re.search(r'<div[^>]*class=["\'][^"\']*(?:alert-danger|toast-error|notification-error)[^"\']*["\'][^>]*>([\s\S]*?)</div>', new_html)
        if err_m:
            err_text = re.sub(r'<[^>]+>', '', err_m.group(1)).strip()
            if err_text:
                raise Exception(err_text)

        new_keys_all = re.findall(r'<span class=["\']key-val mono["\']>([^<]+)</span>', new_html)
        created_keys = [k for k in new_keys_all if k not in old_keys]
        if not created_keys and new_keys_all:
            created_keys = new_keys_all[:count]
        return created_keys

    def reset_hwid(self, key_or_lid: str):
        target = self.find_license(key_or_lid)
        if not target:
            return {"success": False, "message": f"'{key_or_lid}' lisansı bulunamadı!"}

        html = self._get_page()
        csrf = self._extract_csrf(html)

        payload = {"_csrf": csrf, "do": "hwid_reset", "lid": target["lid"]}
        res = self.session.post(self.LICENSES_URL, data=payload, timeout=12)
        return {"success": res.status_code == 200, "message": f"**{target['key']}** anahtarının HWID kilidi başarıyla sıfırlandı!", "key": target["key"]}

    def reset_hwid_all(self, app_id: str = None):
        html = self._get_page()
        csrf = self._extract_csrf(html)
        target_app = (app_id or "").strip() if app_id and app_id != "ALL" else ""
        payload = {"_csrf": csrf, "do": "hwid_reset_all", "app_id": target_app}
        res = self.session.post(self.LICENSES_URL, data=payload, timeout=12)
        return res.status_code == 200

    def clean_expired(self):
        html = self._get_page()
        csrf = self._extract_csrf(html)
        payload = {"_csrf": csrf, "do": "clean_expired"}
        res = self.session.post(self.LICENSES_URL, data=payload, timeout=12)
        return res.status_code == 200

    def clean_all(self, app_id: str = None):
        html = self._get_page()
        csrf = self._extract_csrf(html)
        target_app = (app_id or "").strip() if app_id and app_id != "ALL" else ""
        payload = {"_csrf": csrf, "do": "clean_all", "app_id": target_app}
        res = self.session.post(self.LICENSES_URL, data=payload, timeout=12)
        return res.status_code == 200

    def add_days_all(self, days: int, app_id: str = None):
        html = self._get_page()
        csrf = self._extract_csrf(html)
        target_app = (app_id or "").strip() if app_id and app_id != "ALL" else ""
        payload = {"_csrf": csrf, "do": "add_days_all", "app_id": target_app, "days": str(days)}
        res = self.session.post(self.LICENSES_URL, data=payload, timeout=12)
        return res.status_code == 200

    def freeze_license(self, key_or_lid: str):
        target = self.find_license(key_or_lid)
        if not target:
            return {"success": False, "message": f"'{key_or_lid}' lisansı bulunamadı!"}
        html = self._get_page()
        csrf = self._extract_csrf(html)
        payload = {"_csrf": csrf, "do": "freeze_license", "lid": target["lid"]}
        res = self.session.post(self.LICENSES_URL, data=payload, timeout=12)
        return {"success": res.status_code == 200, "key": target["key"]}

    def ban_license(self, key_or_lid: str):
        target = self.find_license(key_or_lid)
        if not target:
            return {"success": False, "message": f"'{key_or_lid}' lisansı bulunamadı!"}
        html = self._get_page()
        csrf = self._extract_csrf(html)
        payload = {"_csrf": csrf, "do": "ban_license", "lid": target["lid"]}
        res = self.session.post(self.LICENSES_URL, data=payload, timeout=12)
        return {"success": res.status_code == 200, "key": target["key"]}

    def suspend_license(self, key_or_lid: str):
        target = self.find_license(key_or_lid)
        if not target:
            return {"success": False, "message": f"'{key_or_lid}' lisansı bulunamadı!"}
        html = self._get_page()
        csrf = self._extract_csrf(html)
        payload = {"_csrf": csrf, "do": "suspend_license", "lid": target["lid"]}
        res = self.session.post(self.LICENSES_URL, data=payload, timeout=12)
        return {"success": res.status_code == 200, "key": target["key"]}

    def edit_duration(self, key_or_lid: str, action: str = "add", days: int = 1, hours: int = 0):
        target = self.find_license(key_or_lid)
        if not target:
            return {"success": False, "message": f"'{key_or_lid}' lisansı bulunamadı!"}
        html = self._get_page()
        csrf = self._extract_csrf(html)
        payload = {
            "_csrf": csrf,
            "do": "edit_duration",
            "lid": target["lid"],
            "dur_action": action,
            "dur_days": str(days),
            "dur_hours": str(hours)
        }
        res = self.session.post(self.LICENSES_URL, data=payload, timeout=12)
        return {"success": res.status_code == 200, "key": target["key"]}

    def delete_license(self, key_or_lid: str):
        target = self.find_license(key_or_lid)
        if not target:
            return {"success": False, "message": f"'{key_or_lid}' lisansı bulunamadı!"}
        html = self._get_page()
        csrf = self._extract_csrf(html)
        payload = {"_csrf": csrf, "do": "delete_license", "lid": target["lid"]}
        res = self.session.post(self.LICENSES_URL, data=payload, timeout=12)
        return {"success": res.status_code == 200, "key": target["key"]}

    def list_apps(self, force: bool = False):
        now = time.time()
        if not force and self._apps_cache and (now - self._apps_cache_time < 120):
            return self._apps_cache
        try:
            html = self._get_page(self.APPS_URL)
            apps = []
            card_blocks = re.split(r'<div class="app-card\s+', html)[1:]
            for block in card_blocks:
                if 'app-card-add' in block[:50]:
                    continue
                name_m = re.search(r'<div class="app-card-name">([^<]+)</div>', block)
                id_m = re.search(r'class="app-card-id mono"\s+title="([^"]+)"', block) or re.search(r'name="app_id"\s+value="([^"]+)"', block)
                status_m = re.search(r'<span class="app-card-badge[^>]*>([^<]+)</span>', block)
                lic_m = re.search(r'<span class="app-stat-num">(\d+)</span>\s*<span class="app-stat-label">Lisanslar</span>', block)
                hb_m = re.search(r'openHbModal\([^,]+,\s*(\d+)\)', block)

                if name_m and id_m:
                    apps.append({
                        "name": name_m.group(1).strip(),
                        "app_id": id_m.group(1).strip(),
                        "status": status_m.group(1).strip() if status_m else "Aktif",
                        "license_count": lic_m.group(1).strip() if lic_m else "0",
                        "heartbeat_sec": int(hb_m.group(1)) if hb_m else 300
                    })
            if apps:
                self._apps_cache = apps
                self._apps_cache_time = now
        except Exception:
            pass
        return self._apps_cache

    def get_apps_fast(self):
        """Autocomplete için anında bellekten döner, asla network gecikmesi yaşatmaz."""
        return self._apps_cache

    def get_app_name(self, app_id: str) -> str:
        if not app_id:
            return "Varsayılan Uygulama"
        apps = self.list_apps()
        for a in apps:
            if a["app_id"] == app_id:
                return a["name"]
        return app_id

    def create_app(self, name: str):
        html = self._get_page(self.APPS_URL)
        csrf = self._extract_csrf(html)
        payload = {"_csrf": csrf, "do": "create_app", "name": name.strip()}
        res = self.session.post(self.APPS_URL, data=payload, timeout=12)
        self._apps_cache = []
        return res.status_code == 200

    def toggle_app(self, app_id: str = None):
        target_app = (app_id or self.app_id).strip()
        html = self._get_page(self.APPS_URL)
        csrf = self._extract_csrf(html)
        payload = {"_csrf": csrf, "do": "toggle_app", "app_id": target_app}
        res = self.session.post(self.APPS_URL, data=payload, timeout=12)
        self._apps_cache = []
        return res.status_code == 200

    def set_heartbeat(self, interval_sec: int, app_id: str = None):
        target_app = (app_id or self.app_id).strip()
        html = self._get_page(self.APPS_URL)
        csrf = self._extract_csrf(html)
        payload = {"_csrf": csrf, "do": "set_heartbeat", "app_id": target_app, "heartbeat_interval": str(interval_sec)}
        res = self.session.post(self.APPS_URL, data=payload, timeout=12)
        self._apps_cache = []
        return res.status_code == 200

    def delete_app(self, app_id: str):
        html = self._get_page(self.APPS_URL)
        csrf = self._extract_csrf(html)
        payload = {"_csrf": csrf, "do": "delete_app", "app_id": app_id.strip()}
        res = self.session.post(self.APPS_URL, data=payload, timeout=12)
        self._apps_cache = []
        return res.status_code == 200

    def add_blacklist(self, kind: str, value: str, reason: str = ""):
        kind = kind.lower().strip()
        if kind not in ["ip", "hwid"]:
            raise Exception("Geçersiz tür! Yalnızca 'ip' veya 'hwid' seçebilirsiniz.")
        html = self._get_page(self.BLACKLIST_URL)
        csrf = self._extract_csrf(html)
        payload = {
            "_csrf": csrf,
            "do": "bl_add",
            "kind": kind,
            "value": value.strip(),
            "reason": reason.strip()
        }
        res = self.session.post(self.BLACKLIST_URL, data=payload, timeout=12)
        return res.status_code == 200

    def get_blacklist(self):
        html = self._get_page(self.BLACKLIST_URL)
        ip_list = []
        hwid_list = []
        rows = re.findall(r'<tr[\s\S]*?</tr>', html)
        for row in rows:
            tds = re.findall(r'<td>([\s\S]*?)</td>', row)
            if len(tds) >= 2:
                val = re.sub(r'<[^>]+>', '', tds[0]).strip()
                reason = re.sub(r'<[^>]+>', '', tds[1]).strip() if len(tds) > 1 else ""
                entry = {"value": val, "reason": reason}
                if "." in val or ":" in val:
                    ip_list.append(entry)
                else:
                    hwid_list.append(entry)
        return {"ips": ip_list, "hwids": hwid_list}

    def get_stats(self, app_name_filter: str = None):
        licenses = self.list_licenses()
        if app_name_filter and app_name_filter != "ALL":
            licenses = [l for l in licenses if l["app"].lower() == app_name_filter.lower()]
        total = len(licenses)
        active = sum(1 for l in licenses if l["status"] == "Aktif")
        unused = sum(1 for l in licenses if l["status"] == "Kullanılmadı")
        bound = sum(1 for l in licenses if l["hwid"] != "-")
        return {
            "total": total,
            "active": active,
            "unused": unused,
            "bound": bound
        }

    def get_dealers_info(self):
        html = self._get_page(self.DEALERS_URL)
        c_m = re.search(r'Kredi Bakiyeniz.*?stat-val[^>]*>(\d+)<', html, re.DOTALL)
        d_m = re.search(r'Toplam Bayiniz.*?stat-val[^>]*>(\d+)<', html, re.DOTALL)
        credits = int(c_m.group(1)) if c_m else 0
        total_dealers = int(d_m.group(1)) if d_m else 0

        dealers = []
        table_m = re.search(r'<table[\s\S]*?</table>', html)
        if table_m:
            rows = re.findall(r'<tr[\s\S]*?</tr>', table_m.group(0))
            for row in rows:
                tds = re.findall(r'<td[\s\S]*?</td>', row)
                if len(tds) >= 2:
                    email_raw = re.sub(r'<[^>]+>', '', tds[0]).strip()
                    credit_raw = re.sub(r'<[^>]+>', '', tds[1]).strip() if len(tds) > 1 else "0"
                    apps_raw = re.sub(r'<[^>]+>', '', tds[2]).strip() if len(tds) > 2 else "-"
                    status_raw = re.sub(r'<[^>]+>', '', tds[3]).strip() if len(tds) > 3 else "Bilinmiyor"
                    dealers.append({
                        "email": email_raw,
                        "credits": credit_raw,
                        "apps": apps_raw,
                        "status": status_raw
                    })
        return {
            "credits": credits,
            "total_dealers": total_dealers,
            "dealers": dealers
        }

    def invite_dealer(self, email: str, credits: int = 10, app_ids: list = None):
        html = self._get_page(self.DEALERS_URL)
        csrf = self._extract_csrf(html)

        if not app_ids:
            all_apps = self.list_apps()
            app_ids = [a["app_id"] for a in all_apps]

        payload = [
            ("_csrf", csrf),
            ("action", "invite"),
            ("email", email.strip()),
            ("credits", str(credits))
        ]
        for aid in app_ids:
            payload.append(("apps[]", aid))

        res = self.session.post(self.DEALERS_URL, data=payload, timeout=12)
        if res.status_code != 200:
            raise Exception(f"HTTP Hata Kodu: {res.status_code}")

        res_html = res.text
        err_m = re.search(r'<div class=["\'][^"\']*flash-err[^"\']*["\'][^>]*>([\s\S]*?)</div>', res_html)
        if err_m:
            err_msg = re.sub(r'<[^>]+>', '', err_m.group(1)).strip()
            raise Exception(err_msg)

        ok_m = re.search(r'<div class=["\'][^"\']*flash-ok[^"\']*["\'][^>]*>([\s\S]*?)</div>', res_html)
        success_msg = re.sub(r'<[^>]+>', '', ok_m.group(1)).strip() if ok_m else "Bayi daveti başarıyla gönderildi!"
        return success_msg

