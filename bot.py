import os, re, logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ChatMemberHandler, filters
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("HERO")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DEVELOPER_ID = int(os.getenv("DEVELOPER_ID", "1806855789"))
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
BOT_NAME = "HERO"

ROLE_LEVEL = {"member":0,"vip":1,"admin":2,"manager":3,"creator":4,"owner":5,"developer":6}
ROLE_AR = {"member":"عضو","vip":"مميز","admin":"أدمن","manager":"مدير","creator":"منشئ","owner":"مالك","developer":"مطوّر HERO"}

def sb_headers():
    return {"apikey": SUPABASE_SERVICE_ROLE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type":"application/json", "Prefer":"resolution=merge-duplicates,return=minimal"}

def sb_request(method, table, params=None, payload=None):
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        log.warning("Supabase environment variables are not configured")
        return None
    try:
        r = requests.request(method, f"{SUPABASE_URL}/rest/v1/{table}",
            headers=sb_headers(), params=params, json=payload, timeout=15)
        if r.status_code >= 400:
            log.error("Supabase %s %s: %s", table, r.status_code, r.text[:500])
            return None
        if r.text.strip():
            return r.json()
        return []
    except Exception:
        log.exception("Supabase request failed")
        return None

def save_group(chat, owner=None, active=None):
    row = {"chat_id": chat.id, "title": chat.title or ""}
    if owner:
        row.update({"owner_id": owner.id, "owner_name": owner.full_name})
    if active is not None:
        row["is_active"] = active
    sb_request("POST", "groups", {"on_conflict":"chat_id"}, row)
    sb_request("POST", "group_settings", {"on_conflict":"chat_id"}, {"chat_id":chat.id})

def save_role(chat_id, user_id, role):
    sb_request("POST", "group_roles", {"on_conflict":"chat_id,user_id"},
               {"chat_id":chat_id,"user_id":user_id,"role":role})

def get_role(chat_id, user_id):
    if user_id == DEVELOPER_ID:
        return "developer"
    rows = sb_request("GET", "group_roles",
        {"chat_id":f"eq.{chat_id}","user_id":f"eq.{user_id}","select":"role","limit":"1"})
    if rows:
        return rows[0].get("role","member")
    rows = sb_request("GET", "groups",
        {"chat_id":f"eq.{chat_id}","owner_id":f"eq.{user_id}","select":"chat_id","limit":"1"})
    return "owner" if rows else "member"

def get_anti_link(chat_id):
    rows = sb_request("GET", "group_settings",
        {"chat_id":f"eq.{chat_id}","select":"anti_link","limit":"1"})
    return bool(rows and rows[0].get("anti_link"))

def set_anti_link(chat_id, enabled):
    sb_request("POST", "group_settings", {"on_conflict":"chat_id"},
               {"chat_id":chat_id,"anti_link":enabled})

def log_action(chat_id, actor_id, action, target_id=None, details=None):
    sb_request("POST","audit_logs",None,{"chat_id":chat_id,"actor_id":actor_id,
        "action":action,"target_id":target_id,"details":details or {}})

def add_warning(chat_id, user_id, moderator_id, reason=""):
    sb_request("POST","user_warnings",None,{"chat_id":chat_id,"user_id":user_id,
        "moderator_id":moderator_id,"reason":reason})

def warning_count(chat_id, user_id):
    rows = sb_request("GET","user_warnings",
        {"chat_id":f"eq.{chat_id}","user_id":f"eq.{user_id}","select":"id"})
    return len(rows or [])

def can_manage(chat_id, actor_id, target_id, new_role):
    actor, target = get_role(chat_id, actor_id), get_role(chat_id, target_id)
    if actor == "developer":
        return True
    ceiling = {"owner":4,"creator":3,"manager":2,"admin":1}.get(actor,-1)
    return ROLE_LEVEL.get(new_role,99) <= ceiling and ROLE_LEVEL.get(target,0) < ROLE_LEVEL[actor] and actor_id != target_id

def keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛡️ الحماية",callback_data="protection"),InlineKeyboardButton("👑 الرتب",callback_data="ranks")],
        [InlineKeyboardButton("🎮 الألعاب",callback_data="games"),InlineKeyboardButton("⚙️ الإعدادات",callback_data="settings")],
        [InlineKeyboardButton("📋 الأوامر",callback_data="commands"),InlineKeyboardButton("ℹ️ عن HERO",callback_data="about")]
    ])

WELCOME = "💜 <b>أهلاً بك في HERO</b>\nرفيق مجموعتك للحماية والتنظيم والترفيه.\n\nاختر القسم من الأزرار:"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(WELCOME,parse_mode=ParseMode.HTML,reply_markup=keyboard())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "📋 <b>أوامر HERO</b>\n/start — القائمة\n/activate — تفعيل المالك الحقيقي\n/id — المعرفات\n/rank — رتبتك\n"
        "/promote بالرد على عضو ثم اسم الرتبة\n/demote بالرد على عضو\n/warn و /unwarn\n/antilink_on و /antilink_off",
        parse_mode=ParseMode.HTML,reply_markup=keyboard())

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        f"معرّفك: <code>{update.effective_user.id}</code>\nمعرّف المجموعة: <code>{update.effective_chat.id}</code>",
        parse_mode=ParseMode.HTML)

async def rank_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = get_role(update.effective_chat.id,update.effective_user.id)
    await update.effective_message.reply_text(f"رتبتك: <b>{ROLE_AR.get(role,'عضو')}</b>",parse_mode=ParseMode.HTML)

async def activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat,user=update.effective_chat,update.effective_user
    if chat.type=="private":
        await update.effective_message.reply_text("أضف HERO إلى مجموعتك ثم أرسل /activate هناك.")
        return
    try: member=await context.bot.get_chat_member(chat.id,user.id)
    except Exception:
        await update.effective_message.reply_text("تعذر التحقق. اجعل HERO مشرفاً بالمجموعة ثم حاول.")
        return
    if member.status!="creator":
        await update.effective_message.reply_text("❌ التفعيل متاح لمالك المجموعة الحقيقي فقط.")
        return
    save_group(chat,user,True); save_role(chat.id,user.id,"owner")
    log_action(chat.id,user.id,"activate")
    await update.effective_message.reply_text("👑 <b>تم تفعيل HERO وربط المجموعة بقاعدة البيانات!</b>",
        parse_mode=ParseMode.HTML,reply_markup=keyboard())

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    pages={
      "protection":"🛡️ <b>الحماية</b>\n/antilink_on لتفعيل منع الروابط\n/antilink_off لإيقافه\nامنح HERO صلاحية حذف الرسائل.",
      "ranks":"👑 <b>الرتب</b>\nمالك ← منشئ ← مدير ← أدمن ← مميز ← عضو\nترقية: رد على العضو بـ /promote admin أو vip أو manager أو creator",
      "games":"🎮 <b>الألعاب</b>\nقسم الألعاب قيد التطوير.",
      "settings":"⚙️ <b>الإعدادات</b>\n/antilink_on\n/antilink_off",
      "commands":"📋 <b>الأوامر</b>\n/start /help /activate /id /rank\n/promote /demote /warn /unwarn\n/antilink_on /antilink_off",
      "about":"💜 <b>HERO</b>\nبوت تيليجرام لحماية المجموعات وإدارتها والترفيه عنها."
    }
    await q.edit_message_text(pages.get(q.data,WELCOME),parse_mode=ParseMode.HTML,reply_markup=keyboard())

async def set_antilink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat,user=update.effective_chat,update.effective_user
    if chat.type=="private": return
    if ROLE_LEVEL.get(get_role(chat.id,user.id),0)<ROLE_LEVEL["admin"]:
        await update.effective_message.reply_text("هذا الأمر للمشرفين الإداريين.")
        return
    enabled=update.effective_message.text.endswith("_on")
    set_anti_link(chat.id,enabled); log_action(chat.id,user.id,"anti_link",details={"enabled":enabled})
    await update.effective_message.reply_text("🛡️ منع الروابط مفعّل." if enabled else "تم إيقاف منع الروابط.")

async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg,chat,actor=update.effective_message,update.effective_chat,update.effective_user
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        await msg.reply_text("استخدم /promote بالرد على رسالة العضو، مثال /promote admin"); return
    arg=msg.text.split(maxsplit=1)[1].strip().lower() if len(msg.text.split(maxsplit=1))>1 else ""
    roles={"مميز":"vip","vip":"vip","ادمن":"admin","أدمن":"admin","admin":"admin",
           "مدير":"manager","manager":"manager","منشئ":"creator","creator":"creator"}
    role=roles.get(arg); target=msg.reply_to_message.from_user
    if not role:
        await msg.reply_text("الرتب: vip أو admin أو manager أو creator"); return
    if not can_manage(chat.id,actor.id,target.id,role):
        await msg.reply_text("❌ ما عندك صلاحية كافية."); return
    save_role(chat.id,target.id,role); log_action(chat.id,actor.id,"promote",target.id,{"role":role})
    await msg.reply_text(f"👑 تمت ترقية {target.mention_html()} إلى {ROLE_AR[role]}.",parse_mode=ParseMode.HTML)

async def demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg,chat,actor=update.effective_message,update.effective_chat,update.effective_user
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        await msg.reply_text("استخدم /demote بالرد على العضو."); return
    target=msg.reply_to_message.from_user
    if ROLE_LEVEL.get(get_role(chat.id,actor.id),0)<ROLE_LEVEL["manager"] or ROLE_LEVEL.get(get_role(chat.id,target.id),0)>=ROLE_LEVEL.get(get_role(chat.id,actor.id),0):
        await msg.reply_text("❌ ما عندك صلاحية."); return
    sb_request("DELETE","group_roles",{"chat_id":f"eq.{chat.id}","user_id":f"eq.{target.id}"})
    log_action(chat.id,actor.id,"demote",target.id)
    await msg.reply_text(f"تمت إعادة {target.mention_html()} إلى عضو.",parse_mode=ParseMode.HTML)

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg,chat,actor=update.effective_message,update.effective_chat,update.effective_user
    if ROLE_LEVEL.get(get_role(chat.id,actor.id),0)<ROLE_LEVEL["admin"]:
        await msg.reply_text("هذا الأمر للمشرفين."); return
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        await msg.reply_text("استخدم /warn بالرد على العضو."); return
    target=msg.reply_to_message.from_user
    add_warning(chat.id,target.id,actor.id)
    await msg.reply_text(f"⚠️ إنذار لـ {target.mention_html()}\nعدد الإنذارات: {warning_count(chat.id,target.id)}",parse_mode=ParseMode.HTML)

async def unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg,chat,actor=update.effective_message,update.effective_chat,update.effective_user
    if ROLE_LEVEL.get(get_role(chat.id,actor.id),0)<ROLE_LEVEL["admin"]:
        await msg.reply_text("هذا الأمر للمشرفين."); return
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        await msg.reply_text("استخدم /unwarn بالرد على العضو."); return
    target=msg.reply_to_message.from_user
    rows=sb_request("GET","user_warnings",{"chat_id":f"eq.{chat.id}","user_id":f"eq.{target.id}","select":"id","order":"created_at.desc","limit":"1"})
    if rows:
        sb_request("DELETE","user_warnings",{"id":f"eq.{rows[0]['id']}"})
    await msg.reply_text(f"تم تحديث الإنذارات. المتبقي: {warning_count(chat.id,target.id)}")

URL_RE=re.compile(r"(https?://|www\.|t\.me/)",re.I)
async def moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg=update.effective_message; chat=update.effective_chat
    if not msg or chat.type=="private" or not msg.text: return
    if get_anti_link(chat.id) and URL_RE.search(msg.text):
        try:
            member=await context.bot.get_chat_member(chat.id,msg.from_user.id)
            if member.status in ("administrator","creator"): return
            await msg.delete()
            await context.bot.send_message(chat.id,"🛡️ تم حذف رابط حسب إعدادات الحماية.")
            log_action(chat.id,msg.from_user.id,"delete_link")
        except Exception: log.exception("Link moderation failed; check bot permissions")

async def owner_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cm=update.chat_member
    if not cm: return
    chat=cm.chat
    try:
        admins=await context.bot.get_chat_administrators(chat.id)
        owner=next((a.user for a in admins if a.status=="creator"),None)
        if owner:
            old=sb_request("GET","groups",{"chat_id":f"eq.{chat.id}","select":"owner_id","limit":"1"})
            old_id=old[0].get("owner_id") if old else None
            if old_id and int(old_id)!=owner.id:
                sb_request("DELETE","group_roles",{"chat_id":f"eq.{chat.id}","user_id":f"eq.{old_id}"})
            save_group(chat,owner,None); save_role(chat.id,owner.id,"owner")
    except Exception: log.exception("Could not refresh group owner")


from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from telegram import Update

application = Application.builder().token(BOT_TOKEN).build()

for cmd, fn in [("start",start),("help",help_cmd),("activate",activate),("id",id_cmd),("rank",rank_cmd),
                ("promote",promote),("demote",demote),("warn",warn),("unwarn",unwarn),
                ("antilink_on",set_antilink),("antilink_off",set_antilink)]:
    application.add_handler(CommandHandler(cmd,fn))
application.add_handler(CallbackQueryHandler(callback))
application.add_handler(ChatMemberHandler(owner_change,ChatMemberHandler.CHAT_MEMBER))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,moderation))

@asynccontextmanager
async def lifespan(api: FastAPI):
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing")
    await application.initialize()
    await application.start()
    external_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not external_url:
        raise RuntimeError("RENDER_EXTERNAL_URL is missing; deploy this as a Render Web Service")
    secret = os.getenv("WEBHOOK_SECRET", "").strip()
    webhook_url = external_url + "/telegram"
    await application.bot.set_webhook(
        url=webhook_url,
        secret_token=secret if secret else None,
        allowed_updates=Update.ALL_TYPES
    )
    log.info("HERO webhook configured: %s", webhook_url)
    yield
    await application.bot.delete_webhook()
    await application.stop()
    await application.shutdown()

api = FastAPI(title="HERO Telegram Bot", lifespan=lifespan)

@api.get("/")
async def health():
    return {"ok": True, "service": "HERO Telegram Bot", "mode": "webhook"}

@api.post("/telegram")
async def telegram_webhook(request: Request):
    secret = os.getenv("WEBHOOK_SECRET", "").strip()
    if secret and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}
