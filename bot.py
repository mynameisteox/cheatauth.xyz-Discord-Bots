import os
import json
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from cheatauth_api import CheatAuthClient

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

config = load_config()
auth_client = CheatAuthClient(config["cheatauth_cookie"], config.get("app_id", ""))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=config.get("prefix", "!"), intents=intents, help_command=None)

async def send_log(title: str, description: str, color=discord.Color.blue()):
    log_channel_id = config.get("log_channel_id")
    if not log_channel_id:
        return
    try:
        channel = bot.get_channel(int(log_channel_id))
        if channel:
            embed = discord.Embed(title=title, description=description, color=color)
            embed.set_footer(text="CheatAuth Audit Log")
            await channel.send(embed=embed)
    except Exception:
        pass

# ==========================================
# AUTOCOMPLETE YARDIMCILARI (UYGULAMA SEÇİCİ)
# ==========================================

async def app_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Paneldeki mevcut uygulamaları bellekten anında (0ms) listeler."""
    try:
        apps = auth_client.get_apps_fast()
        choices = []
        for a in apps:
            name = a["name"]
            aid = a["app_id"]
            label = f"{name} ({aid[:12]}…)" if len(aid) > 12 else f"{name} ({aid})"
            if current.lower() in name.lower() or current.lower() in aid.lower():
                choices.append(app_commands.Choice(name=label[:100], value=aid))
        return choices[:25]
    except Exception:
        return []

async def app_autocomplete_with_all(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Tüm Uygulamalar seçeneği ile birlikte uygulamaları bellekten anında listeler."""
    try:
        choices = []
        if not current or any(k in current.lower() for k in ["tüm", "tum", "hepsi", "all"]):
            choices.append(app_commands.Choice(name="🌐 Tüm Uygulamalar (Genel)", value="ALL"))
        apps = auth_client.get_apps_fast()
        for a in apps:
            name = a["name"]
            aid = a["app_id"]
            label = f"{name} ({aid[:12]}…)" if len(aid) > 12 else f"{name} ({aid})"
            if current.lower() in name.lower() or current.lower() in aid.lower():
                choices.append(app_commands.Choice(name=label[:100], value=aid))
        return choices[:25]
    except Exception:
        return []

# ==========================================
# İNTERAKTİF BUTON PANELİ (UI BUTTONS)
# ==========================================

class LicenseActionView(discord.ui.View):
    def __init__(self, key_code: str, lid: str):
        super().__init__(timeout=180)
        self.key_code = key_code
        self.lid = lid

    @discord.ui.button(label="HWID Sıfırla", style=discord.ButtonStyle.primary, emoji="🔄")
    async def btn_reset_hwid(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        res = await asyncio.to_thread(auth_client.reset_hwid, self.key_code)
        if res.get("success"):
            await interaction.followup.send(f"✅ **`{self.key_code}`** HWID kilidi başarıyla sıfırlandı!", ephemeral=True)
            await send_log("🔄 HWID Sıfırlandı", f"Yetkili: {interaction.user.mention}\nKey: `{self.key_code}`", discord.Color.blue())
        else:
            await interaction.followup.send(f"❌ {res.get('message', 'Hata!')}", ephemeral=True)

    @discord.ui.button(label="+1 Gün Ekle", style=discord.ButtonStyle.success, emoji="➕")
    async def btn_add_day(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        res = await asyncio.to_thread(auth_client.edit_duration, self.key_code, action="add", days=1, hours=0)
        if res.get("success"):
            await interaction.followup.send(f"✅ **`{self.key_code}`** anahtarına +1 gün eklendi!", ephemeral=True)
            await send_log("➕ Süre Eklendi", f"Yetkili: {interaction.user.mention}\nKey: `{self.key_code}` (+1 Gün)", discord.Color.green())
        else:
            await interaction.followup.send("❌ Süre eklenemedi!", ephemeral=True)

    @discord.ui.button(label="Dondur / Çöz", style=discord.ButtonStyle.secondary, emoji="❄️")
    async def btn_freeze(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        res = await asyncio.to_thread(auth_client.freeze_license, self.key_code)
        if res.get("success"):
            await interaction.followup.send(f"❄️ **`{self.key_code}`** durumu değiştirildi (Donduruldu/Açıldı)!", ephemeral=True)
            await send_log("❄️ Lisans Donduruldu", f"Yetkili: {interaction.user.mention}\nKey: `{self.key_code}`", discord.Color.light_grey())
        else:
            await interaction.followup.send("❌ İşlem başarısız!", ephemeral=True)

    @discord.ui.button(label="Banla", style=discord.ButtonStyle.danger, emoji="🚫")
    async def btn_ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        res = await asyncio.to_thread(auth_client.ban_license, self.key_code)
        if res.get("success"):
            await interaction.followup.send(f"🚫 **`{self.key_code}`** başarıyla banlandı!", ephemeral=True)
            await send_log("🚫 Lisans Banlandı", f"Yetkili: {interaction.user.mention}\nKey: `{self.key_code}`", discord.Color.red())
        else:
            await interaction.followup.send("❌ Banlama başarısız!", ephemeral=True)

    @discord.ui.button(label="Sil", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def btn_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        res = await asyncio.to_thread(auth_client.delete_license, self.key_code)
        if res.get("success"):
            await interaction.followup.send(f"🗑️ **`{self.key_code}`** panelden silindi!", ephemeral=True)
            await send_log("🗑️ Lisans Silindi", f"Yetkili: {interaction.user.mention}\nKey: `{self.key_code}`", discord.Color.dark_red())
        else:
            await interaction.followup.send("❌ Silinemedi!", ephemeral=True)

@bot.event
async def on_ready():
    print(f"[+] Bot aktif: {bot.user.name} ({bot.user.id})")
    try:
        # Sunuculara anında komut senkronizasyonu (Discord önbelleği beklemeden anında yansır)
        for guild in bot.guilds:
            bot.tree.copy_global_to(guild=guild)
            synced_guild = await bot.tree.sync(guild=guild)
            print(f"[+] '{guild.name}' sunucusuna {len(synced_guild)} komut anında senkronize edildi.")
        synced = await bot.tree.sync()
        print(f"[+] {len(synced)} adet Global Slash komutu senkronize edildi.")
    except Exception as e:
        print(f"[-] Senkronizasyon hatası: {e}")
    # Arka planda uygulama önbelleğini sunucudan çekip ısıt
    asyncio.create_task(asyncio.to_thread(auth_client.list_apps, True))
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="cheatauth.xyz"))

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandInvokeError):
        error = error.original
    # Discord hızlı yazma / geçersiz kılınan etkileşimleri sessizce atla
    if isinstance(error, discord.NotFound) and getattr(error, 'code', None) == 10062:
        return
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ **Hata:** {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ **Hata:** {error}", ephemeral=True)
    except Exception:
        pass

# ==========================================
# 1. KEY OLUŞTURMA (DM Teslimatlı & Uygulama Seçmeli)
# ==========================================

@bot.tree.command(name="key-olustur", description="Yeni CheatAuth lisansı oluşturur ve müşteriye teslim eder.")
@app_commands.describe(
    uygulama="Key'in oluşturulacağı uygulama (Listeden seçin)",
    gun="Lisans süresi (gün). 0 = süresiz",
    saat="Lisans süresi (saat). Opsiyonel.",
    adet="Key adedi (Varsayılan: 1)",
    kullanici="Key'in DM ile gönderileceği müşteri (Opsiyonel)",
    not_bilgisi="Lisans notu (Opsiyonel)"
)
@app_commands.autocomplete(uygulama=app_autocomplete)
async def slash_create_key(
    interaction: discord.Interaction,
    uygulama: str = None,
    gun: int = 1,
    saat: int = 0,
    adet: int = 1,
    kullanici: discord.Member = None,
    not_bilgisi: str = ""
):
    await interaction.response.defer(ephemeral=False)
    try:
        target_app = (uygulama or config.get("app_id", "popupbypass_ff8a7be0")).strip()
        app_name = await asyncio.to_thread(auth_client.get_app_name, target_app)

        keys = await asyncio.to_thread(
            auth_client.create_license,
            days=gun,
            hours=saat,
            count=adet,
            note=not_bilgisi,
            app_id=target_app
        )
        if not keys:
            await interaction.followup.send("❌ Key oluşturulamadı! Panelden yanıt alınamadı.")
            return

        dur_str = "Süresiz" if gun == 0 and saat == 0 else f"{gun} gün {saat} saat" if saat > 0 else f"{gun} gün"

        embed = discord.Embed(title="✅ Lisans Başarıyla Oluşturuldu!", color=discord.Color.green())
        embed.add_field(name="📌 Uygulama", value=f"**{app_name}** (`{target_app}`)", inline=True)
        embed.add_field(name="⏱ Süre", value=dur_str, inline=True)
        embed.add_field(name="🔢 Adet", value=str(len(keys)), inline=True)
        
        if not_bilgisi:
            embed.add_field(name="📝 Not", value=not_bilgisi, inline=False)

        key_list_str = "\n".join([f"`{k}`" for k in keys])
        embed.add_field(name="🔑 Lisans Anahtarları", value=key_list_str, inline=False)

        # Müşteriye DM Teslimatı
        dm_status = ""
        if kullanici:
            try:
                dm_embed = discord.Embed(
                    title="🎉 Satın Alımınız İçin Teşekkürler!",
                    description="Lisans anahtarınız ve kullanım detayları aşağıdadır:",
                    color=discord.Color.purple()
                )
                dm_embed.add_field(name="🔑 Lisans Anahtarınız", value=f"```{keys[0]}```", inline=False)
                dm_embed.add_field(name="⏱ Geçerlilik Süresi", value=dur_str, inline=True)
                dm_embed.add_field(name="📌 Ürün", value=app_name, inline=True)
                dm_embed.add_field(
                    name="📖 Kurulum & Kullanım",
                    value="1. Programı açın ve lisans anahtarınızı yapıştırın.\n2. HWID otomatik olarak bağlanacaktır.\n3. İyi oyunlar dileriz!",
                    inline=False
                )
                dm_embed.set_footer(text="Destek için sunucumuzdan yetkililere ulaşabilirsiniz.")
                await kullanici.send(embed=dm_embed)
                dm_status = f"\n📩 *Key başarıyla {kullanici.mention} kullanıcısına DM ile iletildi.*"
            except Exception:
                dm_status = f"\n⚠️ *{kullanici.mention} kullanıcısının DM'si kapalı olduğu için mesaj gönderilemedi.*"

        embed.set_footer(text=f"Yetkili: {interaction.user.name} • CheatAuth")
        await interaction.followup.send(content=dm_status if dm_status else None, embed=embed)
        await send_log("🔑 Yeni Key Oluşturuldu", f"Yetkili: {interaction.user.mention}\nUygulama: **{app_name}**\nSüre: {dur_str}\nKeyler:\n{key_list_str}", discord.Color.green())
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

# ==========================================
# 2. KEY BİLGİ & İNTERAKTİF YÖNETİM
# ==========================================

@bot.tree.command(name="key-bilgi", description="Bir lisansın tüm detaylarını gösterir ve butonlarla yönetmenizi sağlar.")
@app_commands.describe(key="Sorgulanacak lisans anahtarı")
async def slash_key_info(interaction: discord.Interaction, key: str):
    await interaction.response.defer(ephemeral=False)
    try:
        lic = await asyncio.to_thread(auth_client.find_license, key.strip())
        if not lic:
            await interaction.followup.send(f"❌ **`{key}`** anahtarı sistemde bulunamadı!")
            return

        hwid_status = "🔒 Bağlı (" + lic["hwid"][:12] + "…)" if lic["hwid"] != "-" else "🔓 Boşta (Bağlanmadı)"
        color = discord.Color.green() if lic["status"] == "Aktif" else discord.Color.gold() if lic["status"] == "Kullanılmadı" else discord.Color.red()

        embed = discord.Embed(title=f"🔎 Lisans Bilgisi: `{lic['key']}`", color=color)
        embed.add_field(name="📌 Uygulama", value=lic.get("app", "Bilinmiyor"), inline=True)
        embed.add_field(name="📊 Durum", value=lic["status"], inline=True)
        embed.add_field(name="⏱ Süre / Bitiş", value=f"{lic['expiry']} ({lic['duration']})", inline=True)
        embed.add_field(name="💻 HWID", value=hwid_status, inline=True)
        embed.add_field(name="🔄 Kullanım Sayısı", value=lic["usage"], inline=True)
        embed.add_field(name="🆔 Sistem ID", value=lic["lid"], inline=True)
        
        if lic.get("note"):
            embed.add_field(name="📝 Not", value=lic["note"], inline=False)

        view = LicenseActionView(lic["key"], lic["lid"])
        await interaction.followup.send(embed=embed, view=view)
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

# ==========================================
# 3. HWID SIFIRLAMA (TEKİL)
# ==========================================

@bot.tree.command(name="hwid-sifirla", description="Belirtilen lisansın HWID kilidini sıfırlar.")
@app_commands.describe(key="HWID'si sıfırlanacak lisans anahtarı")
async def slash_reset_hwid(interaction: discord.Interaction, key: str):
    await interaction.response.defer(ephemeral=False)
    try:
        res = await asyncio.to_thread(auth_client.reset_hwid, key.strip())
        if res.get("success"):
            embed = discord.Embed(title="🔄 HWID Sıfırlandı!", description=res["message"], color=discord.Color.blue())
            await interaction.followup.send(embed=embed)
            await send_log("🔄 HWID Sıfırlandı", f"Yetkili: {interaction.user.mention}\nKey: `{key}`", discord.Color.blue())
        else:
            await interaction.followup.send(f"❌ {res['message']}")
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

# ==========================================
# 4. SÜRE DÜZENLEME (Ekle / Çıkar / Ayarla)
# ==========================================

@bot.tree.command(name="sure-duzenle", description="Bir lisansın süresini artırır, azaltır veya doğrudan ayarlar.")
@app_commands.describe(
    key="Lisans anahtarı",
    islem="Yapılacak işlem",
    gun="Gün sayısı",
    saat="Saat sayısı (Opsiyonel)"
)
@app_commands.choices(islem=[
    app_commands.Choice(name="Süre Ekle (+)", value="add"),
    app_commands.Choice(name="Süre Çıkar (-)", value="sub"),
    app_commands.Choice(name="Direkt Ayarla (=)", value="set")
])
async def slash_edit_duration(interaction: discord.Interaction, key: str, islem: app_commands.Choice[str], gun: int, saat: int = 0):
    await interaction.response.defer(ephemeral=False)
    try:
        res = await asyncio.to_thread(auth_client.edit_duration, key.strip(), action=islem.value, days=gun, hours=saat)
        if res.get("success"):
            action_names = {"add": "eklendi", "sub": "çıkarıldı", "set": "olarak ayarlandı"}
            msg = f"⏱ **`{key}`** lisansına {gun} gün {saat} saat başarıyla {action_names.get(islem.value, 'uygulandı')}!"
            await interaction.followup.send(f"✅ {msg}")
            await send_log("⏱ Süre Düzenlendi", f"Yetkili: {interaction.user.mention}\n{msg}", discord.Color.purple())
        else:
            await interaction.followup.send("❌ Süre düzenlenemedi!")
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

# ==========================================
# 5. TOPLU İŞLEMLER (Telafi, Komple HWID, Temizle)
# ==========================================

@bot.tree.command(name="telafi-ver", description="Seçili uygulamadaki (veya tüm) lisanslara toplu gün süresi ekler.")
@app_commands.describe(
    gun="Eklenecek telafi gün sayısı",
    uygulama="Hedef uygulama (Boş bırakılırsa tüm uygulamalara uygulanır)"
)
@app_commands.autocomplete(uygulama=app_autocomplete_with_all)
async def slash_telafi(interaction: discord.Interaction, gun: int, uygulama: str = None):
    await interaction.response.defer(ephemeral=False)
    try:
        target_app = (uygulama or "ALL").strip()
        app_name = "Tüm Uygulamalar" if target_app == "ALL" else await asyncio.to_thread(auth_client.get_app_name, target_app)

        ok = await asyncio.to_thread(auth_client.add_days_all, days=gun, app_id=target_app)
        if ok:
            embed = discord.Embed(
                title="🎁 Toplu Telafi Süresi Eklendi!",
                description=f"**{app_name}** kapsamındaki tüm aktif lisanslara başarıyla **+{gun} gün** süre eklendi.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
            await send_log("🎁 Toplu Telafi Eklendi", f"Yetkili: {interaction.user.mention}\nUygulama: **{app_name}**\nEklenen Süre: **+{gun} Gün**", discord.Color.green())
        else:
            await interaction.followup.send("❌ Toplu süre eklenemedi!")
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

@bot.tree.command(name="komple-hwid-sifirla", description="Seçili uygulamadaki (veya paneldeki tüm) lisansların HWID kilidini sıfırlar.")
@app_commands.describe(uygulama="Hedef uygulama (Boş bırakılırsa tüm uygulamalara uygulanır)")
@app_commands.autocomplete(uygulama=app_autocomplete_with_all)
async def slash_hwid_all(interaction: discord.Interaction, uygulama: str = None):
    await interaction.response.defer(ephemeral=False)
    try:
        target_app = (uygulama or "ALL").strip()
        app_name = "Tüm Uygulamalar" if target_app == "ALL" else await asyncio.to_thread(auth_client.get_app_name, target_app)

        ok = await asyncio.to_thread(auth_client.reset_hwid_all, app_id=target_app)
        if ok:
            embed = discord.Embed(
                title="🔄 Komple HWID Sıfırlandı!",
                description=f"**{app_name}** bünyesindeki tüm kullanıcıların donanım kilitleri başarıyla sıfırlandı.",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed)
            await send_log("🔄 Komple HWID Sıfırlandı", f"Yetkili: {interaction.user.mention}\nHedef: **{app_name}**", discord.Color.blue())
        else:
            await interaction.followup.send("❌ HWID'ler sıfırlanamadı!")
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

@bot.tree.command(name="temizle-suresibitenler", description="Süresi dolmuş tüm eski lisansları panelden temizler.")
async def slash_clean_expired(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    try:
        ok = await asyncio.to_thread(auth_client.clean_expired)
        if ok:
            await interaction.followup.send("🧹 **Süresi biten tüm lisanslar başarıyla silindi ve panel temizlendi!**")
            await send_log("🧹 Süresi Bitenler Temizlendi", f"Yetkili: {interaction.user.mention}", discord.Color.orange())
        else:
            await interaction.followup.send("❌ Temizleme yapılamadı!")
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

@bot.tree.command(name="temizle-tumkayitlar", description="Seçili uygulamadaki (veya tüm) lisansları kalıcı olarak temizler.")
@app_commands.describe(uygulama="Lisansları silinecek uygulama (Listeden seçin)")
@app_commands.autocomplete(uygulama=app_autocomplete_with_all)
async def slash_clean_all(interaction: discord.Interaction, uygulama: str = None):
    await interaction.response.defer(ephemeral=False)
    try:
        target_app = (uygulama or "ALL").strip()
        app_name = "Tüm Uygulamalar" if target_app == "ALL" else await asyncio.to_thread(auth_client.get_app_name, target_app)

        ok = await asyncio.to_thread(auth_client.clean_all, app_id=target_app)
        if ok:
            embed = discord.Embed(
                title="⚠️ Tüm Kayıtlar Temizlendi!",
                description=f"**{app_name}** kapsamındaki tüm lisans kayıtları başarıyla silindi.",
                color=discord.Color.dark_red()
            )
            await interaction.followup.send(embed=embed)
            await send_log("⚠️ Tüm Kayıtlar Temizlendi", f"Yetkili: {interaction.user.mention}\nHedef: **{app_name}**", discord.Color.dark_red())
        else:
            await interaction.followup.send("❌ Kayıtlar temizlenemedi!")
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

# ==========================================
# 6. PANEL İSTATİSTİKLERİ
# ==========================================

@bot.tree.command(name="istatistik", description="Paneldeki lisansların genel durumunu ve istatistiklerini gösterir.")
@app_commands.describe(uygulama="İstatistikleri filtrelenecek uygulama (Opsiyonel)")
@app_commands.autocomplete(uygulama=app_autocomplete_with_all)
async def slash_stats(interaction: discord.Interaction, uygulama: str = None):
    await interaction.response.defer(ephemeral=False)
    try:
        filter_name = None
        target_title = "CheatAuth Genel Panel İstatistikleri"
        if uygulama and uygulama != "ALL":
            filter_name = await asyncio.to_thread(auth_client.get_app_name, uygulama.strip())
            target_title = f"📊 {filter_name} İstatistikleri"

        stats = await asyncio.to_thread(auth_client.get_stats, app_name_filter=filter_name)
        embed = discord.Embed(title=target_title, color=discord.Color.teal())
        embed.add_field(name="📁 Toplam Lisans", value=str(stats["total"]), inline=True)
        embed.add_field(name="🟢 Aktif Kullanımda", value=str(stats["active"]), inline=True)
        embed.add_field(name="⚪ Henüz Kullanılmadı", value=str(stats["unused"]), inline=True)
        embed.add_field(name="🔒 HWID Bağlı", value=str(stats["bound"]), inline=True)
        embed.set_footer(text="CheatAuth Cloud Management")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

# ==========================================
# 7. KARA LİSTE (BLACKLIST) YÖNETİMİ
# ==========================================

@bot.tree.command(name="kara-liste-ekle", description="Bir IP adresini veya HWID'yi panelin kara listesine ekler.")
@app_commands.describe(
    tur="Yasaklama türü (IP veya HWID)",
    deger="IP adresi veya 64 haneli HWID değeri",
    sebep="Yasaklama sebebi (Opsiyonel)"
)
@app_commands.choices(tur=[
    app_commands.Choice(name="IP Adresi", value="ip"),
    app_commands.Choice(name="HWID (Donanım)", value="hwid")
])
async def slash_add_blacklist(interaction: discord.Interaction, tur: app_commands.Choice[str], deger: str, sebep: str = ""):
    await interaction.response.defer(ephemeral=False)
    try:
        ok = await asyncio.to_thread(auth_client.add_blacklist, kind=tur.value, value=deger.strip(), reason=sebep.strip())
        if ok:
            embed = discord.Embed(
                title="⛔ Kara Listeye Eklendi!",
                color=discord.Color.red()
            )
            embed.add_field(name="🏷️ Tür", value=tur.name, inline=True)
            embed.add_field(name="🎯 Yasaklanan Değer", value=f"`{deger.strip()}`", inline=False)
            if sebep:
                embed.add_field(name="📝 Sebep", value=sebep.strip(), inline=False)
            embed.set_footer(text=f"Yetkili: {interaction.user.name} • CheatAuth")
            await interaction.followup.send(embed=embed)
            await send_log("⛔ Kara Listeye Eklendi", f"Yetkili: {interaction.user.mention}\nTür: {tur.name}\nDeğer: `{deger.strip()}`\nSebep: {sebep}", discord.Color.red())
        else:
            await interaction.followup.send("❌ Kara listeye eklenemedi!")
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

@bot.tree.command(name="kara-liste-key", description="Bir lisans anahtarına bağlı olan HWID'yi otomatik bulup kara listeye ekler.")
@app_commands.describe(key="Kara listeye alınacak lisans anahtarı", sebep="Yasak sebebi (Opsiyonel)")
async def slash_bl_key(interaction: discord.Interaction, key: str, sebep: str = ""):
    await interaction.response.defer(ephemeral=False)
    try:
        lic = await asyncio.to_thread(auth_client.find_license, key.strip())
        if not lic:
            await interaction.followup.send(f"❌ **`{key}`** anahtarı bulunamadı!")
            return
        if lic["hwid"] == "-":
            await interaction.followup.send(f"⚠️ Bu lisansa henüz bağlı bir HWID yok, doğrudan banlamak için `/key-bilgi` panelini kullanabilirsiniz.")
            return

        hwid_val = lic["hwid"].replace("…", "").strip()
        ok = await asyncio.to_thread(auth_client.add_blacklist, kind="hwid", value=hwid_val, reason=sebep or f"Key: {lic['key']}")
        await asyncio.to_thread(auth_client.ban_license, lic["key"])

        embed = discord.Embed(
            title="⛔ Cihaz Kara Listeye Alındı & Lisans Banlandı!",
            description=f"**`{lic['key']}`** anahtarının donanım kimliği kara listeye eklendi ve lisans banlandı.",
            color=discord.Color.dark_red()
        )
        embed.add_field(name="🔑 Lisans", value=f"`{lic['key']}`", inline=True)
        embed.add_field(name="💻 HWID", value=f"`{hwid_val}`", inline=False)
        if sebep:
            embed.add_field(name="📝 Sebep", value=sebep, inline=False)
        await interaction.followup.send(embed=embed)
        await send_log("⛔ Cihaz Kara Listeye Alındı", f"Yetkili: {interaction.user.mention}\nKey: `{lic['key']}`\nHWID: `{hwid_val}`", discord.Color.dark_red())
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

@bot.tree.command(name="kara-liste", description="Paneldeki kara liste kayıtlarını listeler.")
async def slash_show_bl(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    try:
        bl = await asyncio.to_thread(auth_client.get_blacklist)
        embed = discord.Embed(title="⛔ CheatAuth Kara Liste Kayıtları", color=discord.Color.red())
        ips = bl.get("ips", [])
        hwids = bl.get("hwids", [])
        
        ip_text = "\n".join([f"• `{i['value']}` ({i['reason'] or 'Sebepsiz'})" for i in ips[:10]]) if ips else "*Kayıtlı yasaklı IP yok*"
        hwid_text = "\n".join([f"• `{h['value'][:16]}…` ({h['reason'] or 'Sebepsiz'})" for h in hwids[:10]]) if hwids else "*Kayıtlı yasaklı HWID yok*"

        embed.add_field(name="🌐 Yasaklı IP'ler", value=ip_text, inline=False)
        embed.add_field(name="💻 Yasaklı HWID'ler", value=hwid_text, inline=False)
        embed.set_footer(text="CheatAuth • Blacklist")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

# ==========================================
# 8. UYGULAMA (APPLICATION) YÖNETİMİ
# ==========================================

@bot.tree.command(name="uygulamalar", description="Paneldeki tüm uygulamaları listeler.")
async def slash_list_apps(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    try:
        apps = await asyncio.to_thread(auth_client.list_apps, force=True)
        if not apps:
            await interaction.followup.send("ℹ️ Panelde kayıtlı uygulama bulunamadı.")
            return

        embed = discord.Embed(title=f"📱 Uygulama Listesi (Toplam: {len(apps)})", color=discord.Color.blurple())
        for a in apps:
            hb_min = a["heartbeat_sec"] // 60
            hb_str = "Kapalı" if a["heartbeat_sec"] == 0 else f"{hb_min} dk" if a["heartbeat_sec"] >= 60 else f"{a['heartbeat_sec']} sn"
            embed.add_field(
                name=f"📦 {a['name']} ({a['status']})",
                value=f"**App ID:** `{a['app_id']}`\n**Lisanslar:** {a['license_count']}\n**Heartbeat:** {hb_str}",
                inline=True
            )
        embed.set_footer(text="CheatAuth Application Management")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

@bot.tree.command(name="uygulama-olustur", description="CheatAuth panelinde yeni bir uygulama oluşturur.")
@app_commands.describe(isim="Oluşturulacak uygulamanın adı (Örn: MyLoader, ValorantCheat)")
async def slash_create_app(interaction: discord.Interaction, isim: str):
    await interaction.response.defer(ephemeral=False)
    try:
        ok = await asyncio.to_thread(auth_client.create_app, name=isim.strip())
        if ok:
            embed = discord.Embed(
                title="✅ Yeni Uygulama Oluşturuldu!",
                description=f"**`{isim.strip()}`** uygulaması panelde başarıyla oluşturuldu.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
            await send_log("📱 Yeni Uygulama Oluşturuldu", f"Yetkili: {interaction.user.mention}\nUygulama: `{isim.strip()}`", discord.Color.green())
        else:
            await interaction.followup.send("❌ Uygulama oluşturulamadı!")
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

@bot.tree.command(name="uygulama-heartbeat", description="Bir uygulamanın heartbeat kontrol aralığını ayarlar.")
@app_commands.describe(
    uygulama="Ayar yapılacak uygulama (Listeden seçin)",
    aralik="Heartbeat kontrol süresi"
)
@app_commands.autocomplete(uygulama=app_autocomplete)
@app_commands.choices(aralik=[
    app_commands.Choice(name="Kapalı (0 sn)", value=0),
    app_commands.Choice(name="30 Saniye", value=30),
    app_commands.Choice(name="1 Dakika", value=60),
    app_commands.Choice(name="2 Dakika", value=120),
    app_commands.Choice(name="5 Dakika (Önerilen)", value=300),
    app_commands.Choice(name="10 Dakika", value=600)
])
async def slash_set_hb(interaction: discord.Interaction, aralik: app_commands.Choice[int], uygulama: str = None):
    await interaction.response.defer(ephemeral=False)
    try:
        target_app = (uygulama or config.get("app_id", "popupbypass_ff8a7be0")).strip()
        app_name = await asyncio.to_thread(auth_client.get_app_name, target_app)

        ok = await asyncio.to_thread(auth_client.set_heartbeat, interval_sec=aralik.value, app_id=target_app)
        if ok:
            embed = discord.Embed(
                title="⏱ Heartbeat Ayarı Güncellendi!",
                description=f"Uygulama: **{app_name}** (`{target_app}`)\nYeni Aralık: **{aralik.name}**",
                color=discord.Color.teal()
            )
            await interaction.followup.send(embed=embed)
            await send_log("⏱ Heartbeat Güncellendi", f"Yetkili: {interaction.user.mention}\nUygulama: **{app_name}**\nAralık: **{aralik.name}**", discord.Color.teal())
        else:
            await interaction.followup.send("❌ Heartbeat güncellenemedi!")
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

@bot.tree.command(name="uygulama-kapat-ac", description="Bir uygulamayı kapatır veya tekrar açar (Girişleri dondurur).")
@app_commands.describe(uygulama="Açılacak / kapatılacak uygulama (Listeden seçin)")
@app_commands.autocomplete(uygulama=app_autocomplete)
async def slash_toggle_app(interaction: discord.Interaction, uygulama: str = None):
    await interaction.response.defer(ephemeral=False)
    try:
        target_app = (uygulama or config.get("app_id", "popupbypass_ff8a7be0")).strip()
        app_name = await asyncio.to_thread(auth_client.get_app_name, target_app)

        ok = await asyncio.to_thread(auth_client.toggle_app, app_id=target_app)
        if ok:
            embed = discord.Embed(
                title="🔄 Uygulama Durumu Değiştirildi!",
                description=f"Uygulama: **{app_name}** (`{target_app}`)\nDurum: **Aktif / Pasif olarak güncellendi.**",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=embed)
            await send_log("🔄 Uygulama Durumu Değiştirildi", f"Yetkili: {interaction.user.mention}\nUygulama: **{app_name}**", discord.Color.orange())
        else:
            await interaction.followup.send("❌ İşlem başarısız!")
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

@bot.tree.command(name="uygulama-sil", description="Bir uygulamayı ve ona bağlı tüm lisansları panelden kalıcı olarak siler.")
@app_commands.describe(uygulama="Silinecek uygulama (Listeden seçin)")
@app_commands.autocomplete(uygulama=app_autocomplete)
async def slash_delete_app(interaction: discord.Interaction, uygulama: str):
    await interaction.response.defer(ephemeral=False)
    try:
        target_app = uygulama.strip()
        app_name = await asyncio.to_thread(auth_client.get_app_name, target_app)

        ok = await asyncio.to_thread(auth_client.delete_app, app_id=target_app)
        if ok:
            embed = discord.Embed(
                title="🗑️ Uygulama Başarıyla Silindi!",
                description=f"**`{app_name}`** (`{target_app}`) uygulaması ve bağlı tüm lisanslar silindi.",
                color=discord.Color.dark_red()
            )
            await interaction.followup.send(embed=embed)
            await send_log("🗑️ Uygulama Silindi", f"Yetkili: {interaction.user.mention}\nUygulama: `{app_name}` (`{target_app}`)", discord.Color.dark_red())
        else:
            await interaction.followup.send("❌ Uygulama silinemedi!")
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

# ==========================================
# 9. LİSANSLARI LİSTELEME
# ==========================================

@bot.tree.command(name="lisanslar", description="Paneldeki lisansları listeler (Uygulama filtresi destekli).")
@app_commands.describe(uygulama="Listelenecek uygulama filtresi (Opsiyonel)")
@app_commands.autocomplete(uygulama=app_autocomplete_with_all)
async def slash_list_licenses(interaction: discord.Interaction, uygulama: str = None):
    await interaction.response.defer(ephemeral=False)
    try:
        licenses = await asyncio.to_thread(auth_client.list_licenses)
        if not licenses:
            await interaction.followup.send("ℹ️ Panelde kayıtlı lisans bulunmuyor.")
            return

        filter_name = None
        if uygulama and uygulama != "ALL":
            filter_name = await asyncio.to_thread(auth_client.get_app_name, uygulama.strip())
            licenses = [l for l in licenses if l["app"].lower() == filter_name.lower()]

        if not licenses:
            await interaction.followup.send(f"ℹ️ **{filter_name or uygulama}** için kayıtlı lisans bulunamadı.")
            return

        title_str = f"📋 Lisans Listesi ({filter_name}) - Toplam: {len(licenses)}" if filter_name else f"📋 Tüm Lisanslar (Toplam: {len(licenses)})"
        embed = discord.Embed(title=title_str, color=discord.Color.gold())
        for lic in licenses[:15]:
            hwid_display = "🔒 Bağlı" if lic["hwid"] != "-" else "🔓 Boşta"
            embed.add_field(
                name=f"🔑 `{lic['key']}`",
                value=f"**Uygulama:** {lic['app']}\n**Durum:** {lic['status']}\n**HWID:** {hwid_display}\n**Süre:** {lic['expiry']}",
                inline=True
            )
        embed.set_footer(text="CheatAuth License Bot")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

# ==========================================
# 10. BAYİ (RESELLER) YÖNETİMİ
# ==========================================

@bot.tree.command(name="bayiler", description="Kredi bakiyenizi, toplam bayilerinizi ve bayi listesini gösterir.")
async def slash_dealers_info(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    try:
        info = await asyncio.to_thread(auth_client.get_dealers_info)
        credits = info.get("credits", 0)
        total = info.get("total_dealers", 0)
        dealers = info.get("dealers", [])

        embed = discord.Embed(title="🤝 CheatAuth Bayi Yönetim Paneli", color=discord.Color.gold())
        embed.add_field(name="💳 Kredi Bakiyeniz", value=f"**{credits}** Kredi\n*(Bayi davetlerinde kullanılır)*", inline=True)
        embed.add_field(name="👥 Toplam Bayiniz", value=f"**{total}** Alt Bayi\n*(Doğrudan alt bayi)*", inline=True)

        if dealers:
            dealer_lines = []
            for d in dealers[:15]:
                dealer_lines.append(f"• **{d['email']}** ➔ Kredi: `{d['credits']}` | Yetki: `{d['apps']}` | Durum: `{d['status']}`")
            embed.add_field(name="📋 Kayıtlı Bayiler", value="\n".join(dealer_lines), inline=False)
        else:
            embed.add_field(name="📋 Bayi Listesi", value="ℹ️ *Henüz kayıtlı bayi bulunmuyor. Yeni bayi eklemek için `/bayi-davet` komutunu kullanabilirsiniz.*", inline=False)

        embed.set_footer(text="CheatAuth Reseller Management System")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

@bot.tree.command(name="bayi-davet", description="Yeni bir bayiye e-posta ve kredi transferi ile davet gönderir.")
@app_commands.describe(
    eposta="Davet edilecek bayinin e-posta adresi (bayi@email.com)",
    kredi="Transfer edilecek kredi miktarı (Varsayılan: 10)",
    uygulama="Erişim verilecek uygulama (Boş bırakılırsa tüm uygulamalar yetkilendirilir)"
)
@app_commands.autocomplete(uygulama=app_autocomplete_with_all)
async def slash_invite_dealer(interaction: discord.Interaction, eposta: str, kredi: int = 10, uygulama: str = None):
    await interaction.response.defer(ephemeral=False)
    try:
        target_app = (uygulama or "ALL").strip()
        app_ids = None
        app_display = "Tüm Uygulamalar"
        if target_app != "ALL":
            app_ids = [target_app]
            app_display = await asyncio.to_thread(auth_client.get_app_name, target_app)

        msg = await asyncio.to_thread(auth_client.invite_dealer, email=eposta.strip(), credits=kredi, app_ids=app_ids)

        embed = discord.Embed(
            title="🎉 Bayi Daveti Başarıyla Gönderildi!",
            description=f"**{eposta.strip()}** adresine bayi davetiyesi başarıyla iletildi.",
            color=discord.Color.green()
        )
        embed.add_field(name="📧 Bayi E-postası", value=f"`{eposta.strip()}`", inline=True)
        embed.add_field(name="💳 Transfer Kredisi", value=f"**{kredi}** Kredi", inline=True)
        embed.add_field(name="📱 Yetkilendirilen Uygulamalar", value=f"**{app_display}**", inline=False)
        embed.set_footer(text="Bayinin panele giriş yaparak daveti onaylaması gerekmektedir.")

        await interaction.followup.send(embed=embed)
        await send_log("🤝 Yeni Bayi Davet Edildi", f"Yetkili: {interaction.user.mention}\nE-posta: `{eposta.strip()}`\nTransfer: **{kredi} Kredi**\nUygulama: **{app_display}**", discord.Color.gold())
    except Exception as e:
        await interaction.followup.send(f"❌ **Hata:** {e}")

# ==========================================
# 11. AYARLAR (Log Kanalı & Cookie)
# ==========================================

@bot.tree.command(name="log-kanali-ayarla", description="Bot işlemlerinin loglanacağı kanalı belirler.")
@app_commands.describe(kanal="Logların gönderileceği kanal")
async def slash_set_log(interaction: discord.Interaction, kanal: discord.TextChannel):
    global config
    config["log_channel_id"] = str(kanal.id)
    save_config(config)
    await interaction.response.send_message(f"✅ Log kanalı {kanal.mention} olarak ayarlandı!", ephemeral=True)

@bot.tree.command(name="cookie-guncelle", description="CheatAuth oturum çerezini günceller.")
@app_commands.describe(yeni_cookie="Chrome'dan alınan yeni cgauth_user değeri")
async def slash_update_cookie(interaction: discord.Interaction, yeni_cookie: str):
    global auth_client, config
    new_c = yeni_cookie.strip()
    config["cheatauth_cookie"] = new_c
    save_config(config)
    auth_client = CheatAuthClient(new_c, config.get("app_id", "popupbypass_ff8a7be0"))
    await interaction.response.send_message("✅ Oturum çerezi güncellendi!", ephemeral=True)

# ==========================================
# YARDIM MENÜSÜ
# ==========================================

@bot.tree.command(name="yardim", description="Tüm bot komutlarını ve özelliklerini gösterir.")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(title="🛡️ CheatAuth Profesyonel Lisans Botu", color=discord.Color.blue())
    embed.add_field(
        name="🔑 Lisans İşlemleri",
        value=(
            "`/key-olustur [uygulama] [gun] [adet] [kullanici]` ➔ İstediğiniz uygulama için key üretir & isteğe bağlı müşteriye DM atar\n"
            "`/key-bilgi [key]` ➔ Key detayları ve butonlu interaktif yönetim paneli açar\n"
            "`/hwid-sifirla [key]` ➔ Tek lisansın HWID kilidini kaldırır\n"
            "`/sure-duzenle [key] [islem] [gun]` ➔ Lisansa süre ekler, çıkarır veya ayarlar\n"
            "`/lisanslar [uygulama]` ➔ Mevcut lisansları uygulamaya göre filtreleyip listeler"
        ),
        inline=False
    )
    embed.add_field(
        name="📱 Uygulama Yönetimi",
        value=(
            "`/uygulamalar` ➔ Paneldeki tüm uygulamaları listeler\n"
            "`/uygulama-olustur [isim]` ➔ Panelde yeni uygulama oluşturur\n"
            "`/uygulama-heartbeat [uygulama] [aralik]` ➔ Heartbeat süresini ayarlar (30sn, 1dk, 5dk vb.)\n"
            "`/uygulama-kapat-ac [uygulama]` ➔ Seçili uygulamaya girişleri dondurur / açar\n"
            "`/uygulama-sil [uygulama]` ➔ Uygulamayı panelden kalıcı siler"
        ),
        inline=False
    )
    embed.add_field(
        name="⚡ Toplu Yönetim & Güvenlik",
        value=(
            "`/kara-liste-ekle [tur] [deger] [sebep]` ➔ IP veya HWID'yi kara listeye ekler\n"
            "`/kara-liste-key [key]` ➔ Key'in HWID'sini bulup anında kara listeye kilitler\n"
            "`/kara-liste` ➔ Kara listedeki tüm kayıtları listeler\n"
            "`/telafi-ver [gun] [uygulama]` ➔ Seçili uygulamadaki (veya tüm) lisanslara telafi süresi ekler\n"
            "`/komple-hwid-sifirla [uygulama]` ➔ Seçili uygulamadaki (veya tüm) HWID'leri sıfırlar\n"
            "`/temizle-suresibitenler` ➔ Süresi biten eski lisansları topluca siler\n"
            "`/temizle-tumkayitlar [uygulama]` ➔ Seçili uygulamadaki tüm lisans kayıtlarını siler\n"
            "`/istatistik [uygulama]` ➔ Panel veya uygulama bazlı istatistikleri gösterir"
        ),
        inline=False
    )
    embed.add_field(
        name="🤝 Bayi (Reseller) Yönetimi",
        value=(
            "`/bayiler` ➔ Kredi bakiyenizi, toplam bayilerinizi ve bayi listesini gösterir\n"
            "`/bayi-davet [eposta] [kredi] [uygulama]` ➔ Yeni bayiye e-posta ve krediyle davetiye gönderir"
        ),
        inline=False
    )
    embed.add_field(
        name="⚙️ Ayarlar",
        value=(
            "`/log-kanali-ayarla [kanal]` ➔ Yetkili işlemlerinin loglanacağı kanalı seçer\n"
            "`/cookie-guncelle [cookie]` ➔ Oturum çerezini günceller"
        ),
        inline=False
    )
    embed.set_footer(text="CheatAuth Bot • Dynamic Cloud Management")
    await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    token = config.get("bot_token")
    if not token or token == "BURAYA_BOT_TOKEN":
        print("[-] HATA: config.json içinde bot_token tanımlı değil!")
    else:
        print("[*] CheatAuth Discord Botu başlatılıyor...")
        bot.run(token)
