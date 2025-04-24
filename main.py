import os
import logging
import asyncio
import schedule
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from openai import OpenAI
import random
import json
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuración de OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")
client_openai = OpenAI(api_key=OPENAI_API_KEY)

# Configuración del bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "7551775190:AAFtrWkTZYAqK0Ei0fptBzsP4VHRQGi9ISw")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1742433244"))

# Definición de canales y sus temáticas
CHANNELS = {
    "Conexión fitness": {"id": -1002299414374, "emoji": "💪"},
    "Criptomonedas": {"id": -1002333098537, "emoji": "💰"},
    "Vitalidad al límite": {"id": -1002297575582, "emoji": "🌱"},
    "Pensamientos de millonarios": {"id": -1002391067004, "emoji": "💎"}
}

# Estado para almacenar configuraciones y estadísticas
bot_state = {
    "auto_post": True,
    "post_time": "10:00",
    "last_posts": {},
    "post_frequency": "daily",  # daily, weekly, custom
    "custom_schedule": {},
    "stats": {
        "total_posts": 0,
        "posts_per_channel": {channel: 0 for channel in CHANNELS}
    }
}

# Intentar cargar estado previo si existe
try:
    with open('bot_state.json', 'r') as f:
        bot_state = json.load(f)
except FileNotFoundError:
    # Si el archivo no existe, guardar el estado inicial
    with open('bot_state.json', 'w') as f:
        json.dump(bot_state, f)

# Función para guardar el estado del bot
def save_state():
    with open('bot_state.json', 'w') as f:
        json.dump(bot_state, f)

# Función para generar contenido con OpenAI
async def generate_content(theme):
    prompts = {
        "Conexión fitness": "Crea una publicación motivadora sobre fitness, ejercicio o vida saludable. Incluye un consejo práctico y una frase motivadora. Formato: título en negrita, 2-3 párrafos de contenido, y una conclusión inspiradora. Usa emojis relevantes.",
        "Criptomonedas": "Crea una publicación informativa sobre criptomonedas. Incluye una tendencia actual, un dato interesante y un consejo para inversores. No hagas predicciones específicas de precios. Formato: título en negrita, 2-3 párrafos informativos, y una conclusión. Usa emojis relevantes.",
        "Vitalidad al límite": "Crea una publicación sobre salud holística, bienestar y vitalidad. Incluye un consejo sobre alimentación, descanso o técnicas de bienestar. Formato: título en negrita, 2-3 párrafos informativos, y una conclusión práctica. Usa emojis relevantes.",
        "Pensamientos de millonarios": "Crea una publicación inspiradora con enseñanzas de emprendedores exitosos y mentalidad de abundancia. Incluye una cita de un emprendedor famoso y un principio de éxito. Formato: título en negrita, 2-3 párrafos motivadores, y una reflexión final. Usa emojis relevantes."
    }
    
    try:
        response = client_openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un experto creador de contenido para redes sociales. Creas publicaciones atractivas, informativas y motivadoras."},
                {"role": "user", "content": prompts[theme]}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error al generar contenido: {e}")
        return f"❌ No se pudo generar contenido para {theme} debido a un error. Por favor, intenta más tarde."

# Función para generar una imagen relacionada (simulada por ahora)
async def generate_image_prompt(theme):
    try:
        response = client_openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Genera una descripción detallada para crear una imagen relacionada con el tema indicado. La descripción debe ser detallada y visual."},
                {"role": "user", "content": f"Crea una descripción detallada para generar una imagen relacionada con {theme}. La imagen será usada en redes sociales."}
            ],
            temperature=0.7,
            max_tokens=200
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error al generar prompt de imagen: {e}")
        return f"Una imagen inspiradora sobre {theme}"

# Función para publicar en un canal
async def post_to_channel(context, channel_name, content=None):
    channel_id = CHANNELS[channel_name]["id"]
    emoji = CHANNELS[channel_name]["emoji"]
    
    if content is None:
        content = await generate_content(channel_name)
    
    # Añadir firma y emoji temático
    current_date = datetime.now().strftime("%d/%m/%Y")
    signature = f"\n\n{emoji} *{channel_name}* | {current_date}"
    full_content = f"{content}\n{signature}"
    
    try:
        # Enviar mensaje
        message = await context.bot.send_message(
            chat_id=channel_id,
            text=full_content,
            parse_mode='Markdown'
        )
        
        # Actualizar estadísticas
        bot_state["stats"]["total_posts"] += 1
        bot_state["stats"]["posts_per_channel"][channel_name] += 1
        bot_state["last_posts"][channel_name] = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message_id": message.message_id
        }
        save_state()
        
        return True, message.message_id
    except Exception as e:
        logger.error(f"Error al publicar en {channel_name}: {e}")
        return False, str(e)

# Función para publicar en todos los canales
async def post_to_all_channels(context):
    results = {}
    for channel in CHANNELS:
        success, msg_id = await post_to_channel(context, channel)
        results[channel] = "✅ Publicado" if success else f"❌ Error: {msg_id}"
    
    # Notificar al administrador
    admin_message = "*Resumen de publicaciones automáticas:*\n\n"
    for channel, result in results.items():
        admin_message += f"*{channel}*: {result}\n"
    
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=admin_message,
        parse_mode='Markdown'
    )

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    welcome_message = (
        "👋 *¡Bienvenido al Bot de Publicaciones Automáticas!*\n\n"
        "Este bot publica contenido automáticamente en varios canales temáticos.\n\n"
        "Comandos disponibles:\n"
        "/menu - Mostrar menú principal\n"
        "/status - Ver estado actual del bot\n"
        "/post - Publicar contenido manualmente\n"
        "/settings - Configurar el bot\n"
        "/help - Mostrar ayuda\n\n"
        "Solo el administrador puede usar todas las funciones."
    )
    
    keyboard = [
        [InlineKeyboardButton("📋 Menú Principal", callback_data="menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Comando /menu
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Verificar si es administrador
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ Solo el administrador puede acceder al menú completo.")
        return
    
    keyboard = [
        [
            InlineKeyboardButton("📝 Publicar Ahora", callback_data="publish_menu"),
            InlineKeyboardButton("⚙️ Configuración", callback_data="settings_menu")
        ],
        [
            InlineKeyboardButton("📊 Estadísticas", callback_data="stats"),
            InlineKeyboardButton("❓ Ayuda", callback_data="help")
        ],
        [
            InlineKeyboardButton("🔄 Estado Actual", callback_data="status")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 *Menú Principal*\n\nSelecciona una opción:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Función para manejar callbacks
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    callback_data = query.data
    
    # Verificar si es administrador para la mayoría de las acciones
    if user_id != ADMIN_ID and not callback_data in ["help", "about"]:
        await query.edit_message_text("⚠️ Solo el administrador puede usar esta función.")
        return
    
    if callback_data == "menu":
        keyboard = [
            [
                InlineKeyboardButton("📝 Publicar Ahora", callback_data="publish_menu"),
                InlineKeyboardButton("⚙️ Configuración", callback_data="settings_menu")
            ],
            [
                InlineKeyboardButton("📊 Estadísticas", callback_data="stats"),
                InlineKeyboardButton("❓ Ayuda", callback_data="help")
            ],
            [
                InlineKeyboardButton("🔄 Estado Actual", callback_data="status")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🤖 *Menú Principal*\n\nSelecciona una opción:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif callback_data == "publish_menu":
        keyboard = []
        # Botón para cada canal
        for channel in CHANNELS:
            keyboard.append([InlineKeyboardButton(f"{CHANNELS[channel]['emoji']} {channel}", callback_data=f"publish_{channel}")])
        
        # Botón para publicar en todos los canales
        keyboard.append([InlineKeyboardButton("🔄 Publicar en Todos", callback_data="publish_all")])
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📝 *Publicar Contenido*\n\nSelecciona un canal para publicar:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif callback_data.startswith("publish_"):
        channel_name = callback_data.replace("publish_", "")
        
        if channel_name == "all":
            await query.edit_message_text("🔄 Publicando en todos los canales... Esto puede tomar un momento.")
            await post_to_all_channels(context)
            
            # Mensaje de confirmación con botón para volver
            keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "✅ *Publicación Completada*\n\nSe ha publicado contenido en todos los canales.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(f"🔄 Generando contenido para {channel_name}...")
            success, result = await post_to_channel(context, channel_name)
            
            # Mensaje de confirmación con botón para volver
            keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if success:
                await query.edit_message_text(
                    f"✅ *Publicación Exitosa*\n\nSe ha publicado contenido en el canal {channel_name}.",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    f"❌ *Error al Publicar*\n\nNo se pudo publicar en {channel_name}.\nError: {result}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
    
    elif callback_data == "settings_menu":
        auto_post_status = "✅ Activado" if bot_state["auto_post"] else "❌ Desactivado"
        post_time = bot_state["post_time"]
        frequency = bot_state["post_frequency"]
        
        keyboard = [
            [InlineKeyboardButton(f"🔄 Auto-publicación: {auto_post_status}", callback_data="toggle_auto_post")],
            [InlineKeyboardButton(f"⏰ Hora de publicación: {post_time}", callback_data="set_post_time")],
            [InlineKeyboardButton(f"📅 Frecuencia: {frequency}", callback_data="set_frequency")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚙️ *Configuración*\n\nAjusta los parámetros del bot:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif callback_data == "toggle_auto_post":
        bot_state["auto_post"] = not bot_state["auto_post"]
        save_state()
        
        # Redireccionar al menú de configuración
        await button_callback(update, context)
    
    elif callback_data == "set_post_time":
        times = ["08:00", "10:00", "12:00", "15:00", "18:00", "20:00", "22:00"]
        keyboard = []
        
        # Crear filas de 3 botones cada una
        row = []
        for i, time in enumerate(times):
            row.append(InlineKeyboardButton(time, callback_data=f"time_{time}"))
            if (i + 1) % 3 == 0 or i == len(times) - 1:
                keyboard.append(row)
                row = []
        
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="settings_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⏰ *Configurar Hora de Publicación*\n\nSelecciona la hora para las publicaciones automáticas:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif callback_data.startswith("time_"):
        selected_time = callback_data.replace("time_", "")
        bot_state["post_time"] = selected_time
        save_state()
        
        # Actualizar programación
        schedule_posts(context)
        
        await query.edit_message_text(
            f"✅ Hora de publicación establecida a las {selected_time}.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="settings_menu")]]),
            parse_mode='Markdown'
        )
    
    elif callback_data == "set_frequency":
        keyboard = [
            [
                InlineKeyboardButton("📅 Diario", callback_data="freq_daily"),
                InlineKeyboardButton("📆 Semanal", callback_data="freq_weekly")
            ],
            [InlineKeyboardButton("🔙 Volver", callback_data="settings_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📅 *Configurar Frecuencia*\n\nSelecciona con qué frecuencia se publicará el contenido:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif callback_data.startswith("freq_"):
        frequency = callback_data.replace("freq_", "")
        bot_state["post_frequency"] = frequency
        save_state()
        
        # Actualizar programación
        schedule_posts(context)
        
        await query.edit_message_text(
            f"✅ Frecuencia establecida a {frequency}.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="settings_menu")]]),
            parse_mode='Markdown'
        )
    
    elif callback_data == "stats":
        total_posts = bot_state["stats"]["total_posts"]
        posts_per_channel = bot_state["stats"]["posts_per_channel"]
        
        stats_text = "*📊 Estadísticas de Publicaciones*\n\n"
        stats_text += f"*Total de publicaciones:* {total_posts}\n\n"
        stats_text += "*Publicaciones por canal:*\n"
        
        for channel, count in posts_per_channel.items():
            emoji = CHANNELS[channel]["emoji"]
            stats_text += f"{emoji} *{channel}:* {count}\n"
        
        # Añadir última publicación si existe
        if bot_state["last_posts"]:
            stats_text += "\n*Últimas publicaciones:*\n"
            for channel, data in bot_state["last_posts"].items():
                if "timestamp" in data:
                    stats_text += f"{CHANNELS[channel]['emoji']} *{channel}:* {data['timestamp']}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            stats_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif callback_data == "status":
        auto_post = "✅ Activado" if bot_state["auto_post"] else "❌ Desactivado"
        post_time = bot_state["post_time"]
        frequency = bot_state["post_frequency"]
        
        status_text = "*🔄 Estado Actual del Bot*\n\n"
        status_text += f"*Auto-publicación:* {auto_post}\n"
        status_text += f"*Hora de publicación:* {post_time}\n"
        status_text += f"*Frecuencia:* {frequency}\n\n"
        
        status_text += "*Canales configurados:*\n"
        for channel, data in CHANNELS.items():
            status_text += f"{data['emoji']} *{channel}*\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            status_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif callback_data == "help":
        help_text = (
            "*❓ Ayuda del Bot*\n\n"
            "*Comandos disponibles:*\n"
            "/start - Iniciar el bot\n"
            "/menu - Mostrar menú principal\n"
            "/post - Publicar contenido manualmente\n"
            "/settings - Configurar el bot\n"
            "/status - Ver estado actual\n"
            "/help - Mostrar esta ayuda\n\n"
            
            "*Funcionalidades:*\n"
            "• Publicación automática en canales temáticos\n"
            "• Generación de contenido con IA\n"
            "• Programación de publicaciones\n"
            "• Estadísticas de publicaciones\n\n"
            
            "*Temáticas disponibles:*\n"
            "💪 Conexión fitness\n"
            "💰 Criptomonedas\n"
            "🌱 Vitalidad al límite\n"
            "💎 Pensamientos de millonarios\n\n"
            
            "Para más información o soporte, contacta al administrador."
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            help_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

# Comando /post
async def post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Verificar si es administrador
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ Solo el administrador puede publicar contenido.")
        return
    
    keyboard = []
    # Botón para cada canal
    for channel in CHANNELS:
        keyboard.append([InlineKeyboardButton(f"{CHANNELS[channel]['emoji']} {channel}", callback_data=f"publish_{channel}")])
    
    # Botón para publicar en todos los canales
    keyboard.append([InlineKeyboardButton("🔄 Publicar en Todos", callback_data="publish_all")])
    keyboard.append([InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📝 *Publicar Contenido*\n\nSelecciona un canal para publicar:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Comando /settings
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Verificar si es administrador
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ Solo el administrador puede modificar la configuración.")
        return
    
    await button_callback(Update(update_id=0, callback_query=type('obj', (object,), {
        'data': 'settings_menu',
        'from_user': type('obj', (object,), {'id': ADMIN_ID}),
        'answer': lambda: None,
        'edit_message_text': update.message.reply_text
    })), context)

# Comando /status
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Verificar si es administrador
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ Solo el administrador puede ver el estado.")
        return
    
    await button_callback(Update(update_id=0, callback_query=type('obj', (object,), {
        'data': 'status',
        'from_user': type('obj', (object,), {'id': ADMIN_ID}),
        'answer': lambda: None,
        'edit_message_text': update.message.reply_text
    })), context)

# Comando /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await button_callback(Update(update_id=0, callback_query=type('obj', (object,), {
        'data': 'help',
        'from_user': type('obj', (object,), {'id': update.effective_user.id}),
        'answer': lambda: None,
        'edit_message_text': update.message.reply_text
    })), context)

# Función para programar las publicaciones
def schedule_posts(context):
    # Limpiar todas las tareas programadas anteriormente
    schedule.clear()
    
    if bot_state["auto_post"]:
        post_time = bot_state["post_time"]
        
        if bot_state["post_frequency"] == "daily":
            schedule.every().day.at(post_time).do(lambda: asyncio.create_task(post_to_all_channels(context)))
        elif bot_state["post_frequency"] == "weekly":
            schedule.every().monday.at(post_time).do(lambda: asyncio.create_task(post_to_all_channels(context)))

# Función para ejecutar las tareas programadas
async def run_scheduled_tasks(context):
    while True:
        schedule.run_pending()
        await asyncio.sleep(60)  # Revisar cada minuto

# Función principal
async def main():
    # Crear la aplicación
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Registrar manejadores de comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("post", post_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Registrar manejador de botones
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Programar publicaciones
    schedule_posts(application)
    
    # Iniciar el ejecutor de tareas programadas en segundo plano
    asyncio.create_task(run_scheduled_tasks(application))
    
    # Iniciar el bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Mantener el bot ejecutándose hasta que se interrumpa manualmente
    try:
        await application.updater.stop()
        await application.stop()
    finally:
        # Guardar el estado antes de salir
        save_state()

if __name__ == "__main__":
    asyncio.run(main())
