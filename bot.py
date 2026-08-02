import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import datetime

# --- CONFIGURATION ---
TOKEN = '8683212510:AAEdE8kq5-5GuKerfPa_Mzaxovgb-J5VU4w' # 
ADMIN_ID = 8894779077 # 
ADMIN_USERNAME = '@Verified_Bandaa' #

bot = telebot.TeleBot(TOKEN)

# --- DATABASE SETUP ---
conn = sqlite3.connect('bot_database.db', check_same_thread=False)
cursor = conn.cursor()

# Users Table
cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)''')
# History Table (Tasks & Withdrawals)
cursor.execute('''CREATE TABLE IF NOT EXISTS history
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, amount REAL, detail TEXT, date TEXT)''')
# Withdrawals Pending Table
cursor.execute('''CREATE TABLE IF NOT EXISTS pending_withdraws
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, method TEXT, address TEXT, amount REAL)''')
conn.commit()

# States for handling user inputs
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

# --- MAIN MENU ---
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("📧 Gmail Task"), KeyboardButton("💰 Wallet"))
    markup.row(KeyboardButton("💸 Withdraw"), KeyboardButton("📞 Contact & Help"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    get_balance(message.chat.id) # Ensure user is in DB
    bot.send_message(message.chat.id, "Welcome to the Bot! Kripya niche diye gaye options chunein:", reply_markup=main_menu())

# --- BUTTON CLICKS HANDLER ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.chat.id
    text = message.text

    if text == "📧 Gmail Task":
        msg = ("📧 **GMAIL TASK**\n"
               "💰 **Reward:** ₹15\n\n"
               "⚠️ **Instructions & Rules:**\n"
               "Rule - Create a new Gmail account.\n"
               "Password must be - `ethicbro999`\n\n"
               "👉 Complete the task and click the button below!")
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Click Here When Done", callback_data="task_done"))
        bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=markup)

    elif text == "💰 Wallet":
        balance = get_balance(user_id)
        msg = f"💰 **Your Wallet Balance:** ₹{balance}\n\n**Recent History:**\n"
        cursor.execute("SELECT type, amount, detail, date FROM history WHERE user_id=? ORDER BY id DESC LIMIT 5", (user_id,))
        records = cursor.fetchall()
        if not records:
            msg += "Koi history nahi hai."
        for r in records:
            msg += f"• {r[0]} | ₹{r[1]} | {r[2]} | {r[3]}\n"
        bot.send_message(user_id, msg, parse_mode="Markdown")

    elif text == "📞 Contact & Help":
        bot.send_message(user_id, f"Support ke liye humare Admin se baat karein: @{ADMIN_USERNAME}")

    elif text == "💸 Withdraw":
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row(KeyboardButton("🏦 UPI"), KeyboardButton("🪙 USDT"))
        markup.row(KeyboardButton("📜 Withdraw History"), KeyboardButton("🔙 Back to Main"))
        bot.send_message(user_id, "Withdrawal Method select karein:", reply_markup=markup)
        
    elif text == "🔙 Back to Main":
        bot.send_message(user_id, "Main Menu", reply_markup=main_menu())

    elif text in ["🏦 UPI", "🪙 USDT"]:
        balance = get_balance(user_id)
        min_amount = 15 if text == "🏦 UPI" else 0.16
        currency = "₹" if text == "🏦 UPI" else "$"
        
        if balance < min_amount:
            bot.send_message(user_id, f"❌ Aapka balance kam hai. Minimum withdrawal {text} ke liye {currency}{min_amount} hai.")
        else:
            bot.send_message(user_id, f"Amount enter karein (Minimum {currency}{min_amount}):", reply_markup=telebot.types.ReplyKeyboardRemove())
            user_states[user_id] = {'state': 'withdraw_amount', 'method': text}

    elif text == "📜 Withdraw History":
        cursor.execute("SELECT detail, amount, date FROM history WHERE user_id=? AND type='DEBIT' ORDER BY id DESC LIMIT 10", (user_id,))
        records = cursor.fetchall()
        if not records:
            bot.send_message(user_id, "Koi withdrawal history nahi hai.")
        else:
            msg = "📜 **Withdrawal History:**\n\n"
            for r in records:
                msg += f"• {r[2]} | ₹{r[1]} | {r[0]}\n"
            bot.send_message(user_id, msg, parse_mode="Markdown")

    # Handle dynamic states (like entering amount or ID)
    elif user_id in user_states:
        state_data = user_states[user_id]
        
        if state_data['state'] == 'withdraw_amount':
            try:
                amount = float(text)
                method = state_data['method']
                min_amount = 15 if method == "🏦 UPI" else 0.16
                balance = get_balance(user_id)
                
                if amount < min_amount or amount > balance:
                    bot.send_message(user_id, "❌ Invalid amount ya balance kam hai. Wapas try karein.", reply_markup=main_menu())
                    del user_states[user_id]
                else:
                    user_states[user_id]['amount'] = amount
                    user_states[user_id]['state'] = 'withdraw_address'
                    ask_str = "UPI ID" if method == "🏦 UPI" else "USDT Address"
                    bot.send_message(user_id, f"Apna {ask_str} bhejein:")
            except ValueError:
                bot.send_message(user_id, "❌ Sirf numbers me amount likhein.", reply_markup=main_menu())
                del user_states[user_id]

        elif state_data['state'] == 'withdraw_address':
            address = text
            amount = state_data['amount']
            method = state_data['method']
            
            # Deduct balance temporarily and send to admin
            deduct_balance(user_id, amount, f"Pending {method} Withdrawal")
            cursor.execute("INSERT INTO pending_withdraws (user_id, method, address, amount) VALUES (?, ?, ?, ?)", 
                           (user_id, method, address, amount))
            pending_id = cursor.lastrowid
            conn.commit()
            
            bot.send_message(user_id, "✅ Aapka withdrawal request Pending me chala gaya hai. Admin approve karega.", reply_markup=main_menu())
            
            # Notify Admin
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"apprw_{pending_id}"),
                       InlineKeyboardButton("❌ Reject", callback_data=f"rejcc_{pending_id}"))
            admin_msg = f"🔔 **New Withdrawal Request**\nUser: {user_id}\nMethod: {method}\nAmount: {amount}\nAddress: `{address}`"
            bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown", reply_markup=markup)
            del user_states[user_id]

# --- CALLBACK QUERIES (Inline Buttons) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.message.chat.id

    if call.data == "task_done":
        bot.send_message(user_id, "📸 Kripya task complete karne ke baad **Screenshot** bhejein.")
        user_states[user_id] = {'state': 'waiting_for_screenshot'}

    elif call.data.startswith("apprt_"): # Approve Task
        target_user = int(call.data.split("_")[1])
        add_balance(target_user, 15, "Gmail Task Approved")
        bot.send_message(target_user, "🎉 Aapka Gmail Task Approve ho gaya hai! ₹15 aapke Wallet me add kar diye gaye hain.")
        bot.edit_message_text(f"✅ Task Approved for {target_user}", call.message.chat.id, call.message.message_id)

    elif call.data.startswith("rejct_"): # Reject Task
        target_user = int(call.data.split("_")[1])
        bot.send_message(target_user, "❌ Aapka Gmail Task Reject kar diya gaya hai. Screenshot valid nahi tha.")
        bot.edit_message_text(f"❌ Task Rejected for {target_user}", call.message.chat.id, call.message.message_id)

    elif call.data.startswith("apprw_"): # Approve Withdrawal
        pending_id = int(call.data.split("_")[1])
        cursor.execute("SELECT user_id, amount, method FROM pending_withdraws WHERE id=?", (pending_id,))
        req = cursor.fetchone()
        if req:
            target_user, amount, method = req
            bot.send_message(target_user, f"🎉 Aapka {method} withdrawal of {amount} successful ho gaya hai!")
            bot.edit_message_text(f"✅ Withdrawal Approved for {target_user}", call.message.chat.id, call.message.message_id)
            cursor.execute("DELETE FROM pending_withdraws WHERE id=?", (pending_id,))
            conn.commit()

    elif call.data.startswith("rejcc_"): # Reject Withdrawal
        pending_id = int(call.data.split("_")[1])
        cursor.execute("SELECT user_id, amount, method FROM pending_withdraws WHERE id=?", (pending_id,))
        req = cursor.fetchone()
        if req:
            target_user, amount, method = req
            # Refund the balance
            add_balance(target_user, amount, f"Refund: {method} Withdrawal Rejected")
            bot.send_message(target_user, f"❌ Aapka {method} withdrawal reject ho gaya hai. Balance refund kar diya gaya hai.")
            bot.edit_message_text(f"❌ Withdrawal Rejected for {target_user}", call.message.chat.id, call.message.message_id)
            cursor.execute("DELETE FROM pending_withdraws WHERE id=?", (pending_id,))
            conn.commit()

# --- PHOTO HANDLER (For Screenshots) ---
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.chat.id
    if user_id in user_states and user_states[user_id].get('state') == 'waiting_for_screenshot':
        file_id = message.photo[-1].file_id
        
        # Send to admin panel for approval
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"apprt_{user_id}"),
                   InlineKeyboardButton("❌ Reject", callback_data=f"rejct_{user_id}"))
        
        bot.send_photo(ADMIN_ID, file_id, caption=f"🔔 **New Task Submission**\nUser ID: `{user_id}`\nPlease approve or reject.", parse_mode="Markdown", reply_markup=markup)
        
        bot.send_message(user_id, "✅ Aapka screenshot Admin ko bhej diya gaya hai. Approve hone par ₹15 aapke wallet me add ho jayenge.", reply_markup=main_menu())
        del user_states[user_id]
    else:
        bot.send_message(user_id, "Kripya valid option select karein.")

# --- START BOT ---
print("Bot is running...")
bot.polling(none_stop=True)
