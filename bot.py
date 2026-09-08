import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2
from psycopg2 import pool
import datetime
import time
import os
import threading
import random
import imaplib
import email
from email.header import decode_header
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- CONFIGURATION ---
TOKEN = '8683212510:AAEdE8kq5-5GuKerfPa_Mzaxovgb-J5VU4w'
OWNER_ID = 8894779077  
ADMIN_USERNAME = 'Raka_01'  

DATABASE_URL = 'postgresql://neondb_owner:npg_TFXNmVEARt72@ep-twilight-sunset-axd07o2j-pooler.c-4.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require' 
USDT_TO_INR_RATE = 94.0  

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=25)
user_states = {}
settings_cache = {} 

user_locks = {}
def get_user_lock(user_id):
    if user_id not in user_locks:
        user_locks[user_id] = threading.Lock()
    return user_locks[user_id]

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

try:
    db_pool = psycopg2.pool.ThreadedConnectionPool(5, 50, DATABASE_URL)
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
            if conn: db_pool.putconn(conn, close=True) 
            time.sleep(0.1)
    return None

def init_db():
    run_query('''CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, balance FLOAT DEFAULT 0)''', commit=True)
    run_query('''ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT DEFAULT 'Unknown' ''', commit=True)
    run_query('''ALTER TABLE users ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ACTIVE' ''', commit=True)
    run_query('''ALTER TABLE users ADD COLUMN IF NOT EXISTS bot_id BIGINT UNIQUE''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS history (id SERIAL PRIMARY KEY, user_id BIGINT, type TEXT, amount FLOAT, detail TEXT, date TEXT)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS pending_withdraws (id SERIAL PRIMARY KEY, user_id BIGINT, method TEXT, address TEXT, amount FLOAT)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS approved_withdraws (id SERIAL PRIMARY KEY, user_id BIGINT, method TEXT, address TEXT, amount FLOAT, date TEXT)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS admins (user_id BIGINT PRIMARY KEY)''', commit=True)
    
    run_query('''CREATE TABLE IF NOT EXISTS map_tasks (
        id SERIAL PRIMARY KEY, link TEXT, review_text TEXT, status TEXT DEFAULT 'AVAILABLE', 
        assigned_to BIGINT, ss_file_id TEXT, submit_time TIMESTAMP, 
        admin_chat_id BIGINT, admin_msg_id BIGINT, reward_amt FLOAT
    )''', commit=True)
    
    run_query('''CREATE TABLE IF NOT EXISTS new_gmail_tasks (
        id SERIAL PRIMARY KEY, gmail TEXT, password TEXT, status TEXT DEFAULT 'AVAILABLE', 
        assigned_to BIGINT, assigned_time TIMESTAMP, ss_file_id TEXT, submit_time TIMESTAMP, 
        admin_chat_id BIGINT, admin_msg_id BIGINT, reward_amt FLOAT
    )''', commit=True)
    
    run_query('''CREATE TABLE IF NOT EXISTS manual_gmail_tasks (
        id SERIAL PRIMARY KEY, user_id BIGINT, task_type TEXT, gmail TEXT, password TEXT, 
        ss_file_id TEXT, status TEXT DEFAULT 'SUBMITTED', submit_time TIMESTAMP, 
        admin_chat_id BIGINT, admin_msg_id BIGINT, reward_amt FLOAT
    )''', commit=True)

    run_query('''ALTER TABLE new_gmail_tasks ADD COLUMN IF NOT EXISTS sended_buyer BOOLEAN DEFAULT FALSE''', commit=True)
    run_query('''ALTER TABLE new_gmail_tasks ADD COLUMN IF NOT EXISTS is_checked BOOLEAN DEFAULT FALSE''', commit=True)
    run_query('''ALTER TABLE manual_gmail_tasks ADD COLUMN IF NOT EXISTS sended_buyer BOOLEAN DEFAULT FALSE''', commit=True)
    run_query('''ALTER TABLE manual_gmail_tasks ADD COLUMN IF NOT EXISTS is_checked BOOLEAN DEFAULT FALSE''', commit=True)
    run_query('''ALTER TABLE map_tasks ADD COLUMN IF NOT EXISTS sended_buyer BOOLEAN DEFAULT FALSE''', commit=True)
    run_query('''ALTER TABLE map_tasks ADD COLUMN IF NOT EXISTS is_checked BOOLEAN DEFAULT FALSE''', commit=True)

    run_query('''CREATE TABLE IF NOT EXISTS task_logs (id SERIAL PRIMARY KEY, task_type TEXT, action TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''', commit=True)
    
    run_query("INSERT INTO admins (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (OWNER_ID,), commit=True)

    default_settings = {
        'bot_status': 'ON', 'create_gmail_task': 'ON', 'new_gmail_task': 'ON', 'old_gmail_task': 'ON', 'map_review_task': 'ON', 'withdraw': 'ON',
        'vis_create_gmail': 'ON', 'vis_new_gmail': 'ON', 'vis_old_gmail': 'ON', 'vis_map': 'ON', 'vis_withdraw': 'ON', 'vis_bulk_gmail': 'ON', 'vis_bet': 'ON', 
        'min_upi': '15.0', 'min_usdt': '0.16', 'gmail_password': 'ethicbro999', 'old_gmail_password': 'Raka@321', 
        'reward_gmail': '15.0', 'reward_oldgmail': '15.0', 'reward_map': '10.0', 'reward_newgmail_single': '20.0', 'reward_newgmail_bulk': '25.0',
        'map_rules': '1. Open link.\n2. 5-Star rating.\n3. Post text.\n4. Screenshot.',
        'warning_photo': 'none', 'alert_photo_gmail': 'none', 'alert_text_gmail': '🚀 Hurry up! New Gmail tasks available.',
        'alert_photo_map': 'none', 'alert_text_map': '🚀 Hurry up! Map tasks available.',
        'recovery_email': 'your_recovery_mail@gmail.com', 'recovery_pass': 'your_app_password_here', 'recovery_video': 'none', 'welcome_text': 'none', 'req_recovery_mail': 'ON',
        'auto_approve_hours': '54.0'
    }
    for k, v in default_settings.items():
        run_query("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", (k, v), commit=True)
        
    records = run_query("SELECT key, value FROM settings", fetch='all')
    if records:
        for k, v in records: settings_cache[k] = str(v)

init_db()

# --- TIME LEFT FORMATTER ---
def time_left_str(submit_time):
    if not submit_time: return "N/A"
    try: hrs = float(get_setting('auto_approve_hours'))
    except: hrs = 54.0
    target = submit_time + datetime.timedelta(hours=hrs)
    now = datetime.datetime.now()
    if now >= target: return "Ready 🟢"
    diff = target - now
    days = diff.days
    hours, remainder = divmod(diff.seconds, 3600)
    mins, _ = divmod(remainder, 60)
    if days > 0: return f"{days}d {hours}h {mins}m"
    return f"{hours}h {mins}m"

# --- SMART AUTO APPROVER (Checks only IF is_checked=TRUE) ---
def auto_approve_worker():
    while True:
        time.sleep(60)
        try:
            try: hrs = float(get_setting('auto_approve_hours'))
            except: hrs = 54.0
            sec_required = hrs * 3600

            n_tasks = run_query("SELECT id, assigned_to, reward_amt, admin_chat_id, admin_msg_id, gmail FROM new_gmail_tasks WHERE is_checked=TRUE AND status IN ('SUBMITTED', 'CHECKED') AND EXTRACT(EPOCH FROM (NOW() - submit_time)) > %s", (sec_required,), fetch='all')
            if n_tasks:
                for t in n_tasks:
                    tid, uid, amt, ach, amsg, t_gmail = t
                    add_balance(uid, amt, f"New Gmail Task Approved (Auto)")
                    run_query("UPDATE new_gmail_tasks SET status='COMPLETED' WHERE id=%s", (tid,), commit=True)
                    run_query("INSERT INTO task_logs (task_type, action) VALUES ('GMAIL', 'AUTO-APPROVE')", commit=True)
                    try: bot.send_message(uid, f"🎉 <b>Gmail Task Approved (Auto)!</b>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>\n💰 ₹{amt} added.", parse_mode="HTML")
                    except: pass
                    try: bot.edit_message_caption(f"✅ Approved (Auto {hrs}h) | User: <code>{uid}</code>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>", ach, amsg, parse_mode="HTML", reply_markup=None)
                    except: pass
            
            m_tasks = run_query("SELECT id, user_id, reward_amt, admin_chat_id, admin_msg_id, gmail, task_type FROM manual_gmail_tasks WHERE is_checked=TRUE AND status IN ('SUBMITTED', 'CHECKED') AND EXTRACT(EPOCH FROM (NOW() - submit_time)) > %s", (sec_required,), fetch='all')
            if m_tasks:
                for t in m_tasks:
                    tid, uid, amt, ach, amsg, t_gmail, ttype = t
                    add_balance(uid, amt, f"{ttype} Gmail Approved (Auto)")
                    run_query("UPDATE manual_gmail_tasks SET status='COMPLETED' WHERE id=%s", (tid,), commit=True)
                    try: bot.send_message(uid, f"🎉 <b>{ttype} Task Approved (Auto)!</b>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>\n💰 ₹{amt} added.", parse_mode="HTML")
                    except: pass
                    try: bot.edit_message_caption(f"✅ Approved (Auto {hrs}h) | User: <code>{uid}</code>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>", ach, amsg, parse_mode="HTML", reply_markup=None)
                    except: 
                        try: bot.edit_message_text(f"✅ Approved (Auto {hrs}h) | User: <code>{uid}</code>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>", ach, amsg, parse_mode="HTML", reply_markup=None)
                        except: pass

            map_tasks = run_query("SELECT id, assigned_to, reward_amt, admin_chat_id, admin_msg_id FROM map_tasks WHERE is_checked=TRUE AND status IN ('SUBMITTED', 'CHECKED') AND EXTRACT(EPOCH FROM (NOW() - submit_time)) > %s", (sec_required,), fetch='all')
            if map_tasks:
                for t in map_tasks:
                    tid, uid, amt, ach, amsg = t
                    add_balance(uid, amt, f"Map Review Approved (Auto)")
                    run_query("UPDATE map_tasks SET status='COMPLETED' WHERE id=%s", (tid,), commit=True)
                    try: bot.send_message(uid, f"🎉 <b>Map Task Approved (Auto)!</b>\n💰 ₹{amt} added.", parse_mode="HTML")
                    except: pass
                    try: bot.edit_message_caption(f"✅ Approved (Auto {hrs}h) | User: <code>{uid}</code>\n🗺️ Map Task", ach, amsg, parse_mode="HTML", reply_markup=None)
                    except: pass
        except Exception as e:
            pass

threading.Thread(target=auto_approve_worker, daemon=True).start()

def trigger_logout_warning(uid, gm, table_name, task_id):
    time.sleep(600) 
    chk = run_query(f"SELECT status FROM {table_name} WHERE id=%s", (task_id,), fetch='one')
    if chk and chk[0] != 'REJECTED':
        msg = (f"⚠️ <b>Are You Sure You Logouted Gmail in Your Phone If Not Logout Please Logout Gmail Immediately!</b>\n"
               f"📧 <b>Gmail:</b> <code>{gm}</code>")
        try: bot.send_message(uid, msg, parse_mode="HTML")
        except: pass

def extract_gmail(message):
    text = message.caption if message.caption else message.text
    if not text: return "Unknown"
    for line in text.split('\n'):
        if '📧' in line:
            clean_line = re.sub(r'<[^>]+>', '', line)
            res = clean_line.replace('📧', '').replace('Gmail:', '').strip()
            if res: return res
    return "Unknown"

def get_latest_google_otp(target_gmail):
    user = get_setting('recovery_email')
    password = get_setting('recovery_pass')
    if user == 'your_recovery_mail@gmail.com' or not target_gmail: return None
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user, password)
        mail.select("inbox")
        status, messages = mail.search(None, '(FROM "google.com")')
        if status == "OK" and messages[0]:
            email_ids = messages[0].split()
            for e_id in reversed(email_ids[-5:]):
                status, msg_data = mail.fetch(e_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        full_text = ""
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes): subject = subject.decode(encoding if encoding else "utf-8", errors="ignore")
                        full_text += subject + " "
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    full_text += part.get_payload(decode=True).decode(errors="ignore") + " "
                        else: full_text += msg.get_payload(decode=True).decode(errors="ignore") + " "
                        
                        target_local = target_gmail.split('@')[0].lower()
                        if target_local in full_text.lower() or target_gmail.lower() in full_text.lower():
                            match = re.search(r'\b\d{6}\b', full_text)
                            if match: return match.group(0)
        return None
    except: return None

# --- HELPERS ---
def is_admin(user_id):
    if user_id == OWNER_ID: return True
    res = run_query("SELECT user_id FROM admins WHERE user_id=%s", (user_id,), fetch='one')
    return res is not None

def is_banned(user_id):
    res = run_query("SELECT status FROM users WHERE user_id=%s", (user_id,), fetch='one')
    return res and res[0] == 'BANNED'

def get_setting(key): return settings_cache.get(key, 'none')

def update_setting(key, value):
    settings_cache[key] = str(value)
    threading.Thread(target=run_query, args=("UPDATE settings SET value=%s WHERE key=%s", (str(value), key), None, True)).start()

def get_balance(user_id):
    res = run_query("SELECT balance FROM users WHERE user_id=%s", (user_id,), fetch='one')
    if res: return res[0]
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

def is_task_processed(table_name, t_id):
    chk = run_query(f"SELECT status FROM {table_name} WHERE id=%s", (t_id,), fetch='one')
    if not chk or chk[0] in ['COMPLETED', 'REJECTED']: return True
    return False

def admin_markup(user_id):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("⚙️ Bot Settings", callback_data="adm_panel_settings"))
    markup.row(InlineKeyboardButton("📧 Gmail Panel", callback_data="adm_panel_gmail"), InlineKeyboardButton("🗺️ Map Panel", callback_data="adm_panel_map"))
    markup.row(InlineKeyboardButton("📊 Dashboard & Pending Tasks", callback_data="adm_panel_dash"))
    markup.row(InlineKeyboardButton("⏱️ Auto-Approve Queue", callback_data="admin_auto_queue"))
    markup.row(InlineKeyboardButton("📢 Send Broadcast", callback_data="admin_broadcast"), InlineKeyboardButton("💸 Manage Balance", callback_data="admin_manage_bal"))
    markup.row(InlineKeyboardButton("🚫 Ban/Unban User", callback_data="admin_ban_user"), InlineKeyboardButton("📋 Banned List", callback_data="admin_banned_list"))
    markup.row(InlineKeyboardButton("🔍 Search User (Bot ID)", callback_data="admin_search_uid"))
    return markup

def main_menu(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    row1 = []
    if get_setting('vis_new_gmail') == 'ON': row1.append(KeyboardButton("📧 Get New Gmail Task"))
    if get_setting('vis_create_gmail') == 'ON': row1.append(KeyboardButton("📧 Create Gmail Task"))
    if row1: markup.row(*row1)
    
    row2 = []
    if get_setting('vis_old_gmail') == 'ON': row2.append(KeyboardButton("📧 Sell Old Gmail Task"))
    if get_setting('vis_map') == 'ON': row2.append(KeyboardButton("🗺️ Map Review Task"))
    if row2: markup.row(*row2)
    
    row3 = [KeyboardButton("💰 Wallet"), KeyboardButton("📜 Task History")]
    if get_setting('vis_withdraw') == 'ON': row3.append(KeyboardButton("💸 Withdraw"))
    markup.row(*row3)
    
    row4 = [KeyboardButton("👤 My Profile")]
    if get_setting('vis_bet') == 'ON': row4.append(KeyboardButton("🎲 Bet And Earn"))
    row4.append(KeyboardButton("📞 Contact & Help"))
    markup.row(*row4)
    
    if is_admin(user_id): markup.row(KeyboardButton("⚙️ Admin Panel"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    username = message.from_user.username
    uname_str = f"@{username}" if username else str(message.from_user.first_name)
    
    if is_banned(user_id):
        bot.send_message(user_id, "❌ <b>Account Banned!</b>\nAapko is bot se ban kar diya gaya hai.", parse_mode="HTML")
        return
    
    run_query("UPDATE new_gmail_tasks SET status='AVAILABLE', assigned_to=NULL, assigned_time=NULL WHERE status='PENDING' AND assigned_to=%s", (user_id,), commit=True)
    run_query("UPDATE map_tasks SET status='AVAILABLE', assigned_to=NULL WHERE status='PENDING' AND assigned_to=%s", (user_id,), commit=True)
    
    if get_setting('bot_status') == 'OFF' and not is_admin(user_id):
        bot.send_message(user_id, "🛠️ <b>Bot Is Under Maintenance Fixing Bug And Updating</b>\nPlease check back later.", parse_mode="HTML")
        return
        
    res = run_query("SELECT bot_id FROM users WHERE user_id=%s", (user_id,), fetch='one')
    get_balance(user_id) 
    run_query("UPDATE users SET username=%s WHERE user_id=%s", (uname_str, user_id), commit=True)
    
    if res is None and not is_admin(user_id):
        while True:
            bid = random.randint(100000, 999999)
            if not run_query("SELECT user_id FROM users WHERE bot_id=%s", (bid,), fetch='one'): break
        run_query("INSERT INTO users (user_id, balance, username, status, bot_id) VALUES (%s, 0, %s, 'ACTIVE', %s)", (user_id, uname_str, bid), commit=True)
        try: bot.send_message(OWNER_ID, f"🚀 <b>New User Registration</b>\n👤 <b>ID:</b> <code>{user_id}</code>\n🔗 <b>Username:</b> {uname_str}\n🤖 <b>Bot ID:</b> <code>{bid}</code>", parse_mode="HTML")
        except: pass
    else:
        if res and not res[0]:
            while True:
                bid = random.randint(100000, 999999)
                if not run_query("SELECT user_id FROM users WHERE bot_id=%s", (bid,), fetch='one'): break
            run_query("UPDATE users SET bot_id=%s WHERE user_id=%s", (bid, user_id), commit=True)

    msg = (f"✨ <b>𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗧𝗢 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗘𝗔𝗥𝗡𝗜𝗡𝗚𝗦</b> ✨\n\n"
           f"Greetings <b>{message.from_user.first_name}</b>, we are delighted to have you here! 💼\n\n"
           f"Complete verified micro-tasks and earn real cash instantly directly to your account.\n\n"
           f"🔰 <b>Please select an option below to begin:</b>")
           
    ext_welc = get_setting('welcome_text')
    if ext_welc and ext_welc.lower() != 'none': msg += f"\n\n{ext_welc}"
    bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=main_menu(user_id))

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_all_messages(message):
    user_id = message.chat.id
    text = message.text if message.text else message.caption

    if is_banned(user_id):
        bot.send_message(user_id, "❌ <b>Account Banned!</b>\nAapko is bot se ban kar diya gaya hai.", parse_mode="HTML")
        return

    username = message.from_user.username
    uname_str = f"@{username}" if username else str(message.from_user.first_name)
    run_query("UPDATE users SET username=%s WHERE user_id=%s", (uname_str, user_id), commit=True)

    if get_setting('bot_status') == 'OFF' and not is_admin(user_id):
        bot.send_message(user_id, "🛠️ <b>Bot Is Under Maintenance Fixing Bug And Updating</b>\nPlease check back later.", parse_mode="HTML")
        return

    # ADMIN STATES
    if user_id in user_states:
        state = user_states[user_id].get('state')
        state_data = user_states[user_id]

        if state == 'admin_custom_rej_ngm' and is_admin(user_id):
            tid = user_states[user_id]['tid']
            tgt = user_states[user_id]['tgt']
            amsg = user_states[user_id].get('admin_msg_id')
            if is_task_processed('new_gmail_tasks', tid):
                bot.send_message(user_id, "❌ Task pehle hi process ho chuka hai.", reply_markup=admin_markup(user_id))
            else:
                t_gm = run_query("SELECT gmail FROM new_gmail_tasks WHERE id=%s", (tid,), fetch='one')
                t_gmail = t_gm[0] if t_gm else "Unknown"
                run_query("UPDATE new_gmail_tasks SET status='REJECTED', assigned_to=NULL, assigned_time=NULL, is_checked=FALSE WHERE id=%s", (tid,), commit=True)
                run_query("INSERT INTO task_logs (task_type, action) VALUES ('GMAIL', 'REJECT')", commit=True)
                try: bot.send_message(tgt, f"❌ <b>Your Task Rejected!</b>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>\n💬 Reason: {text.strip()}", parse_mode="HTML")
                except: pass
                try: bot.edit_message_caption(f"❌ Rejected | User: <code>{tgt}</code>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>\n💬 Reason: <b>{text.strip()}</b>", user_id, amsg, parse_mode="HTML", reply_markup=None)
                except: pass
                bot.send_message(user_id, "✅ Custom Rejection Applied!", reply_markup=admin_markup(user_id))
            del user_states[user_id]
            return
            
        if state == 'admin_custom_rej_man' and is_admin(user_id):
            tid = user_states[user_id]['tid']
            tgt = user_states[user_id]['tgt']
            amsg = user_states[user_id].get('admin_msg_id')
            if is_task_processed('manual_gmail_tasks', tid):
                bot.send_message(user_id, "❌ Task pehle hi process ho chuka hai.", reply_markup=admin_markup(user_id))
            else:
                t_gm = run_query("SELECT gmail FROM manual_gmail_tasks WHERE id=%s", (tid,), fetch='one')
                t_gmail = t_gm[0] if t_gm else "Unknown"
                run_query("UPDATE manual_gmail_tasks SET status='REJECTED', is_checked=FALSE WHERE id=%s", (tid,), commit=True)
                try: bot.send_message(tgt, f"❌ <b>Your Task Rejected!</b>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>\n💬 Reason: {text.strip()}", parse_mode="HTML")
                except: pass
                try: bot.edit_message_caption(f"❌ Denied for <code>{tgt}</code>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>\n💬 Reason: <b>{text.strip()}</b>", user_id, amsg, parse_mode="HTML", reply_markup=None)
                except: 
                    try: bot.edit_message_text(f"❌ Denied for <code>{tgt}</code>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>\n💬 Reason: <b>{text.strip()}</b>", user_id, amsg, parse_mode="HTML", reply_markup=None)
                    except: pass
                bot.send_message(user_id, "✅ Custom Rejection Applied!", reply_markup=admin_markup(user_id))
            del user_states[user_id]
            return

        if state == 'admin_wd_reject_reason' and is_admin(user_id):
            pid = user_states[user_id]['pid']
            req = run_query("SELECT user_id, amount, method FROM pending_withdraws WHERE id=%s", (pid,), fetch='one')
            if req:
                t_user, amt, meth = req
                refund_inr = amt if meth == "🏦 UPI" else amt * USDT_TO_INR_RATE
                add_balance(t_user, refund_inr, f"Refund: {meth} Denied")
                try: bot.send_message(t_user, f"❌ <b>Request Dropped.</b>\nYour payout via {meth} failed administrative clearance.\n💬 Reason: {text.strip()}\nFunds have been reversed to your portfolio.", parse_mode="HTML")
                except: pass
                try: 
                    amsg = user_states[user_id].get('admin_msg_id')
                    bot.edit_message_text(f"❌ Trans. Dropped for <code>{t_user}</code>\n💬 Reason: {text.strip()}", user_id, amsg, parse_mode="HTML", reply_markup=None)
                except: pass
                run_query("DELETE FROM pending_withdraws WHERE id=%s", (pid,), commit=True)
                bot.send_message(user_id, "✅ Custom Rejection Applied!", reply_markup=admin_markup(user_id))
            del user_states[user_id]
            return

        if state == 'admin_wait_auto_time' and is_admin(user_id):
            try:
                hrs = float(text.strip())
                update_setting('auto_approve_hours', str(hrs))
                bot.send_message(user_id, f"✅ Auto-Approve time successfully set to <b>{hrs} Hours</b>!", parse_mode="HTML", reply_markup=admin_markup(user_id))
            except ValueError:
                bot.send_message(user_id, "❌ Kripya sahi number dalein (e.g., 54 or 2.5).", reply_markup=admin_markup(user_id))
            del user_states[user_id]
            return

        if state == 'admin_wait_search_botid' and is_admin(user_id):
            try:
                target_botid = int(text.strip())
                u_data = run_query("SELECT user_id, username, balance, status FROM users WHERE bot_id=%s", (target_botid,), fetch='one')
                if not u_data:
                    bot.send_message(user_id, "❌ Bot ID database mein nahi mili.", reply_markup=admin_markup(user_id))
                else:
                    uid, uname, bal, stat = u_data
                    tot_earn = run_query("SELECT SUM(amount) FROM history WHERE user_id=%s AND type='CREDIT'", (uid,), fetch='one')[0] or 0.0
                    tot_wd = run_query("SELECT SUM(amount) FROM approved_withdraws WHERE user_id=%s", (uid,), fetch='one')[0] or 0.0
                    pend_wd = run_query("SELECT SUM(amount) FROM pending_withdraws WHERE user_id=%s", (uid,), fetch='one')[0] or 0.0
                    c1 = run_query("SELECT count(id) FROM new_gmail_tasks WHERE assigned_to=%s AND status IN ('SUBMITTED','CHECKED','COMPLETED')", (uid,), fetch='one')[0] or 0
                    c2 = run_query("SELECT count(id) FROM map_tasks WHERE assigned_to=%s AND status IN ('SUBMITTED','CHECKED','COMPLETED')", (uid,), fetch='one')[0] or 0
                    c3 = run_query("SELECT count(id) FROM manual_gmail_tasks WHERE user_id=%s", (uid,), fetch='one')[0] or 0
                    
                    msg = (f"🔍 <b>USER DETAILS</b>\n━━━━━━━━━━━━━━━━━━━\n👤 <b>Username:</b> {uname}\n🆔 <b>Telegram ID:</b> <code>{uid}</code>\n"
                           f"🤖 <b>Bot ID:</b> <code>{target_botid}</code>\n📌 <b>Status:</b> {stat}\n\n💰 <b>Current Balance:</b> ₹{bal:.2f}\n"
                           f"📈 <b>Total Earned:</b> ₹{tot_earn:.2f}\n💸 <b>Total Withdrawn:</b> ₹{tot_wd:.2f}\n⏳ <b>Pending Withdraw:</b> ₹{pend_wd:.2f}\n\n"
                           f"📋 <b>Total Tasks Submitted:</b> {c1+c2+c3}")
                    bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=admin_markup(user_id))
            except: bot.send_message(user_id, "❌ Invalid input.", reply_markup=admin_markup(user_id))
            del user_states[user_id]
            return

        if state == 'admin_wait_ban_uid' and is_admin(user_id):
            try:
                target_uid = int(text.strip())
                user_record = run_query("SELECT status FROM users WHERE user_id=%s", (target_uid,), fetch='one')
                if not user_record: bot.send_message(user_id, "❌ User database mein nahi mila.", reply_markup=admin_markup(user_id))
                else:
                    new_status = 'ACTIVE' if user_record[0] == 'BANNED' else 'BANNED'
                    run_query("UPDATE users SET status=%s WHERE user_id=%s", (new_status, target_uid), commit=True)
                    action_text = "Unbanned 🟢" if new_status == 'ACTIVE' else "Banned 🔴"
                    bot.send_message(user_id, f"✅ User <code>{target_uid}</code> has been successfully <b>{action_text}</b>!", parse_mode="HTML", reply_markup=admin_markup(user_id))
                    try:
                        if new_status == 'BANNED': bot.send_message(target_uid, "❌ <b>Account Banned!</b>\nAapko is bot se ban kar diya gaya hai.", parse_mode="HTML")
                        else: bot.send_message(target_uid, "✅ <b>Account Unbanned!</b>\nAapka ban hata diya gaya hai.", parse_mode="HTML")
                    except: pass
            except: bot.send_message(user_id, "❌ Kripya valid numeric Telegram ID dalein.", reply_markup=admin_markup(user_id))
            del user_states[user_id]
            return

        if state == 'admin_wait_deduct_uid' and is_admin(user_id):
            try: user_states[user_id] = {'state': 'admin_wait_deduct_amt', 'uid': int(text.strip())}; bot.send_message(user_id, "👉 Provide deduction amount in ₹:")
            except: del user_states[user_id]; bot.send_message(user_id, "Invalid format.", reply_markup=admin_markup(user_id))
            return
            
        if state == 'admin_wait_deduct_amt' and is_admin(user_id):
            try:
                tgt_uid = user_states[user_id]['uid']
                amt = float(text.strip())
                deduct_balance(tgt_uid, amt, "Admin Deducted Balance")
                bot.send_message(user_id, "✅ Balance successfully deducted!", reply_markup=admin_markup(user_id))
            except: pass
            del user_states[user_id]
            return

        if state == 'admin_wait_old_pass' and is_admin(user_id):
            update_setting('old_gmail_password', text.strip())
            bot.send_message(user_id, f"✅ Old Gmail Password Set to: <code>{text.strip()}</code>", parse_mode="HTML", reply_markup=admin_markup(user_id))
            del user_states[user_id]
            return

        if state == 'admin_wait_welcome' and is_admin(user_id):
            update_setting('welcome_text', text.strip())
            bot.send_message(user_id, "✅ <b>Welcome Text Updated Successfully!</b>", parse_mode="HTML", reply_markup=admin_markup(user_id))
            del user_states[user_id]
            return

        if state == 'admin_wait_rec_vid' and is_admin(user_id):
            if message.content_type == 'video':
                update_setting('recovery_video', message.video.file_id)
                bot.send_message(user_id, "✅ <b>Recovery Video Saved Successfully!</b>", parse_mode="HTML", reply_markup=admin_markup(user_id))
            else:
                update_setting('recovery_video', 'none')
                bot.send_message(user_id, "✅ <b>Recovery Video Removed.</b>", parse_mode="HTML", reply_markup=admin_markup(user_id))
            del user_states[user_id]
            return

        if state == 'admin_wait_rec_email' and is_admin(user_id):
            update_setting('recovery_email', text.strip())
            bot.send_message(user_id, f"✅ Recovery Email updated to: <code>{text.strip()}</code>", parse_mode="HTML", reply_markup=admin_markup(user_id))
            del user_states[user_id]
            return
            
        if state == 'admin_wait_rec_pass' and is_admin(user_id):
            update_setting('recovery_pass', text.strip())
            bot.send_message(user_id, f"✅ Recovery App Password updated to: <code>{text.strip()}</code>", parse_mode="HTML", reply_markup=admin_markup(user_id))
            del user_states[user_id]
            return

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
            
        # 🔥 OLD GMAIL INPUT (STRICT CHECK)
        if state == 'man_gmail_email':
            email_input = text.strip()
            if state_data.get('type') == 'OLD':
                if not email_input.lower().endswith('@gmail.com'):
                    bot.send_message(user_id, "❌ <b>Wrong format!</b> Please enter right Gmail id (e.g., example@gmail.com):", parse_mode="HTML")
                    return
            
            user_states[user_id]['gmail'] = email_input
            user_states[user_id]['state'] = 'man_gmail_password'
            
            if state_data.get('type') == 'OLD':
                old_pass = get_setting('old_gmail_password')
                msg = (f"✅ <b>Data Recorded:</b> <code>{email_input}</code>\n"
                       f"👉 Kindly provide the associated <b>Security Password</b>:\n"
                       f"<i>(Last ka Password <b>{old_pass}</b> Rakhna Optional hai)</i>")
            else:
                msg = (f"✅ <b>Data Recorded:</b> <code>{email_input}</code>\n"
                       f"👉 Kindly provide the associated <b>Security Password</b>:")
            bot.send_message(user_id, msg, parse_mode="HTML")
            return

        if state == 'man_gmail_password':
            user_states[user_id]['pass'] = text.strip()
            
            if state_data.get('type') == 'OLD':
                task_type = 'OLD'
                t_gmail = state_data['gmail']
                t_pass = text.strip()
                r_amt = state_data['reward']
                
                db_id = run_query("INSERT INTO manual_gmail_tasks (user_id, task_type, gmail, password, ss_file_id, status, submit_time, reward_amt) VALUES (%s, %s, %s, %s, %s, 'SUBMITTED', NOW(), %s) RETURNING id", 
                                  (user_id, task_type, t_gmail, t_pass, 'none', r_amt), fetch='id', commit=True)
                                  
                threading.Thread(target=trigger_logout_warning, args=(user_id, t_gmail, 'manual_gmail_tasks', db_id), daemon=True).start()
                
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("📤 Sended To Buyer", callback_data=f"manbuyer_{db_id}"), InlineKeyboardButton("👁️ Checked", callback_data=f"manchecked_{db_id}"))
                markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"manappr_{db_id}"))
                markup.row(InlineKeyboardButton("❌ Quick Reject", callback_data=f"manrej_{db_id}"), InlineKeyboardButton("✍️ Custom Reject", callback_data=f"mancustrej_{db_id}"))
                
                msg_obj = bot.send_message(OWNER_ID, f"🔔 <b>{task_type} GMAIL SUBMISSION</b>\n👤 <code>{user_id}</code>\n🔖 ID: {db_id}\n📧 <code>{t_gmail}</code>\n🔑 <code>{t_pass}</code>\n<i>(No Screenshot required)</i>", parse_mode="HTML", reply_markup=markup)
                run_query("UPDATE manual_gmail_tasks SET admin_msg_id=%s, admin_chat_id=%s WHERE id=%s", (msg_obj.message_id, OWNER_ID, db_id), commit=True)
                
                bot.send_message(user_id, "✅ <b>Your Old Gmail has been submitted directly to the admin. Please wait at least 24 hours for validation.</b>", parse_mode="HTML", reply_markup=main_menu(user_id))
                del user_states[user_id]
                return
            else:
                user_states[user_id]['state'] = 'manual_gmail_screenshot'
                markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Discard", callback_data="back_to_main"))
                bot.send_message(user_id, "📸 <b>Please upload your Screenshot (Photo) proof for final validation:</b>", parse_mode="HTML", reply_markup=markup)
            return

        if state == 'new_gmail_task_ss':
            if message.content_type == 'photo':
                tid = user_states[user_id]['task_id']
                task_check = run_query("SELECT status, assigned_to FROM new_gmail_tasks WHERE id=%s", (tid,), fetch='one')
                if not task_check or task_check[0] != 'PENDING' or task_check[1] != user_id:
                    bot.send_message(user_id, "❌ <b>Task Expired!</b>\n15 Minute se zyada time lene ki wajah se yeh task expire ho chuka hai. Kripya naya task lein.", parse_mode="HTML", reply_markup=main_menu(user_id))
                    del user_states[user_id]
                    return

                file_id = message.photo[-1].file_id
                t_gm = run_query("SELECT gmail, password, reward_amt FROM new_gmail_tasks WHERE id=%s", (tid,), fetch='one')
                t_gmail = t_gm[0] if t_gm else "Unknown"
                t_pass = t_gm[1] if t_gm else "Unknown"
                r_amt = t_gm[2] if t_gm else float(get_setting('reward_newgmail_single'))
                
                run_query("UPDATE new_gmail_tasks SET status='SUBMITTED', ss_file_id=%s, submit_time=NOW() WHERE id=%s", (file_id, tid), commit=True)
                threading.Thread(target=trigger_logout_warning, args=(user_id, t_gmail, 'new_gmail_tasks', tid), daemon=True).start()
                
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("📤 Sended To Buyer", callback_data=f"ngmbuyer_{tid}_{user_id}"), InlineKeyboardButton("👁️ Checked", callback_data=f"ngmchecked_{tid}_{user_id}"))
                markup.row(InlineKeyboardButton(f"✅ Approve (₹{r_amt})", callback_data=f"ngmappr_{r_amt}_{tid}_{user_id}"))
                markup.row(InlineKeyboardButton("❌ Quick Reject", callback_data=f"ngmrej_{tid}_{user_id}"), InlineKeyboardButton("✍️ Custom Reject", callback_data=f"ngmcustrej_{tid}_{user_id}"))
                
                admin_caption = (f"🔔 <b>NEW GMAIL TASK PROOF</b>\n👤 <code>{user_id}</code>\n🔖 Task ID: <code>{tid}</code>\n\n📧 <b>Gmail:</b> <code>{t_gmail}</code>\n🔑 <b>Pass:</b> <code>{t_pass}</code>")
                msg_obj = bot.send_photo(OWNER_ID, file_id, caption=admin_caption, parse_mode="HTML", reply_markup=markup)
                run_query("UPDATE new_gmail_tasks SET admin_msg_id=%s, admin_chat_id=%s WHERE id=%s", (msg_obj.message_id, OWNER_ID, tid), commit=True)
                
                bot.send_message(user_id, "✅ <b>Your screenshot has been submitted to the admin. Please wait at least 24 hours for validation.</b>", parse_mode="HTML", reply_markup=main_menu(user_id))
                del user_states[user_id]
                return
            else:
                bot.send_message(user_id, "❌ Kripya Screenshot (Photo) bhejein.")
                return

        if state == 'manual_gmail_screenshot':
            if message.content_type == 'photo':
                task_type = user_states[user_id]['type']
                t_gmail = user_states[user_id]['gmail']
                t_pass = user_states[user_id]['pass']
                r_amt = user_states[user_id]['reward']
                
                db_id = run_query("INSERT INTO manual_gmail_tasks (user_id, task_type, gmail, password, ss_file_id, status, submit_time, reward_amt) VALUES (%s, %s, %s, %s, %s, 'SUBMITTED', NOW(), %s) RETURNING id", 
                                  (user_id, task_type, t_gmail, t_pass, message.photo[-1].file_id, r_amt), fetch='id', commit=True)
                                  
                threading.Thread(target=trigger_logout_warning, args=(user_id, t_gmail, 'manual_gmail_tasks', db_id), daemon=True).start()
                
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("📤 Sended To Buyer", callback_data=f"manbuyer_{db_id}"), InlineKeyboardButton("👁️ Checked", callback_data=f"manchecked_{db_id}"))
                markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"manappr_{db_id}"))
                markup.row(InlineKeyboardButton("❌ Quick Reject", callback_data=f"manrej_{db_id}"), InlineKeyboardButton("✍️ Custom Reject", callback_data=f"mancustrej_{db_id}"))
                
                msg_obj = bot.send_photo(OWNER_ID, message.photo[-1].file_id, caption=f"🔔 <b>{task_type} GMAIL SUBMISSION</b>\n👤 <code>{user_id}</code>\n🔖 ID: {db_id}\n📧 <code>{t_gmail}</code>\n🔑 <code>{t_pass}</code>", parse_mode="HTML", reply_markup=markup)
                run_query("UPDATE manual_gmail_tasks SET admin_msg_id=%s, admin_chat_id=%s WHERE id=%s", (msg_obj.message_id, OWNER_ID, db_id), commit=True)
                
                bot.send_message(user_id, "✅ <b>Your screenshot has been submitted to the admin. Please wait at least 24 hours for validation.</b>", parse_mode="HTML", reply_markup=main_menu(user_id))
                del user_states[user_id]
                return
            else:
                bot.send_message(user_id, "❌ Invalid format. Please upload a clear <b>Screenshot (Photo)</b>.")
                return
        
        if state == 'map_task_screenshot':
            if message.content_type == 'photo':
                task_id = user_states[user_id]['task_id']
                task_check = run_query("SELECT status, assigned_to FROM map_tasks WHERE id=%s", (task_id,), fetch='one')
                if not task_check or task_check[0] != 'PENDING' or task_check[1] != user_id:
                    bot.send_message(user_id, "❌ <b>Task Expired!</b>", parse_mode="HTML", reply_markup=main_menu(user_id))
                    del user_states[user_id]
                    return
                
                file_id = message.photo[-1].file_id
                r_amt = float(get_setting('reward_map'))
                run_query("UPDATE map_tasks SET status='SUBMITTED', ss_file_id=%s, submit_time=NOW(), reward_amt=%s WHERE id=%s", (file_id, r_amt, task_id), commit=True)
                
                task_data = run_query("SELECT link, review_text FROM map_tasks WHERE id=%s", (task_id,), fetch='one')
                t_link, t_txt = task_data if task_data else ("Unknown", "Unknown")

                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("👁️ Checked", callback_data=f"mapchecked_{task_id}"))
                markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"mappr_{task_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"mrej_{task_id}"))
                
                admin_msg = (f"🗺️ <b>MAP REVIEW VERIFICATION</b>\n👤 <code>{user_id}</code>\n🔖 Task ID: {task_id}\n\n🔗 <b>Assigned Link:</b>\n{t_link}\n\n💬 <b>Assigned Text:</b>\n<code>{t_txt}</code>")
                
                msg_obj = bot.send_photo(OWNER_ID, file_id, caption=admin_msg, parse_mode="HTML", reply_markup=markup)
                run_query("UPDATE map_tasks SET admin_chat_id=%s, admin_msg_id=%s WHERE id=%s", (OWNER_ID, msg_obj.message_id, task_id), commit=True)

                bot.send_message(user_id, "✅ <b>Your screenshot has been submitted to the admin.</b>", parse_mode="HTML", reply_markup=main_menu(user_id))
                del user_states[user_id]
                return
            else:
                bot.send_message(user_id, "❌ Invalid format. Please upload a clear <b>Screenshot (Photo)</b>.")
                return

    if message.content_type == 'text':
        if text == "👤 My Profile":
            bid = run_query("SELECT bot_id FROM users WHERE user_id=%s", (user_id,), fetch='one')
            bal = get_balance(user_id)
            tot_earn = run_query("SELECT SUM(amount) FROM history WHERE user_id=%s AND type='CREDIT'", (user_id,), fetch='one')[0] or 0.0
            msg = (f"👤 <b>MY PROFILE</b>\n━━━━━━━━━━━━━━━━━━━\n"
                   f"🔖 <b>Name:</b> {message.from_user.first_name}\n"
                   f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
                   f"🤖 <b>Bot ID:</b> <code>{bid[0] if bid else 'Unknown'}</code>\n\n"
                   f"💵 <b>Current Balance:</b> ₹{bal:.2f}\n"
                   f"📈 <b>Total Earnings:</b> ₹{tot_earn:.2f}")
            bot.send_message(user_id, msg, parse_mode="HTML")

        elif text == "📜 Task History":
            msg = "📜 <b>YOUR RECENT TASK HISTORY:</b>\n━━━━━━━━━━━━━━━━━━━\n"
            
            n_tasks = run_query("SELECT id, status, submit_time FROM new_gmail_tasks WHERE assigned_to=%s AND status != 'AVAILABLE' ORDER BY id DESC LIMIT 5", (user_id,), fetch='all')
            if n_tasks:
                for r in n_tasks: 
                    tleft = time_left_str(r[2]) if r[1] in ['SUBMITTED', 'CHECKED'] else "N/A"
                    st = r[2].strftime("%Y-%m-%d %H:%M") if r[2] else "Unknown"
                    msg += f"📧 <b>New Gmail</b> (ID: {r[0]})\n📌 Status: <b>{r[1]}</b>\n🕒 Time: {st}\n⏳ Auto-Approve: {tleft}\n\n"
            
            m_tasks = run_query("SELECT id, task_type, status, submit_time FROM manual_gmail_tasks WHERE user_id=%s ORDER BY id DESC LIMIT 5", (user_id,), fetch='all')
            if m_tasks:
                for r in m_tasks:
                    tleft = time_left_str(r[3]) if r[2] in ['SUBMITTED', 'CHECKED'] else "N/A"
                    st = r[3].strftime("%Y-%m-%d %H:%M") if r[3] else "Unknown"
                    msg += f"📧 <b>{r[1]} Gmail</b> (ID: {r[0]})\n📌 Status: <b>{r[2]}</b>\n🕒 Time: {st}\n⏳ Auto-Approve: {tleft}\n\n"
            
            map_tasks = run_query("SELECT id, status, submit_time FROM map_tasks WHERE assigned_to=%s AND status != 'AVAILABLE' ORDER BY id DESC LIMIT 3", (user_id,), fetch='all')
            if map_tasks:
                for r in map_tasks:
                    tleft = time_left_str(r[2]) if r[1] in ['SUBMITTED', 'CHECKED'] else "N/A"
                    st = r[2].strftime("%Y-%m-%d %H:%M") if r[2] else "Unknown"
                    msg += f"🗺️ <b>Map Task</b> (ID: {r[0]})\n📌 Status: <b>{r[1]}</b>\n🕒 Time: {st}\n⏳ Auto-Approve: {tleft}\n\n"
            
            if len(msg) < 50: msg += "<i>No recent tasks found.</i>"
            bot.send_message(user_id, msg, parse_mode="HTML")

        elif text == "📧 Get New Gmail Task":
            if get_setting('new_gmail_task') == 'OFF' and not is_admin(user_id): 
                bot.send_message(user_id, "❌ <b>Bot Option Is Now Closed By Admin</b>", parse_mode="HTML")
                return
            free_expired_gmail_tasks()
            
            pend_chk = run_query("SELECT count(id) FROM new_gmail_tasks WHERE assigned_to=%s AND status='PENDING'", (user_id,), fetch='one')[0]
            if pend_chk > 0:
                markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🗑️ Cancel All Pending Tasks", callback_data="cancel_all_pend_ngm"))
                bot.send_message(user_id, f"⚠️ Aapke paas pehle se {pend_chk} pending tasks hain! Unhe submit karein ya cancel karein.", parse_mode="HTML", reply_markup=markup)
                return

            r_single = get_setting('reward_newgmail_single')
            r_bulk = get_setting('reward_newgmail_bulk')
            
            submitted_count_res = run_query("SELECT count(id) FROM new_gmail_tasks WHERE assigned_to=%s AND status IN ('SUBMITTED', 'COMPLETED', 'CHECKED') AND assigned_time >= NOW() - INTERVAL '24 hours'", (user_id,), fetch='one')
            submitted_count = submitted_count_res[0] if submitted_count_res else 0
            req_tasks = 3
            
            msg = "📧 <b>SELECT GMAIL TASK TYPE</b>\n\nChoose how many tasks you want to process at once:"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton(f"👤 Single Task (₹{r_single})", callback_data="ngm_type_single"))
            
            if get_setting('vis_bulk_gmail') == 'ON':
                if submitted_count >= req_tasks: markup.row(InlineKeyboardButton(f"📚 Bulk Task (₹{r_bulk}/each)", callback_data="ngm_type_bulk"))
                else: markup.row(InlineKeyboardButton(f"🔒 Bulk Task (Submit {req_tasks - submitted_count} more singles)", callback_data="locked_bulk"))
                    
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
            markup.add(InlineKeyboardButton("✅ Mark as Completed", callback_data="create_task_done"))
            markup.add(InlineKeyboardButton("🔙 Return to Main Menu", callback_data="back_to_main"))
            bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)

        elif text == "📧 Sell Old Gmail Task":
            if get_setting('old_gmail_task') == 'OFF' and not is_admin(user_id): 
                bot.send_message(user_id, "❌ <b>Bot Option Is Now Closed By Admin</b>", parse_mode="HTML")
                return
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Return to Main Menu", callback_data="back_to_main"))
            r_old = get_setting('reward_oldgmail')
            old_pass = get_setting('old_gmail_password')
            msg = (f"📧 <b>SELL OLD GMAIL SUBMISSION</b>\n💰 <b>Reward:</b> ₹{r_old}\n\n"
                   f"⚠️ <b>Rule:</b> Password Ho Sake To Change Karke <code>{old_pass}</code> Rakh De Phir hame Sell Kare.\n\n"
                   "👉 Please provide your valid <b>Old Gmail Address</b>:")
            bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)
            user_states[user_id] = {'state': 'man_gmail_email', 'type': 'OLD', 'reward': float(r_old)}

        elif text == "🗺️ Map Review Task":
            if get_setting('map_review_task') == 'OFF' and not is_admin(user_id): 
                bot.send_message(user_id, "❌ <b>Bot Option Is Now Closed By Admin</b>", parse_mode="HTML")
                return
            rules = get_setting('map_rules')
            reward = get_setting('reward_map')
            msg = (f"🗺️ <b>GOOGLE MAPS REVIEW</b>\n💰 <b>Reward:</b> ₹{reward}\n\n📜 <b>Guidelines & Procedure:</b>\n{rules}\n\n👇 <i>Accept the terms below to receive your unique assignment:</i>")
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ I Agree (Initiate Task)", callback_data="map_agree")).add(InlineKeyboardButton("🔙 Return to Main Menu", callback_data="back_to_main"))
            bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)

        elif text == "🎲 Bet And Earn":
            if get_setting('vis_bet') == 'OFF' and not is_admin(user_id): 
                bot.send_message(user_id, "❌ <b>Bot Option Is Now Closed By Admin</b>", parse_mode="HTML")
                return
            msg = ("🎲 <b>BET AND EARN</b> 🎲\n━━━━━━━━━━━━━━━━━━━\n\n"
                   "⚠️ <b>RULES:</b>\n"
                   "🔹 If you Win, you get <b>90% Extra</b> added to your wallet! (Bet ₹10 ➔ Win ₹19)\n"
                   "🔹 If you Lose, your bet amount is cut.\n\n"
                   "🔢 <b>Small Number:</b> 1, 2, 3\n"
                   "🔢 <b>Big Number:</b> 4, 5, 6\n\n"
                   "<i>⚠️ Warning: Yeh ek game hai, kripya is par zyada paise na lagayein.</i>\n\n"
                   "📝 <b>Kitna money Bet karna chahte ho? (Type below):</b>")
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Cancel", callback_data="back_to_main"))
            bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)
            user_states[user_id] = {'state': 'wait_bet_amt'}

        elif user_id in user_states and user_states[user_id].get('state') == 'wait_bet_amt':
            try:
                amt = float(text)
                bal = get_balance(user_id)
                if amt <= 0 or amt > bal:
                    bot.send_message(user_id, f"❌ <b>Invalid Amount!</b>\nYour current balance is: ₹{bal:.2f}", parse_mode="HTML", reply_markup=main_menu(user_id))
                    del user_states[user_id]
                else:
                    user_states[user_id]['bet_amt'] = amt
                    user_states[user_id]['state'] = 'wait_bet_side'
                    msg = f"💸 <b>Betting Amount:</b> ₹{amt}\n\n👇 Select your choice:"
                    markup = InlineKeyboardMarkup()
                    markup.row(InlineKeyboardButton("🔼 BIG (4, 5, 6)", callback_data="betplay_big"), InlineKeyboardButton("🔽 SMALL (1, 2, 3)", callback_data="betplay_small"))
                    markup.row(InlineKeyboardButton("🔙 Cancel", callback_data="back_to_main"))
                    bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)
            except ValueError:
                bot.send_message(user_id, "❌ Please enter a valid number.", reply_markup=main_menu(user_id))
                del user_states[user_id]

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

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.message.chat.id
    data = call.data
    
    if is_banned(user_id):
        bot.answer_callback_query(call.id, "❌ Account Banned! Aap bot use nahi kar sakte.", show_alert=True)
        return

    if not data.startswith("ngmotp_"): 
        try: bot.answer_callback_query(call.id)
        except: pass

    if data.startswith("betplay_"):
        if user_id not in user_states or user_states[user_id].get('state') != 'wait_bet_side':
            bot.edit_message_text("❌ Action Expired.", user_id, call.message.message_id)
            return
        choice = data.split("_")[1]
        amt = user_states[user_id]['bet_amt']
        bal = get_balance(user_id)
        if bal < amt:
            bot.edit_message_text("❌ Insufficient Balance for this bet.", user_id, call.message.message_id)
            del user_states[user_id]
            return
        deduct_balance(user_id, amt, f"Bet Placed ({choice.upper()})")
        bot.edit_message_text(f"🎲 Rolling Dice... Bet: ₹{amt} on {choice.upper()}", user_id, call.message.message_id)
        dice_msg = bot.send_dice(user_id, emoji='🎲')
        roll_val = dice_msg.dice.value
        time.sleep(3.5)
        is_big = roll_val in [4, 5, 6]
        is_small = roll_val in [1, 2, 3]
        won = False
        if (choice == 'big' and is_big) or (choice == 'small' and is_small): won = True
        if won:
            win_amt = amt + (amt * 0.90)
            add_balance(user_id, win_amt, f"Bet Won (+90%)")
            res_msg = f"🎉 <b>YOU WON!</b>\n\n🎲 Dice Result: <b>{roll_val}</b>\n💰 You got back: ₹{win_amt:.2f} (90% Profit!)"
        else:
            res_msg = f"💥 <b>YOU LOST!</b>\n\n🎲 Dice Result: <b>{roll_val}</b>\n💸 Better luck next time!"
        bot.send_message(user_id, res_msg, parse_mode="HTML", reply_markup=main_menu(user_id))
        del user_states[user_id]
        return

    elif data == "back_to_main":
        if user_id in user_states: del user_states[user_id]
        try: bot.delete_message(user_id, call.message.message_id)
        except: pass
        bot.send_message(user_id, "🏠 <b>Main Menu</b>", parse_mode="HTML", reply_markup=main_menu(user_id))

    elif data == "cancel_all_pend_ngm":
        run_query("UPDATE new_gmail_tasks SET status='AVAILABLE', assigned_to=NULL, assigned_time=NULL WHERE status='PENDING' AND assigned_to=%s", (user_id,), commit=True)
        bot.edit_message_text("✅ All your pending tasks have been safely cancelled. You can now take new tasks.", user_id, call.message.message_id)

    elif data == "locked_bulk":
        submitted_count_res = run_query("SELECT count(id) FROM new_gmail_tasks WHERE assigned_to=%s AND status IN ('SUBMITTED', 'CHECKED', 'COMPLETED') AND assigned_time >= NOW() - INTERVAL '24 hours'", (user_id,), fetch='one')
        submitted_count = submitted_count_res[0] if submitted_count_res else 0
        req_tasks = 3
        rem = req_tasks - submitted_count
        if rem > 0:
            bot.answer_callback_query(call.id, f"🔒 Bulk Option Locked!\n\nYou must SUBMIT {rem} more Single Tasks today to unlock Bulk Mode.", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "Unlocked! Please click 'Get New Gmail Task' again to refresh.", show_alert=True)

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
        else: bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)

    elif data.startswith("ngm_go_"):
        with get_user_lock(user_id):
            mode = data.split("_")[2]
            free_expired_gmail_tasks()
            pend_chk = run_query("SELECT count(id) FROM new_gmail_tasks WHERE assigned_to=%s AND status='PENDING'", (user_id,), fetch='one')[0]
            if pend_chk > 0:
                markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🗑️ Cancel All Pending Tasks", callback_data="cancel_all_pend_ngm"))
                bot.send_message(user_id, f"⚠️ Aapke paas pehle se {pend_chk} pending tasks hain! Pehle unhe cancel ya submit karein.", parse_mode="HTML", reply_markup=markup)
                return
            limit = 1 if mode == "single" else 10
            tasks = run_query(f'''
                UPDATE new_gmail_tasks SET status='PENDING', assigned_to=%s, assigned_time=NOW() 
                WHERE id IN (SELECT id FROM new_gmail_tasks WHERE status='AVAILABLE' ORDER BY id ASC LIMIT {limit} FOR UPDATE SKIP LOCKED) 
                RETURNING id, gmail, password
            ''', (user_id,), fetch='all', commit=True)
            if not tasks:
                bot.send_message(user_id, "🚫 Stock is currently empty! Try again later.", parse_mode="HTML")
                return
            try: bot.delete_message(user_id, call.message.message_id)
            except: pass
            bot.send_message(user_id, f"🎉 <b>Tasks Allocated!</b>\n\nEk baar me sirf utne hi tasks mile hain jitne stock me the (Max {limit}).", parse_mode="HTML")
            rec_sys_active = get_setting('req_recovery_mail')
            amt_to_set = float(get_setting('reward_newgmail_single')) if mode == "single" else float(get_setting('reward_newgmail_bulk'))
            for t in tasks:
                tid, t_gmail, t_pass = t
                run_query("UPDATE new_gmail_tasks SET reward_amt=%s WHERE id=%s", (amt_to_set, tid), commit=True)
                msg = (f"📧 <b>GMAIL TASK DETAILS</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
                       f"<b>Gmail Name:</b> <code>{t_gmail}</code>\n"
                       f"<b>Password:</b> <code>{t_pass}</code>\n\n"
                       f"⏳ <b>Time Limit</b> ➔ 15 Minutes\n\n")
                markup = InlineKeyboardMarkup()
                if rec_sys_active == 'ON':
                    msg += f"<i>Jab account create ho jaye toh 'Done' par click karein.</i>"
                    markup.row(InlineKeyboardButton("✅ Done (Add Recovery)", callback_data=f"ngmdone_{tid}"), InlineKeyboardButton("❌ Cancel Task", callback_data=f"ngm_cancel_{tid}"))
                else:
                    msg += f"<i>Account banne ke baad sidha Screenshot Submit karein.</i>"
                    markup.row(InlineKeyboardButton("📤 Submit Proof", callback_data=f"ngm_ss_{tid}"), InlineKeyboardButton("❌ Cancel Task", callback_data=f"ngm_cancel_{tid}"))
                bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)

    elif data.startswith("ngmdone_"):
        tid = int(data.split("_")[1])
        rec_email = get_setting('recovery_email')
        msg = (f"🔐 <b>STEP 2: ADD RECOVERY EMAIL</b>\n━━━━━━━━━━━━━━━━━━━\n"
               f"Ab apne naye Gmail account mein yeh Recovery Email add karein:\n\n"
               f"📧 <code>{rec_email}</code>\n\n"
               f"👉 <i>Google mein add karne ke baad 'Send Code' par click karein aur phir niche <b>Get Verification OTP</b> dabayein!</i>")
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("📥 Get Verification OTP", callback_data=f"ngmotp_{tid}"))
        markup.row(InlineKeyboardButton("📹 How To Add Recovery", callback_data="show_rec_vid"))
        markup.row(InlineKeyboardButton("❌ Cancel Task", callback_data=f"ngm_cancel_{tid}"))
        try: bot.edit_message_text(msg, user_id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        except: pass

    elif data == "show_rec_vid":
        vid = get_setting('recovery_video')
        if vid and vid != 'none':
            try: bot.send_video(user_id, vid, caption="📺 <b>How to Add Recovery Email (Tutorial)</b>", parse_mode="HTML")
            except: bot.send_message(user_id, "⚠️ Video file is corrupt or invalid format.", parse_mode="HTML")
        else: bot.send_message(user_id, "⚠️ Admin ne abhi tak koi tutorial video set nahi ki hai.", parse_mode="HTML")

    elif data.startswith("ngmotp_"):
        tid = int(data.split("_")[1])
        bot.answer_callback_query(call.id, "Searching Inbox for OTP... Please wait.")
        task_check = run_query("SELECT status, assigned_to FROM new_gmail_tasks WHERE id=%s", (tid,), fetch='one')
        if not task_check or task_check[0] != 'PENDING' or task_check[1] != user_id:
            bot.answer_callback_query(call.id, "❌ Task expired! Cancel karke naya lijiye.", show_alert=True)
            return
        t_gm = run_query("SELECT gmail FROM new_gmail_tasks WHERE id=%s", (tid,), fetch='one')
        target_gmail = t_gm[0] if t_gm else ""
        otp_code = get_latest_google_otp(target_gmail)
        if otp_code:
            msg = (f"🎉 <b>OTP RECEIVED SUCCESSFULLY!</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
                   f"🔢 <b>Your Code:</b> <code>{otp_code}</code>\n\n"
                   f"<i>Google mein OTP daal kar verify karein. Jab account poora secure ho jaye, tab niche 'Submit Proof' dabakar final screenshot bhejein.</i>")
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("📤 Submit Proof", callback_data=f"ngm_ss_{tid}"), InlineKeyboardButton("❌ Cancel Task", callback_data=f"ngm_cancel_{tid}"))
            try: bot.edit_message_text(msg, user_id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
            except: pass
        else: bot.answer_callback_query(call.id, "⏳ OTP not found yet! Please wait 10 seconds and try again.", show_alert=True)

    elif data.startswith("ngm_ss_"):
        tid = int(data.split("_")[2])
        user_states[user_id] = {'state': 'new_gmail_task_ss', 'task_id': tid}
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Cancel Action", callback_data="back_to_main"))
        try: bot.edit_message_text("📸 <b>Awaiting Validation:</b>\nUpload your final screenshot for this specific Gmail:", user_id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        except: bot.send_message(user_id, "📸 <b>Awaiting Validation:</b>\nUpload your final screenshot for this specific Gmail:", parse_mode="HTML", reply_markup=markup)

    elif data.startswith("ngm_cancel_"):
        tid = int(data.split("_")[2])
        run_query("UPDATE new_gmail_tasks SET status='AVAILABLE', assigned_to=NULL, assigned_time=NULL WHERE id=%s AND assigned_to=%s", (tid, user_id), commit=True)
        bot.edit_message_text("❌ <b>Task Cancelled.</b> Returned safely to stock.", user_id, call.message.message_id, parse_mode="HTML")

    # 🔥 NEW GMAIL ADMIN ACTIONS
    elif data.startswith("ngmbuyer_"):
        tid = int(data.split("_")[1])
        tgt = int(data.split("_")[2])
        if is_task_processed('new_gmail_tasks', tid): return bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)
        t_gmail = extract_gmail(call.message)
        run_query("UPDATE new_gmail_tasks SET sended_buyer=TRUE WHERE id=%s", (tid,), commit=True)
        
        try: bot.send_message(tgt, f"🔔 <b>STATUS UPDATE</b>\nGmail Is Under Processing. Wait for completion, then balance will be automatically added.\n📧 <b>Gmail:</b> <code>{t_gmail}</code>", parse_mode="HTML")
        except: pass
        
        t_data = run_query("SELECT is_checked, reward_amt FROM new_gmail_tasks WHERE id=%s", (tid,), fetch='one')
        is_chk = t_data[0]
        amt = t_data[1] if t_data[1] else float(get_setting('reward_newgmail_single'))
        
        markup = InlineKeyboardMarkup()
        if not is_chk: markup.row(InlineKeyboardButton("👁️ Checked", callback_data=f"ngmchecked_{tid}_{tgt}"))
        markup.row(InlineKeyboardButton(f"✅ Appr (₹{amt})", callback_data=f"ngmappr_{amt}_{tid}_{tgt}"))
        markup.row(InlineKeyboardButton("❌ Quick Reject", callback_data=f"ngmrej_{tid}_{tgt}"), InlineKeyboardButton("✍️ Custom Reject", callback_data=f"ngmcustrej_{tid}_{tgt}"))
        
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        except: pass

    elif data.startswith("ngmchecked_"):
        tid = int(data.split("_")[1])
        tgt = int(data.split("_")[2])
        if is_task_processed('new_gmail_tasks', tid): return bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)
        
        run_query("UPDATE new_gmail_tasks SET status='CHECKED', is_checked=TRUE WHERE id=%s", (tid,), commit=True)
        
        t_data = run_query("SELECT sended_buyer, reward_amt FROM new_gmail_tasks WHERE id=%s", (tid,), fetch='one')
        is_snd = t_data[0]
        amt = t_data[1] if t_data[1] else float(get_setting('reward_newgmail_single'))
        try: hrs = float(get_setting('auto_approve_hours'))
        except: hrs = 54.0
        
        markup = InlineKeyboardMarkup()
        if not is_snd: markup.row(InlineKeyboardButton("📤 Sended To Buyer", callback_data=f"ngmbuyer_{tid}_{tgt}"))
        markup.row(InlineKeyboardButton(f"✅ Appr (₹{amt})", callback_data=f"ngmappr_{amt}_{tid}_{tgt}"))
        markup.row(InlineKeyboardButton("❌ Quick Reject", callback_data=f"ngmrej_{tid}_{tgt}"), InlineKeyboardButton("✍️ Custom Reject", callback_data=f"ngmcustrej_{tid}_{tgt}"))
        
        t_gmail = extract_gmail(call.message)
        try: bot.edit_message_caption(f"👁️ STATUS: CHECKED (Auto-Approve {hrs}H) | User: <code>{tgt}</code>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        except: pass

    elif data.startswith("ngmappr_"):
        amt = float(data.split("_")[1])
        tid = int(data.split("_")[2])
        tgt = int(data.split("_")[3])
        if is_task_processed('new_gmail_tasks', tid): return bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)
        
        t_gmail = extract_gmail(call.message)
        add_balance(tgt, amt, f"New Gmail Task Approved (ID: {tid})")
        run_query("UPDATE new_gmail_tasks SET status='COMPLETED' WHERE id=%s", (tid,), commit=True)
        run_query("INSERT INTO task_logs (task_type, action) VALUES ('GMAIL', 'APPROVE')", commit=True)
        
        try: bot.send_message(tgt, f"🎉 <b>Gmail Task Approved!</b>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>\n💰 ₹{amt} added.", parse_mode="HTML")
        except: pass
        
        try: bot.edit_message_caption(f"✅ Approved (₹{amt}) | User: <code>{tgt}</code>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=None)
        except: pass

    elif data.startswith("ngmrej_"):
        tid = int(data.split("_")[1])
        tgt = int(data.split("_")[2])
        if is_task_processed('new_gmail_tasks', tid): return bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("❌ Already Used", callback_data=f"ngmcfmr_1_{tid}_{tgt}"))
        markup.row(InlineKeyboardButton("❌ Wrong Password", callback_data=f"ngmcfmr_2_{tid}_{tgt}"))
        markup.row(InlineKeyboardButton("❌ Suspended/Not Exist", callback_data=f"ngmcfmr_3_{tid}_{tgt}"))
        markup.row(InlineKeyboardButton("❌ Verification Mail Not Accepted", callback_data=f"ngmcfmr_4_{tid}_{tgt}"))
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        except: pass

    elif data.startswith("ngmcustrej_"):
        tid = int(data.split("_")[1])
        tgt = int(data.split("_")[2])
        if is_task_processed('new_gmail_tasks', tid): return bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)
        user_states[user_id] = {'state': 'admin_custom_rej_ngm', 'tid': tid, 'tgt': tgt, 'admin_msg_id': call.message.message_id}
        bot.send_message(user_id, "✍️ Please type the custom rejection reason for this task:", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Cancel", callback_data="adm_panel_dash")))

    elif data.startswith("ngmcfmr_"):
        reason_code = data.split("_")[1]
        tid = int(data.split("_")[2])
        tgt = int(data.split("_")[3])
        if is_task_processed('new_gmail_tasks', tid): return bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)
        
        t_gmail = extract_gmail(call.message)
        run_query("UPDATE new_gmail_tasks SET status='REJECTED', assigned_to=NULL, assigned_time=NULL, is_checked=FALSE WHERE id=%s", (tid,), commit=True)
        run_query("INSERT INTO task_logs (task_type, action) VALUES ('GMAIL', 'REJECT')", commit=True)
        
        if reason_code == "1": r_txt = "You Gmail Account Is Already Used I Can't Accept This"
        elif reason_code == "2": r_txt = "Gmail Password Is Wrong Please Don't Send Wrong Gmail Understand"
        elif reason_code == "3": r_txt = "Gmail Account Is Not Existing Or Suspended Mail 💌"
        else: r_txt = "Device Verification Mail Not Accepted"
        
        try: bot.send_message(tgt, f"❌ <b>Your Task Rejected!</b>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>\n💬 Reason: {r_txt}", parse_mode="HTML")
        except: pass
        
        try: bot.edit_message_caption(f"❌ Rejected | User: <code>{tgt}</code>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>\n💬 Reason: <b>{r_txt}</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=None)
        except: pass

    # 🔥 MANUAL GMAIL ADMIN ACTIONS
    elif data.startswith("manbuyer_"):
        tid = int(data.split("_")[1])
        if is_task_processed('manual_gmail_tasks', tid): return bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)
        
        t_u = run_query("SELECT user_id, gmail, is_checked FROM manual_gmail_tasks WHERE id=%s", (tid,), fetch='one')
        if not t_u: return
        tgt, t_gmail, is_chk = t_u
        
        run_query("UPDATE manual_gmail_tasks SET sended_buyer=TRUE WHERE id=%s", (tid,), commit=True)
        try: bot.send_message(tgt, f"🔔 <b>STATUS UPDATE</b>\nGmail Is Under Processing. Wait for completion, then balance will be automatically added.\n📧 <b>Gmail:</b> <code>{t_gmail}</code>", parse_mode="HTML")
        except: pass
        
        markup = InlineKeyboardMarkup()
        if not is_chk: markup.row(InlineKeyboardButton("👁️ Checked", callback_data=f"manchecked_{tid}"))
        markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"manappr_{tid}"))
        markup.row(InlineKeyboardButton("❌ Quick Reject", callback_data=f"manrej_{tid}"), InlineKeyboardButton("✍️ Custom Reject", callback_data=f"mancustrej_{tid}"))
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        except: pass

    elif data.startswith("manchecked_"):
        tid = int(data.split("_")[1])
        if is_task_processed('manual_gmail_tasks', tid): return bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)
        
        t_u = run_query("SELECT user_id, gmail, sended_buyer FROM manual_gmail_tasks WHERE id=%s", (tid,), fetch='one')
        if not t_u: return
        tgt, t_gmail, is_snd = t_u
        run_query("UPDATE manual_gmail_tasks SET status='CHECKED', is_checked=TRUE WHERE id=%s", (tid,), commit=True)
        try: hrs = float(get_setting('auto_approve_hours'))
        except: hrs = 54.0
        
        markup = InlineKeyboardMarkup()
        if not is_snd: markup.row(InlineKeyboardButton("📤 Sended To Buyer", callback_data=f"manbuyer_{tid}"))
        markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"manappr_{tid}"))
        markup.row(InlineKeyboardButton("❌ Quick Reject", callback_data=f"manrej_{tid}"), InlineKeyboardButton("✍️ Custom Reject", callback_data=f"mancustrej_{tid}"))
        
        try: bot.edit_message_caption(f"👁️ STATUS: CHECKED (Auto-Approve {hrs}H) | User: <code>{tgt}</code>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        except: 
            try: bot.edit_message_text(f"👁️ STATUS: CHECKED (Auto-Approve {hrs}H) | User: <code>{tgt}</code>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
            except: pass

    elif data.startswith("manappr_"):
        tid = int(data.split("_")[1])
        if is_task_processed('manual_gmail_tasks', tid): return bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)
        
        rec = run_query("SELECT user_id, reward_amt, gmail, task_type FROM manual_gmail_tasks WHERE id=%s", (tid,), fetch='one')
        if not rec: return
        tgt, amt, t_gmail, ttype = rec
        
        add_balance(tgt, amt, f"{ttype} Gmail Approved (ID: {tid})")
        run_query("UPDATE manual_gmail_tasks SET status='COMPLETED' WHERE id=%s", (tid,), commit=True)
        
        try: bot.send_message(tgt, f"🎉 <b>Validation Complete!</b>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>\n💰 ₹{amt} added.", parse_mode="HTML")
        except: pass
        try: bot.edit_message_caption(f"✅ Granted (₹{amt}) for <code>{tgt}</code>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=None)
        except: 
            try: bot.edit_message_text(f"✅ Granted (₹{amt}) for <code>{tgt}</code>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=None)
            except: pass

    elif data.startswith("manrej_"):
        tid = int(data.split("_")[1])
        if is_task_processed('manual_gmail_tasks', tid): return bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("❌ Already Used", callback_data=f"mancfmr_1_{tid}"))
        markup.row(InlineKeyboardButton("❌ Wrong Password", callback_data=f"mancfmr_2_{tid}"))
        markup.row(InlineKeyboardButton("❌ Suspended/Not Exist", callback_data=f"mancfmr_3_{tid}"))
        markup.row(InlineKeyboardButton("❌ Verification Mail Not Accepted", callback_data=f"mancfmr_4_{tid}"))
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        except: pass

    elif data.startswith("mancustrej_"):
        tid = int(data.split("_")[1])
        if is_task_processed('manual_gmail_tasks', tid): return bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)
        rec = run_query("SELECT user_id FROM manual_gmail_tasks WHERE id=%s", (tid,), fetch='one')
        user_states[user_id] = {'state': 'admin_custom_rej_man', 'tid': tid, 'tgt': rec[0], 'admin_msg_id': call.message.message_id}
        bot.send_message(user_id, "✍️ Please type the custom rejection reason for this task:", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Cancel", callback_data="adm_panel_dash")))

    elif data.startswith("mancfmr_"):
        reason_code = data.split("_")[1]
        tid = int(data.split("_")[2])
        if is_task_processed('manual_gmail_tasks', tid): return bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)
        
        rec = run_query("SELECT user_id, gmail FROM manual_gmail_tasks WHERE id=%s", (tid,), fetch='one')
        if not rec: return
        tgt, t_gmail = rec
        
        if reason_code == "1": r_txt = "You Gmail Account Is Already Used I Can't Accept This"
        elif reason_code == "2": r_txt = "Gmail Password Is Wrong Please Don't Send Wrong Gmail Understand"
        elif reason_code == "3": r_txt = "Gmail Account Is Not Existing Or Suspended Mail 💌"
        else: r_txt = "Device Verification Mail Not Accepted"
        
        run_query("UPDATE manual_gmail_tasks SET status='REJECTED', is_checked=FALSE WHERE id=%s", (tid,), commit=True)
        try: bot.send_message(tgt, f"❌ <b>Your Task Rejected!</b>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>\n💬 Reason: {r_txt}", parse_mode="HTML")
        except: pass
        try: bot.edit_message_caption(f"❌ Denied for <code>{tgt}</code>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>\n💬 Reason: <b>{r_txt}</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=None)
        except: 
            try: bot.edit_message_text(f"❌ Denied for <code>{tgt}</code>\n📧 <b>Gmail:</b> <code>{t_gmail}</code>\n💬 Reason: <b>{r_txt}</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=None)
            except: pass

    elif data.startswith("mapchecked_"):
        t_id = int(data.split("_")[1])
        if is_task_processed('map_tasks', t_id): return bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)
        run_query("UPDATE map_tasks SET status='CHECKED', is_checked=TRUE WHERE id=%s", (t_id,), commit=True)
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"mappr_{t_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"mrej_{t_id}"))
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        except: pass

    elif data.startswith("mappr_"):
        t_id = int(data.split("_")[1])
        if is_task_processed('map_tasks', t_id): return bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)
        
        t_data = run_query("SELECT assigned_to, reward_amt FROM map_tasks WHERE id=%s", (t_id,), fetch='one')
        if not t_data: return
        tgt, amt = t_data
        
        add_balance(tgt, amt, "Map Review Approved")
        run_query("UPDATE map_tasks SET status='COMPLETED' WHERE id=%s", (t_id,), commit=True)
        run_query("INSERT INTO task_logs (task_type, action) VALUES ('MAP', 'APPROVE')", commit=True)
        
        try: bot.send_message(tgt, f"🎉 <b>Validation Complete!</b>\n₹{amt} has been allocated to your account.", parse_mode="HTML")
        except: pass
        try: bot.edit_message_caption(f"✅ Clearance Granted for <code>{tgt}</code>\n🗺️ Map Task", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=None)
        except: pass

    elif data.startswith("mrej_"):
        t_id = int(data.split("_")[1])
        if is_task_processed('map_tasks', t_id): return bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)
        
        tgt = run_query("SELECT assigned_to FROM map_tasks WHERE id=%s", (t_id,), fetch='one')[0]
        run_query("UPDATE map_tasks SET status='AVAILABLE', assigned_to=NULL, ss_file_id=NULL, is_checked=FALSE WHERE id=%s", (t_id,), commit=True)
        run_query("INSERT INTO task_logs (task_type, action) VALUES ('MAP', 'REJECT')", commit=True)
        
        try: bot.send_message(tgt, f"❌ <b>Your Task Rejected: Map Review Problem.</b>", parse_mode="HTML")
        except: pass
        try: bot.edit_message_caption(f"❌ Clearance Denied (Re-queued) for <code>{tgt}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=None)
        except: pass

    # 🔥 FIX WITHDRAW REJECT/APPROVE
    elif data.startswith("apprw_") and is_admin(user_id):
        pid = int(data.split("_")[1])
        req = run_query("SELECT user_id, amount, method, address FROM pending_withdraws WHERE id=%s", (pid,), fetch='one')
        if req:
            t_user, amt, meth, addr = req
            date_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            insert_check = run_query("INSERT INTO approved_withdraws (user_id, method, address, amount, date) VALUES (%s, %s, %s, %s, %s) RETURNING id", 
                                     (int(t_user), str(meth), str(addr), float(amt), str(date_now)), fetch='id', commit=True)
            if insert_check:
                curr_symbol = "₹" if meth == "🏦 UPI" else "$"
                try: bot.send_message(t_user, f"🎉 <b>FUNDS DISBURSED!</b>\nYour request for {curr_symbol}{amt} via {meth} has been officially fulfilled.", parse_mode="HTML")
                except: pass
                try: bot.edit_message_text(f"✅ Asset Routed for <code>{t_user}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=None)
                except: pass
                run_query("DELETE FROM pending_withdraws WHERE id=%s", (pid,), commit=True)
        else:
            bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)

    elif data.startswith("rejwd_") and is_admin(user_id):
        pid = int(data.split("_")[1])
        req = run_query("SELECT user_id, amount, method FROM pending_withdraws WHERE id=%s", (pid,), fetch='one')
        if req:
            t_user, amt, meth = req
            refund_inr = amt if meth == "🏦 UPI" else amt * USDT_TO_INR_RATE
            add_balance(t_user, refund_inr, f"Refund: {meth} Denied")
            try: bot.send_message(t_user, f"❌ <b>Request Dropped.</b>\nYour payout via {meth} failed administrative clearance. Funds have been reversed to your portfolio.", parse_mode="HTML")
            except: pass
            try: bot.edit_message_text(f"❌ Trans. Dropped for <code>{t_user}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=None)
            except: pass
            run_query("DELETE FROM pending_withdraws WHERE id=%s", (pid,), commit=True)
        else:
            bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)

    elif data.startswith("custrejwd_") and is_admin(user_id):
        pid = int(data.split("_")[1])
        req = run_query("SELECT user_id FROM pending_withdraws WHERE id=%s", (pid,), fetch='one')
        if req:
            user_states[user_id] = {'state': 'admin_wd_reject_reason', 'pid': pid, 'admin_msg_id': call.message.message_id}
            bot.send_message(user_id, "✍️ Please specify the reason for rejecting this withdrawal:", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Cancel", callback_data="adm_panel_dash")))
        else:
            bot.answer_callback_query(call.id, "Already Processed!", show_alert=True)

    # REVIEWS
    elif data == "admin_auto_queue" and is_admin(user_id):
        msg = "⏱️ <b>AUTO-APPROVE QUEUE</b>\n━━━━━━━━━━━━━━━━━━━\n"
        
        n_tasks = run_query("SELECT id, status, submit_time FROM new_gmail_tasks WHERE status IN ('SUBMITTED', 'CHECKED') ORDER BY submit_time ASC LIMIT 7", fetch='all')
        if n_tasks:
            for r in n_tasks: msg += f"📧 <b>New GM (ID:{r[0]})</b> | Status: {r[1]}\n⏳ Left: {time_left_str(r[2])}\n\n"
        
        m_tasks = run_query("SELECT id, task_type, status, submit_time FROM manual_gmail_tasks WHERE status IN ('SUBMITTED', 'CHECKED') ORDER BY submit_time ASC LIMIT 7", fetch='all')
        if m_tasks:
            for r in m_tasks: msg += f"📧 <b>{r[1]} GM (ID:{r[0]})</b> | Status: {r[2]}\n⏳ Left: {time_left_str(r[3])}\n\n"
        
        map_tasks = run_query("SELECT id, status, submit_time FROM map_tasks WHERE status IN ('SUBMITTED', 'CHECKED') ORDER BY submit_time ASC LIMIT 7", fetch='all')
        if map_tasks:
            for r in map_tasks: msg += f"🗺️ <b>Map Task (ID:{r[0]})</b> | Status: {r[1]}\n⏳ Left: {time_left_str(r[2])}\n\n"
        
        if len(msg) < 50: msg += "<i>Queue is completely empty!</i>"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back to Main Panel", callback_data="admin_back"))
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data == "adm_panel_settings" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        stat = get_setting('bot_status')
        rec_sys = get_setting('req_recovery_mail') 
        markup.row(InlineKeyboardButton(f"🤖 Bot Power: {stat}", callback_data="admin_bot_toggle"), InlineKeyboardButton(f"🔐 Recovery System: {rec_sys}", callback_data="toggle_rec_sys"))
        markup.row(InlineKeyboardButton("👁️ Vis Toggles", callback_data="admin_vis_toggles"), InlineKeyboardButton("⛔ Stat Toggles", callback_data="admin_stat_toggles"))
        markup.row(InlineKeyboardButton("💰 Set Task Rewards", callback_data="admin_reward_menu"), InlineKeyboardButton("⚙️ Auto-Alert Setup", callback_data="admin_set_auto_alert"))
        markup.row(InlineKeyboardButton("⏱️ Set Auto Time", callback_data="adm_set_auto_time"), InlineKeyboardButton("⚙️ Set Min Withdraw", callback_data="admin_set_min"))
        markup.row(InlineKeyboardButton("🔑 Create GM Pass", callback_data="admin_set_pass"), InlineKeyboardButton("🔑 Old GM Pass", callback_data="admin_set_oldpass"))
        markup.row(InlineKeyboardButton("🔑 Set Rec Email", callback_data="adm_set_rec_mail"), InlineKeyboardButton("🔑 Set Rec Pass", callback_data="adm_set_rec_pass"))
        markup.row(InlineKeyboardButton("📹 Set Rec Video", callback_data="adm_set_rec_vid"), InlineKeyboardButton("📝 Set Welcome Text", callback_data="adm_set_welcome"))
        if user_id == OWNER_ID: markup.row(InlineKeyboardButton("👥 Manage Admins", callback_data="admin_manage"), InlineKeyboardButton("📊 Total Users", callback_data="admin_total_users"))
        markup.row(InlineKeyboardButton("👥 All User Balances", callback_data="admin_user_balances"), InlineKeyboardButton("📜 Approved WDs", callback_data="admin_approved_list"))
        markup.row(InlineKeyboardButton("🖼️ Warning Photo", callback_data="admin_set_warning_photo"), InlineKeyboardButton("🔙 Back to Main Panel", callback_data="admin_back"))
        bot.edit_message_text("⚙️ <b>BOT SETTINGS & CONFIGURATION</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data == "admin_manage_bal" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("➕ Add Balance", callback_data="admin_addbal"), InlineKeyboardButton("➖ Deduct Balance", callback_data="admin_deductbal"))
        markup.row(InlineKeyboardButton("🔙 Back to Main Panel", callback_data="admin_back"))
        bot.edit_message_text("💸 <b>MANAGE USER BALANCE</b>\nSelect operation:", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data == "admin_deductbal" and is_admin(user_id):
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="admin_manage_bal"))
        bot.edit_message_text("➖ <b>DEDUCT BALANCE</b>\n👉 User ka <b>Telegram ID</b> bhejein jiska balance kaatna hai:", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        user_states[user_id] = {'state': 'admin_wait_deduct_uid'}

    elif data == "admin_addbal" and is_admin(user_id):
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="admin_manage_bal"))
        bot.edit_message_text("➕ <b>ADD BALANCE</b>\n👉 User ka <b>Telegram ID</b> bhejein jisme balance dalna hai:", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        user_states[user_id] = {'state': 'admin_wait_uid'}

    elif data == "admin_search_uid" and is_admin(user_id):
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
        bot.edit_message_text("🔍 <b>SEARCH USER</b>\n👉 User ka <b>6-Digit Bot ID</b> likh kar bhejein:", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        user_states[user_id] = {'state': 'admin_wait_search_botid'}

    elif data == "admin_set_oldpass" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_wait_old_pass'}
        bot.send_message(user_id, "🔑 <b>OLD GMAIL PASSWORD</b>\nNaya password likh kar bhejein jo users ko Old Gmail task mein show hoga:", parse_mode="HTML")

    elif data == "toggle_rec_sys" and is_admin(user_id):
        current = get_setting('req_recovery_mail')
        new_stat = "OFF" if current == "ON" else "ON"
        update_setting('req_recovery_mail', new_stat)
        bot.answer_callback_query(call.id, f"Recovery System {new_stat}", show_alert=False)

    elif data == "admin_bot_toggle" and is_admin(user_id):
        current = get_setting('bot_status')
        new_stat = "OFF" if current == "ON" else "ON"
        update_setting('bot_status', new_stat)
        bot.answer_callback_query(call.id, f"Bot is now {new_stat}", show_alert=False)

    elif data == "adm_set_welcome" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_wait_welcome'}
        bot.send_message(user_id, "📝 <b>WELCOME TEXT SETUP</b>\nPlease send the text you want to appear below the default /start welcome message.\n<i>(Send 'none' if you want to remove the extra text)</i>", parse_mode="HTML")

    elif data == "adm_set_rec_vid" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_wait_rec_vid'}
        bot.send_message(user_id, "📹 <b>RECOVERY VIDEO SETUP</b>\nPlease upload the video file directly here.\n<i>(Send any text to remove the video)</i>", parse_mode="HTML")

    elif data == "adm_set_rec_mail" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_wait_rec_email'}
        bot.send_message(user_id, "📧 <b>RECOVERY EMAIL SETUP</b>\nPlease send the Gmail address you want to use for OTP recovery:", parse_mode="HTML")

    elif data == "adm_set_rec_pass" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_wait_rec_pass'}
        bot.send_message(user_id, "🔑 <b>RECOVERY PASSWORD SETUP</b>\nPlease send the <b>App Password</b> (16 letters, no spaces) for your recovery email.\n<i>Note: You must generate this from Google Account -> Security -> App Passwords.</i>", parse_mode="HTML")

    elif data == "adm_panel_gmail" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("➕ Add Single", callback_data="ngm_add_single"), InlineKeyboardButton("📚 Bulk Add (One Password)", callback_data="ngm_add_bulk"))
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

        pend_gmail = run_query("SELECT count(id) FROM new_gmail_tasks WHERE status IN ('SUBMITTED', 'CHECKED')", fetch='one')[0] or 0
        pend_man = run_query("SELECT count(id) FROM manual_gmail_tasks WHERE status IN ('SUBMITTED', 'CHECKED')", fetch='one')[0] or 0
        pend_map = run_query("SELECT count(id) FROM map_tasks WHERE status IN ('SUBMITTED', 'CHECKED')", fetch='one')[0] or 0
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
               f"   ┣ 📧 New Gmails: {pend_gmail}\n"
               f"   ┣ 📧 Old/Create Gmails: {pend_man}\n"
               f"   ┣ 🗺️ Maps: {pend_map}\n"
               f"   ┗ 💸 Withdraws: {pend_wd}")
        
        markup = InlineKeyboardMarkup()
        if pend_gmail > 0: markup.row(InlineKeyboardButton(f"🔍 Review New Gmails ({pend_gmail})", callback_data="review_pend_gmail"))
        if pend_man > 0: markup.row(InlineKeyboardButton(f"🔍 Review Old/Create Gmails ({pend_man})", callback_data="review_pend_man"))
        if pend_map > 0: markup.row(InlineKeyboardButton(f"🔍 Review Maps ({pend_map})", callback_data="review_pend_map"))
        if pend_wd > 0: markup.row(InlineKeyboardButton(f"🔍 Review Withdraws ({pend_wd})", callback_data="review_pend_wd"))
        markup.row(InlineKeyboardButton("🔙 Back to Main Panel", callback_data="admin_back"))
        
        if call.message.content_type == 'photo':
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except: pass
            bot.send_message(call.message.chat.id, msg, parse_mode="HTML", reply_markup=markup)
        else:
            try: bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
            except: bot.send_message(call.message.chat.id, msg, parse_mode="HTML", reply_markup=markup)

    elif data == "admin_back" and is_admin(user_id):
        try:
            if call.message.content_type == 'photo':
                bot.delete_message(call.message.chat.id, call.message.message_id)
                bot.send_message(call.message.chat.id, "🛠️ <b>EXECUTIVE DASHBOARD</b>\nPlease select a category:", parse_mode="HTML", reply_markup=admin_markup(user_id))
            else:
                bot.edit_message_text("🛠️ <b>EXECUTIVE DASHBOARD</b>\nPlease select a category:", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=admin_markup(user_id))
        except: pass

    elif data == "admin_ban_user" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_wait_ban_uid'}
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back to Main Panel", callback_data="admin_back"))
        bot.edit_message_text("🚫 <b>BAN / UNBAN USER</b>\n\n👉 Kripya User ka <b>Telegram ID</b> bhejein jise aap Ban ya Unban karna chahte hain:", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        
    elif data == "admin_banned_list" and is_admin(user_id):
        records = run_query("SELECT user_id, username FROM users WHERE status='BANNED'", fetch='all')
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back to Main Panel", callback_data="admin_back"))
        if not records:
            bot.edit_message_text("📋 <b>BANNED USERS LIST</b>\n\nKoi bhi user ban nahi hai.", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        else:
            msg = "📋 <b>BANNED USERS LIST:</b>\n━━━━━━━━━━━━━━━━━━━\n"
            for r in records: msg += f"👤 {r[1]} | <code>{r[0]}</code>\n"
            bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    # PENDING QUEUE REVIEWS
    elif data.startswith("review_pend_gmail") and is_admin(user_id):
        skip_id = 0
        parts = data.split("_")
        if len(parts) > 3: skip_id = int(parts[3])
            
        task = run_query("SELECT id, assigned_to, gmail, password, ss_file_id, sended_buyer, is_checked, reward_amt FROM new_gmail_tasks WHERE status IN ('SUBMITTED', 'CHECKED') AND id != %s ORDER BY id ASC LIMIT 1", (skip_id,), fetch='one')
        if not task:
            task = run_query("SELECT id, assigned_to, gmail, password, ss_file_id, sended_buyer, is_checked, reward_amt FROM new_gmail_tasks WHERE status IN ('SUBMITTED', 'CHECKED') ORDER BY id ASC LIMIT 1", fetch='one')
            
        if task:
            tid, assigned_to, gmail, pwd, ss, sended, checked, r_amt = task
            amt = r_amt if r_amt else float(get_setting('reward_newgmail_single'))
            
            markup = InlineKeyboardMarkup()
            row1 = []
            if not sended: row1.append(InlineKeyboardButton("📤 Sended To Buyer", callback_data=f"ngmbuyer_{tid}_{assigned_to}"))
            if not checked: row1.append(InlineKeyboardButton("👁️ Checked", callback_data=f"ngmchecked_{tid}_{assigned_to}"))
            if row1: markup.row(*row1)
            
            markup.row(InlineKeyboardButton(f"✅ Appr (₹{amt})", callback_data=f"ngmappr_{amt}_{tid}_{assigned_to}"))
            markup.row(InlineKeyboardButton("❌ Quick Reject", callback_data=f"ngmrej_{tid}_{assigned_to}"), InlineKeyboardButton("✍️ Custom Reject", callback_data=f"ngmcustrej_{tid}_{assigned_to}"))
            markup.row(InlineKeyboardButton("⏭️ Next Pending Task", callback_data=f"review_pend_gmail_{tid}"))
            markup.row(InlineKeyboardButton("🔙 Dashboard", callback_data="adm_panel_dash"))
            
            try: bot.delete_message(user_id, call.message.message_id)
            except: pass
            
            caption_text = (f"🔔 <b>PENDING GMAIL REVIEW</b>\n"
                            f"👤 <code>{assigned_to}</code>\n"
                            f"🔖 Task ID: <code>{tid}</code>\n\n"
                            f"📧 <b>Gmail:</b> <code>{gmail}</code>\n"
                            f"🔑 <b>Pass:</b> <code>{pwd}</code>")
            try: bot.send_photo(user_id, ss, caption=caption_text, parse_mode="HTML", reply_markup=markup)
            except: bot.send_message(user_id, f"⚠️ <b>Screenshot Expired/Error!</b>\n\n{caption_text}", parse_mode="HTML", reply_markup=markup)
        else:
            try: bot.delete_message(user_id, call.message.message_id)
            except: pass
            bot.send_message(user_id, "No pending New Gmail tasks left!", parse_mode="HTML", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Dashboard", callback_data="adm_panel_dash")))

    elif data.startswith("review_pend_man") and is_admin(user_id):
        skip_id = 0
        parts = data.split("_")
        if len(parts) > 3: skip_id = int(parts[3])
            
        task = run_query("SELECT id, user_id, task_type, gmail, password, ss_file_id, sended_buyer, is_checked FROM manual_gmail_tasks WHERE status IN ('SUBMITTED', 'CHECKED') AND id != %s ORDER BY id ASC LIMIT 1", (skip_id,), fetch='one')
        if not task:
            task = run_query("SELECT id, user_id, task_type, gmail, password, ss_file_id, sended_buyer, is_checked FROM manual_gmail_tasks WHERE status IN ('SUBMITTED', 'CHECKED') ORDER BY id ASC LIMIT 1", fetch='one')
            
        if task:
            tid, uid, ttype, gmail, pwd, ss, sended, checked = task
            markup = InlineKeyboardMarkup()
            row1 = []
            if not sended: row1.append(InlineKeyboardButton("📤 Sended To Buyer", callback_data=f"manbuyer_{tid}"))
            if not checked: row1.append(InlineKeyboardButton("👁️ Checked", callback_data=f"manchecked_{tid}"))
            if row1: markup.row(*row1)
            
            markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"manappr_{tid}"))
            markup.row(InlineKeyboardButton("❌ Quick Reject", callback_data=f"manrej_{tid}"), InlineKeyboardButton("✍️ Custom Reject", callback_data=f"mancustrej_{tid}"))
            markup.row(InlineKeyboardButton("⏭️ Next Pending Task", callback_data=f"review_pend_man_{tid}"))
            markup.row(InlineKeyboardButton("🔙 Dashboard", callback_data="adm_panel_dash"))
            
            try: bot.delete_message(user_id, call.message.message_id)
            except: pass
            
            caption_text = (f"🔔 <b>PENDING {ttype} GMAIL</b>\n"
                            f"👤 <code>{uid}</code>\n"
                            f"🔖 Task ID: <code>{tid}</code>\n\n"
                            f"📧 <b>Gmail:</b> <code>{gmail}</code>\n"
                            f"🔑 <b>Pass:</b> <code>{pwd}</code>")
            if ss == 'none': bot.send_message(user_id, caption_text, parse_mode="HTML", reply_markup=markup)
            else:
                try: bot.send_photo(user_id, ss, caption=caption_text, parse_mode="HTML", reply_markup=markup)
                except: bot.send_message(user_id, f"⚠️ <b>Screenshot Expired/Error!</b>\n\n{caption_text}", parse_mode="HTML", reply_markup=markup)
        else:
            try: bot.delete_message(user_id, call.message.message_id)
            except: pass
            bot.send_message(user_id, "No pending Old/Create Gmail tasks left!", parse_mode="HTML", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Dashboard", callback_data="adm_panel_dash")))
            
    elif data.startswith("review_pend_map") and is_admin(user_id):
        skip_id = 0
        parts = data.split("_")
        if len(parts) > 3: skip_id = int(parts[3])
        
        task = run_query("SELECT id, assigned_to, link, review_text, ss_file_id, is_checked FROM map_tasks WHERE status IN ('SUBMITTED', 'CHECKED') AND id != %s ORDER BY id ASC LIMIT 1", (skip_id,), fetch='one')
        if not task:
            task = run_query("SELECT id, assigned_to, link, review_text, ss_file_id, is_checked FROM map_tasks WHERE status IN ('SUBMITTED', 'CHECKED') ORDER BY id ASC LIMIT 1", fetch='one')
            
        if task:
            tid, assigned_to, link, text, ss, checked = task
            markup = InlineKeyboardMarkup()
            if not checked: markup.row(InlineKeyboardButton("👁️ Checked", callback_data=f"mapchecked_{tid}"))
            markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"mappr_{tid}"), InlineKeyboardButton("❌ Reject", callback_data=f"mrej_{tid}"))
            markup.row(InlineKeyboardButton("⏭️ Next Pending Task", callback_data=f"review_pend_map_{tid}"))
            markup.row(InlineKeyboardButton("🔙 Dashboard", callback_data="adm_panel_dash"))
            
            try: bot.delete_message(user_id, call.message.message_id)
            except: pass
            
            caption_text = f"🗺️ <b>PENDING MAP REVIEW</b>\n👤 <code>{assigned_to}</code>\n🔖 Task ID: {tid}\n\n🔗 Link: {link}\n💬 Text: <code>{text}</code>"
            try: bot.send_photo(user_id, ss, caption=caption_text, parse_mode="HTML", reply_markup=markup)
            except: bot.send_message(user_id, f"⚠️ <b>Screenshot Expired!</b>\n\n{caption_text}", parse_mode="HTML", reply_markup=markup)
        else:
            try: bot.delete_message(user_id, call.message.message_id)
            except: pass
            bot.send_message(user_id, "No pending Map tasks left!", parse_mode="HTML", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Dashboard", callback_data="adm_panel_dash")))

    elif data == "review_pend_wd" and is_admin(user_id):
        req = run_query("SELECT id, user_id, method, address, amount FROM pending_withdraws LIMIT 1", fetch='one')
        if req:
            pid, u_id, meth, addr, amt = req
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"apprw_{pid}"))
            markup.row(InlineKeyboardButton("❌ Quick Reject", callback_data=f"rejwd_{pid}"), InlineKeyboardButton("✍️ Custom Reject", callback_data=f"custrejwd_{pid}"))
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
        for r in records: msg += f"🆔 <b>ID:</b> <code>{r[0]}</code> | 📧 {r[1]} | 📌 {r[2]}\n"
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
        for r in records: msg += f"🆔 <b>ID:</b> <code>{r[0]}</code>\n🔗 {r[1]}\n💬 <code>{r[2][:25]}...</code>\n\n"
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
        markup.row(InlineKeyboardButton(f"Vis New Gmail: {'ON 🟢' if get_setting('vis_new_gmail')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_new_gmail"),
                   InlineKeyboardButton(f"Vis Bulk N.Gmail: {'ON 🟢' if get_setting('vis_bulk_gmail')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_bulk_gmail"))
        markup.row(InlineKeyboardButton(f"Vis Create Gmail: {'ON 🟢' if get_setting('vis_create_gmail')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_create_gmail"))
        markup.row(InlineKeyboardButton(f"Vis Old Gmail: {'ON 🟢' if get_setting('vis_old_gmail')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_old_gmail"))
        markup.row(InlineKeyboardButton(f"Vis Map Task: {'ON 🟢' if get_setting('vis_map')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_map"))
        markup.row(InlineKeyboardButton(f"Vis Withdraw: {'ON 🟢' if get_setting('vis_withdraw')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_withdraw"))
        markup.row(InlineKeyboardButton(f"Vis Bet & Earn: {'ON 🟢' if get_setting('vis_bet')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_bet"))
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
        markup.row(InlineKeyboardButton(f"Vis New Gmail: {'ON 🟢' if get_setting('vis_new_gmail')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_new_gmail"),
                   InlineKeyboardButton(f"Vis Bulk N.Gmail: {'ON 🟢' if get_setting('vis_bulk_gmail')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_bulk_gmail"))
        markup.row(InlineKeyboardButton(f"Vis Create Gmail: {'ON 🟢' if get_setting('vis_create_gmail')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_create_gmail"))
        markup.row(InlineKeyboardButton(f"Vis Old Gmail: {'ON 🟢' if get_setting('vis_old_gmail')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_old_gmail"))
        markup.row(InlineKeyboardButton(f"Vis Map Task: {'ON 🟢' if get_setting('vis_map')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_map"))
        markup.row(InlineKeyboardButton(f"Vis Withdraw: {'ON 🟢' if get_setting('vis_withdraw')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_withdraw"))
        markup.row(InlineKeyboardButton(f"Vis Bet & Earn: {'ON 🟢' if get_setting('vis_bet')=='ON' else 'OFF 🔴'}", callback_data="vtoggle_vis_bet"))
        markup.row(InlineKeyboardButton("🔙 Back to Settings", callback_data="adm_panel_settings"))
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        bot.send_message(user_id, "🔄 Visibility updated dynamically.", reply_markup=main_menu(user_id))

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
        rec_sys = get_setting('req_recovery_mail')
        markup.row(InlineKeyboardButton(f"🤖 Bot Power: {stat}", callback_data="admin_bot_toggle"), InlineKeyboardButton(f"🔐 Recovery System: {rec_sys}", callback_data="toggle_rec_sys"))
        markup.row(InlineKeyboardButton("👁️ Vis Toggles", callback_data="admin_vis_toggles"), InlineKeyboardButton("⛔ Stat Toggles", callback_data="admin_stat_toggles"))
        markup.row(InlineKeyboardButton("💰 Set Task Rewards", callback_data="admin_reward_menu"), InlineKeyboardButton("⚙️ Auto-Alert Setup", callback_data="admin_set_auto_alert"))
        markup.row(InlineKeyboardButton("⏱️ Set Auto Time", callback_data="adm_set_auto_time"), InlineKeyboardButton("⚙️ Set Min Withdraw", callback_data="admin_set_min"))
        markup.row(InlineKeyboardButton("🔑 Create GM Pass", callback_data="admin_set_pass"), InlineKeyboardButton("🔑 Old GM Pass", callback_data="admin_set_oldpass"))
        markup.row(InlineKeyboardButton("🔑 Set Rec Email", callback_data="adm_set_rec_mail"), InlineKeyboardButton("🔑 Set Rec Pass", callback_data="adm_set_rec_pass"))
        markup.row(InlineKeyboardButton("📹 Set Rec Video", callback_data="adm_set_rec_vid"), InlineKeyboardButton("📝 Set Welcome Text", callback_data="adm_set_welcome"))
        markup.row(InlineKeyboardButton("⚙️ Set Min Withdraw", callback_data="admin_set_min"), InlineKeyboardButton("🖼️ Warning Photo", callback_data="admin_set_warning_photo"))
        if user_id == OWNER_ID: markup.row(InlineKeyboardButton("👥 Manage Admins", callback_data="admin_manage"), InlineKeyboardButton("📊 Total Users", callback_data="admin_total_users"))
        markup.row(InlineKeyboardButton("👥 All User Balances", callback_data="admin_user_balances"), InlineKeyboardButton("📜 Approved WDs", callback_data="admin_approved_list"))
        markup.row(InlineKeyboardButton("🔙 Back to Main Panel", callback_data="admin_back"))
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)

if __name__ == "__main__":
    try: bot.remove_webhook()
    except Exception as e: pass
    print("🤖 VIP Boss System Online. Running Infinity Polling...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
