import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2
from psycopg2 import pool
import datetime
import time
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- CONFIGURATION ---
TOKEN = '8683212510:AAEdE8kq5-5GuKerfPa_Mzaxovgb-J5VU4w'
OWNER_ID = 8894779077  
ADMIN_USERNAME = 'Raka_01'  

DATABASE_URL = 'postgresql://neondb_owner:npg_TFXNmVEARt72@ep-twilight-sunset-axd07o2j-pooler.c-4.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require' 
USDT_TO_INR_RATE = 94.0  

bot = telebot.TeleBot(TOKEN)
user_states = {}

# --- ANTI-CRASH RAILWAY HEALTH SERVER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is LIVE and running perfectly!")
    def log_message(self, format, *args): pass 

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# --- SUPER FAST DATABASE POOL ---
try:
    db_pool = psycopg2.pool.ThreadedConnectionPool(1, 20, DATABASE_URL)
    print("✅ Turbo DB Pool Connected!")
except Exception as e:
    print(f"❌ DB Pool Error: {e}")

def run_query(query, params=(), fetch=None, commit=False):
    retries = 3
    for attempt in range(retries):
        conn = None
        try:
            conn = db_pool.getconn()
            cursor = conn.cursor()
            cursor.execute(query, params)
            if commit: conn.commit()
            
            res = None
            if fetch == 'one': res = cursor.fetchone()
            elif fetch == 'all': res = cursor.fetchall()
            elif fetch == 'id':
                row = cursor.fetchone()
                res = row[0] if row else None
                
            cursor.close()
            db_pool.putconn(conn)
            return res
        except Exception as e:
            if conn:
                db_pool.putconn(conn, close=True) # Clear broken connection instantly
            time.sleep(0.5)
    return None

# --- INIT DATABASE ---
def init_db():
    run_query('''CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, balance FLOAT DEFAULT 0)''', commit=True)
    run_query('''ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT DEFAULT 'Unknown' ''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS history (id SERIAL PRIMARY KEY, user_id BIGINT, type TEXT, amount FLOAT, detail TEXT, date TEXT)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS pending_withdraws (id SERIAL PRIMARY KEY, user_id BIGINT, method TEXT, address TEXT, amount FLOAT)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS approved_withdraws (id SERIAL PRIMARY KEY, user_id BIGINT, method TEXT, address TEXT, amount FLOAT, date TEXT)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS admins (user_id BIGINT PRIMARY KEY)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS map_tasks (id SERIAL PRIMARY KEY, link TEXT, review_text TEXT, status TEXT DEFAULT 'AVAILABLE', assigned_to BIGINT)''', commit=True)
    run_query('''ALTER TABLE map_tasks ADD COLUMN IF NOT EXISTS ss_file_id TEXT''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS new_gmail_tasks (id SERIAL PRIMARY KEY, gmail TEXT, password TEXT, status TEXT DEFAULT 'AVAILABLE', assigned_to BIGINT, assigned_time TIMESTAMP)''', commit=True)
    run_query('''ALTER TABLE new_gmail_tasks ADD COLUMN IF NOT EXISTS ss_file_id TEXT''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS task_logs (id SERIAL PRIMARY KEY, task_type TEXT, action TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''', commit=True)
    
    run_query("INSERT INTO admins (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (OWNER_ID,), commit=True)

    default_settings = {
        'bot_status': 'ON', 
        'create_gmail_task': 'ON', 'new_gmail_task': 'ON', 'old_gmail_task': 'ON', 'map_review_task': 'ON', 'withdraw': 'ON',
        'vis_create_gmail': 'ON', 'vis_new_gmail': 'ON', 'vis_old_gmail': 'ON', 'vis_map': 'ON', 'vis_withdraw': 'ON',
        'min_upi': '15.0', 'min_usdt': '0.16', 'gmail_password': 'ethicbro999', 
        'reward_gmail': '15.0', 'reward_oldgmail': '15.0', 'reward_map': '10.0',
        'reward_newgmail_single': '20.0', 'reward_newgmail_bulk': '25.0',
        'map_rules': '1. Open the provided link.\n2. Submit a 5-Star rating.\n3. Copy the exact text below and post it.\n4. Take a clear screenshot and submit it here.',
        'warning_photo': 'none',
        'alert_photo_gmail': 'none', 'alert_text_gmail': '🚀 Hurry up! New Gmail tasks are available in the bot.',
        'alert_photo_map': 'none', 'alert_text_map': '🚀 Hurry up! New Map Review tasks are available in the bot.'
    }
    for k, v in default_settings.items():
        run_query("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", (k, v), commit=True)

init_db()

# --- HELPERS ---
def is_admin(user_id):
    if user_id == OWNER_ID: return True
    res = run_query("SELECT user_id FROM admins WHERE user_id=%s", (user_id,), fetch='one')
    return res is not None

def get_setting(key):
    res = run_query("SELECT value FROM settings WHERE key=%s", (key,), fetch='one')
    return res[0] if res else 'none'

def update_setting(key, value):
    run_query("UPDATE settings SET value=%s WHERE key=%s", (str(value), key), commit=True)

def get_balance(user_id):
    res = run_query("SELECT balance FROM users WHERE user_id=%s", (user_id,), fetch='one')
    if res: return res[0]
    run_query("INSERT INTO users (user_id, balance) VALUES (%s, %s)", (user_id, 0), commit=True)
    return 0

def add_balance(user_id, amount, detail):
    current = get_balance(user_id)
    run_query("UPDATE users SET balance=%s WHERE user_id=%s", (current + amount, user_id), commit=True)
    date_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_query("INSERT INTO history (user_id, type, amount, detail, date) VALUES (%s, %s, %s, %s, %s)", (user_id, "CREDIT", amount, detail, date_now), commit=True)

def deduct_balance(user_id, amount, detail):
    current = get_balance(user_id)
    run_query("UPDATE users SET balance=%s WHERE user_id=%s", (current - amount, user_id), commit=True)
    date_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_query("INSERT INTO history (user_id, type, amount, detail, date) VALUES (%s, %s, %s, %s, %s)", (user_id, "DEBIT", amount, detail, date_now), commit=True)

def get_all_users():
    records = run_query("SELECT user_id FROM users", fetch='all')
    return [row[0] for row in records] if records else []

def free_expired_gmail_tasks():
    run_query("UPDATE new_gmail_tasks SET status='AVAILABLE', assigned_to=NULL, assigned_time=NULL WHERE status='PENDING' AND EXTRACT(EPOCH FROM (NOW() - assigned_time)) > 900", commit=True)

def process_broadcast(admin_id, msg_id):
    success, failed = 0, 0
    for u in get_all_users():
        try:
            bot.copy_message(chat_id=u, from_chat_id=admin_id, message_id=msg_id)
            success += 1
            time.sleep(0.035) 
        except: failed += 1
    try: bot.send_message(admin_id, f"✅ <b>Broadcast Completed Successfully!</b>\n\n🚀 Delivered: {success}\n❌ Failed: {failed}", parse_mode="HTML")
    except: pass

def auto_broadcast_stock(count, task_type):
    if task_type == 'gmail':
        photo_id = get_setting('alert_photo_gmail')
        raw_text = get_setting('alert_text_gmail')
        t_name = "New Gmail Tasks"
    else:
        photo_id = get_setting('alert_photo_map')
        raw_text = get_setting('alert_text_map')
        t_name = "Map Review Tasks"
        
    msg = f"🚀 <b>NEW TASKS AVAILABLE!</b>\n\n📌 <b>Stock Added:</b> {count} {t_name}\n━━━━━━━━━━━━━━━━━━\n{raw_text}"
    users = get_all_users()
    for u in users:
        try:
            if photo_id and photo_id != 'none' and photo_id != '0':
                bot.send_photo(u, photo_id, caption=msg, parse_mode="HTML")
            else:
                bot.send_message(u, msg, parse_mode="HTML")
            time.sleep(0.035)
        except: pass

def admin_markup(user_id):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("⚙️ Bot Settings", callback_data="adm_panel_settings"))
    markup.row(InlineKeyboardButton("📧 Gmail Panel", callback_data="adm_panel_gmail"), InlineKeyboardButton("🗺️ Map Panel", callback_data="adm_panel_map"))
    markup.row(InlineKeyboardButton("📊 Dashboard & Pending Tasks", callback_data="adm_panel_dash"))
    markup.row(InlineKeyboardButton("📢 Send Broadcast", callback_data="admin_broadcast"), InlineKeyboardButton("💸 Add Balance", callback_data="admin_addbal"))
    return markup

def main_menu(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    row1 = []
    if get_setting('vis_new_gmail') == 'ON': row1.append(KeyboardButton("📧 Get New Gmail Task"))
    if get_setting('vis_create_gmail') == 'ON': row1.append(KeyboardButton("📧 Create Gmail Task"))
    if row1: markup.row(*row1)
    
    row2 = []
    if get_setting('vis_old_gmail') == 'ON': row2.append(KeyboardButton("📧 Old Gmail Task"))
    if get_setting('vis_map') == 'ON': row2.append(KeyboardButton("🗺️ Map Review Task"))
    if row2: markup.row(*row2)
    
    row3 = [KeyboardButton("💰 Wallet")]
    if get_setting('vis_withdraw') == 'ON': row3.append(KeyboardButton("💸 Withdraw"))
    markup.row(*row3)
    
    markup.row(KeyboardButton("📞 Contact & Help"))
    if is_admin(user_id): markup.row(KeyboardButton("⚙️ Admin Panel"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    username = message.from_user.username
    uname_str = f"@{username}" if username else str(message.from_user.first_name)
    
    if get_setting('bot_status') == 'OFF' and not is_admin(user_id):
        bot.send_message(user_id, "🛠️ <b>Bot Is Under Maintenance Fixing Bug And Updating</b>\nPlease check back later.", parse_mode="HTML")
        return
        
    res = run_query("SELECT user_id FROM users WHERE user_id=%s", (user_id,), fetch='one')
    get_balance(user_id) 
    run_query("UPDATE users SET username=%s WHERE user_id=%s", (uname_str, user_id), commit=True)
    
    if res is None and not is_admin(user_id):
        try: bot.send_message(OWNER_ID, f"🚀 <b>New User Registration</b>\n\n👤 <b>User ID:</b> <code>{user_id}</code>\n🔗 <b>Username:</b> {uname_str}", parse_mode="HTML")
        except: pass

    msg = (f"✨ <b>𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗧𝗢 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗘𝗔𝗥𝗡𝗜𝗡𝗚𝗦</b> ✨\n\n"
           f"Greetings <b>{message.from_user.first_name}</b>, we are delighted to have you here! 💼\n\n"
           f"Complete verified micro-tasks and earn real cash instantly directly to your account.\n\n"
           f"🔰 <b>Please select an option below to begin:</b>")
    bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=main_menu(user_id))

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_all_messages(message):
    user_id = message.chat.id
    text = message.text if message.text else message.caption

    username = message.from_user.username
    uname_str = f"@{username}" if username else str(message.from_user.first_name)
    run_query("UPDATE users SET username=%s WHERE user_id=%s", (uname_str, user_id), commit=True)

    if get_setting('bot_status') == 'OFF' and not is_admin(user_id):
        bot.send_message(user_id, "🛠️ <b>Bot Is Under Maintenance Fixing Bug And Updating</b>\nPlease check back later.", parse_mode="HTML")
        return

    # ADMIN STATES
    if user_id in user_states:
        state = user_states[user_id].get('state')

        if state == 'admin_wait_warning_photo' and is_admin(user_id):
            if message.content_type == 'photo':
                update_setting('warning_photo', message.photo[-1].file_id)
                bot.send_message(user_id, "✅ <b>Warning Photo Saved Successfully!</b>", parse_mode="HTML")
            else:
                update_setting('warning_photo', 'none')
                bot.send_message(user_id, "✅ <b>Warning Photo Removed.</b>", parse_mode="HTML")
            del user_states[user_id]
            bot.send_message(user_id, "🛠️ <b>EXECUTIVE DASHBOARD</b>", parse_mode="HTML", reply_markup=admin_markup(user_id))
            return

        if state == 'admin_wait_alert_gmail' and is_admin(user_id):
            if message.content_type == 'photo':
                update_setting('alert_photo_gmail', message.photo[-1].file_id)
                update_setting('alert_text_gmail', message.caption if message.caption else "New Gmail Tasks Added!")
            else:
                update_setting('alert_photo_gmail', 'none')
                update_setting('alert_text_gmail', text if text else "New Gmail Tasks Added!")
            bot.send_message(user_id, "✅ <b>Gmail Auto-Broadcast Configuration Saved!</b>", parse_mode="HTML")
            del user_states[user_id]
            bot.send_message(user_id, "🛠️ <b>EXECUTIVE DASHBOARD</b>", parse_mode="HTML", reply_markup=admin_markup(user_id))
            return
            
        if state == 'admin_wait_alert_map' and is_admin(user_id):
            if message.content_type == 'photo':
                update_setting('alert_photo_map', message.photo[-1].file_id)
                update_setting('alert_text_map', message.caption if message.caption else "New Map Tasks Added!")
            else:
                update_setting('alert_photo_map', 'none')
                update_setting('alert_text_map', text if text else "New Map Tasks Added!")
            bot.send_message(user_id, "✅ <b>Map Auto-Broadcast Configuration Saved!</b>", parse_mode="HTML")
            del user_states[user_id]
            bot.send_message(user_id, "🛠️ <b>EXECUTIVE DASHBOARD</b>", parse_mode="HTML", reply_markup=admin_markup(user_id))
            return

        if state == 'admin_wait_broadcast' and is_admin(user_id):
            del user_states[user_id] 
            bot.send_message(user_id, "🚀 <b>Broadcast Started in background!</b>\nYou can keep using the bot, you will be notified when it finishes.", parse_mode="HTML", reply_markup=main_menu(user_id))
            threading.Thread(target=process_broadcast, args=(user_id, message.message_id)).start()
            return
            
        if state == 'new_gmail_task_ss':
            if message.content_type == 'photo':
                tid = user_states[user_id]['task_id']
                file_id = message.photo[-1].file_id
                run_query("UPDATE new_gmail_tasks SET status='SUBMITTED', ss_file_id=%s WHERE id=%s", (file_id, tid), commit=True)
                
                t_gm = run_query("SELECT gmail FROM new_gmail_tasks WHERE id=%s", (tid,), fetch='one')
                t_gmail = t_gm[0] if t_gm else "Unknown"
                
                r_single = get_setting('reward_newgmail_single')
                r_bulk = get_setting('reward_newgmail_bulk')
                
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton(f"✅ Appr (₹{r_single})", callback_data=f"ngmappr_{r_single}_{tid}_{user_id}"), 
                           InlineKeyboardButton(f"✅ Appr (₹{r_bulk})", callback_data=f"ngmappr_{r_bulk}_{tid}_{user_id}"))
                markup.row(InlineKeyboardButton("❌ Reject", callback_data=f"ngmrej_{tid}_{user_id}"))
                
                bot.send_photo(OWNER_ID, file_id, caption=f"🔔 <b>NEW GMAIL TASK PROOF</b>\n👤 <code>{user_id}</code>\n🔖 Task ID: <code>{tid}</code>\n📧 Gmail: <code>{t_gmail}</code>", parse_mode="HTML", reply_markup=markup)
                bot.send_message(user_id, "✅ <b>Your screenshot has been submitted to the admin. Please wait at least 24 hours for validation.</b>", parse_mode="HTML", reply_markup=main_menu(user_id))
                del user_states[user_id]
                return
            else:
                bot.send_message(user_id, "❌ Kripya Screenshot (Photo) bhejein.")
                return

        if state == 'gmail_task_screenshot':
            if message.content_type == 'photo':
                gmail_name = user_states[user_id]['gmail_name']
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"apprt_{user_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"rejct_{user_id}"))
                bot.send_photo(OWNER_ID, message.photo[-1].file_id, caption=f"🔔 <b>LEGACY GMAIL TASK SUBMISSION</b>\n👤 <code>{user_id}</code>\n📧 <code>{gmail_name}</code>", parse_mode="HTML", reply_markup=markup)
                bot.send_message(user_id, "✅ <b>Your screenshot has been submitted to the admin. Please wait at least 24 hours for validation.</b>", parse_mode="HTML", reply_markup=main_menu(user_id))
                del user_states[user_id]
                return
            else:
                bot.send_message(user_id, "❌ Invalid format. Please upload a clear <b>Screenshot (Photo)</b>.")
                return
        
        if state == 'map_task_screenshot':
            if message.content_type == 'photo':
                task_id = user_states[user_id]['task_id']
                file_id = message.photo[-1].file_id
                
                run_query("UPDATE map_tasks SET status='SUBMITTED', ss_file_id=%s WHERE id=%s", (file_id, task_id), commit=True)
                task_data = run_query("SELECT link, review_text FROM map_tasks WHERE id=%s", (task_id,), fetch='one')
                t_link, t_txt = task_data if task_data else ("Unknown", "Unknown")

                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"mappr_{user_id}_{task_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"mrej_{user_id}_{task_id}"))
                
                admin_msg = (f"🗺️ <b>MAP REVIEW VERIFICATION</b>\n👤 <code>{user_id}</code>\n🔖 Task ID: {task_id}\n\n"
                             f"🔗 <b>Assigned Link:</b>\n{t_link}\n\n"
                             f"💬 <b>Assigned Text:</b>\n<code>{t_txt}</code>")
                
                bot.send_photo(OWNER_ID, file_id, caption=admin_msg, parse_mode="HTML", reply_markup=markup)
                bot.send_message(user_id, "✅ <b>Your screenshot has been submitted to the admin. Please wait at least 24 hours for validation.</b>", parse_mode="HTML", reply_markup=main_menu(user_id))
                del user_states[user_id]
                return
            else:
                bot.send_message(user_id, "❌ Invalid format. Please upload a clear <b>Screenshot (Photo)</b>.")
                return

    if message.content_type == 'text':
        if text == "📧 Get New Gmail Task":
            if get_setting('new_gmail_task') == 'OFF' and not is_admin(user_id): 
                bot.send_message(user_id, "❌ <b>Bot Option Is Now Closed By Admin</b>", parse_mode="HTML")
                return
            free_expired_gmail_tasks()
            
            r_single = get_setting('reward_newgmail_single')
            r_bulk = get_setting('reward_newgmail_bulk')
            
            msg = "📧 <b>SELECT GMAIL TASK TYPE</b>\n\nChoose how many tasks you want to process at once:"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton(f"👤 Single Task (₹{r_single})", callback_data="ngm_type_single"))
            markup.row(InlineKeyboardButton(f"📚 Bulk Task (₹{r_bulk}/each)", callback_data="ngm_type_bulk"))
            markup.row(InlineKeyboardButton("🔙 Cancel", callback_data="back_to_main"))
            bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)

        elif text == "📧 Create Gmail Task":
            if get_setting('create_gmail_task') == 'OFF' and not is_admin(user_id): 
                bot.send_message(user_id, "❌ <b>Bot Option Is Now Closed By Admin</b>", parse_mode="HTML")
                return
            current_pass = get_setting('gmail_password')
            reward = get_setting('reward_gmail')
            msg = (f"📧 <b>GMAIL CREATION TASK</b>\n💰 <b>Reward:</b> ₹{reward}\n\n⚠️ <b>Instructions:</b>\n"
                   f"• Create a brand new Gmail account.\n• Use password:\n🔐 <code>{current_pass}</code>\n\n👉 <i>Click below when Done!</i>")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✅ Mark as Completed", callback_data="task_done"))
            markup.add(InlineKeyboardButton("🔙 Return to Main Menu", callback_data="back_to_main"))
            bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)

        elif text == "📧 Old Gmail Task":
            if get_setting('old_gmail_task') == 'OFF' and not is_admin(user_id): 
                bot.send_message(user_id, "❌ <b>Bot Option Is Now Closed By Admin</b>", parse_mode="HTML")
                return
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 Return to Main Menu", callback_data="back_to_main"))
            bot.send_message(user_id, "📧 <b>OLD GMAIL SUBMISSION</b>\n\n👉 Please provide your valid <b>Old Gmail Address</b>:", parse_mode="HTML", reply_markup=markup)
            user_states[user_id] = {'state': 'old_gmail_email'}

        elif text == "🗺️ Map Review Task":
            if get_setting('map_review_task') == 'OFF' and not is_admin(user_id): 
                bot.send_message(user_id, "❌ <b>Bot Option Is Now Closed By Admin</b>", parse_mode="HTML")
                return
            rules = get_setting('map_rules')
            reward = get_setting('reward_map')
            msg = (f"🗺️ <b>GOOGLE MAPS REVIEW</b>\n💰 <b>Reward:</b> ₹{reward}\n\n📜 <b>Guidelines & Procedure:</b>\n{rules}\n\n👇 <i>Accept the terms below to receive your unique assignment:</i>")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✅ I Agree (Initiate Task)", callback_data="map_agree"))
            markup.add(InlineKeyboardButton("🔙 Return to Main Menu", callback_data="back_to_main"))
            bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)

        elif text == "💰 Wallet":
            balance_inr = get_balance(user_id)
            msg = (f"💼 <b>ACCOUNT DASHBOARD</b>\n━━━━━━━━━━━━━━━━━━━\n"
                   f"💵 <b>Available Balance:</b> ₹{balance_inr:.2f} / ${balance_inr/USDT_TO_INR_RATE:.2f} USD\n━━━━━━━━━━━━━━━━━━━\n\n"
                   f"📊 <b>Recent Transactions:</b>\n")
            records = run_query("SELECT type, amount, detail, date FROM history WHERE user_id=%s ORDER BY id DESC LIMIT 5", (user_id,), fetch='all')
            if not records: msg += "📝 <i>No transaction records found.</i>"
            for r in records: msg += f"{'🟢' if r[0]=='CREDIT' else '🔴'} <b>₹{r[1]}</b> | {r[2]}\n📅 <i>{r[3]}</i>\n\n"
            bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=main_menu(user_id))

        elif text == "📞 Contact & Help":
            bot.send_message(user_id, f"📞 <b>SUPPORT CENTER</b>\n\nFor any inquiries or assistance, please reach out to our administration:\n👨‍💻 <b>Support Desk:</b> @{ADMIN_USERNAME}", parse_mode="HTML", reply_markup=main_menu(user_id))

        elif text == "💸 Withdraw":
            if get_setting('withdraw') == 'OFF' and not is_admin(user_id): 
                bot.send_message(user_id, "❌ <b>Bot Option Is Now Closed By Admin</b>", parse_mode="HTML")
                return
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(KeyboardButton("🏦 UPI"), KeyboardButton("🪙 USDT"))
            markup.row(KeyboardButton("📜 Withdraw History"), KeyboardButton("🔙 Back to Main"))
            bot.send_message(user_id, f"💸 <b>FUNDS WITHDRAWAL</b>\n\nPlease select your preferred payout gateway:\n🔹 <b>UPI</b> (Min Request: ₹{get_setting('min_upi')})\n🔹 <b>USDT</b> (Min Request: ${get_setting('min_usdt')})", parse_mode="HTML", reply_markup=markup)
            
        elif text == "🔙 Back to Main":
            if user_id in user_states: del user_states[user_id]
            bot.send_message(user_id, "🏠 <b>Main Menu</b>", parse_mode="HTML", reply_markup=main_menu(user_id))

        elif text in ["🏦 UPI", "🪙 USDT"]:
            if get_setting('withdraw') == 'OFF' and not is_admin(user_id): return
            bal = get_balance(user_id)
            min_val = float(get_setting('min_upi')) if text == "🏦 UPI" else float(get_setting('min_usdt'))
            check_bal = bal if text == "🏦 UPI" else (bal / USDT_TO_INR_RATE)
            
            if check_bal < min_val:
                bot.send_message(user_id, f"❌ <b>Insufficient Funds.</b> Minimum payout threshold is {min_val}.", parse_mode="HTML", reply_markup=main_menu(user_id))
            else:
                curr = "INR (₹)" if text == "🏦 UPI" else "USDT ($)"
                bot.send_message(user_id, f"📝 Please specify the withdrawal amount in <b>{curr}</b>:", parse_mode="HTML", reply_markup=telebot.types.ReplyKeyboardRemove())
                user_states[user_id] = {'state': 'withdraw_amount', 'method': text}

        elif text == "📜 Withdraw History":
            records = run_query("SELECT detail, amount, date FROM history WHERE user_id=%s AND type='DEBIT' ORDER BY id DESC LIMIT 10", (user_id,), fetch='all')
            if not records: bot.send_message(user_id, "📝 <i>No payout records found.</i>", parse_mode="HTML", reply_markup=main_menu(user_id))
            else:
                msg = "📜 <b>PAYOUT HISTORY:</b>\n━━━━━━━━━━━━━━━━━━━\n"
                for r in records: msg += f"🔴 <b>₹{r[1]}</b> | {r[0]}\n📅 <i>{r[2]}</i>\n\n"
                bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=main_menu(user_id))

        elif text == "⚙️ Admin Panel" and is_admin(user_id):
            bot.send_message(user_id, "🛠️ <b>EXECUTIVE DASHBOARD</b>\nPlease select a category:", parse_mode="HTML", reply_markup=admin_markup(user_id))

        # --- ADMIN CHAT STATES ---
        elif user_id in user_states:
            state_data = user_states[user_id]
            st = state_data['state']

            if st == 'admin_ngm_add_single' and is_admin(user_id):
                try:
                    gmail, pwd = text.split('|', 1)
                    run_query("INSERT INTO new_gmail_tasks (gmail, password) VALUES (%s, %s)", (gmail.strip(), pwd.strip()), commit=True)
                    bot.send_message(user_id, "✅ Single New Gmail Task Added!", reply_markup=main_menu(user_id))
                    threading.Thread(target=auto_broadcast_stock, args=(1, "gmail")).start()
                except: bot.send_message(user_id, "❌ Format error. Use: email | pass")
                del user_states[user_id]

            elif st == 'admin_ngm_bulk_pass' and is_admin(user_id):
                user_states[user_id] = {'state': 'admin_ngm_bulk_emails', 'pass': text.strip()}
                bot.send_message(user_id, "📧 <b>STEP 2: Enter Gmails</b>\nNow send the list of all Gmails (one per line). Sab par yahi password lagega:", parse_mode="HTML")

            elif st == 'admin_ngm_bulk_emails' and is_admin(user_id):
                lines = text.split('\n')
                pwd = user_states[user_id]['pass']
                added = 0
                for line in lines:
                    gm = line.strip()
                    if gm:
                        run_query("INSERT INTO new_gmail_tasks (gmail, password) VALUES (%s, %s)", (gm, pwd), commit=True)
                        added += 1
                bot.send_message(user_id, f"✅ <b>Bulk Import Done!</b> Added {added} Gmails to stock.", parse_mode="HTML", reply_markup=main_menu(user_id))
                del user_states[user_id]
                threading.Thread(target=auto_broadcast_stock, args=(added, "gmail")).start()

            elif st == 'admin_ngm_manage_id' and is_admin(user_id):
                try:
                    tid = int(text.strip())
                    run_query("DELETE FROM new_gmail_tasks WHERE id=%s", (tid,), commit=True)
                    bot.send_message(user_id, f"✅ Deleted Gmail Task ID {tid}", reply_markup=main_menu(user_id))
                except: bot.send_message(user_id, "❌ Invalid ID")
                del user_states[user_id]

            elif st == 'admin_map_manage_id' and is_admin(user_id):
                try:
                    tid = int(text.strip())
                    task = run_query("SELECT link, review_text, status FROM map_tasks WHERE id=%s", (tid,), fetch='one')
                    if not task: bot.send_message(user_id, "❌ Invalid Task ID.", reply_markup=main_menu(user_id))
                    else:
                        msg = f"🛠️ <b>MANAGE TASK ID:</b> <code>{tid}</code>\n━━━━━━━━━━━━━━━━━━━\n🔗 <b>Link:</b> {task[0]}\n💬 <b>Text:</b> <code>{task[1]}</code>\n📌 <b>Status:</b> {task[2]}"
                        markup = InlineKeyboardMarkup()
                        markup.row(InlineKeyboardButton("🗑️ Delete Task", callback_data=f"mdel_{tid}"))
                        markup.row(InlineKeyboardButton("🔗 Edit Link", callback_data=f"medl_{tid}"), InlineKeyboardButton("💬 Edit Text", callback_data=f"medt_{tid}"))
                        bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)
                except ValueError: bot.send_message(user_id, "❌ Kripya valid numeric Task ID dalein.")
                del user_states[user_id]

            elif st == 'admin_map_edit_link' and is_admin(user_id):
                tid = state_data['task_id']; run_query("UPDATE map_tasks SET link=%s WHERE id=%s", (text.strip(), tid), commit=True)
                bot.send_message(user_id, f"✅ Task {tid} ka Link Update ho gaya!", reply_markup=main_menu(user_id))
                del user_states[user_id]

            elif st == 'admin_map_edit_text' and is_admin(user_id):
                tid = state_data['task_id']; run_query("UPDATE map_tasks SET review_text=%s WHERE id=%s", (text.strip(), tid), commit=True)
                bot.send_message(user_id, f"✅ Task {tid} ka Review Text Update ho gaya!", reply_markup=main_menu(user_id))
                del user_states[user_id]

            elif st == 'admin_set_map_rules' and is_admin(user_id):
                update_setting('map_rules', text); bot.send_message(user_id, "✅ Map Task Rules updated successfully!", reply_markup=main_menu(user_id))
                del user_states[user_id]

            elif st == 'admin_map_add_single' and is_admin(user_id):
                try:
                    link, rev_txt = text.split('|', 1)
                    run_query("INSERT INTO map_tasks (link, review_text) VALUES (%s, %s)", (link.strip(), rev_txt.strip()), commit=True)
                    bot.send_message(user_id, "✅ Single Map Task Added!", reply_markup=main_menu(user_id))
                    threading.Thread(target=auto_broadcast_stock, args=(1, "map")).start()
                except: bot.send_message(user_id, "❌ Format galat hai. (Link | Text) use karein.")
                del user_states[user_id]

            elif st == 'admin_map_add_bulk' and is_admin(user_id):
                lines = text.split('\n')
                added = 0
                for line in lines:
                    if '|' in line:
                        link, rev_txt = line.split('|', 1)
                        run_query("INSERT INTO map_tasks (link, review_text) VALUES (%s, %s)", (link.strip(), rev_txt.strip()), commit=True)
                        added += 1
                bot.send_message(user_id, f"✅ Bulk Import Done! Added {added} tasks in Stock.", reply_markup=main_menu(user_id))
                del user_states[user_id]
                threading.Thread(target=auto_broadcast_stock, args=(added, "map")).start()

            elif st.startswith('admin_set_reward_') and is_admin(user_id):
                try:
                    val = float(text)
                    key = st.replace('admin_set_', '') 
                    update_setting(key, val)
                    bot.send_message(user_id, f"✅ Configuration applied. Reward updated to ₹{val}", reply_markup=main_menu(user_id))
                    del user_states[user_id]
                except ValueError: bot.send_message(user_id, "❌ Please input a valid numeric value.")

            elif st == 'admin_add_id' and user_id == OWNER_ID:
                try:
                    run_query("INSERT INTO admins (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (int(text),), commit=True)
                    bot.send_message(user_id, f"✅ Administrator Privileges Granted!", reply_markup=main_menu(user_id))
                    del user_states[user_id]
                except: bot.send_message(user_id, "❌ Invalid Identity.")

            elif st == 'admin_remove_id' and user_id == OWNER_ID:
                try:
                    run_query("DELETE FROM admins WHERE user_id=%s", (int(text),), commit=True)
                    bot.send_message(user_id, f"✅ Administrator Privileges Revoked!", reply_markup=main_menu(user_id))
                    del user_states[user_id]
                except: bot.send_message(user_id, "❌ Invalid Identity.")

            elif st == 'gmail_task_name':
                user_states[user_id] = {'state': 'gmail_task_screenshot', 'gmail_name': text.strip()}
                bot.send_message(user_id, f"📸 <b>Account Verified:</b> <code>{text.strip()}</code>\n👉 Please securely upload your <b>Screenshot</b> for final validation:", parse_mode="HTML")

            elif st == 'admin_set_gmail_pass' and is_admin(user_id):
                update_setting('gmail_password', text.strip()); bot.send_message(user_id, f"✅ Security Key updated to: <code>{text.strip()}</code>", parse_mode="HTML", reply_markup=main_menu(user_id))
                del user_states[user_id]

            elif st == 'admin_set_min_upi' and is_admin(user_id):
                try: update_setting('min_upi', float(text)); bot.send_message(user_id, f"✅ UPI Limit Set to ₹{text}", reply_markup=main_menu(user_id)); del user_states[user_id]
                except: bot.send_message(user_id, "❌ Invalid format.")

            elif st == 'admin_set_min_usdt' and is_admin(user_id):
                try: update_setting('min_usdt', float(text)); bot.send_message(user_id, f"✅ USDT Limit Set to ${text}", reply_markup=main_menu(user_id)); del user_states[user_id]
                except: bot.send_message(user_id, "❌ Invalid format.")

            elif st == 'old_gmail_email':
                user_states[user_id] = {'state': 'old_gmail_password', 'gmail_email': text.strip()}
                bot.send_message(user_id, f"✅ <b>Data Recorded:</b> <code>{text.strip()}</code>\n👉 Kindly provide the associated <b>Security Password</b>:", parse_mode="HTML")

            elif st == 'old_gmail_password':
                bot.send_message(user_id, "✅ <b>Your screenshot has been submitted to the admin. Please wait at least 24 hours for validation.</b>", parse_mode="HTML", reply_markup=main_menu(user_id))
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"oldappr_{user_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"oldrej_{user_id}"))
                bot.send_message(OWNER_ID, f"🔔 <b>OLD GMAIL SUBMISSION</b>\n👤 <code>{user_id}</code>\n📧 <code>{state_data['gmail_email']}</code>\n🔑 <code>{text.strip()}</code>", parse_mode="HTML", reply_markup=markup)
                del user_states[user_id]

            elif st == 'withdraw_amount':
                try:
                    val = float(text)
                    bal = get_balance(user_id)
                    meth = state_data['method']
                    if meth == "🏦 UPI":
                        if val < float(get_setting('min_upi')) or val > bal: raise Exception
                    else:
                        if val < float(get_setting('min_usdt')) or (val*USDT_TO_INR_RATE) > bal: raise Exception
                    user_states[user_id]['amt'] = val
                    user_states[user_id]['state'] = 'withdraw_address'
                    bot.send_message(user_id, f"✅ Value acknowledged. Please provide your precise <b>UPI/BP20 Destination Address</b>:", parse_mode="HTML")
                except:
                    bot.send_message(user_id, "❌ Limit anomaly or insufficient account balance detected.", reply_markup=main_menu(user_id))
                    del user_states[user_id]

            elif st == 'withdraw_address':
                meth = state_data['method']
                val = state_data['amt']
                val_inr = val if meth == "🏦 UPI" else val * USDT_TO_INR_RATE
                deduct_balance(user_id, val_inr, f"Pending {meth} Withdraw ({val})")
                
                pid = run_query("INSERT INTO pending_withdraws (user_id, method, address, amount) VALUES (%s, %s, %s, %s) RETURNING id", (user_id, meth, text.strip(), val), fetch='id', commit=True)
                bot.send_message(user_id, "✅ <b>Disbursement Request Logged!</b>\nYour transaction will be processed post administrative clearance.", parse_mode="HTML", reply_markup=main_menu(user_id))
                
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"apprw_{pid}"), InlineKeyboardButton("❌ Reject", callback_data=f"rejcc_{pid}"))
                bot.send_message(OWNER_ID, f"🔔 <b>PAYOUT REQUEST</b>\n👤 <code>{user_id}</code>\n🏦 {meth}\n💰 {val}\n📌 <code>{text.strip()}</code>", parse_mode="HTML", reply_markup=markup)
                del user_states[user_id]

            elif st == 'admin_wait_uid' and is_admin(user_id):
                try: user_states[user_id] = {'state': 'admin_wait_amt', 'uid': int(text)}; bot.send_message(user_id, "👉 Provide target amount in ₹:")
                except: del user_states[user_id]

            elif st == 'admin_wait_amt' and is_admin(user_id):
                try:
                    add_balance(state_data['uid'], float(text), "Admin Added Balance")
                    bot.send_message(user_id, "✅ Liquidity successfully routed!", reply_markup=main_menu(user_id))
                    try: bot.send_message(state_data['uid'], f"🎉 <b>System Notification</b>\nAn administrative bonus of ₹{text} has been credited to your portfolio!", parse_mode="HTML")
                    except: pass
                except: pass
                del user_states[user_id]

# --- SECURED CALLBACK QUERIES ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.message.chat.id
    data = call.data
    
    # 🔥 Answer instantly to stop loading icon
    bot.answer_callback_query(call.id)

    if data == "back_to_main":
        if user_id in user_states: del user_states[user_id]
        try: bot.delete_message(user_id, call.message.message_id)
        except: pass
        bot.send_message(user_id, "🏠 <b>Main Menu</b>", parse_mode="HTML", reply_markup=main_menu(user_id))

    elif data.startswith("ngm_type_"):
        if get_setting('new_gmail_task') == 'OFF' and not is_admin(user_id):
            bot.send_message(user_id, "❌ Bot Option Is Now Closed By Admin", parse_mode="HTML")
            return
            
        mode = data.split("_")[2]
        r_single = get_setting('reward_newgmail_single')
        r_bulk = get_setting('reward_newgmail_bulk')
        
        msg = (f"⚠️ <b>INSTRUCTIONS & WARNING</b>\n\n"
               f"<b>Submit Like This After Created Gmail 👇</b>\n\n"
               f"🔹 Single Task Reward: ₹{r_single}\n"
               f"🔹 Bulk Task Reward: ₹{r_bulk} (per account)\n\n"
               f"<i>(Wrong screenshot = No payment and Account Ban!)</i>")
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("✅ Got It", callback_data=f"ngm_go_{mode}"), InlineKeyboardButton("❌ Cancel", callback_data="back_to_main"))
        
        try: bot.delete_message(user_id, call.message.message_id)
        except: pass
        
        warn_photo = get_setting('warning_photo')
        if warn_photo and warn_photo != 'none':
            try: bot.send_photo(user_id, warn_photo, caption=msg, parse_mode="HTML", reply_markup=markup)
            except: bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)
        else:
            bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)

    elif data.startswith("ngm_go_"):
        mode = data.split("_")[2]
        free_expired_gmail_tasks()
        
        pend_chk = run_query("SELECT count(id) FROM new_gmail_tasks WHERE assigned_to=%s AND status='PENDING'", (user_id,), fetch='one')[0]
        if pend_chk > 0:
            bot.send_message(user_id, f"⚠️ Aapke paas pehle se pending tasks hain! Unhe submit ya cancel karein.", parse_mode="HTML")
            return

        limit = 1 if mode == "single" else 10
        tasks = run_query(f'''
            UPDATE new_gmail_tasks SET status='PENDING', assigned_to=%s, assigned_time=NOW() 
            WHERE id IN (SELECT id FROM new_gmail_tasks WHERE status='AVAILABLE' LIMIT {limit} FOR UPDATE SKIP LOCKED) 
            RETURNING id, gmail, password
        ''', (user_id,), fetch='all', commit=True)
        
        if not tasks:
            bot.send_message(user_id, "🚫 Stock is currently empty! Try again later.", parse_mode="HTML")
            return
            
        try: bot.delete_message(user_id, call.message.message_id)
        except: pass
        
        bot.send_message(user_id, f"🎉 <b>Tasks Allocated!</b>\n\nEk baar me sirf utne hi tasks mile hain jitne stock me the (Max {limit}).", parse_mode="HTML")
        
        for t in tasks:
            tid, t_gmail, t_pass = t
            msg = (f"📧 <b>GMAIL TASK DETAILS</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
                   f"<b>Gmail Name:</b> <code>{t_gmail}</code>\n"
                   f"<b>Password:</b> <code>{t_pass}</code>\n\n"
                   f"⏳ <b>Time Limit</b> ➔ 15 Minutes\n\n"
                   f"<i>Click 'Submit Proof' to send screenshot.</i>")
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("📤 Submit Proof", callback_data=f"ngm_ss_{tid}"), InlineKeyboardButton("❌ Cancel Task", callback_data=f"ngm_cancel_{tid}"))
            bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)

    elif data.startswith("ngm_ss_"):
        tid = int(data.split("_")[2])
        user_states[user_id] = {'state': 'new_gmail_task_ss', 'task_id': tid}
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Cancel Action", callback_data="back_to_main"))
        bot.send_message(user_id, "📸 <b>Awaiting Validation:</b>\nUpload your screenshot for this specific Gmail:", parse_mode="HTML", reply_markup=markup)

    elif data.startswith("ngm_cancel_"):
        tid = int(data.split("_")[2])
        run_query("UPDATE new_gmail_tasks SET status='AVAILABLE', assigned_to=NULL, assigned_time=NULL WHERE id=%s", (tid,), commit=True)
        bot.edit_message_text("❌ <b>Task Cancelled.</b> Returned safely to stock.", user_id, call.message.message_id, parse_mode="HTML")

    elif data.startswith("ngmappr_"):
        amt = float(data.split("_")[1])
        tid = int(data.split("_")[2])
        tgt = int(data.split("_")[3])
        
        t_gmail = run_query("SELECT gmail FROM new_gmail_tasks WHERE id=%s", (tid,), fetch='one')
        t_gmail = t_gmail[0] if t_gmail else "Unknown"
        
        add_balance(tgt, amt, f"New Gmail Task Approved (ID: {tid})")
        run_query("UPDATE new_gmail_tasks SET status='COMPLETED' WHERE id=%s", (tid,), commit=True)
        run_query("INSERT INTO task_logs (task_type, action) VALUES ('GMAIL', 'APPROVE')", commit=True)
        
        try: bot.send_message(tgt, f"🎉 <b>Gmail Task Approved!</b> ₹{amt} added.", parse_mode="HTML")
        except: pass
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⏭️ Next Pending Task", callback_data="review_pend_gmail"))
        markup.add(InlineKeyboardButton("🔙 Dashboard", callback_data="adm_panel_dash"))
        try: bot.edit_message_caption(f"✅ Approved (₹{amt}) | User: {tgt}\n📧 Gmail: <code>{t_gmail}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        except: pass

    elif data.startswith("ngmrej_"):
        tid = int(data.split("_")[1])
        tgt = int(data.split("_")[2])
        
        t_gmail = run_query("SELECT gmail FROM new_gmail_tasks WHERE id=%s", (tid,), fetch='one')
        t_gmail = t_gmail[0] if t_gmail else "Unknown"
        
        run_query("UPDATE new_gmail_tasks SET status='AVAILABLE', assigned_to=NULL, assigned_time=NULL WHERE id=%s", (tid,), commit=True)
        run_query("INSERT INTO task_logs (task_type, action) VALUES ('GMAIL', 'REJECT')", commit=True)
        
        try: bot.send_message(tgt, "❌ <b>Your Task Rejected: Gmail Problem.</b>", parse_mode="HTML")
        except: pass
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⏭️ Next Pending Task", callback_data="review_pend_gmail"))
        markup.add(InlineKeyboardButton("🔙 Dashboard", callback_data="adm_panel_dash"))
        try: bot.edit_message_caption(f"❌ Rejected (Re-queued) | User: {tgt}\n📧 Gmail: <code>{t_gmail}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        except: pass

    elif data == "map_agree":
        if get_setting('map_review_task') == 'OFF' and not is_admin(user_id):
            bot.send_message(user_id, "❌ Bot Option Is Now Closed By Admin", parse_mode="HTML")
            return
        
        chk = run_query("SELECT id, link, review_text FROM map_tasks WHERE assigned_to=%s AND status='PENDING'", (user_id,), fetch='one')
        if chk:
            t_id, t_link, t_txt = chk
            msg = f"⚠️ <b>Action Blocked</b>\nYou currently hold an active unresolved assignment:\n\n🔗 <b>Assigned Resource:</b>\n{t_link}\n\n💬 <b>Required Transcript:</b>\n<code>{t_txt}</code>"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("✅ Mark Completed", callback_data=f"mapdone_{t_id}"), InlineKeyboardButton("❌ Cancel", callback_data=f"mapcancel_{t_id}"))
            bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)
            return

        task = run_query('''
            UPDATE map_tasks SET status='PENDING', assigned_to=%s 
            WHERE id = (
                SELECT id FROM map_tasks 
                WHERE status='AVAILABLE' 
                AND review_text NOT IN (SELECT review_text FROM map_tasks WHERE assigned_to=%s AND status='COMPLETED') 
                LIMIT 1 FOR UPDATE SKIP LOCKED
            ) 
            RETURNING id, link, review_text
        ''', (user_id, user_id), fetch='one', commit=True)
        
        if not task:
            bot.send_message(user_id, "🚫 We are currently out of Unique Review Tasks for you!", parse_mode="HTML")
        else:
            t_id, t_link, t_txt = task
            msg = f"🎉 <b>Asset Allocated!</b>\n\n🔗 <b>Target Directory:</b>\n{t_link}\n\n💬 <b>Required Publish Data:</b>\n<code>{t_txt}</code>\n\n👉 <i>Select 'Completed' upon successful execution.</i>"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("✅ Mark Completed", callback_data=f"mapdone_{t_id}"), InlineKeyboardButton("❌ Cancel", callback_data=f"mapcancel_{t_id}"))
            try: bot.delete_message(user_id, call.message.message_id)
            except: pass
            bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)

    elif data.startswith("mapdone_"):
        t_id = data.split("_")[1]
        user_states[user_id] = {'state': 'map_task_screenshot', 'task_id': t_id}
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Discard", callback_data="back_to_main"))
        bot.send_message(user_id, "📸 <b>Awaiting Validation:</b>\nPlease upload your unedited screenshot proof below:", parse_mode="HTML", reply_markup=markup)

    elif data.startswith("mapcancel_"):
        t_id = data.split("_")[1]
        run_query("UPDATE map_tasks SET status='AVAILABLE', assigned_to=NULL WHERE id=%s", (t_id,), commit=True)
        bot.edit_message_text("❌ <b>Operation Aborted.</b> The task has been successfully re-queued to the grid.", user_id, call.message.message_id, parse_mode="HTML")

    elif data == "adm_panel_settings" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        stat = get_setting('bot_status')
        markup.row(InlineKeyboardButton(f"🤖 Bot Power: {stat}", callback_data="admin_bot_toggle"))
        markup.row(InlineKeyboardButton("👁️ Visibility Toggles", callback_data="admin_vis_toggles"), InlineKeyboardButton("⛔ Closed Alerts", callback_data="admin_stat_toggles"))
        markup.row(InlineKeyboardButton("💰 Set Task Rewards", callback_data="admin_reward_menu"), InlineKeyboardButton("⚙️ Auto-Alert Setup", callback_data="admin_set_auto_alert"))
        if user_id == OWNER_ID: markup.row(InlineKeyboardButton("👥 Manage Admins", callback_data="admin_manage"))
        markup.row(InlineKeyboardButton("📊 Total Users", callback_data="admin_total_users"), InlineKeyboardButton("👥 All User Balances", callback_data="admin_user_balances"))
        markup.row(InlineKeyboardButton("⚙️ Set Min Withdraw", callback_data="admin_set_min"), InlineKeyboardButton("🔑 Legacy Pass", callback_data="admin_set_pass"))
        markup.row(InlineKeyboardButton("📜 Approved WDs", callback_data="admin_approved_list"), InlineKeyboardButton("🖼️ Warning Photo", callback_data="admin_set_warning_photo"))
        markup.row(InlineKeyboardButton("🔙 Back to Main Panel", callback_data="admin_back"))
        bot.edit_message_text("⚙️ <b>BOT SETTINGS & CONFIGURATION</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data == "adm_panel_gmail" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("➕ Add Single", callback_data="ngm_add_single"), InlineKeyboardButton("📚 Bulk Add", callback_data="ngm_add_bulk"))
        markup.row(InlineKeyboardButton("📦 View Current Stock", callback_data="ngm_view_stock"), InlineKeyboardButton("🛠️ Delete Task (ID)", callback_data="ngm_manage_id"))
        markup.row(InlineKeyboardButton("🗑️ Delete ALL Gmails", callback_data="ngm_delete_all"))
        markup.row(InlineKeyboardButton("🔙 Back to Main Panel", callback_data="admin_back"))
        free_expired_gmail_tasks()
        avail = run_query("SELECT count(id) FROM new_gmail_tasks WHERE status='AVAILABLE'", fetch='one')[0]
        bot.edit_message_text(f"📧 <b>GMAIL MANAGEMENT PANEL</b>\n━━━━━━━━━━━━━━━━━━━\nAssets in Stock: <b>{avail}</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data == "adm_panel_map" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("➕ Add Single Task", callback_data="map_add_single"), InlineKeyboardButton("📚 Bulk Compile", callback_data="map_add_bulk"))
        markup.row(InlineKeyboardButton("📦 View Current Stock", callback_data="map_view_stock"), InlineKeyboardButton("🛠️ Edit/Delete Task", callback_data="map_manage_task"))
        markup.row(InlineKeyboardButton("📝 Edit Global Rules", callback_data="map_edit_rules"))
        markup.row(InlineKeyboardButton("🔙 Back to Main Panel", callback_data="admin_back"))
        avail = run_query("SELECT count(id) FROM map_tasks WHERE status='AVAILABLE'", fetch='one')[0]
        bot.edit_message_text(f"🗺️ <b>MAP TASKS PANEL</b>\n━━━━━━━━━━━━━━━━━━━\nAssets in Stock: <b>{avail}</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data == "adm_panel_dash" and is_admin(user_id):
        users_count = run_query("SELECT count(user_id) FROM users", fetch='one')[0]
        total_bal = run_query("SELECT sum(balance) FROM users", fetch='one')[0] or 0.0

        wd_appr_all = run_query("SELECT sum(amount) FROM approved_withdraws", fetch='one')[0] or 0.0
        wd_appr_24h = run_query("SELECT sum(amount) FROM approved_withdraws WHERE TO_TIMESTAMP(date, 'YYYY-MM-DD HH24:MI') >= NOW() - INTERVAL '24 hours'", fetch='one')
        wd_appr_24h = wd_appr_24h[0] if wd_appr_24h and wd_appr_24h[0] else 0.0

        task_appr_all = run_query("SELECT count(id) FROM task_logs WHERE action='APPROVE'", fetch='one')[0] or 0
        task_appr_24h = run_query("SELECT count(id) FROM task_logs WHERE action='APPROVE' AND date >= NOW() - INTERVAL '24 hours'", fetch='one')[0] or 0
        task_rej_all = run_query("SELECT count(id) FROM task_logs WHERE action='REJECT'", fetch='one')[0] or 0
        task_rej_24h = run_query("SELECT count(id) FROM task_logs WHERE action='REJECT' AND date >= NOW() - INTERVAL '24 hours'", fetch='one')[0] or 0

        pend_gmail = run_query("SELECT count(id) FROM new_gmail_tasks WHERE status='SUBMITTED'", fetch='one')[0] or 0
        pend_map = run_query("SELECT count(id) FROM map_tasks WHERE status='SUBMITTED'", fetch='one')[0] or 0
        pend_wd = run_query("SELECT count(id) FROM pending_withdraws", fetch='one')[0] or 0

        msg = (f"📊 <b>ADMIN DASHBOARD</b>\n━━━━━━━━━━━━━━━━━━━\n"
               f"👥 <b>Total Users:</b> {users_count}\n"
               f"💰 <b>Total User Balances:</b> ₹{total_bal:.2f}\n\n"
               f"💸 <b>Withdrawals Approved:</b>\n"
               f"   ┣ <i>Last 24 Hrs:</i> ₹{wd_appr_24h:.2f}\n"
               f"   ┗ <i>All Time:</i> ₹{wd_appr_all:.2f}\n\n"
               f"✅ <b>Tasks Approved:</b>\n"
               f"   ┣ <i>Last 24 Hrs:</i> {task_appr_24h}\n"
               f"   ┗ <i>All Time:</i> {task_appr_all}\n\n"
               f"❌ <b>Tasks Rejected:</b>\n"
               f"   ┣ <i>Last 24 Hrs:</i> {task_rej_24h}\n"
               f"   ┗ <i>All Time:</i> {task_rej_all}\n\n"
               f"⏳ <b>PENDING QUEUE:</b>\n"
               f"   ┣ 📧 Gmails: {pend_gmail}\n"
               f"   ┣ 🗺️ Maps: {pend_map}\n"
               f"   ┗ 💸 Withdraws: {pend_wd}")
        
        markup = InlineKeyboardMarkup()
        if pend_gmail > 0: markup.row(InlineKeyboardButton(f"🔍 Review Gmails ({pend_gmail})", callback_data="review_pend_gmail"))
        if pend_map > 0: markup.row(InlineKeyboardButton(f"🔍 Review Maps ({pend_map})", callback_data="review_pend_map"))
        if pend_wd > 0: markup.row(InlineKeyboardButton(f"🔍 Review Withdraws ({pend_wd})", callback_data="review_pend_wd"))
        markup.row(InlineKeyboardButton("🔙 Back to Main Panel", callback_data="admin_back"))
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data == "admin_back" and is_admin(user_id):
        bot.edit_message_text("🛠️ <b>EXECUTIVE DASHBOARD</b>\nPlease select a category:", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=admin_markup(user_id))

    # PENDING QUEUE REVIEWS
    elif data == "review_pend_gmail" and is_admin(user_id):
        task = run_query("SELECT id, assigned_to, gmail, ss_file_id FROM new_gmail_tasks WHERE status='SUBMITTED' LIMIT 1", fetch='one')
        if task:
            tid, assigned_to, gmail, ss = task
            r_single = get_setting('reward_newgmail_single')
            r_bulk = get_setting('reward_newgmail_bulk')
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton(f"✅ Appr (₹{r_single})", callback_data=f"ngmappr_{r_single}_{tid}_{assigned_to}"), InlineKeyboardButton(f"✅ Appr (₹{r_bulk})", callback_data=f"ngmappr_{r_bulk}_{tid}_{assigned_to}"))
            markup.row(InlineKeyboardButton("❌ Reject", callback_data=f"ngmrej_{tid}_{assigned_to}"))
            markup.row(InlineKeyboardButton("🔙 Dashboard", callback_data="adm_panel_dash"))
            
            try: bot.delete_message(user_id, call.message.message_id)
            except: pass
            
            try: bot.send_photo(user_id, ss, caption=f"🔔 <b>PENDING GMAIL REVIEW</b>\n👤 <code>{assigned_to}</code>\n🔖 Task ID: <code>{tid}</code>\n📧 Gmail: <code>{gmail}</code>", parse_mode="HTML", reply_markup=markup)
            except: bot.send_message(user_id, "⚠️ User ka screenshot expired. Task Reject karo.", reply_markup=markup)
        else:
            bot.send_message(user_id, "No pending Gmail tasks left!", parse_mode="HTML")
            
    elif data == "review_pend_map" and is_admin(user_id):
        task = run_query("SELECT id, assigned_to, link, review_text, ss_file_id FROM map_tasks WHERE status='SUBMITTED' LIMIT 1", fetch='one')
        if task:
            tid, assigned_to, link, text, ss = task
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"mappr_{assigned_to}_{tid}"), InlineKeyboardButton("❌ Reject", callback_data=f"mrej_{assigned_to}_{tid}"))
            markup.row(InlineKeyboardButton("🔙 Dashboard", callback_data="adm_panel_dash"))
            
            try: bot.delete_message(user_id, call.message.message_id)
            except: pass
            
            try: bot.send_photo(user_id, ss, caption=f"🗺️ <b>PENDING MAP REVIEW</b>\n👤 <code>{assigned_to}</code>\n🔖 Task ID: {tid}\n\n🔗 Link: {link}\n💬 Text: <code>{text}</code>", parse_mode="HTML", reply_markup=markup)
            except: bot.send_message(user_id, "⚠️ User ka screenshot expired. Task Reject karo.", reply_markup=markup)
        else:
            bot.send_message(user_id, "No pending Map tasks left!", parse_mode="HTML")

    elif data == "review_pend_wd" and is_admin(user_id):
        req = run_query("SELECT id, user_id, method, address, amount FROM pending_withdraws LIMIT 1", fetch='one')
        if req:
            pid, u_id, meth, addr, amt = req
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"apprw_{pid}"), InlineKeyboardButton("❌ Reject", callback_data=f"rejcc_{pid}"))
            markup.row(InlineKeyboardButton("🔙 Dashboard", callback_data="adm_panel_dash"))
            try: bot.delete_message(user_id, call.message.message_id)
            except: pass
            bot.send_message(user_id, f"🔔 <b>PENDING WITHDRAWAL</b>\n👤 <code>{u_id}</code>\n🏦 {meth}\n💰 {amt}\n📌 <code>{addr}</code>", parse_mode="HTML", reply_markup=markup)
        else:
            bot.send_message(user_id, "No pending withdrawals left!", parse_mode="HTML")

    elif data == "ngm_delete_all" and is_admin(user_id):
        run_query("DELETE FROM new_gmail_tasks", commit=True)
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("➕ Add Single", callback_data="ngm_add_single"), InlineKeyboardButton("📚 Bulk Add", callback_data="ngm_add_bulk"))
        markup.row(InlineKeyboardButton("📦 View Current Stock", callback_data="ngm_view_stock"), InlineKeyboardButton("🛠️ Delete Task (ID)", callback_data="ngm_manage_id"))
        markup.row(InlineKeyboardButton("🗑️ Delete ALL Gmails", callback_data="ngm_delete_all"))
        markup.row(InlineKeyboardButton("🔙 Back to Main Panel", callback_data="admin_back"))
        bot.edit_message_text(f"📧 <b>GMAIL MANAGEMENT PANEL</b>\n━━━━━━━━━━━━━━━━━━━\nAssets in Stock: <b>0</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data == "ngm_add_single" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_ngm_add_single'}
        bot.send_message(user_id, "📝 Execute parameter injection:\n<code>email@gmail.com | password123</code>\n<i>(Strict parameter separation via '|' is mandatory)</i>", parse_mode="HTML")

    elif data == "ngm_add_bulk" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_ngm_bulk_pass'}
        bot.send_message(user_id, "🔑 <b>STEP 1: Set Bulk Password</b>\nEnter the single password that will be applied to ALL Gmail accounts in this bulk list:", parse_mode="HTML")

    elif data == "ngm_manage_id" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_ngm_manage_id'}
        bot.send_message(user_id, "🗑️ Please specify the <b>Task ID</b> you wish to Delete:", parse_mode="HTML")

    elif data == "ngm_view_stock" and is_admin(user_id):
        records = run_query("SELECT id, gmail, status FROM new_gmail_tasks WHERE status != 'COMPLETED' ORDER BY id ASC LIMIT 20", fetch='all')
        if not records:
            bot.send_message(user_id, "📦 Stock is completely empty!", parse_mode="HTML")
            return
        msg = "📦 <b>CURRENT NEW GMAIL STOCK (Top 20)</b>\n━━━━━━━━━━━━━━━━━━━\n"
        for r in records:
            msg += f"🆔 <b>ID:</b> <code>{r[0]}</code> | 📧 {r[1]} | 📌 {r[2]}\n"
        bot.send_message(user_id, msg, parse_mode="HTML")

    elif data == "map_add_single" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_map_add_single'}
        bot.send_message(user_id, "📝 Execute parameter injection:\n<code>Link | Review Text</code>", parse_mode="HTML")

    elif data == "map_add_bulk" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_map_add_bulk'}
        bot.send_message(user_id, "📚 Execute bulk parameter injection (one per line):\n<code>Link1 | Review1</code>\n<code>Link2 | Review2</code>", parse_mode="HTML")

    elif data == "map_edit_rules" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_set_map_rules'}
        bot.send_message(user_id, "📝 Awaiting transmission of new administrative Map Task directives:")

    elif data == "map_view_stock" and is_admin(user_id):
        records = run_query("SELECT id, link, review_text FROM map_tasks WHERE status='AVAILABLE' ORDER BY id ASC LIMIT 15", fetch='all')
        if not records:
            bot.send_message(user_id, "📦 Stock is completely empty!", parse_mode="HTML")
            return
        msg = "📦 <b>CURRENT MAP TASK STOCK</b>\n<i>(Showing oldest 15 tasks)</i>\n━━━━━━━━━━━━━━━━━━━\n"
        for r in records:
            msg += f"🆔 <b>ID:</b> <code>{r[0]}</code>\n🔗 {r[1]}\n💬 <code>{r[2][:25]}...</code>\n\n"
        bot.send_message(user_id, msg, parse_mode="HTML")

    elif data == "map_manage_task" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_map_manage_id'}
        bot.send_message(user_id, "📝 Please specify the <b>Task ID</b> you wish to Edit or Delete:", parse_mode="HTML")

    elif data.startswith("mdel_") and is_admin(user_id):
        tid = int(data.split("_")[1])
        run_query("DELETE FROM map_tasks WHERE id=%s", (tid,), commit=True)
        bot.edit_message_text(f"✅ <b>Task ID {tid} successfully eradicated from the grid.</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML")

    elif data.startswith("medl_") and is_admin(user_id):
        tid = int(data.split("_")[1])
        user_states[user_id] = {'state': 'admin_map_edit_link', 'task_id': tid}
        bot.send_message(user_id, "🔗 Please insert the updated <b>Resource Link</b>:", parse_mode="HTML")

    elif data.startswith("medt_") and is_admin(user_id):
        tid = int(data.split("_")[1])
        user_states[user_id] = {'state': 'admin_map_edit_text', 'task_id': tid}
        bot.send_message(user_id, "💬 Please insert the updated <b>Review Transcript</b>:", parse_mode="HTML")

    elif data.startswith("mappr_") and is_admin(user_id):
        tgt = int(data.split("_")[1])
        t_id = int(data.split("_")[2])
        rw = float(get_setting('reward_map'))
        add_balance(tgt, rw, "Map Review Approved")
        run_query("UPDATE map_tasks SET status='COMPLETED' WHERE id=%s", (t_id,), commit=True)
        run_query("INSERT INTO task_logs (task_type, action) VALUES ('MAP', 'APPROVE')", commit=True)
        
        try: bot.send_message(tgt, f"🎉 <b>Validation Complete!</b>\n₹{rw} has been allocated to your account.", parse_mode="HTML")
        except: pass
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⏭️ Next Pending Task", callback_data="review_pend_map"))
        markup.add(InlineKeyboardButton("🔙 Dashboard", callback_data="adm_panel_dash"))
        try: bot.edit_message_caption(f"✅ Clearance Granted for <code>{tgt}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        except: pass

    elif data.startswith("mrej_") and is_admin(user_id):
        tgt = int(data.split("_")[1])
        t_id = int(data.split("_")[2])
        run_query("UPDATE map_tasks SET status='AVAILABLE', assigned_to=NULL, ss_file_id=NULL WHERE id=%s", (t_id,), commit=True)
        run_query("INSERT INTO task_logs (task_type, action) VALUES ('MAP', 'REJECT')", commit=True)
        
        try: bot.send_message(tgt, f"❌ <b>Your Task Rejected: Map Review Problem.</b>", parse_mode="HTML")
        except: pass
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⏭️ Next Pending Task", callback_data="review_pend_map"))
        markup.add(InlineKeyboardButton("🔙 Dashboard", callback_data="adm_panel_dash"))
        try: bot.edit_message_caption(f"❌ Clearance Denied (Re-queued) for <code>{tgt}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        except: pass

    elif data == "task_done":
        if get_setting('create_gmail_task') == 'OFF' and not is_admin(user_id): return
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Discard", callback_data="back_to_main"))
        bot.send_message(user_id, "📧 Provide your newly generated <b>Gmail Address</b>:", parse_mode="HTML", reply_markup=markup)
        user_states[user_id] = {'state': 'gmail_task_name'}

    elif data == "admin_reward_menu" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton(f"Create Gmail (₹{get_setting('reward_gmail')})", callback_data="setrw_reward_gmail"))
        markup.row(InlineKeyboardButton(f"New Gmail Single (₹{get_setting('reward_newgmail_single')})", callback_data="setrw_reward_newgmail_single"))
        markup.row(InlineKeyboardButton(f"New Gmail Bulk (₹{get_setting('reward_newgmail_bulk')})", callback_data="setrw_reward_newgmail_bulk"))
        markup.row(InlineKeyboardButton(f"Old Gmail (₹{get_setting('reward_oldgmail')})", callback_data="setrw_reward_oldgmail"))
        markup.row(InlineKeyboardButton(f"Map Review (₹{get_setting('reward_map')})", callback_data="setrw_reward_map"))
        markup.row(InlineKeyboardButton("🔙 Back to Settings", callback_data="adm_panel_settings"))
        bot.edit_message_text("💰 <b>REMUNERATION CONFIGURATION</b>\nSelect parameters to overwrite:", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data.startswith("setrw_") and is_admin(user_id):
        key = data.split("setrw_")[1]
        user_states[user_id] = {'state': f'admin_set_{key}'}
        bot.send_message(user_id, "📝 Designate new numeric threshold (₹):")

    elif data == "admin_manage" and is_admin(user_id) and user_id == OWNER_ID:
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("➕ Add Admin", callback_data="admin_add_btn"), InlineKeyboardButton("➖ Remove Admin", callback_data="admin_rem_btn"))
        
        admins = run_query("SELECT user_id FROM admins WHERE user_id != %s", (OWNER_ID,), fetch='all')
        adm_list = "\n".join([f"👤 <code>{a[0]}</code>" for a in admins]) if admins else "No extra admins."
        
        markup.row(InlineKeyboardButton("🔙 Back to Settings", callback_data="adm_panel_settings"))
        bot.edit_message_text(f"👥 <b>MANAGE ADMINS</b>\n\n<b>Current Admins:</b>\n{adm_list}", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data == "admin_add_btn" and is_admin(user_id) and user_id == OWNER_ID:
        user_states[user_id] = {'state': 'admin_add_id'}
        bot.send_message(user_id, "📝 Send Telegram User ID to Add as Admin:", parse_mode="HTML")

    elif data == "admin_rem_btn" and is_admin(user_id) and user_id == OWNER_ID:
        user_states[user_id] = {'state': 'admin_remove_id'}
        bot.send_message(user_id, "📝 Send Telegram User ID to Remove from Admin:", parse_mode="HTML")

    elif data == "admin_vis_toggles" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton(f"Vis New Gmail: {'ON 🟢' if get_setting('vis_new_gmail')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_new_gmail"))
        markup.row(InlineKeyboardButton(f"Vis Create Gmail: {'ON 🟢' if get_setting('vis_create_gmail')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_create_gmail"))
        markup.row(InlineKeyboardButton(f"Vis Old Gmail: {'ON 🟢' if get_setting('vis_old_gmail')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_old_gmail"))
        markup.row(InlineKeyboardButton(f"Vis Map Task: {'ON 🟢' if get_setting('vis_map')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_map"))
        markup.row(InlineKeyboardButton(f"Vis Withdraw: {'ON 🟢' if get_setting('vis_withdraw')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_withdraw"))
        markup.row(InlineKeyboardButton("🔙 Back to Settings", callback_data="adm_panel_settings"))
        bot.edit_message_text("👁️ <b>MENU VISIBILITY TOGGLES</b>\n(Turning these OFF will hide the button from users entirely)", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data == "admin_stat_toggles" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton(f"Stat New Gmail: {'ON 🟢' if get_setting('new_gmail_task')=='ON' else 'OFF 🔴'}", callback_data="stoggle_new_gmail_task"))
        markup.row(InlineKeyboardButton(f"Stat Create Gmail: {'ON 🟢' if get_setting('create_gmail_task')=='ON' else 'OFF 🔴'}", callback_data="stoggle_create_gmail_task"))
        markup.row(InlineKeyboardButton(f"Stat Old Gmail: {'ON 🟢' if get_setting('old_gmail_task')=='ON' else 'OFF 🔴'}", callback_data="stoggle_old_gmail_task"))
        markup.row(InlineKeyboardButton(f"Stat Map Task: {'ON 🟢' if get_setting('map_review_task')=='ON' else 'OFF 🔴'}", callback_data="stoggle_map_review_task"))
        markup.row(InlineKeyboardButton(f"Stat Withdraw: {'ON 🟢' if get_setting('withdraw')=='ON' else 'OFF 🔴'}", callback_data="stoggle_withdraw"))
        markup.row(InlineKeyboardButton("🔙 Back to Settings", callback_data="adm_panel_settings"))
        bot.edit_message_text("⛔ <b>TASK STATUS TOGGLES</b>\n(If OFF, button still shows but clicks are rejected with 'Closed By Admin')", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data.startswith("vtoggle_") and is_admin(user_id):
        key = data.replace("vtoggle_", "")
        current = get_setting(key)
        update_setting(key, "OFF" if current == "ON" else "ON")
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton(f"Vis New Gmail: {'ON 🟢' if get_setting('vis_new_gmail')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_new_gmail"))
        markup.row(InlineKeyboardButton(f"Vis Create Gmail: {'ON 🟢' if get_setting('vis_create_gmail')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_create_gmail"))
        markup.row(InlineKeyboardButton(f"Vis Old Gmail: {'ON 🟢' if get_setting('vis_old_gmail')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_old_gmail"))
        markup.row(InlineKeyboardButton(f"Vis Map Task: {'ON 🟢' if get_setting('vis_map')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_map"))
        markup.row(InlineKeyboardButton(f"Vis Withdraw: {'ON 🟢' if get_setting('vis_withdraw')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_withdraw"))
        markup.row(InlineKeyboardButton("🔙 Back to Settings", callback_data="adm_panel_settings"))
        
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.send_message(user_id, "🔄 Visibility updated dynamically. Keyboard refreshing...", reply_markup=main_menu(user_id))

    elif data.startswith("stoggle_") and is_admin(user_id):
        key = data.replace("stoggle_", "")
        current = get_setting(key)
        update_setting(key, "OFF" if current == "ON" else "ON")
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton(f"Stat New Gmail: {'ON 🟢' if get_setting('new_gmail_task')=='ON' else 'OFF 🔴'}", callback_data="stoggle_new_gmail_task"))
        markup.row(InlineKeyboardButton(f"Stat Create Gmail: {'ON 🟢' if get_setting('create_gmail_task')=='ON' else 'OFF 🔴'}", callback_data="stoggle_create_gmail_task"))
        markup.row(InlineKeyboardButton(f"Stat Old Gmail: {'ON 🟢' if get_setting('old_gmail_task')=='ON' else 'OFF 🔴'}", callback_data="stoggle_old_gmail_task"))
        markup.row(InlineKeyboardButton(f"Stat Map Task: {'ON 🟢' if get_setting('map_review_task')=='ON' else 'OFF 🔴'}", callback_data="stoggle_map_review_task"))
        markup.row(InlineKeyboardButton(f"Stat Withdraw: {'ON 🟢' if get_setting('withdraw')=='ON' else 'OFF 🔴'}", callback_data="stoggle_withdraw"))
        markup.row(InlineKeyboardButton("🔙 Back to Settings", callback_data="adm_panel_settings"))
        
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif data == "admin_bot_toggle" and is_admin(user_id):
        current = get_setting('bot_status')
        new_stat = "OFF" if current == "ON" else "ON"
        update_setting('bot_status', new_stat)
        
        markup = InlineKeyboardMarkup()
        stat = get_setting('bot_status')
        markup.row(InlineKeyboardButton(f"🤖 Bot Power: {stat}", callback_data="admin_bot_toggle"))
        markup.row(InlineKeyboardButton("👁️ Visibility Toggles", callback_data="admin_vis_toggles"), InlineKeyboardButton("⛔ Closed Alerts", callback_data="admin_stat_toggles"))
        markup.row(InlineKeyboardButton("💰 Set Task Rewards", callback_data="admin_reward_menu"), InlineKeyboardButton("⚙️ Auto-Alert Setup", callback_data="admin_set_auto_alert"))
        if user_id == OWNER_ID: markup.row(InlineKeyboardButton("👥 Manage Admins", callback_data="admin_manage"))
        markup.row(InlineKeyboardButton("📊 Total Users", callback_data="admin_total_users"), InlineKeyboardButton("👥 All User Balances", callback_data="admin_user_balances"))
        markup.row(InlineKeyboardButton("⚙️ Set Min Withdraw", callback_data="admin_set_min"), InlineKeyboardButton("🔑 Legacy Pass", callback_data="admin_set_pass"))
        markup.row(InlineKeyboardButton("📜 Approved WDs", callback_data="admin_approved_list"), InlineKeyboardButton("🖼️ Warning Photo", callback_data="admin_set_warning_photo"))
        markup.row(InlineKeyboardButton("🔙 Back to Main Panel", callback_data="admin_back"))
        
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif data == "admin_set_warning_photo" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_wait_warning_photo'}
        bot.send_message(user_id, "🖼️ <b>WARNING PHOTO SETUP</b>\n\nKripya wo <b>Photo</b> bhejein jo users ko 'Get New Gmail Task' click karne par rules ke sath dikhegi.\n\n<i>Note: Sirf photo bhejein, text ki zaroorat nahi hai. Agar hatana ho toh koi bhi text bhej de.</i>", parse_mode="HTML")

    elif data == "admin_set_auto_alert" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("📧 Set Gmail Alert Photo/Text", callback_data="set_alert_gmail"))
        markup.row(InlineKeyboardButton("🗺️ Set Map Alert Photo/Text", callback_data="set_alert_map"))
        markup.row(InlineKeyboardButton("🔙 Back to Settings", callback_data="adm_panel_settings"))
        bot.edit_message_text("📢 <b>AUTO-ALERT SETUP</b>\nSelect which task's automated broadcast you want to configure:", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data == "set_alert_gmail" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_wait_alert_gmail'}
        bot.send_message(user_id, "📧 <b>GMAIL ALERT SETUP</b>\n\nSend a <b>Photo with Caption (Text)</b> that will be broadcasted automatically to all users whenever you add New Gmail Tasks.\n\n<i>Note: If you only want text, just send the text.</i>", parse_mode="HTML")

    elif data == "set_alert_map" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_wait_alert_map'}
        bot.send_message(user_id, "🗺️ <b>MAP ALERT SETUP</b>\n\nSend a <b>Photo with Caption (Text)</b> that will be broadcasted automatically to all users whenever you add New Map Tasks.\n\n<i>Note: If you only want text, just send the text.</i>", parse_mode="HTML")

    elif data == "admin_set_min" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("Set Threshold UPI (₹)", callback_data="set_min_upi"), InlineKeyboardButton("Set Threshold USDT ($)", callback_data="set_min_usdt"))
        markup.row(InlineKeyboardButton("🔙 Back to Settings", callback_data="adm_panel_settings"))
        bot.edit_message_text("⚙️ <b>WITHDRAWAL RESTRICTIONS</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
    
    elif data == "set_min_upi" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_set_min_upi'}; bot.send_message(user_id, "📝 Transmit UPI Floor (₹):")
    elif data == "set_min_usdt" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_set_min_usdt'}; bot.send_message(user_id, "📝 Transmit USDT Floor ($):")
    elif data == "admin_set_pass" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_set_gmail_pass'}; bot.send_message(user_id, "🔑 Deploy Legacy Gmail Crypt-Key:")

    elif data == "admin_total_users" and is_admin(user_id):
        pass # Dashboard mein dikhta hai ab, but fallback ke liye skip nahi karte
        
    elif data == "admin_user_balances" and is_admin(user_id):
        records = run_query("SELECT user_id, username, balance FROM users ORDER BY balance DESC", fetch='all')
        if not records:
            bot.send_message(user_id, "No users registered yet!", parse_mode="HTML")
            return
        
        current_msg = f"👥 <b>ALL USER BALANCES (Total: {len(records)})</b>\n━━━━━━━━━━━━━━━━━━━\n"
        for r in records:
            uname = r[1] if r[1] else "Unknown"
            line = f"👤 {uname} | <code>{r[0]}</code> | 💰 ₹{r[2]:.2f}\n"
            if len(current_msg) + len(line) > 3900:
                bot.send_message(call.message.chat.id, current_msg, parse_mode="HTML")
                current_msg = "👥 <b>ALL USER BALANCES (Contd.)</b>\n━━━━━━━━━━━━━━━━━━━\n" + line
            else:
                current_msg += line
        if current_msg:
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back to Settings", callback_data="adm_panel_settings"))
            bot.send_message(call.message.chat.id, current_msg, parse_mode="HTML", reply_markup=markup)
    
    elif data == "admin_approved_list" and is_admin(user_id):
        records = run_query("SELECT user_id, method, address, amount, date FROM approved_withdraws ORDER BY id DESC LIMIT 15", fetch='all')
        if not records:
            bot.send_message(user_id, "No approved withdraw history yet!", parse_mode="HTML")
        else:
            msg = "📜 <b>APPROVED WITHDRAWALS HISTORY:</b>\n\n"
            for r in records:
                curr_symbol = "₹" if r[1] == "🏦 UPI" else "$"
                safe_addr = str(r[2]).replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
                msg += f"👤 <code>{r[0]}</code> | {r[1]} | 💰 {curr_symbol}{r[3]} | 📌 <code>{safe_addr}</code>\n📅 {r[4]}\n\n"
            if len(msg) > 4000:
                msg = msg[:4000] + "\n\n⚠️ (Limit reached, Showing latest)"
            try:
                bot.send_message(user_id, msg, parse_mode="HTML")
            except Exception as e: pass

    elif data == "admin_broadcast" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back to Main Panel", callback_data="admin_back"))
        bot.send_message(user_id, "📢 <b>BROADCAST MODE</b>\n\nJo message sabko bhejna hai, wo bhejein (Text, Photo with Caption, Video etc):", parse_mode="HTML", reply_markup=markup)
        user_states[user_id] = {'state': 'admin_wait_broadcast'}

    elif data == "admin_addbal" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back to Main Panel", callback_data="admin_back"))
        bot.send_message(user_id, "💸 <b>ADD BALANCE MODE</b>\n\n👉 User ka <b>Telegram ID</b> bhejein:", parse_mode="HTML", reply_markup=markup)
        user_states[user_id] = {'state': 'admin_wait_uid'}

    elif data.startswith("oldappr_") and is_admin(user_id):
        tgt = int(data.split("_")[1])
        rw = float(get_setting('reward_oldgmail'))
        add_balance(tgt, rw, "Old Gmail Task Approved")
        run_query("INSERT INTO task_logs (task_type, action) VALUES ('OLD_GMAIL', 'APPROVE')", commit=True)
        try: bot.edit_message_caption(f"✅ Granted (₹{rw}) for {tgt}", call.message.chat.id, call.message.message_id)
        except: bot.edit_message_text(f"✅ Granted (₹{rw}) for {tgt}", call.message.chat.id, call.message.message_id)
        try: bot.send_message(tgt, f"🎉 <b>Validation Complete!</b>\n₹{rw} added for Old Gmail Task.", parse_mode="HTML")
        except: pass

    elif data.startswith("apprt_") and is_admin(user_id):
        tgt = int(data.split("_")[1])
        rw = float(get_setting('reward_gmail'))
        add_balance(tgt, rw, "Gmail Task Approved")
        run_query("INSERT INTO task_logs (task_type, action) VALUES ('CREATE_GMAIL', 'APPROVE')", commit=True)
        try: bot.edit_message_caption(f"✅ Granted (₹{rw}) for {tgt}", call.message.chat.id, call.message.message_id)
        except: bot.edit_message_text(f"✅ Granted (₹{rw}) for {tgt}", call.message.chat.id, call.message.message_id)
        try: bot.send_message(tgt, f"🎉 <b>Validation Complete!</b>\n₹{rw} added for Legacy Gmail Task.", parse_mode="HTML")
        except: pass

    elif data.startswith("oldrej_") or data.startswith("rejct_"):
        if is_admin(user_id):
            tgt = int(data.split("_")[1])
            run_query("INSERT INTO task_logs (task_type, action) VALUES ('GMAIL', 'REJECT')", commit=True)
            try: bot.edit_message_caption(f"❌ Denied for {tgt}", call.message.chat.id, call.message.message_id)
            except: bot.edit_message_text(f"❌ Denied for {tgt}", call.message.chat.id, call.message.message_id)
            try: bot.send_message(tgt, "❌ <b>Your Task Rejected: Gmail Problem.</b>", parse_mode="HTML")
            except: pass

    elif data.startswith("apprw_") and is_admin(user_id): 
        pid = int(data.split("_")[1])
        req = run_query("SELECT user_id, amount, method, address FROM pending_withdraws WHERE id=%s", (pid,), fetch='one')
        if req:
            t_user, amt, meth, addr = req
            
            date_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            insert_check = run_query("INSERT INTO approved_withdraws (user_id, method, address, amount, date) VALUES (%s, %s, %s, %s, %s) RETURNING id", 
                                     (int(t_user), str(meth), str(addr), float(amt), str(date_now)), fetch='id', commit=True)
            
            if not insert_check:
                return
                
            curr_symbol = "₹" if meth == "🏦 UPI" else "$"
            try:
                bot.send_message(t_user, f"🎉 <b>FUNDS DISBURSED!</b>\nYour request for {curr_symbol}{amt} via {meth} has been officially fulfilled.", parse_mode="HTML")
            except: pass
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⏭️ Next Pending Withdraw", callback_data="review_pend_wd"))
            markup.add(InlineKeyboardButton("🔙 Dashboard", callback_data="adm_panel_dash"))
            try:
                bot.edit_message_text(f"✅ Asset Routed for <code>{t_user}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
            except: pass
            run_query("DELETE FROM pending_withdraws WHERE id=%s", (pid,), commit=True)

    elif data.startswith("rejcc_") and is_admin(user_id): 
        pid = int(data.split("_")[1])
        req = run_query("SELECT user_id, amount, method FROM pending_withdraws WHERE id=%s", (pid,), fetch='one')
        if req:
            t_user, amt, meth = req
            refund_inr = amt if meth == "🏦 UPI" else amt * USDT_TO_INR_RATE
            
            add_balance(t_user, refund_inr, f"Refund: {meth} Denied")
            try:
                bot.send_message(t_user, f"❌ <b>Request Dropped.</b>\nYour payout via {meth} failed administrative clearance. Funds have been reversed to your portfolio.", parse_mode="HTML")
            except: pass
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⏭️ Next Pending Withdraw", callback_data="review_pend_wd"))
            markup.add(InlineKeyboardButton("🔙 Dashboard", callback_data="adm_panel_dash"))
            try:
                bot.edit_message_text(f"❌ Transaction Dropped (Refunded) for <code>{t_user}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
            except: pass
            run_query("DELETE FROM pending_withdraws WHERE id=%s", (pid,), commit=True)

# --- START BOT ---
if __name__ == "__main__":
    try:
        bot.remove_webhook()
    except Exception as e:
        pass
        
    print("🤖 VIP Turbo Bot System Online. Running Infinity Polling...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
