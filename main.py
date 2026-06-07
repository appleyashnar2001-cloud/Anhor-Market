import asyncio
import logging
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler as AsyncioScheduler
from pytz import timezone

import database as db

# Siz taqdim etgan haqiqiy bot tokeni joylashtirildi
BOT_TOKEN = "8311735093:AAE6-C0E_6dNq6fW9yrQSYEASB-ge4kvnMU" 
ADMIN_ID = 7180864511  
UZB_TZ = timezone("Asia/Tashkent")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncioScheduler(timezone=UZB_TZ)

class AdminStates(StatesGroup):
    waiting_for_worker_id = State()
    waiting_for_worker_name = State()
    waiting_for_remove_id = State()
    waiting_for_broadcast = State()

class WorkerStates(StatesGroup):
    waiting_for_chat = State()

# --- KLAVIATURALAR ---
def get_admin_kb():
    kb = [
        [types.KeyboardButton(text="👥 Ishchilar va Hisobot"), types.KeyboardButton(text="➕ Ishchi qo'shish")],
        [types.KeyboardButton(text="❌ Ishchini bo'shatish"), types.KeyboardButton(text="🗄 O'tgan oylar hisoboti")],
        [types.KeyboardButton(text="📥 Chatni o'qish"), types.KeyboardButton(text="📢 Hammaga xabar")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_worker_kb(status="inactive"):
    kb = []
    if status == "inactive":
        kb.append([types.KeyboardButton(text="🚀 Ishni boshlash")])
    else:
        kb.append([types.KeyboardButton(text="🛑 Ishni yakunlash")])
    kb.append([types.KeyboardButton(text="📊 Shaxsiy hisobot (Oy)"), types.KeyboardButton(text="💬 Chatga yozish")])
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- START COMMAND ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Magazin boshqaruv tizimi. Xush kelibsiz, Admin!", reply_markup=get_admin_kb())
    else:
        worker_name = db.check_worker(message.from_user.id)
        if worker_name:
            await message.answer(f"Xush kelibsiz, {worker_name}! Ish vaqti: 06:00 - 23:30", reply_markup=get_worker_kb())
        else:
            await message.answer(f"Siz magazin tizimida yo'qsiz. ID raqamingiz: `{message.from_user.id}`\nBuni adminga bering.", parse_mode="Markdown")

# --- ADMIN LOGIKASI ---
@dp.message(F.text == "👥 Ishchilar va Hisobot", F.from_user.id == ADMIN_ID)
async def list_workers(message: types.Message):
    workers = db.get_workers()
    if not workers:
        return await message.answer("Tizimda ishchilar yo'q.")
    
    text = "📋 *Joriy oydagi umumiy hisobot:*\n\n"
    for tg_id, name, status in workers:
        st = "🟢 Ishda" if status == "active" else "🔴 Ketgan"
        total = db.get_monthly_report(tg_id)
        text += f"👤 *{name}* ({st})\n↳ Shu oyda jami: `{total}`\n\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🗄 O'tgan oylar hisoboti", F.from_user.id == ADMIN_ID)
async def archived_reports(message: types.Message):
    rows = db.get_archive_reports()
    if not rows:
        return await message.answer("Arxivda eski hisobotlar mavjud emas.")
    text = "🗄 *Arxivlangan oylar hisoboti:*\n\n"
    for month, name, time in rows:
        text += f"📅 {month} | 👤 {name}: `{time}`\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "📥 Chatni o'qish", F.from_user.id == ADMIN_ID)
async def read_chat(message: types.Message):
    logs = db.get_chat_logs()
    if not logs:
        return await message.answer("Chatda xabarlar yo'q.")
    text = "💬 *Chatdagi oxirgi xabarlar:*\n\n"
    for name, msg, tm in reversed(logs):
        text += f"[{tm}] *{name}*: {msg}\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "➕ Ishchi qo'shish", F.from_user.id == ADMIN_ID)
async def add_worker_start(message: types.Message, state: FSMContext):
    await message.answer("Ishchining Telegram ID raqamini kiriting:")
    await state.set_state(AdminStates.waiting_for_worker_id)

@dp.message(AdminStates.waiting_for_worker_id, F.from_user.id == ADMIN_ID)
async def add_worker_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("ID faqat raqam bo'lishi kerak!")
    await state.update_data(tg_id=int(message.text))
    await message.answer("Ishchining Ismi va Familiyasini kiriting:")
    await state.set_state(AdminStates.waiting_for_worker_name)

@dp.message(AdminStates.waiting_for_worker_name, F.from_user.id == ADMIN_ID)
async def add_worker_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if db.add_worker(data['tg_id'], message.text):
        await message.answer(f"✅ {message.text} muvaffaqiyatli qo'shildi!", reply_markup=get_admin_kb())
    await state.clear()

# --- ISHCHINI BO'SHATISH LOGIKASI ---
@dp.message(F.text == "❌ Ishchini bo'shatish", F.from_user.id == ADMIN_ID)
async def remove_worker_start(message: types.Message, state: FSMContext):
    await message.answer("Bo'shatiladigan (o'chiriladigan) ishchining Telegram ID raqamini kiriting:")
    await state.set_state(AdminStates.waiting_for_remove_id)

@dp.message(AdminStates.waiting_for_remove_id, F.from_user.id == ADMIN_ID)
async def remove_worker_finish(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("ID raqam bo'lishi kerak!")
    
    tg_id = int(message.text)
    worker_name = db.remove_worker(tg_id)
    
    if worker_name:
        await message.answer(f"❌ *{worker_name}* (ID: `{tg_id}`) magazin tizimidan muvaffaqiyatli o'chirildi va bo'shatildi.", reply_markup=get_admin_kb(), parse_mode="Markdown")
        try:
            await bot.send_message(chat_id=tg_id, text="⚠️ Siz admin tomonidan magazin tizimidan chiqarildingiz va bo'shatildingiz.")
        except: pass
    else:
        await message.answer("❌ Bunday ID ga ega ishchi topilmadi.", reply_markup=get_admin_kb())
    await state.clear()

@dp.message(F.text == "📢 Hammaga xabar", F.from_user.id == ADMIN_ID)
async def broadcast_start(message: types.Message, state: FSMContext):
    await message.answer("Xabarni kiriting:")
    await state.set_state(AdminStates.waiting_for_broadcast)

@dp.message(AdminStates.waiting_for_broadcast, F.from_user.id == ADMIN_ID)
async def broadcast_finish(message: types.Message, state: FSMContext):
    for tg_id, _, _ in db.get_workers():
        try:
            await bot.send_message(chat_id=tg_id, text=f"📢 *Admindan xabar:*\n\n{message.text}", parse_mode="Markdown")
        except: pass
    await message.answer("✅ Yuborildi.", reply_markup=get_admin_kb())
    await state.clear()


# --- ISHCHILAR LOGIKASI ---
@dp.message(F.text == "🚀 Ishni boshlash")
async def process_start_work(message: types.Message):
    name = db.check_worker(message.from_user.id)
    if not name: return await message.answer("Ro'yxatda yo'qsiz.")
    
    current_hour = datetime.now(UZB_TZ).hour
    current_minute = datetime.now(UZB_TZ).minute
    
    if (current_hour < 6) or (current_hour == 23 and current_minute > 30) or (current_hour > 23):
        return await message.answer("❌ Hozir ish vaqti emas! Ishni faqat 06:00 dan keyin boshlash mumkin.")
        
    db.start_work(message.from_user.id)
    await message.answer("🟢 Ish boshlandi. Magazin ochildi!", reply_markup=get_worker_kb("active"))
    
    alert_text = f"🏪 *Magazin ochildi!*\n👤 *{name}* ishni boshladi."
    await bot.send_message(chat_id=ADMIN_ID, text=alert_text, parse_mode="Markdown")
    for tg_id, _, _ in db.get_workers():
        if tg_id != message.from_user.id:
            try: await bot.send_message(chat_id=tg_id, text=alert_text, parse_mode="Markdown")
            except: pass

@dp.message(F.text == "🛑 Ishni yakunlash")
async def process_end_work(message: types.Message):
    name = db.check_worker(message.from_user.id)
    if not name: return

    dur = db.end_work(message.from_user.id)
    if dur:
        await message.answer(f"🛑 Ish tugadi. Bugun ish vaqtingiz: {dur}", reply_markup=get_worker_kb("inactive"))
        await bot.send_message(chat_id=ADMIN_ID, text=f"🛑 *{name}* ishni yakunladi. Vaqt: {dur}")
    else:
        await message.answer("Siz hali ish boshlamagansiz.", reply_markup=get_worker_kb("inactive"))

@dp.message(F.text == "📊 Shaxsiy hisobot (Oy)")
async def process_report(message: types.Message):
    if db.check_worker(message.from_user.id):
        total = db.get_monthly_report(message.from_user.id)
        await message.answer(f"📊 Shu oyda jami ishlagan vaqtingiz: *{total}*", parse_mode="Markdown")

# --- ICHKI CHAT LOGIKASI ---
@dp.message(F.text == "💬 Chatga yozish")
async def chat_start(message: types.Message, state: FSMContext):
    if db.check_worker(message.from_user.id):
        await message.answer("Chatga yubormoqchi bo'lgan xabaringizni yozing:")
        await state.set_state(WorkerStates.waiting_for_chat)

@dp.message(WorkerStates.waiting_for_chat)
async def chat_finish(message: types.Message, state: FSMContext):
    name = db.check_worker(message.from_user.id)
    if not name: return
    
    db.save_chat(name, message.text)
    chat_msg = f"💬 *[CHAT]* *{name}*: {message.text}"
    
    await bot.send_message(chat_id=ADMIN_ID, text=chat_msg, parse_mode="Markdown")
    for tg_id, _, _ in db.get_workers():
        if tg_id != message.from_user.id:
            try: await bot.send_message(chat_id=tg_id, text=chat_msg, parse_mode="Markdown")
            except: pass
            
    await message.answer("✅ Xabaringiz barcha ishchilarga va adminga yuborildi.", reply_markup=get_worker_kb())
    await state.clear()


# --- AVTOMATIK CRON VAZIFALAR ---
async def remind_start_5min():
    for tg_id, _, _ in db.get_workers():
        try: await bot.send_message(chat_id=tg_id, text="⏰ Diqqat! Ish boshlanishiga 5 minut qoldi.")
        except: pass

async def check_0600_shop():
    for tg_id, name, status in db.get_workers():
        if status == "inactive":
            try: await bot.send_message(chat_id=tg_id, text="🚨 *Ish vaqti boshlandi!* Darxol magazinni ochishingizni va magazinga borishingizni so'raymiz!", parse_mode="Markdown")
            except: pass

async def remind_end_5min():
    for tg_id, _, _ in db.get_workers():
        try: await bot.send_message(chat_id=tg_id, text="⏰ Diqqat! Ish tugashiga 5 minut qoldi. Ishni yopishni unutmang.")
        except: pass

async def auto_close_job():
    closed = db.auto_close_all()
    for tg_id, dur in closed:
        name = db.check_worker(tg_id)
        try:
            await bot.send_message(chat_id=tg_id, text=f"⚠️ Vaqt 23:40 bo'ldi, tizim ishni avtomatik yopdi. Vaqt: {dur}", reply_markup=get_worker_kb("inactive"))
            await bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ *{name}* ishni yopishni unutgan! Tizim avtomatik yopdi. Vaqt: {dur}")
        except: pass

async def monthly_archive_job():
    db.archive_month_tizim()
    await bot.send_message(chat_id=ADMIN_ID, text="📅 *Tizim eslatmasi:* Yangi oy boshlandi! O'tgan oy hisobotlari arxivlandi va joriy hisoblagichlar 0 ga tushirildi.")

# Taymerlarni sozlash (Asia/Tashkent vaqti bo'yicha)
scheduler.add_job(remind_start_5min, "cron", hour=5, minute=55)
scheduler.add_job(check_0600_shop, "cron", hour=6, minute=0)
scheduler.add_job(remind_end_5min, "cron", hour=23, minute=25)
scheduler.add_job(auto_close_job, "cron", hour=23, minute=40)
scheduler.add_job(monthly_archive_job, "cron", day="last", hour=23, minute=59)

async def main():
    db.init_db()
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
