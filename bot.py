import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2
import datetime
import time

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
        print(f"Database Error: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

# --- DATABASE SETUP (POSTGRESQL) ---
def init_db():
    run_query('''CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, balance FLOAT DEFAULT 0)''', commit=True)
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
        'map_rules': '1. Link par click karein.\n2. 5 Star rating dein.\n3. Niche diya gaya text copy karke paste karein.\n4. Screenshot le kar bot me bhejein.'
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
    if get_setting('bot_status') == 'OFF' and not is_admin(user_id):
        bot.send_message(user_id, "🛠️ <b>Bot is under Maintenance!</b>\nKripya thodi der baad try karein.", parse_mode="HTML")
        return
    res = run_query("SELECT user_id FROM users WHERE user_id=%s", (user_id,), fetch='one')
    get_balance(user_id) 
    if res is None and not is_admin(user_id):
        try: bot.send_message(OWNER_ID, f"🚀 <b>New User Started Bot!</b>\n\n👤 <b>User ID:</b> <code>{user_id}</code>", parse_mode="HTML")
        except: pass

    msg = f"✨ <b>WELCOME TO OUR BOT!</b> ✨\n\nHello {message.from_user.first_name}, yahan aap simple tasks complete karke real cash earn kar sakte hain! 💸\n\n👇 <b>Niche diye gaye buttons se apna task shuru karein:</b>"
    bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=main_menu(user_id))

# --- MAIN TEXT HANDLER ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_all_messages(message):
    user_id = message.chat.id
    text = message.text if message.text else message.caption

    if get_setting('bot_status') == 'OFF' and not is_admin(user_id):
        bot.send_message(user_id, "🛠️ <b>Bot is currently OFF for Maintenance!</b>", parse_mode="HTML")
        return

    # ADMIN BROADCAST
    if user_id in user_states and user_states[user_id].get('state') == 'admin_wait_broadcast' and is_admin(user_id):
        del user_states[user_id] 
        bot.send_message(user_id, "⏳ <b>Broadcast Started...</b> Please wait.", parse_mode="HTML")
        success, failed = 0, 0
        for u_id in get_all_users():
            try:
                bot.copy_message(chat_id=u_id, from_chat_id=user_id, message_id=message.message_id)
                success += 1
                time.sleep(0.04) 
            except: failed += 1
        bot.send_message(user_id, f"✅ <b>Broadcast Complete!</b>\n\n🚀 Sent: {success}\n❌ Failed: {failed}", parse_mode="HTML", reply_markup=main_menu(user_id))
        return

    # SCREENSHOT CATCHERS
    if user_id in user_states:
        state = user_states[user_id].get('state')
        
        # Gmail Task SS
        if state == 'gmail_task_screenshot':
            if message.content_type == 'photo':
                gmail_name = user_states[user_id]['gmail_name']
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"apprt_{user_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"rejct_{user_id}"))
                bot.send_photo(OWNER_ID, message.photo[-1].file_id, caption=f"🔔 <b>NEW GMAIL TASK</b>\n👤 <code>{user_id}</code>\n📧 <code>{gmail_name}</code>", parse_mode="HTML", reply_markup=markup)
                bot.send_message(user_id, "✅ <b>Screenshot Admin ko bhej diya gaya hai. Pls Wait 24Hrs.</b>", parse_mode="HTML", reply_markup=main_menu(user_id))
                del user_states[user_id]
                return
            else:
                bot.send_message(user_id, "❌ Kripya valid **Screenshot (Photo)** bhejein!")
                return
        
        # Map Task SS
        if state == 'map_task_screenshot':
            if message.content_type == 'photo':
                task_id = user_states[user_id]['task_id']
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"mappr_{user_id}_{task_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"mrej_{user_id}_{task_id}"))
                bot.send_photo(OWNER_ID, message.photo[-1].file_id, caption=f"🗺️ <b>NEW MAP REVIEW SUBMITTED</b>\n👤 <code>{user_id}</code>\n🔖 Task ID: {task_id}", parse_mode="HTML", reply_markup=markup)
                bot.send_message(user_id, "✅ <b>Map Review Admin ko check ke liye bhej diya gaya hai!</b>", parse_mode="HTML", reply_markup=main_menu(user_id))
                del user_states[user_id]
                return
            else:
                bot.send_message(user_id, "❌ Kripya valid **Screenshot (Photo)** bhejein!")
                return

    if message.content_type == 'text':
        if text == "📧 Gmail Task":
            if get_setting('gmail_task') == 'OFF' and not is_admin(user_id):
                bot.send_message(user_id, "❌ Option is OFF.")
                return
            current_pass = get_setting('gmail_password')
            reward = get_setting('reward_gmail')
            msg = (f"📧 *GMAIL TASK*\n💰 *Reward:* ₹{reward}\n\n⚠️ *Rules:*\nCreate new Gmail.\nPassword must be - `{current_pass}`\n\n👉 *Click below when Done!*")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✅ Click Here When Done", callback_data="task_done"))
            markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
            bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=markup)

        elif text == "📧 Old Gmail Task":
            if get_setting('old_gmail_task') == 'OFF' and not is_admin(user_id):
                bot.send_message(user_id, "❌ Option is OFF.")
                return
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
            bot.send_message(user_id, "📧 *OLD GMAIL TASK*\n\n👉 Kripya apna valid **Old Gmail Account** bhejein:", parse_mode="Markdown", reply_markup=markup)
            user_states[user_id] = {'state': 'old_gmail_email'}

        elif text == "🗺️ Map Review Task":
            if get_setting('map_review_task') == 'OFF' and not is_admin(user_id):
                bot.send_message(user_id, "❌ Map Review filhal Admin dwara **OFF** hai.")
                return
            
            rules = get_setting('map_rules')
            reward = get_setting('reward_map')
            msg = f"🗺️ *MAP REVIEW TASK*\n💰 *Reward:* ₹{reward}\n\n📜 *Rules & How to Submit:*\n{rules}\n\n👇 *Agree karke Task Lein:*"
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✅ I Agree (Get Task)", callback_data="map_agree"))
            markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
            bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=markup)

        elif text == "💰 Wallet":
            balance_inr = get_balance(user_id)
            msg = f"💼 *YOUR WALLET*\n━━━━━━━━━━━━━━━━━━\n💵 *Balance:* ₹{balance_inr:.2f} / ${balance_inr/USDT_TO_INR_RATE:.2f} USD\n━━━━━━━━━━━━━━━━━━\n\n📊 *Recent Transactions:*\n"
            records = run_query("SELECT type, amount, detail, date FROM history WHERE user_id=%s ORDER BY id DESC LIMIT 5", (user_id,), fetch='all')
            if not records: msg += "📝 _No history found._"
            for r in records: msg += f"{'🟢' if r[0]=='CREDIT' else '🔴'} *₹{r[1]}* | {r[2]}\n📅 {r[3]}\n\n"
            bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=main_menu(user_id))

        elif text == "📞 Contact & Help":
            bot.send_message(user_id, f"📞 <b>CONTACT & SUPPORT</b>\n👨‍💻 Admin ID: @{ADMIN_USERNAME}", parse_mode="HTML", reply_markup=main_menu(user_id))

        elif text == "💸 Withdraw":
            if get_setting('withdraw') == 'OFF' and not is_admin(user_id):
                bot.send_message(user_id, "❌ Withdrawals OFF.")
                return
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(KeyboardButton("🏦 UPI"), KeyboardButton("🪙 USDT"))
            markup.row(KeyboardButton("📜 Withdraw History"), KeyboardButton("🔙 Back to Main"))
            bot.send_message(user_id, f"💸 *WITHDRAW FUNDS*\n🔹 *UPI* (Min ₹{get_setting('min_upi')})\n🔹 *USDT* (Min ${get_setting('min_usdt')})", parse_mode="Markdown", reply_markup=markup)
            
        elif text == "🔙 Back to Main":
            if user_id in user_states: del user_states[user_id]
            bot.send_message(user_id, "🏠 *Main Menu*", parse_mode="Markdown", reply_markup=main_menu(user_id))

        elif text in ["🏦 UPI", "🪙 USDT"]:
            if get_setting('withdraw') == 'OFF' and not is_admin(user_id): return
            bal = get_balance(user_id)
            min_val = float(get_setting('min_upi')) if text == "🏦 UPI" else float(get_setting('min_usdt'))
            check_bal = bal if text == "🏦 UPI" else (bal / USDT_TO_INR_RATE)
            
            if check_bal < min_val:
                bot.send_message(user_id, f"❌ Insufficient Balance! Min: {min_val}", reply_markup=main_menu(user_id))
            else:
                curr = "INR (₹)" if text == "🏦 UPI" else "USDT ($)"
                bot.send_message(user_id, f"📝 Amount likhein in {curr}:", reply_markup=telebot.types.ReplyKeyboardRemove())
                user_states[user_id] = {'state': 'withdraw_amount', 'method': text}

        elif text == "📜 Withdraw History":
            records = run_query("SELECT detail, amount, date FROM history WHERE user_id=%s AND type='DEBIT' ORDER BY id DESC LIMIT 10", (user_id,), fetch='all')
            if not records: bot.send_message(user_id, "📝 _No withdrawal history._", parse_mode="Markdown", reply_markup=main_menu(user_id))
            else:
                msg = "📜 *WITHDRAWAL HISTORY:*\n\n"
                for r in records: msg += f"🔴 *₹{r[1]}* | {r[0]}\n📅 {r[2]}\n\n"
                bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=main_menu(user_id))

        elif text == "⚙️ Admin Panel" and is_admin(user_id):
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("🤖 Bot Toggle", callback_data="admin_bot_toggle"), InlineKeyboardButton("🟢/🔴 Options", callback_data="admin_toggles"))
            markup.row(InlineKeyboardButton("💰 Set Task Rewards", callback_data="admin_reward_menu"), InlineKeyboardButton("🗺️ Manage Map Tasks", callback_data="admin_map_menu"))
            if user_id == OWNER_ID: markup.row(InlineKeyboardButton("👥 Manage Admins", callback_data="admin_manage"))
            markup.row(InlineKeyboardButton("📊 Total Users", callback_data="admin_total_users"), InlineKeyboardButton("⚙️ Set Min Withdraw", callback_data="admin_set_min"))
            markup.row(InlineKeyboardButton("🔑 Gmail Pass", callback_data="admin_set_pass"), InlineKeyboardButton("📜 Approved Withdrawals", callback_data="admin_approved_list"))
            markup.row(InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"), InlineKeyboardButton("💸 Add Balance", callback_data="admin_addbal"))
            bot.send_message(user_id, "🛠️ *ADMIN PANEL*", parse_mode="Markdown", reply_markup=markup)

        # --- DYNAMIC STATES FOR ADMIN & WITHDRAWALS ---
        elif user_id in user_states:
            state_data = user_states[user_id]
            st = state_data['state']

            if st == 'admin_set_map_rules' and is_admin(user_id):
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
                bot.send_message(user_id, f"✅ Bulk Import Done! Added {added} tasks.", reply_markup=main_menu(user_id))
                del user_states[user_id]

            elif st.startswith('admin_set_reward_') and is_admin(user_id):
                try:
                    val = float(text)
                    key = st.replace('admin_set_', '') # e.g. reward_gmail
                    update_setting(key, val)
                    bot.send_message(user_id, f"✅ Reward updated to ₹{val}", reply_markup=main_menu(user_id))
                    del user_states[user_id]
                except ValueError:
                    bot.send_message(user_id, "❌ Kripya number dalein.")

            elif st == 'admin_add_id' and user_id == OWNER_ID:
                try:
                    run_query("INSERT INTO admins (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (int(text),), commit=True)
                    bot.send_message(user_id, f"✅ Admin Added!", reply_markup=main_menu(user_id))
                    del user_states[user_id]
                except: bot.send_message(user_id, "❌ Invalid ID.")

            elif st == 'admin_remove_id' and user_id == OWNER_ID:
                try:
                    run_query("DELETE FROM admins WHERE user_id=%s", (int(text),), commit=True)
                    bot.send_message(user_id, f"✅ Admin Removed!", reply_markup=main_menu(user_id))
                    del user_states[user_id]
                except: bot.send_message(user_id, "❌ Invalid ID.")

            elif st == 'gmail_task_name':
                user_states[user_id] = {'state': 'gmail_task_screenshot', 'gmail_name': text.strip()}
                bot.send_message(user_id, f"📸 *Gmail Name saved:* `{text.strip()}`\n👉 Ab task complete karke **Screenshot** bhejein:", parse_mode="Markdown")

            elif st == 'admin_set_gmail_pass' and is_admin(user_id):
                update_setting('gmail_password', text.strip())
                bot.send_message(user_id, f"✅ Password updated to: `{text.strip()}`", parse_mode="Markdown", reply_markup=main_menu(user_id))
                del user_states[user_id]

            elif st == 'admin_set_min_upi' and is_admin(user_id):
                try: update_setting('min_upi', float(text)); bot.send_message(user_id, f"✅ Updated to ₹{text}", reply_markup=main_menu(user_id)); del user_states[user_id]
                except: bot.send_message(user_id, "❌ Invalid.")

            elif st == 'admin_set_min_usdt' and is_admin(user_id):
                try: update_setting('min_usdt', float(text)); bot.send_message(user_id, f"✅ Updated to ${text}", reply_markup=main_menu(user_id)); del user_states[user_id]
                except: bot.send_message(user_id, "❌ Invalid.")

            elif st == 'old_gmail_email':
                user_states[user_id] = {'state': 'old_gmail_password', 'gmail_email': text.strip()}
                bot.send_message(user_id, f"✅ Saved: `{text.strip()}`\n👉 Ab iska **Password** bhejein:", parse_mode="Markdown")

            elif st == 'old_gmail_password':
                bot.send_message(user_id, "✅ Submitted to admin.", reply_markup=main_menu(user_id))
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"oldappr_{user_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"oldrej_{user_id}"))
                bot.send_message(OWNER_ID, f"🔔 <b>OLD GMAIL</b>\n👤 <code>{user_id}</code>\n📧 <code>{state_data['gmail_email']}</code>\n🔑 <code>{text.strip()}</code>", parse_mode="HTML", reply_markup=markup)
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
                    bot.send_message(user_id, f"✅ Amount saved. Ab apna UPI/BP20 Address bhejein:")
                except:
                    bot.send_message(user_id, "❌ Invalid Amount or Insufficient Bal.", reply_markup=main_menu(user_id))
                    del user_states[user_id]

            elif st == 'withdraw_address':
                meth = state_data['method']
                val = state_data['amt']
                val_inr = val if meth == "🏦 UPI" else val * USDT_TO_INR_RATE
                deduct_balance(user_id, val_inr, f"Pending {meth} Withdraw ({val})")
                
                pid = run_query("INSERT INTO pending_withdraws (user_id, method, address, amount) VALUES (%s, %s, %s, %s) RETURNING id", (user_id, meth, text.strip(), val), fetch='id', commit=True)
                bot.send_message(user_id, "✅ Withdraw Request Submitted!", reply_markup=main_menu(user_id))
                
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"apprw_{pid}"), InlineKeyboardButton("❌ Reject", callback_data=f"rejcc_{pid}"))
                bot.send_message(OWNER_ID, f"🔔 <b>WITHDRAW</b>\n👤 <code>{user_id}</code>\n🏦 {meth}\n💰 {val}\n📌 <code>{text.strip()}</code>", parse_mode="HTML", reply_markup=markup)
                del user_states[user_id]

            elif st == 'admin_wait_uid' and is_admin(user_id):
                try: user_states[user_id] = {'state': 'admin_wait_amt', 'uid': int(text)}; bot.send_message(user_id, "👉 Amount in ₹:")
                except: del user_states[user_id]

            elif st == 'admin_wait_amt' and is_admin(user_id):
                try:
                    add_balance(state_data['uid'], float(text), "Admin Added Balance")
                    bot.send_message(user_id, "✅ Added!", reply_markup=main_menu(user_id))
                    try: bot.send_message(state_data['uid'], f"🎉 Admin added ₹{text}!")
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
        bot.send_message(user_id, "🏠 *Main Menu*", parse_mode="Markdown", reply_markup=main_menu(user_id))

    # 👉 MAP REVIEW SYSTEM logic
    elif data == "map_agree":
        if get_setting('map_review_task') == 'OFF':
            bot.answer_callback_query(call.id, "Map Task OFF hai!", show_alert=True); return
        
        # Check if already pending
        chk = run_query("SELECT id, link, review_text FROM map_tasks WHERE assigned_to=%s AND status='PENDING'", (user_id,), fetch='one')
        if chk:
            t_id, t_link, t_txt = chk
            msg = f"⚠️ *Aapke paas pehle se ek task pending hai:*\n\n🔗 *Link:* {t_link}\n💬 *Review Text:* `{t_txt}`"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("✅ Done (Send SS)", callback_data=f"mapdone_{t_id}"), InlineKeyboardButton("❌ Cancel Task", callback_data=f"mapcancel_{t_id}"))
            bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=markup)
            return

        # Fetch new task specifically assigning it
        task = run_query("UPDATE map_tasks SET status='PENDING', assigned_to=%s WHERE id = (SELECT id FROM map_tasks WHERE status='AVAILABLE' LIMIT 1) RETURNING id, link, review_text", (user_id,), fetch='one', commit=True)
        
        if not task:
            bot.answer_callback_query(call.id, "🚫 No Review Task Available Right Now!", show_alert=True)
        else:
            t_id, t_link, t_txt = task
            msg = f"🎉 *Task Assigned!*\n\n🔗 *Click Link:* {t_link}\n💬 *Post this Review:* `{t_txt}`\n\n👉 *Review karne ke baad Done par click karein.*"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("✅ Done (Send SS)", callback_data=f"mapdone_{t_id}"), InlineKeyboardButton("❌ Cancel Task", callback_data=f"mapcancel_{t_id}"))
            bot.edit_message_text(msg, user_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif data.startswith("mapdone_"):
        t_id = data.split("_")[1]
        user_states[user_id] = {'state': 'map_task_screenshot', 'task_id': t_id}
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
        bot.send_message(user_id, "📸 *Kripya review post karne ka Screenshot bhejein:*", parse_mode="Markdown", reply_markup=markup)

    elif data.startswith("mapcancel_"):
        t_id = data.split("_")[1]
        run_query("UPDATE map_tasks SET status='AVAILABLE', assigned_to=NULL WHERE id=%s", (t_id,), commit=True)
        bot.edit_message_text("❌ *Task Cancelled.* Wapas stock me chala gaya.", user_id, call.message.message_id, parse_mode="Markdown")

    elif data.startswith("mappr_") and is_admin(user_id):
        tgt = int(data.split("_")[1])
        t_id = int(data.split("_")[2])
        rw = float(get_setting('reward_map'))
        add_balance(tgt, rw, "Map Review Approved")
        run_query("UPDATE map_tasks SET status='COMPLETED' WHERE id=%s", (t_id,), commit=True)
        try: bot.send_message(tgt, f"🎉 Map Review Approved! ₹{rw} added.")
        except: pass
        try: bot.edit_message_caption(f"✅ Map Review Approved for <code>{tgt}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        except: pass

    elif data.startswith("mrej_") and is_admin(user_id):
        tgt = int(data.split("_")[1])
        t_id = int(data.split("_")[2])
        # Reject means goes back to stock!
        run_query("UPDATE map_tasks SET status='AVAILABLE', assigned_to=NULL WHERE id=%s", (t_id,), commit=True)
        try: bot.send_message(tgt, f"❌ Map Review Rejected.")
        except: pass
        try: bot.edit_message_caption(f"❌ Map Rejected (Back to Stock) for <code>{tgt}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        except: pass

    elif data == "task_done":
        if get_setting('gmail_task') == 'OFF' and not is_admin(user_id): return
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="back_to_main"))
        bot.send_message(user_id, "📧 Apna **Gmail Name** type karein:", parse_mode="Markdown", reply_markup=markup)
        user_states[user_id] = {'state': 'gmail_task_name'}

    # Admin Panel Menus
    elif data == "admin_map_menu" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("➕ Add Single Task", callback_data="map_add_single"))
        markup.row(InlineKeyboardButton("📚 Bulk Add Tasks", callback_data="map_add_bulk"))
        markup.row(InlineKeyboardButton("📝 Edit Task Rules", callback_data="map_edit_rules"))
        markup.row(InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back"))
        avail = run_query("SELECT count(id) FROM map_tasks WHERE status='AVAILABLE'", fetch='one')[0]
        bot.edit_message_text(f"🗺️ *MAP TASK MANAGER*\nAvailable in Stock: {avail}", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif data == "map_add_single" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_map_add_single'}
        bot.send_message(user_id, "📝 Task bhejein is format me:\n`Link | Review Text`\n(Dhyan rahe beech me `|` lagana zaroori hai)", parse_mode="Markdown")

    elif data == "map_add_bulk" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_map_add_bulk'}
        bot.send_message(user_id, "📚 Bulk List bhejein har task new line me:\n`Link1 | Review1`\n`Link2 | Review2`", parse_mode="Markdown")

    elif data == "map_edit_rules" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_set_map_rules'}
        bot.send_message(user_id, "📝 Kripya naye Map Review rules / instructions bhejein:")

    elif data == "admin_reward_menu" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton(f"Gmail (₹{get_setting('reward_gmail')})", callback_data="setrw_reward_gmail"))
        markup.row(InlineKeyboardButton(f"Old Gmail (₹{get_setting('reward_oldgmail')})", callback_data="setrw_reward_oldgmail"))
        markup.row(InlineKeyboardButton(f"Map Review (₹{get_setting('reward_map')})", callback_data="setrw_reward_map"))
        markup.row(InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back"))
        bot.edit_message_text("💰 *SET TASK REWARDS*\nSelect task to change reward:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif data.startswith("setrw_") and is_admin(user_id):
        key = data.split("setrw_")[1]
        user_states[user_id] = {'state': f'admin_set_{key}'}
        bot.send_message(user_id, "📝 Naya Reward Amount (₹) likhein:")

    elif data == "admin_toggles" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton(f"Gmail: {'🟢' if get_setting('gmail_task')=='ON' else '🔴'}", callback_data="toggle_gmail_task"))
        markup.row(InlineKeyboardButton(f"Old Gmail: {'🟢' if get_setting('old_gmail_task')=='ON' else '🔴'}", callback_data="toggle_old_gmail_task"))
        markup.row(InlineKeyboardButton(f"Map Task: {'🟢' if get_setting('map_review_task')=='ON' else '🔴'}", callback_data="toggle_map_review_task"))
        markup.row(InlineKeyboardButton(f"Withdraw: {'🟢' if get_setting('withdraw')=='ON' else '🔴'}", callback_data="toggle_withdraw"))
        markup.row(InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back"))
        bot.edit_message_text("🎛️ *TOGGLE OPTIONS*", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif data.startswith("toggle_") and is_admin(user_id):
        key = data.replace("toggle_", "")
        current = get_setting(key)
        update_setting(key, "OFF" if current == "ON" else "ON")
        # Refresh logic manually (lazy refresh)
        bot.answer_callback_query(call.id, f"Toggled {key}!", show_alert=True)

    elif data == "admin_bot_toggle" and is_admin(user_id):
        update_setting('bot_status', "OFF" if get_setting('bot_status') == "ON" else "ON")
        bot.answer_callback_query(call.id, "Bot Status Changed!", show_alert=True)

    elif data == "admin_back" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🤖 Bot Toggle", callback_data="admin_bot_toggle"), InlineKeyboardButton("🟢/🔴 Options", callback_data="admin_toggles"))
        markup.row(InlineKeyboardButton("💰 Set Task Rewards", callback_data="admin_reward_menu"), InlineKeyboardButton("🗺️ Manage Map Tasks", callback_data="admin_map_menu"))
        if user_id == OWNER_ID: markup.row(InlineKeyboardButton("👥 Manage Admins", callback_data="admin_manage"))
        markup.row(InlineKeyboardButton("📊 Total Users", callback_data="admin_total_users"), InlineKeyboardButton("⚙️ Set Min Withdraw", callback_data="admin_set_min"))
        markup.row(InlineKeyboardButton("🔑 Gmail Pass", callback_data="admin_set_pass"), InlineKeyboardButton("📜 Approved Withdrawals", callback_data="admin_approved_list"))
        markup.row(InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"), InlineKeyboardButton("💸 Add Balance", callback_data="admin_addbal"))
        bot.edit_message_text("🛠️ *ADMIN PANEL*", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif data == "admin_set_min" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("Set Min UPI (₹)", callback_data="set_min_upi"), InlineKeyboardButton("Set Min USDT ($)", callback_data="set_min_usdt"))
        markup.row(InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back"))
        bot.edit_message_text("⚙️ *SET MIN*", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
    
    elif data == "set_min_upi" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_set_min_upi'}; bot.send_message(user_id, "📝 UPI Min (₹):")
    elif data == "set_min_usdt" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_set_min_usdt'}; bot.send_message(user_id, "📝 USDT Min ($):")
    elif data == "admin_set_pass" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_set_gmail_pass'}; bot.send_message(user_id, "🔑 Naya Gmail Pass:")

    elif data == "admin_total_users" and is_admin(user_id):
        bot.answer_callback_query(call.id, f"Users: {len(get_all_users())}", show_alert=True)
    
    # Approvals with Dynamic Amounts
    elif data.startswith("oldappr_") and is_admin(user_id):
        tgt = int(data.split("_")[1])
        rw = float(get_setting('reward_oldgmail'))
        add_balance(tgt, rw, "Old Gmail Task Approved")
        try: bot.edit_message_caption(f"✅ Approved (₹{rw}) for {tgt}", call.message.chat.id, call.message.message_id)
        except: bot.edit_message_text(f"✅ Approved (₹{rw}) for {tgt}", call.message.chat.id, call.message.message_id)
        try: bot.send_message(tgt, f"🎉 Old Gmail Approved! ₹{rw} added.")
        except: pass

    elif data.startswith("apprt_") and is_admin(user_id):
        tgt = int(data.split("_")[1])
        rw = float(get_setting('reward_gmail'))
        add_balance(tgt, rw, "Gmail Task Approved")
        try: bot.edit_message_caption(f"✅ Approved (₹{rw}) for {tgt}", call.message.chat.id, call.message.message_id)
        except: bot.edit_message_text(f"✅ Approved (₹{rw}) for {tgt}", call.message.chat.id, call.message.message_id)
        try: bot.send_message(tgt, f"🎉 Gmail Task Approved! ₹{rw} added.")
        except: pass

    elif data.startswith("oldrej_") or data.startswith("rejct_"):
        if is_admin(user_id):
            tgt = int(data.split("_")[1])
            try: bot.edit_message_caption(f"❌ Rejected for {tgt}", call.message.chat.id, call.message.message_id)
            except: bot.edit_message_text(f"❌ Rejected for {tgt}", call.message.chat.id, call.message.message_id)
            try: bot.send_message(tgt, "❌ Task Rejected.")
            except: pass

    # Withdraw Handling
    elif data.startswith("apprw_") and is_admin(user_id): 
        pid = int(data.split("_")[1])
        req = run_query("SELECT user_id, amount, method, address FROM pending_withdraws WHERE id=%s", (pid,), fetch='one')
        if req:
            t_user, amt, meth, addr = req
            dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            if run_query("INSERT INTO approved_withdraws (user_id, method, address, amount, date) VALUES (%s, %s, %s, %s, %s) RETURNING id", (t_user, meth, addr, amt, dt), fetch='id', commit=True):
                curr = "₹" if meth == "🏦 UPI" else "$"
                try: bot.edit_message_text(f"✅ Withdraw Approved for {t_user}", call.message.chat.id, call.message.message_id)
                except: pass
                try: bot.send_message(t_user, f"🎉 Payment Sent! {meth}: {curr}{amt}")
                except: pass
                run_query("DELETE FROM pending_withdraws WHERE id=%s", (pid,), commit=True)
            else: bot.answer_callback_query(call.id, "⚠️ Error!", show_alert=True)
        else: bot.answer_callback_query(call.id, "⚠️ Already processed!", show_alert=True)

    elif data.startswith("rejcc_") and is_admin(user_id): 
        pid = int(data.split("_")[1])
        req = run_query("SELECT user_id, amount, method FROM pending_withdraws WHERE id=%s", (pid,), fetch='one')
        if req:
            t_user, amt, meth = req
            add_balance(t_user, amt if meth == "🏦 UPI" else amt * USDT_TO_INR_RATE, f"Refund: {meth} Rejected")
            try: bot.edit_message_text(f"❌ Rejected & Refunded for {t_user}", call.message.chat.id, call.message.message_id)
            except: pass
            try: bot.send_message(t_user, "❌ Withdraw Rejected & Refunded.")
            except: pass
            run_query("DELETE FROM pending_withdraws WHERE id=%s", (pid,), commit=True)

# --- START BOT ---
print("Bot running with New Token & DB URL...")
bot.polling(none_stop=True)
