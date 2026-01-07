import re
import requests
import threading
import time
from datetime import datetime, timedelta
import pytz
import jdatetime
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater, CallbackContext,
    CallbackQueryHandler, MessageHandler,
    Filters, ConversationHandler, CommandHandler
)

# تنظیمات اولیه
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_USERNAME = "@tesertdnjdjdj"
SOURCE_CHANNEL = "https://t.me/s/qemat_Abshoda"

# ---------- تنظیمات پیش‌فرض دکمه‌ها ----------
bot_settings = {
    "btn1_active": True,
    "btn2_active": True,
    "btn3_active": True,
    "btn3_data": {"text": "👈 مشاوره و ثبت سفارش 👉", "url": "http://t.me/onyxgold_admin"},
    "btn4_active": False,
    "btn4_data": {"text": "کلید چهارم", "url": "http://google.com"}
}

# ---------- تابع ساخت تقویم شمسی ----------
def create_calendar(year, month):
    tehran_tz = pytz.timezone("Asia/Tehran")
    today_dt = datetime.now(tehran_tz)
    today = jdatetime.date.fromgregorian(date=today_dt.date())
    
    first_day = jdatetime.date(year, month, 1)
    month_name = first_day.j_months_fa[month-1]
    
    keyboard = []
    keyboard.append([InlineKeyboardButton(f"{month_name} {year}", callback_data="ignore")])
    
    week_days = ["ج", "پ", "چ", "س", "د", "ی", "ش"]
    keyboard.append([InlineKeyboardButton(day, callback_data="ignore") for day in week_days])
    
    first_day_weekday = first_day.weekday() 
    
    if month <= 6:
        days_in_month = 31
    elif month <= 11:
        days_in_month = 30
    else:
        days_in_month = 30 if first_day.is_leap() else 29
        
    temp_row = [InlineKeyboardButton(" ", callback_data="ignore")] * first_day_weekday
    
    for day in range(1, days_in_month + 1):
        display_text = str(day)
        if year == today.year and month == today.month and day == today.day:
            display_text = f"📍{day}"
            
        temp_row.append(InlineKeyboardButton(display_text, callback_data=f"cal_d_{year}_{month}_{day}"))
        
        if len(temp_row) == 7:
            temp_row.reverse()
            keyboard.append(temp_row)
            temp_row = []
            
    if temp_row:
        temp_row += [InlineKeyboardButton(" ", callback_data="ignore")] * (7 - len(temp_row))
        temp_row.reverse()
        keyboard.append(temp_row)
        
    next_m, next_y = (month + 1, year) if month < 12 else (1, year + 1)
    prev_m, prev_y = (month - 1, year) if month > 1 else (12, year - 1)
    
    keyboard.append([
        InlineKeyboardButton("➡️ ماه بعد", callback_data=f"cal_m_{next_y}_{next_m}"),
        InlineKeyboardButton("ماه قبل ⬅️", callback_data=f"cal_m_{prev_y}_{prev_m}")
    ])
    keyboard.append([InlineKeyboardButton("❌ انصراف", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def is_user_admin(bot, user_id):
    try:
        member = bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['creator', 'administrator']
    except Exception:
        return False

# مراحل Conversation
TEXT, EDIT_FORWARD, WEIGHT, WORK, PROFIT, SCHEDULE, MANAGE, SCHEDULE_TIME, SETTINGS_STATE, SET_LINK = range(10)

def e2p(number):
    if float(number) == int(float(number)):
        number = int(float(number))
    number = str(number)
    translations = {'0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴', '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹'}
    return ''.join(translations.get(char, char) for char in number)

last_saved_price = None
last_price_time = None
PRICE_TTL = 600

def get_latest_abshode_price():
    global last_saved_price, last_price_time
    now = time.time()
    
    if last_saved_price and last_price_time:
        if now - last_price_time < PRICE_TTL:
            return last_saved_price
            
    try:
        r = requests.get(SOURCE_CHANNEL, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        blocks = r.text.split("tgme_widget_message_text")
        
        for block in blocks:
            if "#آبشده_اتحادیه" in block:
                nums = re.findall(r"\d{2,3}(?:,\d{3})+", block)
                if nums:
                    last_saved_price = nums[0]
                    last_price_time = now
                    return last_saved_price
                    
        for block in blocks:
            if "#آبشده_نقدی" in block:
                nums = re.findall(r"\d{2,3}(?:,\d{3})+", block)
                if nums:
                    last_saved_price = nums[0]
                    last_price_time = now
                    return last_saved_price
    except:
        pass
    return None

scheduled_posts = []
scheduled_timers = []

def schedule_post_with_timer(bot, post_data):
    tz_now = pytz.timezone("Asia/Tehran")
    post_time = post_data["time"]
    delay = (post_time - datetime.now(tz_now)).total_seconds()
    
    if delay < 0:
        delay = 0
        
    def send_scheduled_post():
        p = post_data["post"]
        mode = post_data["mode"]
        keyboard = build_gold_keyboard(p['weight'], p['work'], p['profit'])
        
        if mode == "new":
            if p.get("photo"):
                bot.send_photo(CHANNEL_USERNAME, p["photo"], caption=p["text"], reply_markup=keyboard)
            else:
                bot.send_message(CHANNEL_USERNAME, p["text"], reply_markup=keyboard)
        else:
            if p.get("photo"):
                bot.edit_message_caption(chat_id=CHANNEL_USERNAME, message_id=p["message_id"], caption=p["text"], reply_markup=keyboard)
            else:
                bot.edit_message_text(chat_id=CHANNEL_USERNAME, message_id=p["message_id"], text=p["text"], reply_markup=keyboard)
        
        try:
            scheduled_timers.remove(timer)
            scheduled_posts.remove(post_data)
        except:
            pass
            
    from threading import Timer
    timer = Timer(delay, send_scheduled_post)
    timer.start()
    scheduled_timers.append(timer)
    scheduled_posts.append(post_data)

def cancel_scheduled_post(index):
    if index < len(scheduled_timers):
        scheduled_timers[index].cancel()
        scheduled_timers.pop(index)
        scheduled_posts.pop(index)

# ---------- تابع جدید برای ساخت کیبورد بر اساس تنظیمات ----------
def build_gold_keyboard(weight, work, profit):
    keyboard_btns = []
    
    # کلید اول
    if bot_settings["btn1_active"]:
        total_percent = float(work) + float(profit)
        btn_text = f"💎 قیمت روز محصول با اجرت {e2p(total_percent)} درصد"
        keyboard_btns.append([InlineKeyboardButton(btn_text, callback_data=f"gold|{weight}|{work}|{profit}")])
    
    # کلید دوم
    if bot_settings["btn2_active"]:
        keyboard_btns.append([InlineKeyboardButton("💰 قیمت لحظه ای هر گرم طلای ۱۸ عیار", callback_data="price")])
    
    # کلید سوم
    if bot_settings["btn3_active"]:
        keyboard_btns.append([InlineKeyboardButton(bot_settings["btn3_data"]["text"], url=bot_settings["btn3_data"]["url"])])
        
    # کلید چهارم
    if bot_settings["btn4_active"]:
        keyboard_btns.append([InlineKeyboardButton(bot_settings["btn4_data"]["text"], url=bot_settings["btn4_data"]["url"])])
        
    return InlineKeyboardMarkup(keyboard_btns)

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 پست جدید", callback_data="new_post")],
        [InlineKeyboardButton("✏️ ویرایش پست", callback_data="edit_post")],
        [InlineKeyboardButton("⏱️ مدیریت زمان‌بندی‌ها", callback_data="manage_schedule")],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings_main")]
    ])

def cancel_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="cancel")]])

def publish_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 منتشر شود", callback_data="now")],
        [InlineKeyboardButton("⏰ زمان‌بندی", callback_data="schedule")],
        [InlineKeyboardButton("❌ انصراف", callback_data="cancel")]
    ])

def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_user_admin(context.bot, user_id):
        update.effective_message.reply_text("❌ شما ادمین نیستید و دسترسی ندارید.")
        return
        
    msg_text = "به پنل مدیریت ربات خوش آمدید 👇"
    reply_markup = main_menu()
    
    if update.message:
        update.message.reply_text(msg_text, reply_markup=reply_markup)
    else:
        update.callback_query.message.reply_text(msg_text, reply_markup=reply_markup)

def menu_button(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_user_admin(context.bot, user_id):
        query.answer("❌ دسترسی غیرمجاز", show_alert=True)
        return ConversationHandler.END
        
    query.answer()
    context.user_data.clear()
    
    if query.data == "new_post":
        query.message.reply_text("📌 لطفاً متن یا عکس مورد نظر برای پست را ارسال یا فوروارد کنید:", reply_markup=cancel_keyboard())
        return TEXT
    elif query.data == "edit_post":
        query.message.reply_text("📌 لطفاً پست مورد نظر را از کانال به اینجا فوروارد کنید:", reply_markup=cancel_keyboard())
        return EDIT_FORWARD
    elif query.data == "manage_schedule":
        return show_scheduled(update, context)
    elif query.data == "settings_main":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("کلید اول", callback_data="set_btn_1")],
            [InlineKeyboardButton("کلید دوم", callback_data="set_btn_2")],
            [InlineKeyboardButton("کلید سوم", callback_data="set_btn_3")],
            [InlineKeyboardButton("کلید چهارم", callback_data="set_btn_4")],
            [InlineKeyboardButton("⬅️ بازگشت به منوی اصلی", callback_data="back_to_main")]
        ])
        query.message.reply_text("⚙️ تنظیمات نمایش کلیدها زیر پست‌ها:\nیکی از کلیدها را برای تنظیم انتخاب کنید:", reply_markup=keyboard)
        return SETTINGS_STATE

# ---------- هندلر مدیریت تنظیمات ----------
def settings_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data
    
    if data == "back_to_main":
        start(update, context)
        return ConversationHandler.END
        
    if data.startswith("set_btn_"):
        btn_num = data.split("_")[2]
        context.user_data["editing_btn"] = btn_num
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ روشن", callback_data=f"on_{btn_num}"),
             InlineKeyboardButton("❌ خاموش", callback_data=f"off_{btn_num}")],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="settings_main")]
        ])
        query.message.reply_text(f"وضعیت کلید {btn_num} را تعیین کنید:", reply_markup=keyboard)
        return SETTINGS_STATE

    if data.startswith("on_") or data.startswith("off_"):
        status = data.startswith("on_")
        btn_num = data.split("_")[1]
        key = f"btn{btn_num}_active"
        
        if not status: # انتخاب خاموش
            bot_settings[key] = False
            query.message.reply_text(f"✅ کلید {btn_num} غیرفعال شد.")
            start(update, context)
            return ConversationHandler.END
        else: # انتخاب روشن
            if btn_num in ["1", "2"]:
                bot_settings[key] = True
                query.message.reply_text(f"✅ کلید {btn_num} فعال شد.")
                start(update, context)
                return ConversationHandler.END
            else: # کلید 3 و 4 نیاز به لینک دارند
                context.user_data["editing_btn"] = btn_num
                query.message.reply_text("🔗 لطفاً نام و لینک دکمه را دقیقاً با فرمت زیر ارسال کنید:\n\nButton - http://link.com")
                return SET_LINK

def save_link_handler(update: Update, context: CallbackContext):
    text = update.message.text
    btn_num = context.user_data.get("editing_btn")
    if " - " in text:
        try:
            name, url = text.split(" - ", 1)
            bot_settings[f"btn{btn_num}_active"] = True
            bot_settings[f"btn{btn_num}_data"] = {"text": name.strip(), "url": url.strip()}
            update.message.reply_text(f"✅ تنظیمات کلید {btn_num} با موفقیت ذخیره و فعال شد.")
            start(update, context)
            return ConversationHandler.END
        except:
            update.message.reply_text("❌ خطا در پردازش. لطفاً طبق الگو بفرستید (نام - لینک):")
            return SET_LINK
    else:
        update.message.reply_text("❌ فرمت ارسالی اشتباه است. باید بین نام و لینک علامت - باشد.")
        return SET_LINK

def show_scheduled(update: Update, context: CallbackContext):
    if not scheduled_posts:
        update.callback_query.message.reply_text("❌ هیچ پست زمان‌بندی شده‌ای وجود ندارد.")
        start(update, context)
        return ConversationHandler.END
        
    buttons = []
    for i, post in enumerate(scheduled_posts):
        preview_text = post["post"]["text"][:20] + "..." if len(post["post"]["text"]) > 20 else post["post"]["text"]
        buttons.append([InlineKeyboardButton(f"{preview_text} ({post['time'].strftime('%Y-%m-%d %H:%M')})", callback_data=f"manage_{i}")])
    
    buttons.append([InlineKeyboardButton("⬅️ بازگشت به منوی اصلی", callback_data="back_to_main")])
    update.callback_query.message.reply_text("⏱ لیست پست‌های زمان‌بندی شده:", reply_markup=InlineKeyboardMarkup(buttons))
    return MANAGE

def manage_post(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data
    
    if data.startswith("manage_"):
        idx = int(data.split("_")[1])
        context.user_data["manage_index"] = idx
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ حذف پست", callback_data="delete")],
            [InlineKeyboardButton("⏰ تغییر زمان انتشار", callback_data="edit_time")],
            [InlineKeyboardButton("⬅️ بازگشت به لیست", callback_data="back_to_scheduled")]
        ])
        query.message.reply_text("📌 چه عملیاتی روی این پست انجام شود؟", reply_markup=keyboard)
        return MANAGE
    elif data == "delete":
        idx = context.user_data.get("manage_index")
        if idx is not None and idx < len(scheduled_posts):
            cancel_scheduled_post(idx)
            query.message.reply_text("✅ پست با موفقیت حذف شد.")
        return show_scheduled(update, context)
    elif data == "edit_time":
        idx = context.user_data.get("manage_index")
        if idx is not None and idx < len(scheduled_posts):
            context.user_data["post"] = scheduled_posts[idx]["post"]
            context.user_data["mode"] = scheduled_posts[idx]["mode"]
            
        tz_now = pytz.timezone("Asia/Tehran")
        now_sh = jdatetime.datetime.now(tz_now)
        query.message.reply_text("📅 لطفاً تاریخ جدید را از تقویم انتخاب کنید:", reply_markup=create_calendar(now_sh.year, now_sh.month))
        return SCHEDULE
    elif data == "back_to_scheduled":
        return show_scheduled(update, context)
    elif data == "back_to_main":
        start(update, context)
        return ConversationHandler.END

def cancel(update: Update, context: CallbackContext):
    context.user_data.clear()
    msg = "❌ عملیات لغو شد."
    if update.callback_query:
        update.callback_query.message.reply_text(msg)
    else:
        update.message.reply_text(msg)
    start(update, context)
    return ConversationHandler.END

def post_text(update: Update, context: CallbackContext):
    context.user_data["mode"] = "new"
    context.user_data["post"] = {}
    
    if update.message.photo:
        context.user_data["post"]["photo"] = update.message.photo[-1].file_id
        context.user_data["post"]["text"] = update.message.caption or ""
    else:
        context.user_data["post"]["photo"] = None
        context.user_data["post"]["text"] = update.message.text
        
    update.message.reply_text("⚖️ لطفاً وزن محصول را وارد کنید (فقط عدد):", reply_markup=cancel_keyboard())
    return WEIGHT

def edit_forward(update: Update, context: CallbackContext):
    msg = update.message
    if not msg.forward_from_chat or msg.forward_from_chat.username != CHANNEL_USERNAME.replace("@", ""):
        msg.reply_text("❌ خطا: پست باید حتماً از کانال خودتان فوروارد شود.", reply_markup=cancel_keyboard())
        return EDIT_FORWARD
        
    context.user_data["mode"] = "edit"
    context.user_data["post"] = {
        "message_id": msg.forward_from_message_id,
        "photo": msg.photo[-1].file_id if msg.photo else None,
        "text": msg.caption or msg.text or ""
    }
    msg.reply_text("⚖️ وزن جدید محصول را وارد کنید:", reply_markup=cancel_keyboard())
    return WEIGHT

def post_weight(update: Update, context: CallbackContext):
    try:
        context.user_data["post"]["weight"] = float(update.message.text)
        update.message.reply_text("🛠 درصد اجرت را وارد کنید (فقط عدد):", reply_markup=cancel_keyboard())
        return WORK
    except ValueError:
        update.message.reply_text("❌ خطا: لطفاً فقط عدد وارد کنید.")
        return WEIGHT

def post_work(update: Update, context: CallbackContext):
    try:
        context.user_data["post"]["work"] = float(update.message.text)
        update.message.reply_text("📈 درصد سود را وارد کنید (فقط عدد):", reply_markup=cancel_keyboard())
        return PROFIT
    except ValueError:
        update.message.reply_text("❌ خطا: لطفاً فقط عدد وارد کنید.")
        return WORK

def post_profit(update: Update, context: CallbackContext):
    try:
        p = context.user_data["post"]
        p["profit"] = float(update.message.text)
        
        if context.user_data["mode"] == "edit":
            send_post(update.message.bot, p, "edit")
            update.message.reply_text("✅ پست در کانال با موفقیت ویرایش شد.")
            context.user_data.clear()
            start(update, context)
            return ConversationHandler.END
            
        update.message.reply_text("🚀 پست آماده است. نحوه انتشار را انتخاب کنید:", reply_markup=publish_keyboard())
        return SCHEDULE
    except ValueError:
        update.message.reply_text("❌ خطا: لطفاً فقط عدد وارد کنید.")
        return PROFIT

def post_schedule(update: Update, context: CallbackContext):
    tz_now = pytz.timezone("Asia/Tehran")
    if update.callback_query:
        query = update.callback_query
        query.answer()
        
        if query.data.startswith("cal_m_"):
            _, _, y, m = query.data.split("_")
            query.edit_message_reply_markup(reply_markup=create_calendar(int(y), int(m)))
            return SCHEDULE
        elif query.data.startswith("cal_d_"):
            _, _, y, m, d = query.data.split("_")
            sh_dt = jdatetime.date(int(y), int(m), int(d))
            context.user_data["schedule_date"] = sh_dt.togregorian().strftime("%Y-%m-%d")
            query.message.reply_text(f"✅ تاریخ {y}/{m}/{d} انتخاب شد.\n⏰ حالا ساعت انتشار را با فرمت HHMM وارد کنید (مثال: 1430):")
            return SCHEDULE_TIME
        elif query.data == "schedule":
            now_sh = jdatetime.datetime.now(tz_now)
            query.message.reply_text("📅 تقویم را مشاهده و روز انتشار را انتخاب کنید:", reply_markup=create_calendar(now_sh.year, now_sh.month))
            return SCHEDULE
        elif query.data == "now":
            p = context.user_data["post"]
            send_post(query.bot, p, context.user_data["mode"])
            query.message.reply_text("✅ پست با موفقیت منتشر شد.")
            context.user_data.clear()
            start(update, context)
            return ConversationHandler.END
        elif query.data == "cancel":
            return cancel(update, context)
    return SCHEDULE

def post_schedule_time_handler(update: Update, context: CallbackContext):
    tz_now = pytz.timezone("Asia/Tehran")
    text = update.message.text
    if len(text) == 4 and text.isdigit():
        try:
            hour = int(text[:2])
            minute = int(text[2:])
            dt_str = f"{context.user_data['schedule_date']} {hour:02d}:{minute:02d}"
            post_time = tz_now.localize(datetime.strptime(dt_str, "%Y-%m-%d %H:%M"))
            
            if context.user_data.get("manage_index") is not None:
                cancel_scheduled_post(context.user_data["manage_index"])
                
            schedule_post_with_timer(update.message.bot, {
                "post": context.user_data["post"],
                "mode": context.user_data["mode"],
                "time": post_time
            })
            update.message.reply_text(f"✅ پست برای ساعت {post_time.strftime('%Y-%m-%d %H:%M')} زمان‌بندی شد.")
            context.user_data.clear()
            start(update, context)
            return ConversationHandler.END
        except Exception:
            update.message.reply_text("❌ خطا در تنظیم ساعت. دوباره تلاش کنید:")
            return SCHEDULE_TIME
    else:
        update.message.reply_text("❌ فرمت ساعت اشتباه است. مثال: 1430")
        return SCHEDULE_TIME

def send_post(bot, post, mode):
    # استفاده از تابع جدید برای ساخت کیبورد بر اساس تنظیمات
    keyboard = build_gold_keyboard(post['weight'], post['work'], post['profit'])
    
    if mode == "edit" and "message_id" in post:
        if post.get("photo"):
            return bot.edit_message_caption(chat_id=CHANNEL_USERNAME, message_id=post["message_id"], caption=post["text"], reply_markup=keyboard)
        else:
            return bot.edit_message_text(chat_id=CHANNEL_USERNAME, message_id=post["message_id"], text=post["text"], reply_markup=keyboard)
    else:
        if post.get("photo"):
            return bot.send_photo(CHANNEL_USERNAME, post["photo"], caption=post["text"], reply_markup=keyboard)
        else:
            return bot.send_message(CHANNEL_USERNAME, post["text"], reply_markup=keyboard)

def price_button(update: Update, context: CallbackContext):
    query = update.callback_query
    p = get_latest_abshode_price()
    
    if not p:
        query.answer("❌ متأسفانه قیمت لحظه‌ای دریافت نشد.", show_alert=True)
        return
        
    price_val = int(p.replace(",", ""))
    gram_18 = price_val / 4.3318
    query.answer(f"💰 قیمت لحظه ای هر گرم طلای ۱۸ عیار:\n{round(gram_18):,} تومان", show_alert=True)

def gold_piece_button(update: Update, context: CallbackContext):
    query = update.callback_query
    p = get_latest_abshode_price()
    
    if not p:
        query.answer("❌ خطا در دریافت قیمت زنده.", show_alert=True)
        return
        
    _, weight, work, profit = query.data.split("|")
    price_val = int(p.replace(",", ""))
    base_gram_18 = price_val / 4.3318
    
    # محاسبه قیمت نهایی
    total_price = base_gram_18 * float(weight) * (1 + float(work)/100) * (1 + float(profit)/100)
    
    query.answer(f"💎 قیمت نهایی این محصول با احتساب اجرت و سود:\n{round(total_price):,} تومان", show_alert=True)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(price_button, pattern="price"))
    dp.add_handler(CallbackQueryHandler(gold_piece_button, pattern="gold\\|"))
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(menu_button, pattern="new_post|edit_post|manage_schedule|settings_main")],
        states={
            TEXT: [MessageHandler(Filters.text | Filters.photo, post_text)],
            EDIT_FORWARD: [MessageHandler(Filters.forwarded, edit_forward)],
            WEIGHT: [MessageHandler(Filters.text, post_weight)],
            WORK: [MessageHandler(Filters.text, post_work)],
            PROFIT: [MessageHandler(Filters.text, post_profit)],
            SCHEDULE: [MessageHandler(Filters.text, post_schedule), CallbackQueryHandler(post_schedule)],
            SCHEDULE_TIME: [MessageHandler(Filters.text, post_schedule_time_handler)],
            MANAGE: [CallbackQueryHandler(manage_post)],
            SETTINGS_STATE: [CallbackQueryHandler(settings_handler)],
            SET_LINK: [MessageHandler(Filters.text & ~Filters.command, save_link_handler)]
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="cancel")]
    )
    
    dp.add_handler(conv_handler)
    
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
