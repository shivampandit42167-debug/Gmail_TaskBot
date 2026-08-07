import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2
import datetime
import time
import os

# --- CONFIGURATION ---
TOKEN = '8683212510:AAEdE8kq5-5GuKerfPa_Mzaxovgb-J5VU4w'
OWNER_ID = 8894779077  # Main Super Admin ID
ADMIN_USERNAME = 'Raka_01'  

# 👉 Tumhara Neon.tech PostgreSQL Database URL 👈
DATABASE_URL = 'postgresql://neondb_owner:npg_TFXNmVEARt72@ep-twilight-sunset-axd07o2j-pooler.c-4.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require' 

# Conversion Rate: 1 USDT = ₹94
USDT_TO_INR_RATE = 94.0  

bot = telebot.TeleBot(TOKEN)
user_states = {}

# --- DATABASE CONNECTION HELPER ---
def run_query(query, params=(), fetch=None, commit=False):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        if commit:
            conn.commit()
        if fetch == 'one':
            return cursor.fetchone()
        elif fetch == 'all':
            return cursor.fetchall()
        elif fetch == 'id':
            return cursor.fetchone()[0]
    except Exception as e:
        return None
    finally:
        cursor.close()
        conn.close()

# --- DATABASE SETUP (POSTGRESQL) ---
def init_db():
    run_query('''CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, balance FLOAT DEFAULT 0)''', commit=True)
    run_query('''ALTER TABLE users ADD COLUMN username TEXT DEFAULT 'Unknown' ''', commit=True)
    
    run_query('''CREATE TABLE IF NOT EXISTS history (id SERIAL PRIMARY KEY, user_id BIGINT, type TEXT, amount FLOAT, detail TEXT, date TEXT)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS pending_withdraws (id SERIAL PRIMARY KEY, user_id BIGINT, method TEXT, address TEXT, amount FLOAT)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS approved_withdraws (id SERIAL PRIMARY KEY, user_id BIGINT, method TEXT, address TEXT, amount FLOAT, date TEXT)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS admins (user_id BIGINT PRIMARY KEY)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS map_tasks (id SERIAL PRIMARY KEY, link TEXT, review_text TEXT, status TEXT DEFAULT 'AVAILABLE', assigned_to BIGINT)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''', commit=True)
    
    run_query("INSERT INTO admins (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (OWNER_ID,), commit=True)

    default_settings = {
        'bot_status': 'ON',
        'gmail_task': 'ON',
        'old_gmail_task': 'ON',
        'map_review_task': 'ON',
        'withdraw': 'ON',
        'min_upi': '15.0',
        'min_usdt': '0.16',
        'gmail_password': 'ethicbro999',
        'reward_gmail': '15.0',
        'reward_oldgmail': '15.0',
        'reward_map': '10.0',
        'map_rules': '1. Open the provided link.\n2. Submit a 5-Star rating.\n3. Copy the exact text below and post it.\n4. Take a clear screenshot and submit it here.'
    }
    for k, v in default_settings.items():
        run_query("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", (k, v), commit=True)

init_db()

# --- HELPER FUNCTIONS ---
def is_admin(user_id):
    if user_id == OWNER_ID: return True
    res = run_query("SELECT user_id FROM admins WHERE user_id=%s", (user_id,), fetch='one')
    return res is not None

def get_setting(key):
    res = run_query("SELECT value FROM settings WHERE key=%s", (key,), fetch='one')
    return res[0] if res else '0'

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

def admin_markup(user_id):
    markup = InlineKeyboardMarkup()
    stat = get_setting('bot_status')
    markup.row(InlineKeyboardButton(f"🤖 Bot Status: {stat}", callback_data="admin_bot_toggle"), InlineKeyboardButton("🟢/🔴 Options", callback_data="admin_toggles"))
    markup.row(InlineKeyboardButton("💰 Set Task Rewards", callback_data="admin_reward_menu"), InlineKeyboardButton("🗺️ Manage Map Tasks", callback_data="admin_map_menu"))
    if user_id == OWNER_ID: markup.row(InlineKeyboardButton("👥 Manage Admins", callback_data="admin_manage"))
    
    markup.row(InlineKeyboardButton("📊 Total Users", callback_data="admin_total_users"), InlineKeyboardButton("👥 All User Balances", callback_data="admin_user_balances"))
    
    markup.row(InlineKeyboardButton("⚙️ Set Min Withdraw", callback_data="admin_set_min"), InlineKeyboardButton("🔑 Gmail Pass", callback_data="admin_set_pass"))
    markup.row(InlineKeyboardButton("📜 Approved Withdrawals", callback_data="admin_approved_list"))
    markup.row(InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"), InlineKeyboardButton("💸 Add Balance", callback_data="admin_addbal"))
    return markup

# --- MAIN MENU ---
def main_menu(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("📧 Gmail Task"), KeyboardButton("📧 Old Gmail Task"))
    markup.row(KeyboardButton("🗺️ Map Review Task"))
    markup.row(KeyboardButton("💰 Wallet"), KeyboardButton("💸 Withdraw"))
    markup.row(KeyboardButton("📞 Contact & Help"))
    if is_admin(user_id):
        markup.row(KeyboardButton("⚙️ Admin Panel"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    username = message.from_user.username
    uname_str = f"@{username}" if username else str(message.from_user.first_name)
    
    if get_setting('bot_status') == 'OFF' and not is_admin(user_id):
        bot.send_message(user_id, "🛠️ <b>System Under Maintenance</b>\nWe are currently upgrading our systems. Please check back later.", parse_mode="HTML")
        return
    res = run_query("SELECT user_id FROM users WHERE user_id=%s", (user_id,), fetch='one')
    get_balance(user_id) 
    
    run_query("UPDATE users SET username=%s WHERE user_id=%s", (uname_str, user_id), commit=True)
    
    if res is None and not is_admin(user_id):
        try: bot.send_message(OWNER_ID, f"🚀 <b>New User Registration</b>\n\n👤 <b>User ID:</b> <code>{user_id}</code>\n👤 <b>Name:</b> {message.from_user.first_name}\n🔗 <b>Username:</b> {uname_str}", parse_mode="HTML")
        except: pass

    msg = (f"✨ <b>𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗧𝗢 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗘𝗔𝗥𝗡𝗜𝗡𝗚𝗦</b> ✨\n\n"
           f"Greetings <b>{message.from_user.first_name}</b>, we are delighted to have you here! 💼\n\n"
           f"Complete verified micro-tasks and earn real cash instantly directly to your account.\n\n"
           f"🔰 <b>Please select an option below to begin:</b>")
    bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=main_menu(user_id))

# --- MAIN TEXT HANDLER ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_all_messages(message):
    user_id = message.chat.id
    text = message.text if message.text else message.caption

    username = message.from_user.username
    uname_str = f"@{username}" if username else str(message.from_user.first_name)
    run_query("UPDATE users SET username=%s WHERE user_id=%s", (uname_str, user_id), commit=True)

    if get_setting('bot_status') == 'OFF' and not is_admin(user_id):
        bot.send_message(user_id, "🛠️ <b>System is currently under maintenance!</b>", parse_mode="HTML")
        return

    # ADMIN BROADCAST
    if user_id in user_states and user_states[user_id].get('state') == 'admin_wait_broadcast' and is_admin(user_id):
        del user_states[user_id] 
        bot.send_message(user_id, "⏳ <b>Initiating Broadcast...</b> Please wait.", parse_mode="HTML")
        success, failed = 0, 0
        for u_id in get_all_users():
            try:
                bot.copy_message(chat_id=u_id, from_chat_id=user_id, message_id=message.message_id)
                success += 1
                time.sleep(0.04) 
            except: failed += 1
        bot.send_message(user_id, f"✅ <b>Broadcast Completed Successfully!</b>\n\n🚀 Delivered: {success}\n❌ Failed: {failed}", parse_mode="HTML", reply_markup=main_menu(user_id))
        return

    # SCREENSHOT CATCHERS
    if user_id in user_states:
        state = user_states[user_id].get('state')
        
        if state == 'gmail_task_screenshot':
            if message.content_type == 'photo':
                gmail_name = user_states[user_id]['gmail_name']
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"apprt_{user_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"rejct_{user_id}"))
                bot.send_photo(OWNER_ID, message.photo[-1].file_id, caption=f"🔔 <b>NEW GMAIL TASK SUBMISSION</b>\n👤 <code>{user_id}</code>\n📧 <code>{gmail_name}</code>", parse_mode="HTML", reply_markup=markup)
                bot.send_message(user_id, "✅ <b>Submission Received!</b>\nYour screenshot is under review. Please allow up to 24 hours for verification.", parse_mode="HTML", reply_markup=main_menu(user_id))
                del user_states[user_id]
                return
            else:
                bot.send_message(user_id, "❌ Invalid format. Please upload a clear <b>Screenshot (Photo)</b>.")
                return
        
        if state == 'map_task_screenshot':
            if message.content_type == 'photo':
                task_id = user_states[user_id]['task_id']
                task_data = run_query("SELECT link, review_text FROM map_tasks WHERE id=%s", (task_id,), fetch='one')
                t_link, t_txt = task_data if task_data else ("Unknown", "Unknown")

                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"mappr_{user_id}_{task_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"mrej_{user_id}_{task_id}"))
                
                admin_msg = (f"🗺️ <b>MAP REVIEW VERIFICATION</b>\n👤 <code>{user_id}</code>\n🔖 Task ID: {task_id}\n\n"
                             f"🔗 <b>Assigned Link:</b>\n{t_link}\n\n"
                             f"💬 <b>Assigned Text:</b>\n<code>{t_txt}</code>")
                
                bot.send_photo(OWNER_ID, message.photo[-1].file_id, caption=admin_msg, parse_mode="HTML", reply_markup=markup)
                bot.send_message(user_id, "✅ <b>Review Submitted!</b>\nOur team is verifying your submission. Funds will be credited shortly.", parse_mode="HTML", reply_markup=main_menu(user_id))
                del user_states[user_id]
                return
            else:
                bot.send_message(user_id, "❌ Invalid format. Please upload a clear <b>Screenshot (Photo)</b>.")
                return

    if message.content_type == 'text':
        if text == "📧 Gmail Task":
            if get_setting('gmail_task') == 'OFF' and not is_admin(user_id):
                bot.send_message(user_id, "❌ <b>Currently Unavailable</b>\nThis task is temporarily disabled by the administrator.", parse_mode="HTML")
                return
            current_pass = get_setting('gmail_password')
            reward = get_setting('reward_gmail')
            msg = (f"📧 <b>GMAIL CREATION TASK</b>\n"
                   f"💰 <b>Reward:</b> ₹{reward}\n\n"
                   f"⚠️ <b>Instructions:</b>\n"
                   f"• Create a brand new Gmail account Age 18+ Select ok.\n"
                   f"• Use this Anyway Invalid Must Use My password provided below:\n"
                   f"🔐 <code>{current_pass}</code>\n\n"
                   f"👉 <i>Click the button below once completed!</i>")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✅ Mark as Completed", callback_data="task_done"))
            markup.add(InlineKeyboardButton("🔙 Return to Main Menu", callback_data="back_to_main"))
            bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)

        elif text == "📧 Old Gmail Task":
            if get_setting('old_gmail_task') == 'OFF' and not is_admin(user_id):
                bot.send_message(user_id, "❌ <b>Currently Unavailable</b>\nThis task is temporarily disabled.", parse_mode="HTML")
                return
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 Return to Main Menu", callback_data="back_to_main"))
            bot.send_message(user_id, "📧 <b>OLD GMAIL SUBMISSION</b>\n\n👉 Please provide your valid <b>Old Gmail Address</b>:", parse_mode="HTML", reply_markup=markup)
            user_states[user_id] = {'state': 'old_gmail_email'}

        elif text == "🗺️ Map Review Task":
            if get_setting('map_review_task') == 'OFF' and not is_admin(user_id):
                bot.send_message(user_id, "❌ <b>Map Reviews are currently disabled by the Admin.</b>", parse_mode="HTML")
                return
            
            rules = get_setting('map_rules')
            reward = get_setting('reward_map')
            msg = (f"🗺️ <b>GOOGLE MAPS REVIEW</b>\n"
                   f"💰 <b>Reward:</b> ₹{reward}\n\n"
                   f"📜 <b>Guidelines & Procedure:</b>\n{rules}\n\n"
                   f"👇 <i>Accept the terms below to receive your unique assignment:</i>")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✅ I Agree (Initiate Task)", callback_data="map_agree"))
            markup.add(InlineKeyboardButton("🔙 Return to Main Menu", callback_data="back_to_main"))
            
            if os.path.exists("31928.jpg"):
                with open("31928.jpg", "rb") as photo:
                    bot.send_photo(user_id, photo, caption=msg, parse_mode="HTML", reply_markup=markup)
            else:
                bot.send_message(user_id, msg + "\n\n<i>(Guideline image currently unavailable)</i>", parse_mode="HTML", reply_markup=markup)

        elif text == "💰 Wallet":
            balance_inr = get_balance(user_id)
            msg = (f"💼 <b>ACCOUNT DASHBOARD</b>\n"
                   f"━━━━━━━━━━━━━━━━━━━\n"
                   f"💵 <b>Available Balance:</b> ₹{balance_inr:.2f} / ${balance_inr/USDT_TO_INR_RATE:.2f} USD\n"
                   f"━━━━━━━━━━━━━━━━━━━\n\n"
                   f"📊 <b>Recent Transactions:</b>\n")
            records = run_query("SELECT type, amount, detail, date FROM history WHERE user_id=%s ORDER BY id DESC LIMIT 5", (user_id,), fetch='all')
            if not records: msg += "📝 <i>No transaction records found.</i>"
            for r in records: msg += f"{'🟢' if r[0]=='CREDIT' else '🔴'} <b>₹{r[1]}</b> | {r[2]}\n📅 <i>{r[3]}</i>\n\n"
            bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=main_menu(user_id))

        elif text == "📞 Contact & Help":
            bot.send_message(user_id, f"📞 <b>SUPPORT CENTER</b>\n\nFor any inquiries or assistance, please reach out to our administration:\n👨‍💻 <b>Support Desk:</b> @{ADMIN_USERNAME}", parse_mode="HTML", reply_markup=main_menu(user_id))

        elif text == "💸 Withdraw":
            if get_setting('withdraw') == 'OFF' and not is_admin(user_id):
                bot.send_message(user_id, "❌ <b>Withdrawals are temporarily suspended.</b>", parse_mode="HTML")
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
            bot.send_message(user_id, "🛠️ <b>EXECUTIVE DASHBOARD</b>", parse_mode="HTML", reply_markup=admin_markup(user_id))

        # --- DYNAMIC STATES FOR ADMIN & WITHDRAWALS ---
        elif user_id in user_states:
            state_data = user_states[user_id]
            st = state_data['state']

            if st == 'admin_map_manage_id' and is_admin(user_id):
                try:
                    tid = int(text.strip())
                    task = run_query("SELECT link, review_text, status FROM map_tasks WHERE id=%s", (tid,), fetch='one')
                    if not task:
                        bot.send_message(user_id, "❌ Invalid Task ID.", reply_markup=main_menu(user_id))
                    else:
                        msg = f"🛠️ <b>MANAGE TASK ID:</b> <code>{tid}</code>\n━━━━━━━━━━━━━━━━━━━\n🔗 <b>Link:</b> {task[0]}\n💬 <b>Text:</b> <code>{task[1]}</code>\n📌 <b>Status:</b> {task[2]}"
                        markup = InlineKeyboardMarkup()
                        markup.row(InlineKeyboardButton("🗑️ Delete Task", callback_data=f"mdel_{tid}"))
                        markup.row(InlineKeyboardButton("🔗 Edit Link", callback_data=f"medl_{tid}"), InlineKeyboardButton("💬 Edit Text", callback_data=f"medt_{tid}"))
                        bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)
                except ValueError:
                    bot.send_message(user_id, "❌ Kripya valid numeric Task ID dalein.")
                del user_states[user_id]

            elif st == 'admin_map_edit_link' and is_admin(user_id):
                tid = state_data['task_id']
                run_query("UPDATE map_tasks SET link=%s WHERE id=%s", (text.strip(), tid), commit=True)
                bot.send_message(user_id, f"✅ Task {tid} ka Link Update ho gaya!", reply_markup=main_menu(user_id))
                del user_states[user_id]

            elif st == 'admin_map_edit_text' and is_admin(user_id):
                tid = state_data['task_id']
                run_query("UPDATE map_tasks SET review_text=%s WHERE id=%s", (text.strip(), tid), commit=True)
                bot.send_message(user_id, f"✅ Task {tid} ka Review Text Update ho gaya!", reply_markup=main_menu(user_id))
                del user_states[user_id]

            elif st == 'admin_set_map_rules' and is_admin(user_id):
                update_setting('map_rules', text)
                bot.send_message(user_id, "✅ Map Task Rules updated successfully!", reply_markup=main_menu(user_id))
                del user_states[user_id]

            elif st == 'admin_map_add_single' and is_admin(user_id):
                try:
                    link, rev_txt = text.split('|', 1)
                    run_query("INSERT INTO map_tasks (link, review_text) VALUES (%s, %s)", (link.strip(), rev_txt.strip()), commit=True)
                    bot.send_message(user_id, "✅ Single Map Task Added!", reply_markup=main_menu(user_id))
                except:
                    bot.send_message(user_id, "❌ Format galat hai. (Link | Text) use karein.")
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

            elif st.startswith('admin_set_reward_') and is_admin(user_id):
                try:
                    val = float(text)
                    key = st.replace('admin_set_', '') 
                    update_setting(key, val)
                    bot.send_message(user_id, f"✅ Configuration applied. Reward updated to ₹{val}", reply_markup=main_menu(user_id))
                    del user_states[user_id]
                except ValueError:
                    bot.send_message(user_id, "❌ Please input a valid numeric value.")

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
                update_setting('gmail_password', text.strip())
                bot.send_message(user_id, f"✅ Security Key updated to: <code>{text.strip()}</code>", parse_mode="HTML", reply_markup=main_menu(user_id))
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
                bot.send_message(user_id, "✅ <b>Credentials securely transmitted.</b> Pending verification.", parse_mode="HTML", reply_markup=main_menu(user_id))
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

    if data == "back_to_main":
        if user_id in user_states: del user_states[user_id]
        try: bot.delete_message(user_id, call.message.message_id)
        except: pass
        bot.send_message(user_id, "🏠 <b>Main Menu</b>", parse_mode="HTML", reply_markup=main_menu(user_id))

    # 👉 MAP REVIEW SYSTEM logic
    elif data == "map_agree":
        if get_setting('map_review_task') == 'OFF':
            bot.answer_callback_query(call.id, "Map Task is currently disabled!", show_alert=True); return
        
        chk = run_query("SELECT id, link, review_text FROM map_tasks WHERE assigned_to=%s AND status='PENDING'", (user_id,), fetch='one')
        if chk:
            t_id, t_link, t_txt = chk
            msg = f"⚠️ <b>Action Blocked</b>\nYou currently hold an active unresolved assignment:\n\n🔗 <b>Assigned Resource:</b>\n{t_link}\n\n💬 <b>Required Transcript:</b>\n<code>{t_txt}</code>"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("✅ Mark as Completed", callback_data=f"mapdone_{t_id}"), InlineKeyboardButton("❌ Abort Operation", callback_data=f"mapcancel_{t_id}"))
            bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)
            return

        task = run_query('''
            UPDATE map_tasks SET status='PENDING', assigned_to=%s 
            WHERE id = (SELECT id FROM map_tasks WHERE status='AVAILABLE' LIMIT 1 FOR UPDATE SKIP LOCKED) 
            RETURNING id, link, review_text
        ''', (user_id,), fetch='one', commit=True)
        
        if not task:
            bot.answer_callback_query(call.id, "🚫 We are currently out of Review Tasks. Check back soon!", show_alert=True)
        else:
            t_id, t_link, t_txt = task
            msg = f"🎉 <b>Asset Allocated!</b>\n\n🔗 <b>Target Directory:</b>\n{t_link}\n\n💬 <b>Required Publish Data:</b>\n<code>{t_txt}</code>\n\n👉 <i>Select 'Completed' upon successful execution.</i>"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("✅ Mark as Completed", callback_data=f"mapdone_{t_id}"), InlineKeyboardButton("❌ Abort Operation", callback_data=f"mapcancel_{t_id}"))
            bot.edit_message_text(msg, user_id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data.startswith("mapdone_"):
        t_id = data.split("_")[1]
        user_states[user_id] = {'state': 'map_task_screenshot', 'task_id': t_id}
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Discard", callback_data="back_to_main"))
        bot.send_message(user_id, "📸 <b>Awaiting Validation:</b>\nPlease upload your unedited screenshot proof below:", parse_mode="HTML", reply_markup=markup)

    elif data.startswith("mapcancel_"):
        t_id = data.split("_")[1]
        run_query("UPDATE map_tasks SET status='AVAILABLE', assigned_to=NULL WHERE id=%s", (t_id,), commit=True)
        bot.edit_message_text("❌ <b>Operation Aborted.</b> The task has been successfully re-queued to the grid.", user_id, call.message.message_id, parse_mode="HTML")

    # 🛠️ ADMIN MAP STOCK MANAGER CALLBACKS
    elif data == "map_view_stock" and is_admin(user_id):
        records = run_query("SELECT id, link, review_text FROM map_tasks WHERE status='AVAILABLE' ORDER BY id ASC LIMIT 15", fetch='all')
        if not records:
            bot.answer_callback_query(call.id, "📦 Stock is completely empty!", show_alert=True)
            return
        total_avail = run_query("SELECT count(id) FROM map_tasks WHERE status='AVAILABLE'", fetch='one')[0]
        msg = f"📦 <b>CURRENT MAP TASK STOCK</b>\nTotal Available: <b>{total_avail}</b>\n<i>(Showing oldest 15 tasks)</i>\n━━━━━━━━━━━━━━━━━━━\n"
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
        try: bot.send_message(tgt, f"🎉 <b>Validation Complete!</b>\n₹{rw} has been allocated to your account.", parse_mode="HTML")
        except: pass
        try: bot.edit_message_caption(f"✅ Clearance Granted for <code>{tgt}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        except: pass

    elif data.startswith("mrej_") and is_admin(user_id):
        tgt = int(data.split("_")[1])
        t_id = int(data.split("_")[2])
        run_query("UPDATE map_tasks SET status='AVAILABLE', assigned_to=NULL WHERE id=%s", (t_id,), commit=True)
        try: bot.send_message(tgt, f"❌ <b>Validation Failed.</b> Your review submission did not meet the necessary criteria.", parse_mode="HTML")
        except: pass
        try: bot.edit_message_caption(f"❌ Clearance Denied (Re-queued) for <code>{tgt}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        except: pass

    elif data == "task_done":
        if get_setting('gmail_task') == 'OFF' and not is_admin(user_id): return
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Discard", callback_data="back_to_main"))
        bot.send_message(user_id, "📧 Provide your newly generated <b>Gmail Address</b>:", parse_mode="HTML", reply_markup=markup)
        user_states[user_id] = {'state': 'gmail_task_name'}

    # Admin Panel Menus
    elif data == "admin_map_menu" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("➕ Add Single Task", callback_data="map_add_single"))
        markup.row(InlineKeyboardButton("📚 Bulk Compile Tasks", callback_data="map_add_bulk"))
        markup.row(InlineKeyboardButton("📦 View Current Stock", callback_data="map_view_stock"))
        markup.row(InlineKeyboardButton("🛠️ Edit/Delete Task", callback_data="map_manage_task"))
        markup.row(InlineKeyboardButton("📝 Edit Global Rules", callback_data="map_edit_rules"))
        markup.row(InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_back"))
        avail = run_query("SELECT count(id) FROM map_tasks WHERE status='AVAILABLE'", fetch='one')[0]
        bot.edit_message_text(f"🗺️ <b>MAP TASK DIRECTORY</b>\n━━━━━━━━━━━━━━━━━━━\nAssets in Circulation: <b>{avail}</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data == "map_add_single" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_map_add_single'}
        bot.send_message(user_id, "📝 Execute parameter injection:\n<code>Link | Review Text</code>\n<i>(Strict parameter separation via '|' is mandatory)</i>", parse_mode="HTML")

    elif data == "map_add_bulk" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_map_add_bulk'}
        bot.send_message(user_id, "📚 Execute bulk parameter injection (one per line):\n<code>Link1 | Review1</code>\n<code>Link2 | Review2</code>", parse_mode="HTML")

    elif data == "map_edit_rules" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_set_map_rules'}
        bot.send_message(user_id, "📝 Awaiting transmission of new administrative Map Task directives:")

    elif data == "admin_reward_menu" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton(f"Gmail (₹{get_setting('reward_gmail')})", callback_data="setrw_reward_gmail"))
        markup.row(InlineKeyboardButton(f"Old Gmail (₹{get_setting('reward_oldgmail')})", callback_data="setrw_reward_oldgmail"))
        markup.row(InlineKeyboardButton(f"Map Review (₹{get_setting('reward_map')})", callback_data="setrw_reward_map"))
        markup.row(InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_back"))
        bot.edit_message_text("💰 <b>REMUNERATION CONFIGURATION</b>\nSelect parameters to overwrite:", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data.startswith("setrw_") and is_admin(user_id):
        key = data.split("setrw_")[1]
        user_states[user_id] = {'state': f'admin_set_{key}'}
        bot.send_message(user_id, "📝 Designate new numeric threshold (₹):")

    elif data == "admin_toggles" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton(f"Gmail: {'🟢' if get_setting('gmail_task')=='ON' else '🔴'}", callback_data="toggle_gmail_task"))
        markup.row(InlineKeyboardButton(f"Old Gmail: {'🟢' if get_setting('old_gmail_task')=='ON' else '🔴'}", callback_data="toggle_old_gmail_task"))
        markup.row(InlineKeyboardButton(f"Map Task: {'🟢' if get_setting('map_review_task')=='ON' else '🔴'}", callback_data="toggle_map_review_task"))
        markup.row(InlineKeyboardButton(f"Withdrawals: {'🟢' if get_setting('withdraw')=='ON' else '🔴'}", callback_data="toggle_withdraw"))
        markup.row(InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_back"))
        bot.edit_message_text("🎛️ <b>SYSTEM ACCESS SWITCHES</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data.startswith("toggle_") and is_admin(user_id):
        key = data.replace("toggle_", "")
        current = get_setting(key)
        update_setting(key, "OFF" if current == "ON" else "ON")
        bot.answer_callback_query(call.id, f"State transitioned for {key}", show_alert=True)

    elif data == "admin_bot_toggle" and is_admin(user_id):
        current = get_setting('bot_status')
        new_stat = "OFF" if current == "ON" else "ON"
        update_setting('bot_status', new_stat)
        bot.answer_callback_query(call.id, f"Global Bot Status: {new_stat}", show_alert=True)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=admin_markup(user_id))

    elif data == "admin_back" and is_admin(user_id):
        bot.edit_message_text("🛠️ <b>EXECUTIVE DASHBOARD</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=admin_markup(user_id))

    elif data == "admin_set_min" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("Set Threshold UPI (₹)", callback_data="set_min_upi"), InlineKeyboardButton("Set Threshold USDT ($)", callback_data="set_min_usdt"))
        markup.row(InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_back"))
        bot.edit_message_text("⚙️ <b>WITHDRAWAL RESTRICTIONS</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
    
    elif data == "set_min_upi" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_set_min_upi'}; bot.send_message(user_id, "📝 Transmit UPI Floor (₹):")
    elif data == "set_min_usdt" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_set_min_usdt'}; bot.send_message(user_id, "📝 Transmit USDT Floor ($):")
    elif data == "admin_set_pass" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_set_gmail_pass'}; bot.send_message(user_id, "🔑 Deploy New Gmail Crypt-Key:")

    elif data == "admin_total_users" and is_admin(user_id):
        bot.answer_callback_query(call.id, f"Global Population: {len(get_all_users())}", show_alert=True)
        
    # 👉 CHUNKING MECHANISM FOR ALL USER BALANCES (NO LIMIT, NO CRASH)
    elif data == "admin_user_balances" and is_admin(user_id):
        records = run_query("SELECT user_id, username, balance FROM users ORDER BY balance DESC", fetch='all')
        if not records:
            bot.answer_callback_query(call.id, "No users registered yet!", show_alert=True)
            return
        
        bot.answer_callback_query(call.id, "Fetching all users data...")
        
        header = f"👥 <b>ALL USER BALANCES (Total: {len(records)})</b>\n━━━━━━━━━━━━━━━━━━━\n"
        current_msg = header
        
        for r in records:
            uname = r[1] if r[1] else "Unknown"
            line = f"👤 {uname} | <code>{r[0]}</code> | 💰 ₹{r[2]:.2f}\n"
            
            # Message split logic if exceeding Telegram max char limit (~4000)
            if len(current_msg) + len(line) > 3900:
                bot.send_message(call.message.chat.id, current_msg, parse_mode="HTML")
                current_msg = "👥 <b>ALL USER BALANCES (Contd.)</b>\n━━━━━━━━━━━━━━━━━━━\n" + line
            else:
                current_msg += line
                
        if current_msg:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_back"))
            bot.send_message(call.message.chat.id, current_msg, parse_mode="HTML", reply_markup=markup)
    
    elif data == "admin_approved_list" and is_admin(user_id):
        records = run_query("SELECT user_id, method, address, amount, date FROM approved_withdraws ORDER BY id DESC LIMIT 15", fetch='all')
        if not records:
            bot.answer_callback_query(call.id, "Koi approved withdraw history nahi hai!", show_alert=True)
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
                bot.answer_callback_query(call.id)
            except Exception as e:
                bot.answer_callback_query(call.id, "⚠️ History dikhane me error aaya.", show_alert=True)

    elif data == "admin_broadcast" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_back"))
        bot.send_message(user_id, "📢 <b>BROADCAST MODE</b>\n\nJo message sabko bhejna hai, wo bhejein (Text, Photo, Video etc):", parse_mode="HTML", reply_markup=markup)
        user_states[user_id] = {'state': 'admin_wait_broadcast'}

    elif data == "admin_addbal" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_back"))
        bot.send_message(user_id, "💸 <b>ADD BALANCE MODE</b>\n\n👉 User ka <b>Telegram ID</b> bhejein:", parse_mode="HTML", reply_markup=markup)
        user_states[user_id] = {'state': 'admin_wait_uid'}

    # Approvals with Dynamic Amounts
    elif data.startswith("oldappr_") and is_admin(user_id):
        tgt = int(data.split("_")[1])
        rw = float(get_setting('reward_oldgmail'))
        add_balance(tgt, rw, "Old Gmail Task Approved")
        try: bot.edit_message_caption(f"✅ Granted (₹{rw}) for {tgt}", call.message.chat.id, call.message.message_id)
        except: bot.edit_message_text(f"✅ Granted (₹{rw}) for {tgt}", call.message.chat.id, call.message.message_id)
        try: bot.send_message(tgt, f"🎉 <b>Validation Complete!</b>\n₹{rw} added for Old Gmail Task.", parse_mode="HTML")
        except: pass

    elif data.startswith("apprt_") and is_admin(user_id):
        tgt = int(data.split("_")[1])
        rw = float(get_setting('reward_gmail'))
        add_balance(tgt, rw, "Gmail Task Approved")
        try: bot.edit_message_caption(f"✅ Granted (₹{rw}) for {tgt}", call.message.chat.id, call.message.message_id)
        except: bot.edit_message_text(f"✅ Granted (₹{rw}) for {tgt}", call.message.chat.id, call.message.message_id)
        try: bot.send_message(tgt, f"🎉 <b>Validation Complete!</b>\n₹{rw} added for new Gmail Task.", parse_mode="HTML")
        except: pass

    elif data.startswith("oldrej_") or data.startswith("rejct_"):
        if is_admin(user_id):
            tgt = int(data.split("_")[1])
            try: bot.edit_message_caption(f"❌ Denied for {tgt}", call.message.chat.id, call.message.message_id)
            except: bot.edit_message_text(f"❌ Denied for {tgt}", call.message.chat.id, call.message.message_id)
            try: bot.send_message(tgt, "❌ <b>Submission Denied.</b> Task protocols were not followed properly.", parse_mode="HTML")
            except: pass

    # Withdraw Handling
    elif data.startswith("apprw_") and is_admin(user_id): 
        pid = int(data.split("_")[1])
        req = run_query("SELECT user_id, amount, method, address FROM pending_withdraws WHERE id=%s", (pid,), fetch='one')
        if req:
            t_user, amt, meth, addr = req
            
            date_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            insert_check = run_query("INSERT INTO approved_withdraws (user_id, method, address, amount, date) VALUES (%s, %s, %s, %s, %s) RETURNING id", 
                                     (int(t_user), str(meth), str(addr), float(amt), str(date_now)), fetch='id', commit=True)
            
            if not insert_check:
                bot.answer_callback_query(call.id, "⚠️ Database Error! Halt operation.", show_alert=True)
                return
                
            bot.answer_callback_query(call.id, "Routing Asset...")
            curr_symbol = "₹" if meth == "🏦 UPI" else "$"
            try:
                bot.send_message(t_user, f"🎉 <b>FUNDS DISBURSED!</b>\nYour request for {curr_symbol}{amt} via {meth} has been officially fulfilled.", parse_mode="HTML")
            except: pass
            try:
                bot.edit_message_text(f"✅ Asset Routed for <code>{t_user}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
            except: pass
            run_query("DELETE FROM pending_withdraws WHERE id=%s", (pid,), commit=True)
        else:
            bot.answer_callback_query(call.id, "⚠️ Identity mismatched or request invalid.", show_alert=True)

    elif data.startswith("rejcc_") and is_admin(user_id): 
        pid = int(data.split("_")[1])
        req = run_query("SELECT user_id, amount, method FROM pending_withdraws WHERE id=%s", (pid,), fetch='one')
        if req:
            t_user, amt, meth = req
            refund_inr = amt if meth == "🏦 UPI" else amt * USDT_TO_INR_RATE
            
            bot.answer_callback_query(call.id, "Refunding Asset...")
            add_balance(t_user, refund_inr, f"Refund: {meth} Denied")
            try:
                bot.send_message(t_user, f"❌ <b>Request Dropped.</b>\nYour payout via {meth} failed administrative clearance. Funds have been reversed to your portfolio.", parse_mode="HTML")
            except: pass
            try:
                bot.edit_message_text(f"❌ Transaction Dropped (Refunded) for <code>{t_user}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
            except: pass
            run_query("DELETE FROM pending_withdraws WHERE id=%s", (pid,), commit=True)
        else:
            bot.answer_callback_query(call.id, "⚠️ Identity mismatched or request invalid.", show_alert=True)

# --- START BOT ---
print("System Online: All Users Balance Feature Activated Safely.")
bot.polling(none_stop=True)
