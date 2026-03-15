import asyncio
from typing import Dict, List
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Cấu hình ---
TELEGRAM_TOKEN = "8426116706:AAEr8bDM_3tJoZB-78vLYSiyQINinGsKWxQ"
LLM_BASE_URL = "http://localhost:20128/v1"  # Trỏ về server mới
LLM_API_KEY = "none"

# Bộ nhớ tạm lưu lịch sử chat của từng người dùng
chat_histories: Dict[int, List[dict]] = {}
user_models: Dict[int, str] = {} # Lưu model mà mỗi user đang trỏ tới

client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

async def _get_available_models() -> List[str]:
    """Lấy danh sách model từ server"""
    try:
        models = await client.models.list()
        return [m.id for m in models.data]
    except Exception as e:
        print(f"Error fetching models: {e}")
        return []

async def _get_model(chat_id: int):
    """Tự động phát hiện model nếu user chưa set cứng"""
    if chat_id in user_models:
        return user_models[chat_id]
        
    models = await _get_available_models()
    if models:
        user_models[chat_id] = models[0]
        return models[0]
    return "local-model"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /start"""
    chat_id = update.effective_chat.id
    chat_histories[chat_id] = [{"role": "system", "content": "You are a helpful AI assistant. Always reply in Vietnamese."}]
    await update.message.reply_text(
        "👋 Xin chào! Tôi là trợ lý AI.\n\n"
        "Bạn có thể nhắn tin bình thường để trò chuyện với tôi.\n\n"
        "� **Các lệnh hệ thống:**\n"
        "👉 `/clear` - Xóa lịch sử và bắt đầu câu chuyện mới.\n"
        "👉 `/models` - Xem danh sách các AI đang được bật.\n"
        "👉 `/setmodel <tên>` - Chọn AI để chat."
    )

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /clear để xóa lịch sử chat"""
    chat_id = update.effective_chat.id
    chat_histories[chat_id] = [{"role": "system", "content": "You are a helpful AI assistant. Always reply in Vietnamese."}]
    await update.message.reply_text("🧹 Đã xóa ngữ cảnh trò chuyện. Phép màu đã reset, ta có thể bắt đầu chủ đề mới!")

async def list_models(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /models để xem danh sách"""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    models = await _get_available_models()
    
    if not models:
        await update.message.reply_text("❌ Không tìm thấy model nào đang chạy trên server (hoặc web server ở port 20128 đang tắt).")
        return
        
    text = "📋 **Danh sách các AI Model:**\n\n"
    for i, m in enumerate(models):
        text += f"{i+1}. `{m}`\n"
    
    text += "\n👉 Để đổi AI, hãy copy tên và gõ lệnh: `/setmodel <tên>`"
    await update.message.reply_text(text, parse_mode='Markdown')

async def set_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /setmodel <name>"""
    if not context.args:
        await update.message.reply_text("❌ Bạn cần truyền tên model. Ví dụ: `/setmodel qwen-3b`", parse_mode='Markdown')
        return
        
    model_name = context.args[0]
    chat_id = update.effective_chat.id
    
    user_models[chat_id] = model_name
    await update.message.reply_text(f"✅ Đã chuyển trí tuệ sang mã: `{model_name}`\n*(Lưu ý: Nếu Model này không có trên server, bot sẽ báo lỗi ở câu hỏi tới. Hãy dùng /models để tham chiếu.)*", parse_mode='Markdown')

def escape_markdown(text: str) -> str:
    """Escapes markdown characters for Telegram V1/V2 parsing if needed."""
    return text

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý mọi tin nhắn text gửi đến bot"""
    chat_id = update.effective_chat.id
    user_text = update.message.text
    
    # Khởi tạo history nếu người dùng chưa /start
    if chat_id not in chat_histories:
        chat_histories[chat_id] = [{"role": "system", "content": "You are a helpful AI assistant. Always reply in Vietnamese."}]
        
    chat_histories[chat_id].append({"role": "user", "content": user_text})
    
    # Hiển thị trạng thái "đang gõ..." trên app Telegram
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        model_name = await _get_model(chat_id)
        response = await client.chat.completions.create(
            model=model_name,
            messages=chat_histories[chat_id],
            temperature=0.7,
            max_tokens=2048
        )
        
        reply_content = response.choices[0].message.content
        
        # Lưu vào lịch sử
        chat_histories[chat_id].append({"role": "assistant", "content": reply_content})
        
        # Cắt thẻ <think> nếu có để format lại cho đẹp (Dành cho models của DeepSeek R1)
        display_text = reply_content
        if "<think>" in reply_content and "</think>" in reply_content:
            parts = reply_content.split("</think>")
            thought = parts[0].replace("<think>", "").strip()
            answer = parts[1].strip() if len(parts) > 1 else ""
            display_text = f"💭 *Suy nghĩ:*\n_{thought}_\n\n{answer}"
            
        await update.message.reply_text(display_text, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi kết nối tới AI (cổng 20128 tắt, hoặc sai tên Model)\nChi tiết API Error: {e}")
        # Xóa tin nhắn lỗi để khỏi bị kẹt context
        if len(chat_histories[chat_id]) > 0:
            chat_histories[chat_id].pop()

def main():
    print("🤖 Đang khởi động Telegram AI Bot trên port 20128...")
    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("clear", clear))
        app.add_handler(CommandHandler("models", list_models))
        app.add_handler(CommandHandler("setmodel", set_model))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("✅ Telegram Bot đang chạy! Hãy nhắn tin cho bot của bạn trên điện thoại.")
        print("Bấm Ctrl+C (2 lần) để dừng bot.")
        app.run_polling()
    except Exception as e:
        print(f"❌ Lỗi khởi động Telegram Bot: {e}")

if __name__ == "__main__":
    main()
