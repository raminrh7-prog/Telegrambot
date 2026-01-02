import re
import requests
import threading
import time
from datetime import datetime, timedelta
import pytz

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater, CallbackContext,
    CallbackQueryHandler, MessageHandler,
    Filters, ConversationHandler, CommandHandler
)

TOKEN = "8380198058:AAFvq34yans-G13UXtAHOKgNeSMUhSJWFLc"
CHANNEL_USERNAME = "@tesertdnjdjdj"
SOURCE_CHANNEL = "https://t.me/s/qemat_Abshoda"

# مراحل
TEXT, EDIT_FORWARD, WEIGHT, WORK, PROFIT, SCHEDULE, MANAGE, SCHEDULE_TIME = range(8)

# ---------- ذخیره آخرین قیمت ----------
last_saved_price = None

# ---------- زمان‌بندی پست‌ها ----------
scheduled_posts = []

# ---------- قیمت ----------
def get_latest_abshode_price():
    global last_saved_price
    try:
        r = requests.get(SOURCE_CHANNEL, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        for block in r.text.split("tgme_widget_message_text"):
            if "#آبشده_غیررسمی" in block:
                nums = re.findall(r"\d{2,3}(?:,\d{3})+", block)
                if nums:
                    last_saved_price = nums[0]
                    return last_saved_price
    except:
        pass
    return last_saved_price

# ---------- حلقه بهینه چک قیمت ----------
def price_scheduler():
    tz_now = pytz.timezone("Asia/Tehran")
    while True:
        now = datetime.now(tz_now)
        if 11 <= now.hour < 20:  # فقط بین 11 صبح تا 20 فعال باشد
            get_latest_abshode_price()
        time.sleep(300)  # هر 5 دقیقه یک بار

# ---------- حلقه بهینه زمان‌بندی پست ----------
def post_scheduler(bot):
    tz_now = pytz.timezone("Asia/Tehran")
    while True:
        if not scheduled_posts:
            time.sleep(60)
            continue
        now = datetime.now(tz_now)
        for post in scheduled_posts[:]:
            if post["time"] <= now:
                p = post["post"]
                mode = post["mode"]
                callback_gold = f"gold|{p['weight']}|{p['work']}|{p['profit']}"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 قیمت لحظه ای طلا", callback_data="price")],
                    [InlineKeyboardButton("💎 قیمت روز محصول", callback_data=callback_gold)]
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
                scheduled_posts.remove(post)
        # فاصله کوتاه ولی فقط وقتی پستی داریم
        time.sleep(10)

# ---------- کیبوردها ----------
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 پست جدید", callback_data="new_post")],
        [InlineKeyboardButton("✏️ ویرایش پست", callback_data="edit_post")],
        [InlineKeyboardButton("⏱️ مدیریت زمان‌بندی‌ها", callback_data="manage_schedule")]
    ])

def cancel_keyboard():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ انصراف", callback_data="cancel")]]
    )

def publish_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 فوری منتشر شود", callback_data="now")],
        [InlineKeyboardButton("⏰ زمان‌بندی", callback_data="schedule")],
        [InlineKeyboardButton("❌ انصراف", callback_data="cancel")]
    ])

def day_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("امروز", callback_data="today"),
            InlineKeyboardButton("فردا", callback_data="tomorrow"),
            InlineKeyboardButton("پس‌فردا", callback_data="day_after")
        ],
        [InlineKeyboardButton("❌ انصراف", callback_data="cancel")]
    ])

# ---------- توابع اصلی کد0 ----------
def start(update: Update, context: CallbackContext):
    if update.message:
        update.message.reply_text("منوی اصلی 👇", reply_markup=main_menu())
    else:
        update.callback_query.message.reply_text("منوی اصلی 👇", reply_markup=main_menu())

def menu_button(update: Update, context: CallbackContext):
    query = update.callback_query
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

def show_scheduled(update: Update, context: CallbackContext):
    if not scheduled_posts:
        update.callback_query.message.reply_text("❌ هیچ پست زمان‌بندی‌شده‌ای وجود ندارد.")
        start(update, context)
        return ConversationHandler.END

    buttons = []
    for i, post in enumerate(scheduled_posts):
        preview_text = post["post"]["text"][:20] + "..." if len(post["post"]["text"]) > 20 else post["post"]["text"]
        buttons.append([InlineKeyboardButton(f"{preview_text} ({post['time'].strftime('%Y-%m-%d %H:%M')})", callback_data=f"manage_{i}")])
    buttons.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="back_to_main")])
    update.callback_query.message.reply_text("📌 پست‌های زمان‌بندی‌شده:", reply_markup=InlineKeyboardMarkup(buttons))
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
            [InlineKeyboardButton("⏰ تغییر زمان", callback_data="edit_time")],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="back_to_scheduled")]
        ])
        query.message.reply_text("📌 انتخاب عملیات:", reply_markup=keyboard)
        return MANAGE

    elif data == "delete":
        idx = context.user_data.get("manage_index")
        if idx is not None and idx < len(scheduled_posts):
            scheduled_posts.pop(idx)
            query.message.reply_text("✅ پست حذف شد")
        return show_scheduled(update, context)

    elif data == "edit_time":
        query.message.reply_text("📌 انتخاب روز یا تاریخ را با فرمت YYYYMMDD وارد کنید:", reply_markup=day_keyboard())
        return SCHEDULE

    elif data == "back_to_scheduled":
        return show_scheduled(update, context)

    elif data == "back_to_main":
        start(update, context)
        return ConversationHandler.END

def cancel(update: Update, context: CallbackContext):
    context.user_data.clear()
    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.message.reply_text("❌ عملیات لغو شد")
    else:
        update.message.reply_text("❌ عملیات لغو شد")
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
    update.message.reply_text("📌 وزن (گرم):", reply_markup=cancel_keyboard())
    return WEIGHT

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
    msg.reply_text("📌 وزن (گرم):", reply_markup=cancel_keyboard())
    return WEIGHT

def post_weight(update: Update, context: CallbackContext):
    context.user_data["post"]["weight"] = float(update.message.text)
    update.message.reply_text("📌 اجرت (%):", reply_markup=cancel_keyboard())
    return WORK

def post_work(update: Update, context: CallbackContext):
    context.user_data["post"]["work"] = float(update.message.text)
    update.message.reply_text("📌 سود (%):", reply_markup=cancel_keyboard())
    return PROFIT

def post_profit(update: Update, context: CallbackContext):
    p = context.user_data["post"]
    p["profit"] = float(update.message.text)
    if context.user_data["mode"] == "edit":
        sent = send_post(update.message.bot, p, "edit")
        update.message.reply_text(
            f"✅ [پست](https://t.me/{CHANNEL_USERNAME[1:]}/{p['message_id']}) ویرایش شد",
            parse_mode="Markdown"
        )
        context.user_data.clear()
        start(update, context)
        return ConversationHandler.END
    update.message.reply_text("📌 انتخاب حالت انتشار:", reply_markup=publish_keyboard())
    return SCHEDULE

def post_schedule(update: Update, context: CallbackContext):
    tz_now = pytz.timezone("Asia/Tehran")
    if update.callback_query:
        query = update.callback_query
        query.answer()
        if query.data in ["today", "tomorrow", "day_after"]:
            if query.data == "today":
                day = datetime.now(tz_now)
            elif query.data == "tomorrow":
                day = datetime.now(tz_now) + timedelta(days=1)
            else:
                day = datetime.now(tz_now) + timedelta(days=2)
            context.user_data["schedule_date"] = day.strftime("%Y-%m-%d")
            query.message.reply_text(f"📌 روز انتخاب شد: {day.strftime('%Y-%m-%d')}\nلطفاً ساعت را به صورت HHMM وارد کنید:")
            return SCHEDULE_TIME
        elif query.data == "schedule":
            query.message.reply_text("📌 انتخاب روز یا تاریخ را با فرمت YYYYMMDD وارد کنید:", reply_markup=day_keyboard())
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
        if "schedule_date" not in context.user_data:
            try:
                post_date = datetime.strptime(update.message.text, "%Y%m%d")
                context.user_data["schedule_date"] = post_date.strftime("%Y-%m-%d")
                update.message.reply_text("✅ تاریخ ثبت شد. لطفاً ساعت را به صورت HHMM وارد کنید:")
                return SCHEDULE_TIME
            except ValueError:
                update.message.reply_text("❌ فرمت تاریخ اشتباه است، لطفاً به شکل YYYYMMDD وارد کنید یا یکی از دکمه‌ها را بزنید:")
                update.message.reply_text("📌 انتخاب روز:", reply_markup=day_keyboard())
                return SCHEDULE
        else:
            try:
                hour = int(update.message.text[:2])
                minute = int(update.message.text[2:])
                dt_str = f"{context.user_data['schedule_date']} {hour:02d}:{minute:02d}"
                post_time = tz_now.localize(datetime.strptime(dt_str, "%Y-%m-%d %H:%M"))
                scheduled_posts.append({
                    "post": context.user_data["post"],
                    "mode": context.user_data["mode"],
                    "time": post_time
                })
                update.message.reply_text(f"✅ پست زمان‌بندی شد برای {post_time.strftime('%Y-%m-%d %H:%M')} تهران")
                context.user_data.clear()
                start(update, context)
                return ConversationHandler.END
            except ValueError:
                update.message.reply_text("❌ فرمت ساعت اشتباه است، لطفاً به شکل HHMM وارد کنید:")
                return SCHEDULE_TIME

def send_post(bot, post, mode):
    callback_gold = f"gold|{post['weight']}|{post['work']}|{post['profit']}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 قیمت لحظه ای طلا", callback_data="price")],
        [InlineKeyboardButton("💎 قیمت روز محصول", callback_data=callback_gold)]
    ])
    if mode == "edit" and "message_id" in post:
        if post.get("photo"):
            bot.edit_message_caption(chat_id=CHANNEL_USERNAME, message_id=post["message_id"], caption=post["text"], reply_markup=keyboard)
        else:
            bot.edit_message_text(chat_id=CHANNEL_USERNAME, message_id=post["message_id"], text=post["text"], reply_markup=keyboard)
        return post
    else:
        if post.get("photo"):
            msg = bot.send_photo(CHANNEL_USERNAME, post["photo"], caption=post["text"], reply_markup=keyboard)
        else:
            msg = bot.send_message(CHANNEL_USERNAME, post["text"], reply_markup=keyboard)
        return msg

def price_button(update: Update, context: CallbackContext):
    p = last_saved_price
    if not p:
        update.callback_query.answer("خطا در دریافت قیمت", show_alert=True)
        return
    v = int(p.replace(",", "")) / 4.3318
    update.callback_query.answer(f"{round(v):,} تومان", show_alert=True)

def gold_piece_button(update: Update, context: CallbackContext):
    query = update.callback_query
    _, weight, work, profit = query.data.split("|")
    base = int(last_saved_price.replace(",", "")) / 4.3318
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
            SCHEDULE: [MessageHandler(Filters.text, post_schedule), CallbackQueryHandler(post_schedule)],
            SCHEDULE_TIME: [MessageHandler(Filters.text, post_schedule)],
            MANAGE: [CallbackQueryHandler(manage_post)]
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="cancel")]
    )

    dp.add_handler(conv)

    # ---------- شروع حلقه‌ها ----------
    threading.Thread(target=price_scheduler, daemon=True).start()
    threading.Thread(target=lambda: post_scheduler(updater.bot), daemon=True).start()

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()