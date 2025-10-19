import os
import telebot
from telebot import types
from flask import Flask
from threading import Thread

# === CONFIG ===
TOKEN = os.environ.get('BOT_TOKEN')  # Get token from environment variable
ADMIN_ID = 6899720377
PUBLIC_CHANNEL = "@itz_4nuj1"
PRIVATE_CHANNEL_ID = -1002267241920  # Replace with your actual private channel ID

# Check if token is available
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN environment variable is not set!")

bot = telebot.TeleBot(TOKEN)
user_data = {}

# === Force Join System ===
def is_user_joined(chat_id):
    if chat_id == ADMIN_ID:
        return True
    try:
        pub_status = bot.get_chat_member(PUBLIC_CHANNEL, chat_id).status
        if pub_status not in ['member', 'administrator', 'creator']:
            return False
        priv_status = bot.get_chat_member(PRIVATE_CHANNEL_ID, chat_id).status
        return priv_status in ['member', 'administrator', 'creator']
    except Exception as e:
        print("Join Check Error:", e)
        return False

def send_force_join(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("📢 Join Public", url=f"https://t.me/{PUBLIC_CHANNEL.strip('@')}"),
        types.InlineKeyboardButton("🔐 Join Private", url="https://t.me/+e7vg5ELF-SViY2Zl" + str(PRIVATE_CHANNEL_ID)[4:])
    )
    markup.add(types.InlineKeyboardButton("✅ JOINED", callback_data="check_join"))
    bot.send_message(chat_id, "🚫 To use this bot, please join both channels first:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def recheck_join(call):
    chat_id = call.message.chat.id
    if is_user_joined(chat_id):
        bot.answer_callback_query(call.id, "✅ You're now verified!")
        start_handler(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Still not joined both channels.", show_alert=True)

# === Save Users & Files Count ===
def save_user(user_id):
    if not os.path.exists("users.txt"):
        with open("users.txt", "w") as f:
            f.write(f"{user_id}\n")
    else:
        with open("users.txt", "r") as f:
            users = f.read().splitlines()
        if str(user_id) not in users:
            with open("users.txt", "a") as f:
                f.write(f"{user_id}\n")

def increment_file_count():
    if not os.path.exists("files_count.txt"):
        with open("files_count.txt", "w") as f:
            f.write("1")
    else:
        with open("files_count.txt", "r+") as f:
            count = int(f.read())
            f.seek(0)
            f.write(str(count + 1))
            f.truncate()

def get_file_count():
    if not os.path.exists("files_count.txt"):
        return 0
    with open("files_count.txt", "r") as f:
        return int(f.read())

# === Start Handler ===
@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id

    if not is_user_joined(chat_id):
        send_force_join(chat_id)
        return

    save_user(chat_id)
    bot.reply_to(message, "👋 Welcome! Please send me the 📄 *file* you want to attach a 📸 *thumbnail* to.", parse_mode="Markdown")

# === File Handler ===
@bot.message_handler(content_types=['document'])
def handle_file(message):
    chat_id = message.chat.id
    save_user(chat_id)

    if not is_user_joined(chat_id):
        send_force_join(chat_id)
        return

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    file_name = message.document.file_name
    file_path = f"{chat_id}_{file_name}"

    with open(file_path, 'wb') as f:
        f.write(downloaded_file)

    user_data[chat_id] = {
        "file_path": file_path,
        "file_name": file_name,
        "file_size": message.document.file_size,
        "mime_type": message.document.mime_type
    }

    bot.send_message(chat_id, "✅ File received!\nNow please send a 🖼️ *thumbnail image*.", parse_mode="Markdown")

# === Thumbnail Handler ===
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    save_user(chat_id)

    if not is_user_joined(chat_id):
        send_force_join(chat_id)
        return

    if chat_id not in user_data:
        bot.reply_to(message, "⚠️ Please send a file first before sending an image.")
        return

    photo_file = message.photo[-1]
    photo_info = bot.get_file(photo_file.file_id)
    downloaded_photo = bot.download_file(photo_info.file_path)

    image_path = f"{chat_id}_thumb.jpg"
    with open(image_path, 'wb') as img:
        img.write(downloaded_photo)

    user_data[chat_id]["thumbnail"] = image_path

    data = user_data[chat_id]
    caption = (
        f"📁 **File Info**\n\n"
        f"📦 *File Name:* `{data['file_name']}`\n"
        f"📏 *File Size:* `{data['file_size']}`\n"
        f"📄 *File Type:* `{data['mime_type']}`"
    )

    with open(data['file_path'], 'rb') as f, open(image_path, 'rb') as thumb:
        bot.send_document(
            chat_id,
            document=(data['file_name'], f),
            caption=caption,
            thumb=thumb,
            parse_mode="Markdown"
        )

    increment_file_count()

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✏️ Rename File", callback_data="rename"))
    bot.send_message(chat_id, "🔧 Do you want to rename the file?", reply_markup=markup)

# === Rename Flow ===
@bot.callback_query_handler(func=lambda call: call.data == "rename")
def ask_new_name(call):
    bot.send_message(call.message.chat.id, "📝 Send the *new name* for the file (with extension, e.g. `example.py`)", parse_mode="Markdown")
    bot.register_next_step_handler(call.message, rename_file)

def rename_file(message):
    chat_id = message.chat.id
    new_name = message.text.strip()

    if chat_id not in user_data or "thumbnail" not in user_data[chat_id]:
        bot.send_message(chat_id, "⚠️ Session expired. Please send the file and thumbnail again.")
        return

    data = user_data[chat_id]
    old_path = data["file_path"]
    new_path = f"{chat_id}_{new_name}"

    os.rename(old_path, new_path)

    with open(new_path, 'rb') as f, open(data["thumbnail"], 'rb') as thumb:
        bot.send_document(
            chat_id,
            document=(new_name, f),
            caption=f"✅ *Renamed and sent:* `{new_name}`",
            thumb=thumb,
            parse_mode="Markdown"
        )

    bot.send_message(chat_id, "🎉 Done! File has been renamed and sent.")

    # Cleanup
    if os.path.exists(new_path):
        os.remove(new_path)
    if os.path.exists(data["thumbnail"]):
        os.remove(data["thumbnail"])

    user_data.pop(chat_id, None)

# === Broadcast Command ===
@bot.message_handler(commands=['broadcast'])
def broadcast_handler(message):
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return
    bot.send_message(ADMIN_ID, "📢 Send the broadcast message now.")
    bot.register_next_step_handler(message, process_broadcast)

def process_broadcast(message):
    if not os.path.exists("users.txt"):
        bot.send_message(ADMIN_ID, "⚠️ No users found to broadcast.")
        return
    with open("users.txt", "r") as f:
        users = f.read().splitlines()

    sent = 0
    for user_id in users:
        try:
            bot.send_message(int(user_id), f"📢 *Broadcast:*\n\n{message.text}", parse_mode="Markdown")
            sent += 1
        except Exception:
            continue

    bot.send_message(ADMIN_ID, f"✅ Broadcast sent to {sent} users.")

# === Stats Command ===
@bot.message_handler(commands=['stats'])
def stats_handler(message):
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return

    total_users = 0
    if os.path.exists("users.txt"):
        with open("users.txt", "r") as f:
            total_users = len(f.read().splitlines())

    total_files = get_file_count()

    bot.send_message(ADMIN_ID, f"📊 Bot Stats:\n\n👤 Users: *{total_users}*\n📁 Files Designed: *{total_files}*", parse_mode="Markdown")

# === Flask Web Server for Keep Alive ===
app = Flask('')

@app.route('/')
def home():
    return "Bot is running"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run_flask).start()

# === Start Bot ===
if __name__ == "__main__":
    print("🤖 Bot is starting...")
    keep_alive()
    try:
        bot.polling()
    except Exception as e:
        print("Bot Error:", e)
