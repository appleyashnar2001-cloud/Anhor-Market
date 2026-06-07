import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncioScheduler
from pytz import timezone

import database as db

# --- JORCHILAR SOZLAMASI ---
BOT_TOKEN = "BOT_TOKEN_SHU_YERGA_YOZILADI"  # BotFather bergan tokenni kiriting
ADMIN_ID = 7180864511  # Sizning Telegram ID raqamingiz muvaffaqiyatli joylashtirildi

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncioScheduler(timezone=timezone("Asia/Tashkent"))

class AdminStates(StatesGroup):
    waiting_for_worker_id = State()
    waiting_for_worker_name = State()
    waiting_for_broadcast = State()

# --- ADMIN KLAVIATURASI ---
def get_admin_kb():
    kb = [
        [types.KeyboardButton(text="👥 Ishchilar ro'yxati"), types.KeyboardButton(text="➕ Ishchi qo'shish")],
        [types.KeyboardButton(text="📢 Xabar yuborish")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- ISHCHI KLAVIATURASI ---
def get_worker_kb(status="inactive"):
    if status == "inactive":
        kb = [[types.KeyboardButton(text="🚀 Ishni boshlash")]]
    else:
        kb = [[types.KeyboardButton(text="🛑 Ishni yakunlash")]]
    kb.append([types.KeyboardButton(text="📊 Shaxsiy hisobot (Oy)")])
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- COMMAND START ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Xush kelibsiz, Admin!", reply_markup=get_admin_kb())
    else:
        worker_name = db.check_worker(message.from_user.id)
        if worker_name:
            await message.answer(f"Xush kelibsiz, {worker_name}!", reply_markup=get_worker_kb())
        else:
            await message.answer(f"Siz tizimda yo'qsiz. ID: `{message.from_user.id}`\nBuni adminga yuboring.", parse_mode="Markdown")

# --- ADMIN FUNKSIYALARI ---
@dp.message(F.text == "👥 Ishchilar ro'yxati", F.from_user.id == ADMIN_ID)
async def list_workers(message: types.Message):
    workers = db.get_workers()
    if not workers:
        return await message.answer("Ishchilar mavjud emas.")
    
    text = "📋 *Ishchilar ro'yxati:*\n\n"
    for tg_id, name, status in workers:
        st = "🟢 Ishda" if status == "active" else "🔴 Ketgan"
        text += f"👤 {name} (ID: `{tg_id}`) - {st}\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "➕ Ishchi qo'shish", F.from_user.id == ADMIN_ID)
async def add_worker_start(message: types.Message, state: FSMContext):
    await message.answer("Ishchining Telegram ID raqamini kiriting:")
    await state.set_state(AdminStates.waiting_for_worker_id)

@dp.message(AdminStates.waiting_for_worker_id, F.from_user.id == ADMIN_ID)
async def add_worker_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("ID faqat raqamlardan iborat bo'lishi kerak!")
    await state.update_data(tg_id=int(message.text))
    await message.answer("Ishchining Ismi va Familiyasini kiriting:")
    await state.set_state(AdminStates.waiting_for_worker_name)

@dp.message(AdminStates.waiting_for_worker_name, F.from_user.id == ADMIN_ID)
async def add_worker_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    tg_id = data['tg_id']
    name = message.text
    
    if db.add_worker(tg_id, name):
        await message.answer(f"✅ {name} muvaffaqiyatli qo'shildi!", reply_markup=get_admin_kb())
    else:
        await message.answer("❌ Xatolik yuz berdi.")
    await state.clear()

@dp.message(F.text == "📢 Xabar yuborish", F.from_user.id == ADMIN_ID)
async def broadcast_start(message: types.Message, state: FSMContext):
    await message.answer("Barcha ishchilarga yuboriladigan xabarni kiriting:")
    await state.set_state(AdminStates.waiting_for_broadcast)

@dp.message(AdminStates.waiting_for_broadcast, F.from_user.id == ADMIN_ID)
async def broadcast_finish(message: types.Message, state: FSMContext):
    workers = db.get_workers()
    text = message.text
    count = 0
    for tg_id, _, _ in workers:
        try:
            await bot.send_message(chat_id=tg_id, text=f"📢 *Admindan xabar:*\n\n{text}", parse_mode="Markdown")
            count += 1
        except:
            pass
    await message.answer(f"✅ Xabar {count} ta ishchiga yuborildi.", reply_markup=get_admin_kb())
    await state.clear()

# --- ISHCHILAR FUNKSIYALARI ---
@dp.message(F.text == "🚀 Ishni boshlash")
async def process_start_work(message: types.Message):
    name = db.check_worker(message.from_user.id)
    if not name:
        return await message.answer("Siz ro'yxatda yo'qsiz!")
    
    db.start_work(message.from_user.id)
    await message.answer("🟢 Ishingiz boshlandi. Barakali bo'lsin!", reply_markup=get_worker_kb("active"))
    await bot.send_message(chat_id=ADMIN_ID, text=f"🟢 *{name}* ishga keldi.")

@dp.message(F.text == "🛑 Ishni yakunlash")
async def process_end_work(message: types.Message):
    name = db.check_worker(message.from_user.id)
    if not name:
        return await message.answer("Siz ro'yxatda yo'qsiz!")
    
    duration = db.end_work(message.from_user.id)
    if duration:
        await message.answer(f"🛑 Ish yakunlandi.\nBugun ishlagan vaqtingiz: *{duration}*", reply_markup=get_worker_kb("inactive"), parse_mode="Markdown")
        await bot.send_message(chat_id=ADMIN_ID, text=f"🛑 *{name}* ishni tugatdi.\nSarflangan vaqt: {duration}")
    else:
        await message.answer("Siz ish boshlamagandirsiz?", reply_markup=get_worker_kb("inactive"))

@dp.message(F.text == "📊 Shaxsiy hisobot (Oy)")
async def process_report(message: types.Message):
    name = db.check_worker(message.from_user.id)
    if not name:
        return await message.answer("Siz ro'yxatda yo'qsiz!")
    
    total = db.get_monthly_report(message.from_user.id)
    await message.answer(f"📊 Shu oyda jami ishlagan vaqtingiz: *{total}*", parse_mode="Markdown")


# --- AVTOMATIK XABARLAR (SCHEDULER) ---
async def remind_5_min():
    workers = db.get_workers()
    for tg_id, _, _ in workers:
        try:
            await bot.send_message(chat_id=tg_id, text="⏰ Diqqat! Ish boshlanishiga 5 minut qoldi.")
        except:
            pass

async def auto_close_job():
    closed_list = db.auto_close_all()
    for tg_id, dur in closed_list:
        name = db.check_worker(tg_id)
        try:
            await bot.send_message(chat_id=tg_id, text=f"⚠️ Vaqt 23:40 bo'lgani sababli tizim ishni avtomat yopdi.\nBugun: {dur}", reply_markup=get_worker_kb("inactive"))
            await bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ *{name}* ishni yopishni unutgan! Tizim avtomat yopdi. Vaqt: {dur}")
        except:
            pass

# Taymerlarni sozlash (06:00 va 23:30 dan 5 daqiqa oldin xabar va 23:40 da avtomat yopish)
scheduler.add_job(remind_5_min, "cron", hour=5, minute=55)
scheduler.add_job(remind_5_min, "cron", hour=23, minute=25)
scheduler.add_job(auto_close_job, "cron", hour=23, minute=40)

async def main():
    db.init_db()
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
