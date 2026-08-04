import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2
import datetime
import time

# --- CONFIGURATION ---
TOKEN = '8683212510:AAEdE8kq5-5GuKerfPa_Mzaxovgb-J5VU4w'
OWNER_ID = 8894779077  # Main Super Admin ID
ADMIN_USERNAME = 'Raka_01'  

# 👉 Tumhara Naya Neon.tech PostgreSQL Database URL 👈
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
    run_query('''CREATE TABLE IF NOT EXISTS users
                 (user_id BIGINT PRIMARY KEY, balance FLOAT DEFAULT 0)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS history
                 (id SERIAL PRIMARY KEY, user_id BIGINT, type TEXT, amount FLOAT, detail TEXT, date TEXT)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS pending_withdraws
                 (id SERIAL PRIMARY KEY, user_id BIGINT, method TEXT, address TEXT, amount FLOAT)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS approved_withdraws
                 (id SERIAL PRIMARY KEY, user_id BIGINT, method TEXT, address TEXT, amount FLOAT, date TEXT)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS admins
                 (user_id BIGINT PRIMARY KEY)''', commit=True)
    run_query('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''', commit=True)
    
    # Ensure Main Owner is always in admins table
    run_query("INSERT INTO admins (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (OWNER_ID,), commit=True)

    default_settings = {
        'bot_status': 'ON',
        'gmail_task': 'ON',
        'old_gmail_task': 'ON',
        'withdraw': 'ON',
        'min_upi': '15.0',
        'min_usdt': '0.16',
        'gmail_password': 'ethicbro999'
    }
    for k, v in default_settings.items():
        run_query("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", (k, v), commit=True)

init_db()

# --- HELPER FUNCTIONS ---
def is_admin(user_id):
    if user_id == OWNER_ID:
        return True
    res = run_query("SELECT user_id FROM admins WHERE user_id=%s", (user_id,), fetch='one')
    return res is not None

def get_setting(key):
    res = run_query("SELECT value FROM settings WHERE key=%s", (key,), fetch='one')
    return res[0] if res else 'ON'

def update_setting(key, value):
    run_query("UPDATE settings SET value=%s WHERE key=%s", (str(value), key), commit=True)

def get_balance(user_id):
    res = run_query("SELECT balance FROM users WHERE user_id=%s", (user_id,), fetch='one')
    if res:
        return res[0]
    else:
        run_query("INSERT INTO users (user_id, balance) VALUES (%s, %s)", (user_id, 0), commit=True)
        return 0

def add_balance(user_id, amount, detail):
    current = get_balance(user_id)
    new_balance = current + amount
    run_query("UPDATE users SET balance=%s WHERE user_id=%s", (new_balance, user_id), commit=True)
    date_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_query("INSERT INTO history (user_id, type, amount, detail, date) VALUES (%s, %s, %s, %s, %s)", 
              (user_id, "CREDIT", amount, detail, date_now), commit=True)

def deduct_balance(user_id, amount, detail):
    current = get_balance(user_id)
    new_balance = current - amount
    run_query("UPDATE users SET balance=%s WHERE user_id=%s", (new_balance, user_id), commit=True)
    date_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_query("INSERT INTO history (user_id, type, amount, detail, date) VALUES (%s, %s, %s, %s, %s)", 
              (user_id, "DEBIT", amount, detail, date_now), commit=True)

def get_all_users():
    records = run_query("SELECT user_id FROM users", fetch='all')
    return [row[0] for row in records] if records else []

# --- MAIN MENU ---
def main_menu(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("📧 Gmail Task"), KeyboardButton("📧 Old Gmail Task"))
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
    is_new = res is None
    get_balance(user_id) 
    
    if is_new and not is_admin(user_id):
        try:
            bot.send_message(OWNER_ID, f"🚀 <b>New User Started Bot!</b>\n\n👤 <b>User ID:</b> <code>{user_id}</code>\n👤 <b>Name:</b> {message.from_user.first_name}", parse_mode="HTML")
        except:
            pass

    msg = (f"✨ <b>WELCOME TO OUR BOT!</b> ✨\n\n"
           f"Hello {message.from_user.first_name}, yahan aap simple tasks complete karke real cash earn kar sakte hain! 💸\n\n"
           f"👇 <b>Niche diye gaye buttons se apna task shuru karein:</b>")
    bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=main_menu(user_id))

# --- MAIN TEXT & BROADCAST HANDLER ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_all_messages(message):
    user_id = message.chat.id
    text = message.text if message.text else message.caption

    if get_setting('bot_status') == 'OFF' and not is_admin(user_id):
        bot.send_message(user_id, "🛠️ <b>Bot is currently OFF for Maintenance!</b>", parse_mode="HTML")
        return

    # 1. ADMIN BROADCAST CHECK
    if user_id in user_states and user_states[user_id].get('state') == 'admin_wait_broadcast' and is_admin(user_id):
        del user_states[user_id] 
        bot.send_message(user_id, "⏳ <b>Broadcast Started...</b> Please wait.", parse_mode="HTML")
        
        users = get_all_users()
        success = 0
        failed = 0
        
        for u_id in users:
            try:
                bot.copy_message(chat_id=u_id, from_chat_id=user_id, message_id=message.message_id)
                success += 1
                time.sleep(0.04) 
            except Exception:
                failed += 1
                
        bot.send_message(user_id, f"✅ <b>Broadcast Complete!</b>\n\n🚀 Sent: {success}\n❌ Failed (Blocked): {failed}", parse_mode="HTML", reply_markup=main_menu(user_id))
        return

    # 2. GMAIL TASK: WAITING FOR SCREENSHOT AFTER GMAIL NAME
    if user_id in user_states and user_states[user_id].get('state') == 'gmail_task_screenshot':
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            gmail_name = user_states[user_id]['gmail_name']
            
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"apprt_{user_id}"),
                       InlineKeyboardButton("❌ Reject", callback_data=f"rejct_{user_id}"))
            
            admin_msg = (f"🔔 <b>NEW GMAIL TASK SUBMISSION</b>\n\n"
                         f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
                         f"📧 <b>Gmail Name:</b> <code>{gmail_name}</code>\n\n"
                         f"Please check screenshot.")
            bot.send_photo(OWNER_ID, file_id, caption=admin_msg, parse_mode="HTML", reply_markup=markup)
            
            bot.send_message(user_id, "✅ <b>Apka Screenshot aur Gmail Name Admin ko bhaj diya gaya hai. Pls Wait For Checking in 24Hrs. Be Patient.</b>", parse_mode="HTML", reply_markup=main_menu(user_id))
            del user_states[user_id]
            return
        else:
            bot.send_message(user_id, "❌ Kripya task complete karne ke baad valid **Screenshot (Photo)** bhejein!")
            return

    # 3. NORMAL TEXT MENU & STATES HANDLER
    if message.content_type == 'text':
        
        # 👉 STEP 1: SHOW RULES AND DONE BUTTON
        if text == "📧 Gmail Task":
            if get_setting('gmail_task') == 'OFF' and not is_admin(user_id):
                bot.send_message(user_id, "❌ Yeh option filhal Admin dwara **OFF** kar diya gaya hai. Kripya baad mein try karein.")
                return
            
            current_pass = get_setting('gmail_password')
            msg = (f"📧 *GMAIL TASK*\n"
                   f"💰 *Reward:* ₹15\n\n"
                   f"⚠️ *Instructions & Rules:*\n"
                   f"Rule - Create a new Gmail account.\n"
                   f"Password must be - `{current_pass}`\n\n"
                   f"👉 *Complete the task and click the button below!*")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✅ Click Here When Done", callback_data="task_done"))
            markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
            bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=markup)

        elif text == "📧 Old Gmail Task":
            if get_setting('old_gmail_task') == 'OFF' and not is_admin(user_id):
                bot.send_message(user_id, "❌ Yeh option filhal Admin dwara **OFF** kar diya gaya hai. Kripya baad mein try karein.")
                return
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
            msg = ("📧 *OLD GMAIL TASK*\n\n"
                   "👉 Kripya apna valid **Old Gmail Account** yahan bhejein (jaise: `example@gmail.com`):")
            bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=markup)
            user_states[user_id] = {'state': 'old_gmail_email'}

        elif text == "💰 Wallet":
            balance_inr = get_balance(user_id)
            balance_usd = balance_inr / USDT_TO_INR_RATE
            
            msg = (f"💼 *YOUR WALLET*\n"
                   f"━━━━━━━━━━━━━━━━━━\n"
                   f"💵 *Balance:* ₹{balance_inr:.2f} / ${balance_usd:.2f} USD\n"
                   f"━━━━━━━━━━━━━━━━━━\n\n"
                   f"📊 *Recent Transactions:*\n")
            records = run_query("SELECT type, amount, detail, date FROM history WHERE user_id=%s ORDER BY id DESC LIMIT 5", (user_id,), fetch='all')
            if not records:
                msg += "📝 _No history found yet._"
            for r in records:
                icon = "🟢" if r[0] == "CREDIT" else "🔴"
                r_usd = r[1] / USDT_TO_INR_RATE
                msg += f"{icon} *₹{r[1]} (${r_usd:.2f}u)* | {r[2]}\n📅 {r[3]}\n\n"
            bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=main_menu(user_id))

        elif text == "📞 Contact & Help":
            msg = ("📞 <b>CONTACT & SUPPORT</b>\n\n"
                   "Agar aapko koi problem aa rahi hai ya payment se related koi sawal hai, toh humare Admin se direct baat karein:\n\n"
                   f"👨‍💻 <b>Admin ID:</b> @{ADMIN_USERNAME}\n"
                   "💬 <i>Click on the username to send a message.</i>")
            bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=main_menu(user_id))

        elif text == "💸 Withdraw":
            if get_setting('withdraw') == 'OFF' and not is_admin(user_id):
                bot.send_message(user_id, "❌ Withdrawals filhal Admin dwara **OFF** kiye gaye hain.")
                return
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(KeyboardButton("🏦 UPI"), KeyboardButton("🪙 USDT"))
            markup.row(KeyboardButton("📜 Withdraw History"), KeyboardButton("🔙 Back to Main"))
            msg = ("💸 *WITHDRAW FUNDS*\n\n"
                   "Apna preferred withdrawal method select karein:\n"
                   f"🔹 *UPI* (Minimum ₹{get_setting('min_upi')})\n"
                   f"🔹 *USDT* (Minimum ${get_setting('min_usdt')})")
            bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=markup)
            
        elif text == "🔙 Back to Main":
            if user_id in user_states:
                del user_states[user_id]
            bot.send_message(user_id, "🏠 *Main Menu*", parse_mode="Markdown", reply_markup=main_menu(user_id))

        elif text in ["🏦 UPI", "🪙 USDT"]:
            if get_setting('withdraw') == 'OFF' and not is_admin(user_id):
                bot.send_message(user_id, "❌ Withdrawals are currently disabled.")
                return
            balance_inr = get_balance(user_id)
            if text == "🏦 UPI":
                min_amount = float(get_setting('min_upi'))
                if balance_inr < min_amount:
                    bot.send_message(user_id, f"❌ *Insufficient Balance!*\nMinimum withdrawal ke liye ₹{min_amount} chahiye.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                else:
                    bot.send_message(user_id, f"📝 Kripya apna withdrawal amount likhein in **INR (₹)** (Min: ₹{min_amount}):", parse_mode="Markdown", reply_markup=telebot.types.ReplyKeyboardRemove())
                    user_states[user_id] = {'state': 'withdraw_amount', 'method': text}
            else:
                min_usd = float(get_setting('min_usdt'))
                min_inr = min_usd * USDT_TO_INR_RATE
                if balance_inr < min_inr:
                    bot.send_message(user_id, f"❌ *Insufficient Balance!*\nMinimum withdrawal ke liye ${min_usd} USD (₹{min_inr:.2f}) chahiye.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                else:
                    bot.send_message(user_id, f"📝 Kripya apna withdrawal amount likhein in **USDT ($)** (Min: ${min_usd}):", parse_mode="Markdown", reply_markup=telebot.types.ReplyKeyboardRemove())
                    user_states[user_id] = {'state': 'withdraw_amount', 'method': text}

        elif text == "📜 Withdraw History":
            records = run_query("SELECT detail, amount, date FROM history WHERE user_id=%s AND type='DEBIT' ORDER BY id DESC LIMIT 10", (user_id,), fetch='all')
            if not records:
                bot.send_message(user_id, "📝 _Aapki koi withdrawal history nahi hai._", parse_mode="Markdown", reply_markup=main_menu(user_id))
            else:
                msg = "📜 *WITHDRAWAL HISTORY:*\n\n"
                for r in records:
                    r_usd = r[1] / USDT_TO_INR_RATE
                    msg += f"🔴 *₹{r[1]} (${r_usd:.2f}u)* | {r[0]}\n📅 {r[2]}\n\n"
                bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=main_menu(user_id))

        elif text == "⚙️ Admin Panel" and is_admin(user_id):
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("🤖 Bot ON/OFF", callback_data="admin_bot_toggle"))
            if user_id == OWNER_ID:
                markup.row(InlineKeyboardButton("👥 Manage Admins", callback_data="admin_manage"))
            markup.row(InlineKeyboardButton("📊 Total Users", callback_data="admin_total_users"))
            markup.row(InlineKeyboardButton("🟢/🔴 Toggle Options", callback_data="admin_toggles"))
            markup.row(InlineKeyboardButton("⚙️ Set Min Withdraw", callback_data="admin_set_min"))
            markup.row(InlineKeyboardButton("🔑 Change Gmail Pass", callback_data="admin_set_pass"))
            markup.row(InlineKeyboardButton("📜 Approved Withdrawals", callback_data="admin_approved_list"))
            markup.row(InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast"))
            markup.row(InlineKeyboardButton("💸 Add Balance to User", callback_data="admin_addbal"))
            markup.row(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
            bot.send_message(user_id, "🛠️ *ADMIN PANEL*\nKripya option select karein:", parse_mode="Markdown", reply_markup=markup)

        # --- DYNAMIC STATES ---
        elif user_id in user_states:
            state_data = user_states[user_id]
            
            if state_data['state'] == 'admin_add_id' and user_id == OWNER_ID:
                try:
                    new_admin_id = int(text.strip())
                    run_query("INSERT INTO admins (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (new_admin_id,), commit=True)
                    bot.send_message(user_id, f"✅ Success! User <code>{new_admin_id}</code> ko Admin access de diya gaya hai.", parse_mode="HTML", reply_markup=main_menu(user_id))
                    del user_states[user_id]
                except ValueError:
                    bot.send_message(user_id, "❌ Kripya valid numeric User ID dalein.")
                return

            elif state_data['state'] == 'admin_remove_id' and user_id == OWNER_ID:
                try:
                    rem_admin_id = int(text.strip())
                    if rem_admin_id == OWNER_ID:
                        bot.send_message(user_id, "❌ Owner ko remove nahi kiya ja sakta!")
                        return
                    run_query("DELETE FROM admins WHERE user_id=%s", (rem_admin_id,), commit=True)
                    bot.send_message(user_id, f"✅ Success! User <code>{rem_admin_id}</code> se Admin access hata diya gaya hai.", parse_mode="HTML", reply_markup=main_menu(user_id))
                    del user_states[user_id]
                except ValueError:
                    bot.send_message(user_id, "❌ Kripya valid numeric User ID dalein.")
                return

            # 👉 STEP 3: USER SUBMITS GMAIL NAME -> ASK FOR SCREENSHOT
            elif state_data['state'] == 'gmail_task_name':
                gmail_name = text.strip()
                user_states[user_id] = {'state': 'gmail_task_screenshot', 'gmail_name': gmail_name}
                
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
                bot.send_message(user_id, f"📸 *Gmail Name saved:* `{gmail_name}`\n\n👉 Ab task complete karne ke baad **Screenshot (Photo)** bhejein:", parse_mode="Markdown", reply_markup=markup)
                return

            elif state_data['state'] == 'admin_set_gmail_pass' and is_admin(user_id):
                new_pass = text.strip()
                update_setting('gmail_password', new_pass)
                bot.send_message(user_id, f"✅ Gmail task password successfully updated to: <code>{new_pass}</code>", parse_mode="HTML", reply_markup=main_menu(user_id))
                del user_states[user_id]
                return

            elif state_data['state'] == 'admin_set_min_upi' and is_admin(user_id):
                try:
                    new_val = float(text)
                    update_setting('min_upi', new_val)
                    bot.send_message(user_id, f"✅ UPI Minimum withdrawal successfully updated to: ₹{new_val}", reply_markup=main_menu(user_id))
                    del user_states[user_id]
                except ValueError:
                    bot.send_message(user_id, "❌ Kripya valid number dalein.")
                return

            elif state_data['state'] == 'admin_set_min_usdt' and is_admin(user_id):
                try:
                    new_val = float(text)
                    update_setting('min_usdt', new_val)
                    bot.send_message(user_id, f"✅ USDT Minimum withdrawal successfully updated to: ${new_val}", reply_markup=main_menu(user_id))
                    del user_states[user_id]
                except ValueError:
                    bot.send_message(user_id, "❌ Kripya valid number dalein.")
                return

            elif state_data['state'] == 'old_gmail_email':
                gmail_email = text.strip()
                if "@" not in gmail_email or not gmail_email.endswith("@gmail.com"):
                    bot.send_message(user_id, "❌ *Invalid Gmail Format!*\nKripya sahi format me gmail bhejein (Jaise: `yourname@gmail.com`). Dobara type karein:")
                    return

                user_states[user_id] = {'state': 'old_gmail_password', 'gmail_email': gmail_email}
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
                bot.send_message(user_id, f"✅ Email saved: <code>{gmail_email}</code>\n\n👉 Ab iska <b>Password</b> bhejein:", parse_mode="HTML", reply_markup=markup)

            elif state_data['state'] == 'old_gmail_password':
                gmail_pass = text.strip()
                gmail_email = state_data['gmail_email']
                
                bot.send_message(user_id, "✅ *Old Gmail Submitted!*\nAapka task Admin ke paas bhej diya gaya hai.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"oldappr_{user_id}"),
                           InlineKeyboardButton("❌ Reject", callback_data=f"oldrej_{user_id}"))
                
                admin_msg = (f"🔔 <b>NEW OLD GMAIL SUBMISSION</b>\n\n"
                             f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
                             f"📧 <b>Gmail Name:</b> <code>{gmail_email}</code>\n"
                             f"🔑 <b>Password:</b> <code>{gmail_pass}</code>")
                bot.send_message(OWNER_ID, admin_msg, parse_mode="HTML", reply_markup=markup)
                del user_states[user_id]

            elif state_data['state'] == 'withdraw_amount':
                try:
                    input_val = float(text)
                    method = state_data['method']
                    balance_inr = get_balance(user_id)
                    
                    if method == "🏦 UPI":
                        amount_inr = input_val
                        min_val = float(get_setting('min_upi'))
                        if amount_inr < min_val or amount_inr > balance_inr:
                            bot.send_message(user_id, f"❌ *Invalid Amount!* Min limit ₹{min_val} hai ya balance kam hai.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                            del user_states[user_id]
                            return
                    else: 
                        amount_usd = input_val
                        amount_inr = amount_usd * USDT_TO_INR_RATE
                        min_val = float(get_setting('min_usdt'))
                        if amount_usd < min_val or amount_inr > balance_inr:
                            bot.send_message(user_id, f"❌ *Invalid Amount!* Min limit ${min_val} hai ya balance kam hai.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                            del user_states[user_id]
                            return

                    user_states[user_id]['amount_inr'] = amount_inr
                    user_states[user_id]['display_amount'] = input_val
                    user_states[user_id]['state'] = 'withdraw_address'
                    
                    ask_str = "UPI ID" if method == "🏦 UPI" else "BP20 Address"
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
                    bot.send_message(user_id, f"✅ Amount saved: {input_val} {'₹' if method == '🏦 UPI' else '$'}\n\n👉 Ab apna *{ask_str}* bhejein:", parse_mode="Markdown", reply_markup=markup)
                except ValueError:
                    bot.send_message(user_id, "❌ Sirf numbers mein amount likhein.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                    del user_states[user_id]

            elif state_data['state'] == 'withdraw_address':
                address = text.strip()
                method = state_data['method']
                
                if method == "🏦 UPI" and "@" not in address:
                    bot.send_message(user_id, "❌ *Invalid UPI ID!*\nSahi UPI ID dalein jisme '@' ho. Dobara bhejein:")
                    return
                    
                if method == "🪙 USDT" and (not address.startswith("0x") or len(address) < 30):
                    bot.send_message(user_id, "❌ *Invalid USDT Address!*\nAddress '0x' se start hona chahiye. Dobara bhejein:")
                    return

                amount_inr = state_data['amount_inr']
                display_amount = state_data['display_amount']
                
                deduct_balance(user_id, amount_inr, f"Pending {method} Withdraw ({display_amount})")
                
                pending_id = run_query("INSERT INTO pending_withdraws (user_id, method, address, amount) VALUES (%s, %s, %s, %s) RETURNING id", 
                                       (user_id, method, address, display_amount), fetch='id', commit=True)
                
                bot.send_message(user_id, "✅ *Request Submitted!*\nAapka withdrawal request Admin ko bhej diya gaya hai.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"apprw_{pending_id}"),
                           InlineKeyboardButton("❌ Reject", callback_data=f"rejcc_{pending_id}"))
                
                curr_symbol = "₹" if method == "🏦 UPI" else "$"
                admin_msg = (f"🔔 <b>NEW WITHDRAW REQUEST</b>\n\n"
                             f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
                             f"🏦 <b>Method:</b> {method}\n"
                             f"💰 <b>Amount:</b> {curr_symbol}{display_amount}\n"
                             f"📌 <b>Address:</b> <code>{address}</code>")
                bot.send_message(OWNER_ID, admin_msg, parse_mode="HTML", reply_markup=markup)
                del user_states[user_id]

            elif state_data['state'] == 'admin_wait_uid' and is_admin(user_id):
                try:
                    target_uid = int(text)
                    user_states[user_id] = {'state': 'admin_wait_amt', 'target_uid': target_uid}
                    bot.send_message(user_id, f"✅ User ID saved: `{target_uid}`\n\n👉 Ab *Amount (in ₹)* likhein jo add karna hai:", parse_mode="Markdown")
                except ValueError:
                    bot.send_message(user_id, "❌ User ID number format mein hona chahiye.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                    del user_states[user_id]

            elif state_data['state'] == 'admin_wait_amt' and is_admin(user_id):
                try:
                    amount = float(text)
                    target_uid = state_data['target_uid']
                    add_balance(target_uid, amount, "Bonus / Admin Added Balance")
                    
                    bot.send_message(user_id, f"✅ **Success!** ₹{amount} added to user `{target_uid}`.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                    try:
                        bot.send_message(target_uid, f"🎉 *Congratulations!*\nAdmin has added ₹{amount} to your wallet!", parse_mode="Markdown")
                    except:
                        pass 
                    del user_states[user_id]
                except ValueError:
                    bot.send_message(user_id, "❌ Amount number hona chahiye.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                    del user_states[user_id]

# --- SECURED CALLBACK QUERIES ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.message.chat.id
    data = call.data

    if data == "back_to_main":
        if user_id in user_states:
            del user_states[user_id]
        try:
            bot.delete_message(user_id, call.message.message_id)
        except:
            pass
        bot.send_message(user_id, "🏠 *Main Menu*", parse_mode="Markdown", reply_markup=main_menu(user_id))

    # 👉 STEP 2: USER CLICKS "DONE" -> ASK FOR GMAIL NAME
    elif data == "task_done":
        if get_setting('gmail_task') == 'OFF' and not is_admin(user_id):
            bot.answer_callback_query(call.id, "Gmail Task is currently OFF!", show_alert=True)
            return
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
        bot.send_message(user_id, "📧 Kripya apna **Gmail Account Name / Email** yahan type karke bhejein:", parse_mode="Markdown", reply_markup=markup)
        user_states[user_id] = {'state': 'gmail_task_name'}

    elif data == "admin_total_users" and is_admin(user_id):
        users = run_query("SELECT user_id FROM users", fetch='all')
        total = len(users) if users else 0
        bot.answer_callback_query(call.id, f"Total Users: {total}", show_alert=True)

    elif data == "admin_bot_toggle" and is_admin(user_id):
        current = get_setting('bot_status')
        new_val = "OFF" if current == "ON" else "ON"
        update_setting('bot_status', new_val)
        bot.answer_callback_query(call.id, f"Bot Status is now {new_val}!", show_alert=True)

    elif data == "admin_manage" and user_id == OWNER_ID:
        admins = run_query("SELECT user_id FROM admins", fetch='all')
        admin_list = "\n".join([str(a[0]) for a in admins])
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("➕ Add Admin", callback_data="add_admin"))
        markup.row(InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin"))
        markup.row(InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back"))
        bot.edit_message_text(f"👥 <b>MANAGE ADMINS</b>\n\nCurrent Admins:\n<code>{admin_list}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data == "add_admin" and user_id == OWNER_ID:
        user_states[user_id] = {'state': 'admin_add_id'}
        bot.send_message(user_id, "📝 Jisko Admin banana hai, uska numeric **Telegram User ID** bhejein:")

    elif data == "remove_admin" and user_id == OWNER_ID:
        user_states[user_id] = {'state': 'admin_remove_id'}
        bot.send_message(user_id, "📝 Jiska Admin access hatana hai, uska numeric **Telegram User ID** bhejein:")

    elif data == "admin_toggles" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        g_status = "🟢 ON" if get_setting('gmail_task') == 'ON' else "🔴 OFF"
        og_status = "🟢 ON" if get_setting('old_gmail_task') == 'ON' else "🔴 OFF"
        w_status = "🟢 ON" if get_setting('withdraw') == 'ON' else "🔴 OFF"
        
        markup.row(InlineKeyboardButton(f"Gmail Task: {g_status}", callback_data="toggle_gmail"))
        markup.row(InlineKeyboardButton(f"Old Gmail Task: {og_status}", callback_data="toggle_oldgmail"))
        markup.row(InlineKeyboardButton(f"Withdrawals: {w_status}", callback_data="toggle_withdraw"))
        markup.row(InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back"))
        bot.edit_message_text("🎛️ *TOGGLE OPTIONS*\nKisi bhi option ko on/off karne ke liye click karein:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif data.startswith("toggle_") and is_admin(user_id):
        key_map = {"toggle_gmail": "gmail_task", "toggle_oldgmail": "old_gmail_task", "toggle_withdraw": "withdraw"}
        setting_key = key_map.get(data)
        if setting_key:
            current = get_setting(setting_key)
            new_val = "OFF" if current == "ON" else "ON"
            update_setting(setting_key, new_val)
            
            markup = InlineKeyboardMarkup()
            g_status = "🟢 ON" if get_setting('gmail_task') == 'ON' else "🔴 OFF"
            og_status = "🟢 ON" if get_setting('old_gmail_task') == 'ON' else "🔴 OFF"
            w_status = "🟢 ON" if get_setting('withdraw') == 'ON' else "🔴 OFF"
            
            markup.row(InlineKeyboardButton(f"Gmail Task: {g_status}", callback_data="toggle_gmail"))
            markup.row(InlineKeyboardButton(f"Old Gmail Task: {og_status}", callback_data="toggle_oldgmail"))
            markup.row(InlineKeyboardButton(f"Withdrawals: {w_status}", callback_data="toggle_withdraw"))
            markup.row(InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back"))
            bot.edit_message_text("🎛️ *TOGGLE OPTIONS*\nUpdated successfully:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif data == "admin_set_min" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("Set Min UPI (₹)", callback_data="set_min_upi"))
        markup.row(InlineKeyboardButton("Set Min USDT ($)", callback_data="set_min_usdt"))
        markup.row(InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back"))
        bot.edit_message_text(f"⚙️ *SET MINIMUM WITHDRAWAL*\nCurrent Min UPI: ₹{get_setting('min_upi')}\nCurrent Min USDT: ${get_setting('min_usdt')}", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif data == "set_min_upi" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_set_min_upi'}
        bot.send_message(user_id, "📝 Naya Minimum UPI amount (in ₹) type karke bhejein:")

    elif data == "set_min_usdt" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_set_min_usdt'}
        bot.send_message(user_id, "📝 Naya Minimum USDT amount (in $) type karke bhejein:")

    elif data == "admin_set_pass" and is_admin(user_id):
        user_states[user_id] = {'state': 'admin_set_gmail_pass'}
        bot.send_message(user_id, f"🔑 Naya Gmail Task Password type karke bhejein (Current: <code>{get_setting('gmail_password')}</code>):", parse_mode="HTML")

    elif data == "admin_approved_list" and is_admin(user_id):
        records = run_query("SELECT user_id, method, address, amount, date FROM approved_withdraws ORDER BY id DESC LIMIT 15", fetch='all')
        if not records:
            bot.answer_callback_query(call.id, "Koi approved withdraw history nahi hai!", show_alert=True)
        else:
            msg = "📜 <b>APPROVED WITHDRAWALS HISTORY:</b>\n\n"
            for r in records:
                msg += f"👤 <code>{r[0]}</code> | {r[1]} | 💰 {r[3]} | 📌 <code>{r[2]}</code>\n📅 {r[4]}\n\n"
            bot.send_message(user_id, msg, parse_mode="HTML")

    elif data == "admin_back" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🤖 Bot ON/OFF", callback_data="admin_bot_toggle"))
        if user_id == OWNER_ID:
            markup.row(InlineKeyboardButton("👥 Manage Admins", callback_data="admin_manage"))
        markup.row(InlineKeyboardButton("📊 Total Users", callback_data="admin_total_users"))
        markup.row(InlineKeyboardButton("🟢/🔴 Toggle Options", callback_data="admin_toggles"))
        markup.row(InlineKeyboardButton("⚙️ Set Min Withdraw", callback_data="admin_set_min"))
        markup.row(InlineKeyboardButton("🔑 Change Gmail Pass", callback_data="admin_set_pass"))
        markup.row(InlineKeyboardButton("📜 Approved Withdrawals", callback_data="admin_approved_list"))
        markup.row(InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast"))
        markup.row(InlineKeyboardButton("💸 Add Balance to User", callback_data="admin_addbal"))
        markup.row(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
        bot.edit_message_text("🛠️ *ADMIN PANEL*\nKripya option select karein:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif data == "admin_broadcast" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
        bot.send_message(user_id, "📢 *Broadcast Mode*\n\nJo message sabko bhejna hai, wo bhejein (Text, Photo, Video etc):", parse_mode="Markdown", reply_markup=markup)
        user_states[user_id] = {'state': 'admin_wait_broadcast'}

    elif data == "admin_addbal" and is_admin(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
        bot.send_message(user_id, "💸 *Add Balance Mode*\n\n👉 User ka *Telegram ID* bhejein:", parse_mode="Markdown", reply_markup=markup)
        user_states[user_id] = {'state': 'admin_wait_uid'}

    elif data.startswith("oldappr_") and is_admin(user_id):
        target_user = int(data.split("_")[1])
        bot.answer_callback_query(call.id, "Processing...")
        add_balance(target_user, 15.0, "Old Gmail Task Approved")
        try:
            bot.send_message(target_user, "🎉 *Old Gmail Approved!*\n₹15 aapke Wallet me add kar diye gaye hain.", parse_mode="Markdown")
        except: pass
        try:
            bot.edit_message_caption(f"✅ Old Gmail Approved for <code>{target_user}</code> (Done)", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=None)
        except:
            bot.edit_message_text(f"✅ Old Gmail Approved for <code>{target_user}</code> (Done)", call.message.chat.id, call.message.message_id, parse_mode="HTML")

    elif data.startswith("oldrej_") and is_admin(user_id):
        target_user = int(data.split("_")[1])
        bot.answer_callback_query(call.id, "Processing...")
        try:
            bot.send_message(target_user, "❌ *Old Gmail Rejected!*\nAapka Old Gmail task reject kar diya gaya hai.", parse_mode="Markdown")
        except: pass
        try:
            bot.edit_message_caption(f"❌ Old Gmail Rejected for <code>{target_user}</code> (Done)", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=None)
        except:
            bot.edit_message_text(f"❌ Old Gmail Rejected for <code>{target_user}</code> (Done)", call.message.chat.id, call.message.message_id, parse_mode="HTML")

    elif data.startswith("apprt_") and is_admin(user_id): 
        target_user = int(data.split("_")[1])
        bot.answer_callback_query(call.id, "Processing...")
        add_balance(target_user, 15.0, "Gmail Task Approved")
        try:
            bot.send_message(target_user, "🎉 *Task Approved!*\n₹15 aapke Wallet me add kar diye gaye hain.", parse_mode="Markdown")
        except: pass
        try:
            bot.edit_message_caption(f"✅ Task Approved for <code>{target_user}</code> (Done)", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=None)
        except:
            bot.edit_message_text(f"✅ Task Approved for <code>{target_user}</code> (Done)", call.message.chat.id, call.message.message_id, parse_mode="HTML")

    elif data.startswith("rejct_") and is_admin(user_id): 
        target_user = int(data.split("_")[1])
        bot.answer_callback_query(call.id, "Processing...")
        try:
            bot.send_message(target_user, "❌ *Task Rejected!*\nAapka Gmail Task reject kar diya gaya hai.", parse_mode="Markdown")
        except: pass
        try:
            bot.edit_message_caption(f"❌ Task Rejected for <code>{target_user}</code> (Done)", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=None)
        except:
            bot.edit_message_text(f"❌ Task Rejected for <code>{target_user}</code> (Done)", call.message.chat.id, call.message.message_id, parse_mode="HTML")

    elif data.startswith("apprw_") and is_admin(user_id): 
        pending_id = int(data.split("_")[1])
        req = run_query("SELECT user_id, amount, method, address FROM pending_withdraws WHERE id=%s", (pending_id,), fetch='one')
        if req:
            target_user, display_amount, method, address = req
            curr_symbol = "₹" if method == "🏦 UPI" else "$"
            bot.answer_callback_query(call.id, "Processing...")
            
            date_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            run_query("INSERT INTO approved_withdraws (user_id, method, address, amount, date) VALUES (%s, %s, %s, %s, %s)", 
                      (target_user, method, address, f"{curr_symbol}{display_amount}", date_now), commit=True)

            try:
                bot.send_message(target_user, f"🎉 *Payment Sent!*\nAapka {method} withdrawal of {curr_symbol}{display_amount} successful ho gaya hai!", parse_mode="Markdown")
            except: pass
            try:
                bot.edit_message_text(f"✅ Withdrawal Approved for <code>{target_user}</code> (Done)", call.message.chat.id, call.message.message_id, parse_mode="HTML")
            except: pass
            run_query("DELETE FROM pending_withdraws WHERE id=%s", (pending_id,), commit=True)
        else:
            bot.answer_callback_query(call.id, "⚠️ Already processed or invalid request!", show_alert=True)

    elif data.startswith("rejcc_") and is_admin(user_id): 
        pending_id = int(data.split("_")[1])
        req = run_query("SELECT user_id, amount, method FROM pending_withdraws WHERE id=%s", (pending_id,), fetch='one')
        if req:
            target_user, display_amount, method = req
            refund_inr = display_amount if method == "🏦 UPI" else display_amount * USDT_TO_INR_RATE
            
            bot.answer_callback_query(call.id, "Processing...")
            add_balance(target_user, refund_inr, f"Refund: {method} Withdraw Rejected")
            try:
                bot.send_message(target_user, f"❌ *Withdrawal Rejected!*\nAapka {method} withdrawal reject ho gaya hai. Balance wallet me refund ho gaya hai.", parse_mode="Markdown")
            except: pass
            try:
                bot.edit_message_text(f"❌ Withdrawal Rejected for <code>{target_user}</code> (Refunded)", call.message.chat.id, call.message.message_id, parse_mode="HTML")
            except: pass
            run_query("DELETE FROM pending_withdraws WHERE id=%s", (pending_id,), commit=True)
        else:
            bot.answer_callback_query(call.id, "⚠️ Already processed or invalid request!", show_alert=True)

# --- START BOT ---
print("Bot running with new Token, DB and Fixed Flow...")
bot.polling(none_stop=True)
