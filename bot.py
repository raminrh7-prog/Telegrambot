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

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_USERNAME = "@tesertdnjdjdj"
SOURCE_CHANNEL = "https://t.me/s/qemat_Abshoda"

# ---------- تابع ساخت تقویم شمسی (اضافه شده) ----------
def create_calendar(year, month):
    tehran_tz = pytz.timezone("Asia/Tehran")
    today_dt = datetime.now(tehran_tz)
    today = jdatetime.date.fromgregorian(date=today_dt.date())

    first_day = jdatetime.date(year, month, 1)
    month_name = first_day.j_months_fa[month-1]

    keyboard = []
    # ردیف اول: نام ماه و سال
    keyboard.append([InlineKeyboardButton(f"{month_name} {year}", callback_data="ignore")])

    # ردیف دوم: روزهای هفته
    week_days = ["ج", "پ", "چ", "س", "د", "ی", "ش"]
    keyboard.append([InlineKeyboardButton(day, callback_data="ignore") for day in week_days])

    # محاسبه روزهای ماه
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
            display_text = f"📍 {day}"

        temp_row.append(InlineKeyboardButton(display_text, callback_data=f"cal_d_{year}_{month}_{day}"))

        if len(temp_row) == 7:
            temp_row.reverse() # برای نمایش راست به چپ در تلگرام
            keyboard.append(temp_row)
            temp_row = []

    if temp_row:
        temp_row += [InlineKeyboardButton(" ", callback_data="ignore")] * (7 - len(temp_row))
        temp_row.reverse()
        keyboard.append(temp_row)

    # دکمه‌های جابجایی ماه
    next_m, next_y = (month + 1, year) if month < 12 else (1, year + 1)
    prev_m, prev_y = (month - 1, year) if month > 1 else (12, year - 1)

    keyboard.append([
        InlineKeyboardButton("➡️ ماه بعد", callback_data=f"cal_m_{next_y}_{next_m}"),
        InlineKeyboardButton("ماه قبل ⬅️", callback_data=f"cal_m_{prev_y}_{prev_m}")
    ])
    keyboard.append([InlineKeyboardButton("❌ انصراف", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

# ---------- تابع بررسی ادمین بودن (قابلیت جدید) ----------
def is_user_admin(bot, user_id):
    try:
        member = bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        # بررسی اینکه آیا کاربر سازنده (creator) یا مدیر (administrator) است
        return member.status in ['creator', 'administrator']
    except Exception:
        return False

# مراحل
TEXT, EDIT_FORWARD, WEIGHT, WORK, PROFIT, SCHEDULE, MANAGE, SCHEDULE_TIME = range(8)

# ---------- تابع تبدیل عدد به فارسی ----------
def e2p(number):
    # تبدیل به عدد صحیح در صورت امکان برای زیبایی (مثلاً 38.0 بشود 38)
    if float(number) == int(float(number)):
        number = int(float(number))

    number = str(number)
    translations = {'0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴', '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹'}
    return ''.join(translations.get(char, char) for char in number)

# ---------- کش قیمت ----------
last_saved_price = None
last_price_time = None
PRICE_TTL = 600  # 10 دقیقه

# ---------- قیمت ----------
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

# ---------- زمان‌بندی پست‌ها با Timer ----------
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
        callback_gold = f"gold|{p['weight']}|{p['work']}|{p['profit']}"

        # --- تغییر: جمع اجرت و سود برای نمایش در دکمه ---
        total_percent = float(p['work']) + float(p['profit'])
        work_val_farsi = e2p(total_percent)
        btn_text = f"💎 قیمت روز محصول با اجرت {work_val_farsi} درصد"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(btn_text, callback_data=callback_gold)],
            [InlineKeyboardButton("💰 قیمت لحظه ای طلا", callback_data="price")],
            [InlineKeyboardButton("👈 مشاوره و ثبت سفارش 👉", url="http://t.me/onyxgold_admin")]
        ])

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

# ---------- کیبوردها ----------
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 پست جدید", callback_data="new_post")],
        [InlineKeyboardButton("✏️ ویرایش پست", callback_data="edit_post")],
        [InlineKeyboardButton("⏱️ مدیریت زمان‌بندی‌ها", callback_data="manage_schedule")]
    ])

def cancel_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="cancel")]])

def publish_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 منتشر شود", callback_data="now")],
        [InlineKeyboardButton("⏰ زمان‌بندی", callback_data="schedule")],
        [InlineKeyboardButton("❌ انصراف", callback_data="cancel")]
    ])

def day_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("پس‌فردا", callback_data="day_after"),
            InlineKeyboardButton("فردا", callback_data="tomorrow"),
            InlineKeyboardButton("امروز", callback_data="today")
        ],
        [InlineKeyboardButton("❌ انصراف", callback_data="cancel")]
    ])

# ---------- start ----------
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    # چک کردن ادمین بودن
    if not is_user_admin(context.bot, user_id):
        update.effective_message.reply_text("❌ دسترسی محدود! فقط ادمین‌های کانال مجاز به استفاده از ربات هستند.")
        return

    if update.message:
        update.message.reply_text("منوی اصلی 👇", reply_markup=main_menu())
    else:
        update.callback_query.message.reply_text("منوی اصلی 👇", reply_markup=main_menu())

# ---------- دکمه‌های منو ----------
def menu_button(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id

    # چک کردن ادمین بودن در هنگام زدن دکمه‌ها
    if not is_user_admin(context.bot, user_id):
        query.answer("❌ شما ادمین نیستید و دسترسی ندارید!", show_alert=True)
        return ConversationHandler.END

    query.answer()
    context.user_data.clear()
    if query.data == "new_post":
        query.message.reply_text("📌 متن یا عکس پست را ارسال کنید:", reply_markup=cancel_keyboard())
        return TEXT
    if query.data == "edit_post":
        query.message.reply_text("📌 پست مورد نظر را از کانال فوروارد کنید:", reply_markup=cancel_keyboard())
        return EDIT_FORWARD
    if query.data == "manage_schedule":
        return show_scheduled(update, context)

# ---------- نمایش و مدیریت زمان‌بندی‌ها ----------
def show_scheduled(update: Update, context: CallbackContext):
    if not scheduled_posts:
        update.callback_query.message.reply_text("❌ هیچ پست زمان‌بندی‌شده‌ای وجود ندارد.")
        start(update, context)
        return ConversationHandler.END
    buttons = []
    for i, post in enumerate(scheduled_posts):
        preview_text = post["post"]["text"][:20] + "..." if len(post["post"]["text"]) > 20 else post["post"]["text"]
        buttons.append([
            InlineKeyboardButton(
                f"{preview_text} ({post['time'].strftime('%Y-%m-%d %H:%M')})",
                callback_data=f"manage_{i}"
            )
        ])
    buttons.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="back_to_main")])
    update.callback_query.message.reply_text(
        "⏱  پست‌های زمان‌بندی‌شده:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return MANAGE

# ---------- مدیریت پست ----------
def manage_post(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data
    if data.startswith("manage_"):
        idx = int(data.split("_")[1])
        context.user_data["manage_index"] = idx
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ حذف پست", callback_data="delete")],
            [InlineKeyboardButton("⏰ تغییر زمان", callback_data="edit_time")],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="back_to_scheduled")]
        ])
        query.message.reply_text("📌 انتخاب عملیات:", reply_markup=keyboard)
        return MANAGE
    elif data == "delete":
        idx = context.user_data.get("manage_index")
        if idx is not None and idx < len(scheduled_posts):
            cancel_scheduled_post(idx)
            query.message.reply_text("✅ پست حذف شد")
        return show_scheduled(update, context)
    elif data == "edit_time":
        idx = context.user_data.get("manage_index")
        if idx is not None and idx < len(scheduled_posts):
            context.user_data["post"] = scheduled_posts[idx]["post"]
            context.user_data["mode"] = scheduled_posts[idx]["mode"]

        # تغییر: نمایش تقویم به جای دکمه‌های امروز/فردا
        tz_now = pytz.timezone("Asia/Tehran")
        now_sh = jdatetime.datetime.now(tz_now)
        query.message.reply_text(
            "📅 انتخاب تاریخ جدید از تقویم:",
            reply_markup=create_calendar(now_sh.year, now_sh.month)
        )
        return SCHEDULE
    elif data == "back_to_scheduled":
        return show_scheduled(update, context)
    elif data == "back_to_main":
        start(update, context)
        return ConversationHandler.END

# ---------- انصراف ----------
def cancel(update: Update, context: CallbackContext):
    context.user_data.clear()
    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.message.reply_text("❌ عملیات لغو شد")
    else:
        update.message.reply_text("❌ عملیات لغو شد")
    start(update, context)
    return ConversationHandler.END

# ---------- پست جدید ----------
def post_text(update: Update, context: CallbackContext):
    context.user_data["mode"] = "new"
    context.user_data["post"] = {}
    if update.message.photo:
        context.user_data["post"]["photo"] = update.message.photo[-1].file_id
        context.user_data["post"]["text"] = update.message.caption or ""
    else:
        context.user_data["post"]["photo"] = None
        context.user_data["post"]["text"] = update.message.text
    update.message.reply_text(""⚖️ وزن را وارد کنید:"", reply_markup=cancel_keyboard())
    return WEIGHT

# ---------- ویرایش پست ----------
def edit_forward(update: Update, context: CallbackContext):
    msg = update.message
    if not msg.forward_from_chat or msg.forward_from_chat.username != CHANNEL_USERNAME.replace("@", ""):
        msg.reply_text("❌ پست باید از همان کانال فوروارد شود", reply_markup=cancel_keyboard())
        return EDIT_FORWARD
    context.user_data["mode"] = "edit"
    context.user_data["post"] = {
        "message_id": msg.forward_from_message_id,
        "photo": msg.photo[-1].file_id if msg.photo else None,
        "text": msg.caption or msg.text or ""
    }
    msg.reply_text("⚖️ وزن را وارد کنید:", reply_markup=cancel_keyboard())
    return WEIGHT

# ---------- مراحل مشترک ----------
def post_weight(update: Update, context: CallbackContext):
    context.user_data["post"]["weight"] = float(update.message.text)
    update.message.reply_text("🛠 اجرت (%):", reply_markup=cancel_keyboard())
    return WORK

def post_work(update: Update, context: CallbackContext):
    context.user_data["post"]["work"] = float(update.message.text)
    update.message.reply_text("📈 سود (%):", reply_markup=cancel_keyboard())
    return PROFIT

def post_profit(update: Update, context: CallbackContext):
    p = context.user_data["post"]
    p["profit"] = float(update.message.text)
    if context.user_data["mode"] == "edit":
        send_post(update.message.bot, p, "edit")
        update.message.reply_text(
            f"✅ [پست](https://t.me/{CHANNEL_USERNAME[1:]}/{p['message_id']}) ویرایش شد",
            parse_mode="Markdown"
        )
        context.user_data.clear()
        start(update, context)
        return ConversationHandler.END
    update.message.reply_text("🚀 انتخاب نحوه انتشار:", reply_markup=publish_keyboard())
    return SCHEDULE

# ---------- انتشار فوری یا زمان‌بندی (تغییر یافته برای تقویم) ----------
def post_schedule(update: Update, context: CallbackContext):
    tz_now = pytz.timezone("Asia/Tehran")
    if update.callback_query:
        query = update.callback_query
        query.answer()

        # مدیریت دکمه‌های تقویم
        if query.data.startswith("cal_m_"):
            _, _, y, m = query.data.split("_")
            query.edit_message_reply_markup(reply_markup=create_calendar(int(y), int(m)))
            return SCHEDULE

        elif query.data.startswith("cal_d_"):
            _, _, y, m, d = query.data.split("_")
            # ذخیره تاریخ به صورت میلادی برای پردازش نهایی
            sh_dt = jdatetime.date(int(y), int(m), int(d))
            context.user_data["schedule_date"] = sh_dt.togregorian().strftime("%Y-%m-%d")
            query.message.reply_text(
                f"✅ تاریخ انتخاب شد: {y}/{m}/{d}\nلطفاً ساعت را به صورت HHMM وارد کنید:"
            )
            return SCHEDULE_TIME

        elif query.data == "schedule":
            now_sh = jdatetime.datetime.now(tz_now)
            query.message.reply_text(
                "📅 انتخاب تاریخ از تقویم:",
                reply_markup=create_calendar(now_sh.year, now_sh.month)
            )
            return SCHEDULE

        elif query.data == "now":
            p = context.user_data["post"]
            mode = context.user_data["mode"]
            sent = send_post(query.bot, p, mode)
            query.message.reply_text(
                f"✅ [پست](https://t.me/{CHANNEL_USERNAME[1:]}/{sent.message_id}) منتشر شد",
                parse_mode="Markdown"
            )
            context.user_data.clear()
            start(update, context)
            return ConversationHandler.END

        elif query.data == "cancel":
            return cancel(update, context)

    elif update.message:
        # حفظ قابلیت ورود دستی تاریخ به صورت YYYYMMDD
        if "schedule_date" not in context.user_data:
            try:
                post_date = datetime.strptime(update.message.text, "%Y%m%d")
                context.user_data["schedule_date"] = post_date.strftime("%Y-%m-%d")
                update.message.reply_text("✅ تاریخ ثبت شد. لطفاً ساعت را به صورت HHMM وارد کنید:")
                return SCHEDULE_TIME
            except ValueError:
                update.message.reply_text("❌ فرمت تاریخ اشتباه است")
                now_sh = jdatetime.datetime.now(tz_now)
                update.message.reply_text("📅 تاریخ جدید:", reply_markup=create_calendar(now_sh.year, now_sh.month))
                return SCHEDULE
        else:
            # این بخش مربوط به دریافت ساعت است که در تابع SCHEDULE_TIME مدیریت می‌شود
            pass

# تابع جدید برای مدیریت دریافت ساعت (برای جلوگیری از تداخل با منطق تقویم)
def post_schedule_time_handler(update: Update, context: CallbackContext):
    tz_now = pytz.timezone("Asia/Tehran")
    try:
        hour = int(update.message.text[:2])
        minute = int(update.message.text[2:])
        dt_str = f"{context.user_data['schedule_date']} {hour:02d}:{minute:02d}"
        post_time = tz_now.localize(datetime.strptime(dt_str, "%Y-%m-%d %H:%M"))

        if context.user_data.get("manage_index") is not None:
            idx = context.user_data["manage_index"]
            cancel_scheduled_post(idx)

        schedule_post_with_timer(update.message.bot, {
            "post": context.user_data["post"],
            "mode": context.user_data["mode"],
            "time": post_time
        })

        update.message.reply_text(
            f"✅ پست زمان‌بندی شد برای {post_time.strftime('%Y-%m-%d %H:%M')} تهران"
        )
        context.user_data.clear()
        start(update, context)
        return ConversationHandler.END
    except ValueError:
        update.message.reply_text("❌ فرمت ساعت اشتباه است. مثال: 1430")
        return SCHEDULE_TIME

# ---------- ارسال پست ----------
def send_post(bot, post, mode):
    callback_gold = f"gold|{post['weight']}|{post['work']}|{post['profit']}"

    # --- تغییر: جمع اجرت و سود برای نمایش در دکمه ---
    total_percent = float(post['work']) + float(post['profit'])
    work_val_farsi = e2p(total_percent)
    btn_text = f"💎 قیمت روز محصول با اجرت {work_val_farsi} درصد"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_text, callback_data=callback_gold)],
        [InlineKeyboardButton("💰 قیمت لحظه ای طلا", callback_data="price")],
        [InlineKeyboardButton("👈 مشاوره و ثبت سفارش 👉", url="http://t.me/onyxgold_admin")]
    ])
    if mode == "edit" and "message_id" in post:
        if post.get("photo"):
            bot.edit_message_caption(chat_id=CHANNEL_USERNAME, message_id=post["message_id"], caption=post["text"], reply_markup=keyboard)
        else:
            bot.edit_message_text(chat_id=CHANNEL_USERNAME, message_id=post["message_id"], text=post["text"], reply_markup=keyboard)
        return post
    else:
        if post.get("photo"):
            return bot.send_photo(CHANNEL_USERNAME, post["photo"], caption=post["text"], reply_markup=keyboard)
        return bot.send_message(CHANNEL_USERNAME, post["text"], reply_markup=keyboard)

# ---------- Popup ----------
def price_button(update: Update, context: CallbackContext):
    p = get_latest_abshode_price()
    if not p:
        update.callback_query.answer("فعلاً قیمت در دسترس نیست، لطفاً بعداً دوباره امتحان کنید.", show_alert=True)
        return
    v = int(p.replace(",", "")) / 4.3318
    update.callback_query.answer(f"{round(v):,} تومان", show_alert=True)

def gold_piece_button(update: Update, context: CallbackContext):
    query = update.callback_query
    p = get_latest_abshode_price()
    if not p:
        query.answer("فعلاً قیمت در دسترس نیست، لطفاً بعداً دوباره امتحان کنید.", show_alert=True)
        return
    _, weight, work, profit = query.data.split("|")
    base = int(p.replace(",", "")) / 4.3318
    total = base * float(weight)
    total *= (1 + float(work)/100)
    total *= (1 + float(profit)/100)
    query.answer(f"{round(total):,} تومان", show_alert=True)

# ---------- MAIN ----------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(price_button, pattern="price"))
    dp.add_handler(CallbackQueryHandler(gold_piece_button, pattern="gold\\|"))

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(menu_button, pattern="new_post|edit_post|manage_schedule")],
        states={
            TEXT: [MessageHandler(Filters.text | Filters.photo, post_text)],
            EDIT_FORWARD: [MessageHandler(Filters.forwarded, edit_forward)],
            WEIGHT: [MessageHandler(Filters.text, post_weight)],
            WORK: [MessageHandler(Filters.text, post_work)],
            PROFIT: [MessageHandler(Filters.text, post_profit)],
            SCHEDULE: [
                MessageHandler(Filters.text, post_schedule),
                CallbackQueryHandler(post_schedule)
            ],
            SCHEDULE_TIME: [MessageHandler(Filters.text, post_schedule_time_handler)],
            MANAGE: [CallbackQueryHandler(manage_post)]
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="cancel")]
    )

    dp.add_handler(conv)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
