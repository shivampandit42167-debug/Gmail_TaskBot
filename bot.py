import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import datetime
import time

# --- CONFIGURATION ---
TOKEN = '8683212510:AAEdE8kq5-5GuKerfPa_Mzaxovgb-J5VU4w'
ADMIN_ID = 8894779077  
ADMIN_USERNAME = 'Verified_Bandaa' 

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
    
    # Check if user is new
    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    is_new = cursor.fetchone() is None
    
    get_balance(user_id) 
    
    # If new user, notify Admin
    if is_new and user_id != ADMIN_ID:
        try:
            bot.send_message(ADMIN_ID, f"🚀 *New User Started Bot!*\n\n👤 *User ID:* `{user_id}`\n👤 *Name:* {message.from_user.first_name}", parse_mode="Markdown")
        except:
            pass

    msg = (f"✨ *WELCOME TO OUR BOT!* ✨\n\n"
           f"Hello {message.from_user.first_name}, yahan aap simple tasks complete karke real cash earn kar sakte hain! 💸\n\n"
           f"👇 *Niche diye gaye buttons se apna task shuru karein:*")
    bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=main_menu(user_id))

# --- BUTTON CLICKS HANDLER ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.chat.id
    text = message.text

    if text == "📧 Gmail Task":
        msg = ("📧 *GMAIL TASK*\n"
               "💰 *Reward:* ₹15\n\n"
               "⚠️ *Instructions & Rules:*\n"
               "Rule - Create a new Gmail account.\n"
               "Password must be - `ethicbro999`\n\n"
               "👉 *Complete the task and click the button below!*")
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Click Here When Done", callback_data="task_done"))
        markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
        bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=markup)

    elif text == "📧 Old Gmail Task":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
        msg = ("📧 *OLD GMAIL TASK*\n\n"
               "👉 Kripya apna **Old Gmail Account** yahan bhejein:")
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
        msg = ("📞 *CONTACT & SUPPORT*\n\n"
               "Agar aapko koi problem aa rahi hai ya payment se related koi sawal hai, toh humare Admin se direct baat karein:\n\n"
               f"👨‍💻 *Admin ID:* @{ADMIN_USERNAME}\n"
               "💬 _Click on the username to send a message._")
        bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=main_menu(user_id))

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

    # --- ADMIN PANEL OPTIONS ---
    elif text == "⚙️ Admin Panel" and user_id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("📊 Total Users", callback_data="admin_total_users"))
        markup.row(InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast"))
        markup.row(InlineKeyboardButton("💸 Add Balance to User", callback_data="admin_addbal"))
        markup.row(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
        bot.send_message(user_id, "🛠️ *ADMIN PANEL*\nKripya option select karein:", parse_mode="Markdown", reply_markup=markup)

    # --- DYNAMIC STATES HANDLING ---
    elif user_id in user_states:
        state_data = user_states[user_id]
        
        # Old Gmail Task - Step 1: Email received, now ask Password
        if state_data['state'] == 'old_gmail_email':
            gmail_email = text
            user_states[user_id] = {'state': 'old_gmail_password', 'gmail_email': gmail_email}
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
            bot.send_message(user_id, f"✅ Email saved: `{gmail_email}`\n\n👉 Ab iska *Password* bhejein:", parse_mode="Markdown", reply_markup=markup)

        # Old Gmail Task - Step 2: Password received, submit to Admin
        elif state_data['state'] == 'old_gmail_password':
            gmail_pass = text
            gmail_email = state_data['gmail_email']
            
            bot.send_message(user_id, "✅ *Old Gmail Submitted!*\nAapka task Admin ke paas bhej diya gaya hai. Check hone ke baad reward add ho jayega.", parse_mode="Markdown", reply_markup=main_menu(user_id))
            
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"oldappr_{user_id}"),
                       InlineKeyboardButton("❌ Reject", callback_data=f"oldrej_{user_id}"))
            
            admin_msg = (f"🔔 *NEW OLD GMAIL SUBMISSION*\n\n"
                         f"👤 *User ID:* `{user_id}`\n"
                         f"📧 *Gmail:* `{gmail_email}`\n"
                         f"🔑 *Password:* `{gmail_pass}`")
            bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown", reply_markup=markup)
            del user_states[user_id]

        # Withdraw Amount
        elif state_data['state'] == 'withdraw_amount':
            try:
                input_val = float(text)
                method = state_data['method']
                balance_inr = get_balance(user_id)
                
                if method == "🏦 UPI":
                    amount_inr = input_val
                    min_val = 15.0
                    if amount_inr < min_val or amount_inr > balance_inr:
                        bot.send_message(user_id, "❌ *Invalid Amount!* Ya toh balance kam hai ya minimum limit (₹15) cross nahi hui.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                        del user_states[user_id]
                        return
                else: # USDT
                    amount_usd = input_val
                    amount_inr = amount_usd * USDT_TO_INR_RATE
                    min_val = 0.16
                    if amount_usd < min_val or amount_inr > balance_inr:
                        bot.send_message(user_id, "❌ *Invalid Amount!* Ya toh balance kam hai ya minimum limit ($0.16) cross nahi hui.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                        del user_states[user_id]
                        return

                user_states[user_id]['amount_inr'] = amount_inr
                user_states[user_id]['display_amount'] = input_val
                user_states[user_id]['state'] = 'withdraw_address'
                
                ask_str = "UPI ID" if method == "🏦 UPI" else "USDT (TRC20/BEP20) Address"
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
                bot.send_message(user_id, f"✅ Amount saved: {input_val} {'₹' if method == '🏦 UPI' else '$'}\n\n👉 Ab apna *{ask_str}* bhejein:", parse_mode="Markdown", reply_markup=markup)
            except ValueError:
                bot.send_message(user_id, "❌ Sirf numbers mein amount likhein.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                del user_states[user_id]

        # Withdraw Address
        elif state_data['state'] == 'withdraw_address':
            address = text
            amount_inr = state_data['amount_inr']
            display_amount = state_data['display_amount']
            method = state_data['method']
            
            deduct_balance(user_id, amount_inr, f"Pending {method} Withdraw ({display_amount})")
            cursor.execute("INSERT INTO pending_withdraws (user_id, method, address, amount) VALUES (?, ?, ?, ?)", 
                           (user_id, method, address, display_amount))
            pending_id = cursor.lastrowid
            conn.commit()
            
            bot.send_message(user_id, "✅ *Request Submitted!*\nAapka withdrawal request Admin ko bhej diya gaya hai. Approve hone par payment mil jayegi.", parse_mode="Markdown", reply_markup=main_menu(user_id))
            
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"apprw_{pending_id}"),
                       InlineKeyboardButton("❌ Reject", callback_data=f"rejcc_{pending_id}"))
            
            curr_symbol = "₹" if method == "🏦 UPI" else "$"
            admin_msg = (f"🔔 *NEW WITHDRAW REQUEST*\n\n"
                         f"👤 *User ID:* `{user_id}`\n"
                         f"🏦 *Method:* {method}\n"
                         f"💰 *Amount:* {curr_symbol}{display_amount}\n"
                         f"📌 *Address:* `{address}`")
            bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown", reply_markup=markup)
            del user_states[user_id]

        # Admin - Add Balance (Step 1: Enter ID)
        elif state_data['state'] == 'admin_wait_uid' and user_id == ADMIN_ID:
            try:
                target_uid = int(text)
                user_states[user_id] = {'state': 'admin_wait_amt', 'target_uid': target_uid}
                bot.send_message(user_id, f"✅ User ID saved: `{target_uid}`\n\n👉 Ab *Amount (in ₹)* likhein jo add karna hai:", parse_mode="Markdown")
            except ValueError:
                bot.send_message(user_id, "❌ User ID number format mein hona chahiye. Wapas try karein.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                del user_states[user_id]

        # Admin - Add Balance (Step 2: Enter Amount)
        elif state_data['state'] == 'admin_wait_amt' and user_id == ADMIN_ID:
            try:
                amount = float(text)
                target_uid = state_data['target_uid']
                add_balance(target_uid, amount, "Bonus / Admin Added Balance")
                
                bot.send_message(user_id, f"✅ **Success!** ₹{amount} has been added to user `{target_uid}`.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                try:
                    bot.send_message(target_uid, f"🎉 *Congratulations!*\nAdmin has added ₹{amount} to your wallet! Check your balance.", parse_mode="Markdown")
                except:
                    pass 
                del user_states[user_id]
            except ValueError:
                bot.send_message(user_id, "❌ Amount number hona chahiye. Failed.", parse_mode="Markdown", reply_markup=main_menu(user_id))
                del user_states[user_id]
                
# --- ADMIN BROADCAST HANDLER ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_all_media(message):
    user_id = message.chat.id
    if user_id in user_states and user_states[user_id].get('state') == 'admin_wait_broadcast' and user_id == ADMIN_ID:
        bot.send_message(user_id, "⏳ *Broadcast Started...* Please wait.", parse_mode="Markdown")
        users = get_all_users()
        success = 0
        failed = 0
        
        for u_id in users:
            try:
                bot.copy_message(u_id, user_id, message.message_id)
                success += 1
                time.sleep(0.05) 
            except Exception:
                failed += 1
                
        bot.send_message(user_id, f"✅ *Broadcast Complete!*\n\n🚀 Successfully sent to: {success}\n❌ Failed (Blocked bot): {failed}", parse_mode="Markdown", reply_markup=main_menu(user_id))
        del user_states[user_id]

# --- CALLBACK QUERIES (Inline Buttons) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.message.chat.id

    if call.data == "back_to_main":
        if user_id in user_states:
            del user_states[user_id]
        try:
            bot.delete_message(user_id, call.message.message_id)
        except:
            pass
        bot.send_message(user_id, "🏠 *Main Menu*", parse_mode="Markdown", reply_markup=main_menu(user_id))

    elif call.data == "task_done":
        bot.send_message(user_id, "📸 Kripya task complete karne ke baad **Screenshot** bhejein.", parse_mode="Markdown")
        user_states[user_id] = {'state': 'waiting_for_screenshot'}

    elif call.data == "admin_total_users" and user_id == ADMIN_ID:
        users = get_all_users()
        total = len(users)
        bot.answer_callback_query(call.id, f"Total Users: {total}", show_alert=True)

    elif call.data == "admin_broadcast" and user_id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
        bot.send_message(user_id, "📢 *Broadcast Mode*\n\nJo message aap sabko bhejna chahte hain, wo mujhe bhejein (Text, Photo ya Video kuch bhi).", parse_mode="Markdown", reply_markup=markup)
        user_states[user_id] = {'state': 'admin_wait_broadcast'}

    elif call.data == "admin_addbal" and user_id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main"))
        bot.send_message(user_id, "💸 *Add Balance Mode*\n\n👉 Kripya us user ka *Telegram ID* bhejein jisme paise add karne hain:", parse_mode="Markdown", reply_markup=markup)
        user_states[user_id] = {'state': 'admin_wait_uid'}

    elif call.data.startswith("oldappr_"):
        target_user = int(call.data.split("_")[1])
        add_balance(target_user, 15.0, "Old Gmail Task Approved")
        try:
            bot.send_message(target_user, "🎉 *Old Gmail Approved!*\n₹15 aapke Wallet me add kar diye gaye hain.", parse_mode="Markdown")
        except: pass
        bot.edit_message_text(f"✅ Old Gmail Approved for `{target_user}`", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif call.data.startswith("oldrej_"):
        target_user = int(call.data.split("_")[1])
        try:
            bot.send_message(target_user, "❌ *Old Gmail Rejected!*\nAapka Old Gmail task reject kar diya gaya hai.", parse_mode="Markdown")
        except: pass
        bot.edit_message_text(f"❌ Old Gmail Rejected for `{target_user}`", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif call.data.startswith("apprt_"): 
        target_user = int(call.data.split("_")[1])
        add_balance(target_user, 15.0, "Gmail Task Approved")
        try:
            bot.send_message(target_user, "🎉 *Task Approved!*\n₹15 aapke Wallet me add kar diye gaye hain.", parse_mode="Markdown")
        except: pass
        bot.edit_message_text(f"✅ Task Approved for `{target_user}`", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif call.data.startswith("rejct_"): 
        target_user = int(call.data.split("_")[1])
        try:
            bot.send_message(target_user, "❌ *Task Rejected!*\nAapka Gmail Task reject kar diya gaya hai. Kripya rules dhyaan se padhein.", parse_mode="Markdown")
        except: pass
        bot.edit_message_text(f"❌ Task Rejected for `{target_user}`", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif call.data.startswith("apprw_"): 
        pending_id = int(call.data.split("_")[1])
        cursor.execute("SELECT user_id, amount, method FROM pending_withdraws WHERE id=?", (pending_id,))
        req = cursor.fetchone()
        if req:
            target_user, display_amount, method = req
            curr_symbol = "₹" if method == "🏦 UPI" else "$"
            try:
                bot.send_message(target_user, f"🎉 *Payment Sent!*\nAapka {method} withdrawal of {curr_symbol}{display_amount} successful ho gaya hai. Check your account!", parse_mode="Markdown")
            except: pass
            bot.edit_message_text(f"✅ Withdrawal Approved for `{target_user}`", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            cursor.execute("DELETE FROM pending_withdraws WHERE id=?", (pending_id,))
            conn.commit()

    elif call.data.startswith("rejcc_"): 
        pending_id = int(call.data.split("_")[1])
        cursor.execute("SELECT user_id, amount, method FROM pending_withdraws WHERE id=?", (pending_id,))
        req = cursor.fetchone()
        if req:
            target_user, display_amount, method = req
            refund_inr = display_amount if method == "🏦 UPI" else display_amount * USDT_TO_INR_RATE
            
            add_balance(target_user, refund_inr, f"Refund: {method} Withdraw Rejected")
            try:
                bot.send_message(target_user, f"❌ *Withdrawal Rejected!*\nAapka {method} withdrawal admin dwara reject kar diya gaya hai. Balance wallet me wapas add ho gaya hai.", parse_mode="Markdown")
            except: pass
            bot.edit_message_text(f"❌ Withdrawal Rejected for `{target_user}` (Refunded)", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            cursor.execute("DELETE FROM pending_withdraws WHERE id=?", (pending_id,))
            conn.commit()

# --- PHOTO HANDLER (For Screenshots) ---
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.chat.id
    if user_id in user_states and user_states[user_id].get('state') == 'waiting_for_screenshot':
        file_id = message.photo[-1].file_id
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"apprt_{user_id}"),
                   InlineKeyboardButton("❌ Reject", callback_data=f"rejct_{user_id}"))
        
        admin_msg = f"🔔 *NEW TASK SUBMISSION*\n\n👤 *User ID:* `{user_id}`\n\nPlease approve or reject the proof."
        bot.send_photo(ADMIN_ID, file_id, caption=admin_msg, parse_mode="Markdown", reply_markup=markup)
        
        bot.send_message(user_id, "✅ *Proof Submitted!*\nAapka screenshot Admin ko bhej diya gaya hai. Approve hote hi paise add ho jayenge.", parse_mode="Markdown", reply_markup=main_menu(user_id))
        del user_states[user_id]
    else:
        handle_all_media(message)

# --- START BOT ---
print("Bot is fully updated, bug-free, and running...")
bot.polling(none_stop=True)
