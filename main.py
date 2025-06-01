import os
import logging
import asyncio
import time
import base64
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from openai import OpenAI
import json
import tempfile
from io import BytesIO

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuración de Google AI Studio
GOOGLE_API_KEY = "AIzaSyBqNZnq8eHr5LMJ1yGZQU1rmw-Nmafy4TU"
client_ai = OpenAI(
    api_key=GOOGLE_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/"
)

# Configuración del bot
BOT_TOKEN = "7551775190:AAFtrWkTZYAqK0Ei0fptBzsP4VHRQGi9ISw"
ADMIN_ID = 1742433244  # ID del administrador

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
        "posts_per_channel": {channel: 0 for channel in CHANNELS},
        "with_images": 0
    }
}

# Función para guardar el estado del bot
def save_state():
    try:
        with open('bot_state.json', 'w') as f:
            json.dump(bot_state, f)
        logger.info("Estado del bot guardado correctamente")
    except Exception as e:
        logger.error(f"Error al guardar estado: {e}")

# Función para cargar el estado del bot
def load_state():
    global bot_state
    try:
        with open('bot_state.json', 'r') as f:
            bot_state = json.load(f)
        logger.info("Estado del bot cargado correctamente")
    except FileNotFoundError:
        logger.info("Archivo de estado no encontrado, usando valores predeterminados")
        save_state()
    except Exception as e:
        logger.error(f"Error al cargar estado: {e}")

# Función para generar imágenes con Google AI
async def generate_image(theme):
    # Prompts específicos para cada tema
    image_prompts = {
        "Conexión fitness": "A beautiful minimalist fitness motivation image with vibrant colors, showing athletic silhouettes, stylish and modern design, inspirational, Instagram-worthy, professional quality",
        "Criptomonedas": "A sleek cryptocurrency illustration with modern design, digital currency symbols, blockchain visualization, futuristic, professional financial graphic, clean lines, dark blue and gold colors",
        "Vitalidad al límite": "A serene wellness image showing natural elements, peaceful zen garden, holistic health symbols, organic colors, minimal design, high-quality photography style, Instagram aesthetic",
        "Pensamientos de millonarios": "An elegant luxury minimalist image representing success and wealth mindset, gold accents, modern entrepreneur aesthetic, professional quality, inspirational, sleek design"
    }
    
    try:
        # Aquí usaríamos la API de generación de imágenes
        # Como no podemos usar directamente la API de imagen con el código proporcionado,
        # vamos a implementar una función que simula una URL de imagen
        # En producción, esto debería reemplazarse por una llamada real a la API de generación de imágenes
        
        # Opciones de imágenes de stock por tema para simular la generación
        stock_images = {
            "Conexión fitness": [
                "https://images.unsplash.com/photo-1517836357463-d25dfeac3438",
                "https://images.unsplash.com/photo-1518611012118-696072aa579a",
                "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b"
            ],
            "Criptomonedas": [
                "https://images.unsplash.com/photo-1621504450181-5d356f61d307",
                "https://images.unsplash.com/photo-1621761191319-c6fb62004040",
                "https://images.unsplash.com/photo-1621501103258-3e135c8c1fda"
            ],
            "Vitalidad al límite": [
                "https://images.unsplash.com/photo-1532187643603-ba119ca4109e",
                "https://images.unsplash.com/photo-1545205597-3d9d02c29597",
                "https://images.unsplash.com/photo-1600618528240-fb9fc964eca8"
            ],
            "Pensamientos de millonarios": [
                "https://images.unsplash.com/photo-1626266063343-838d5a257e3a",
                "https://images.unsplash.com/photo-1634757439914-e7ffd8866a56",
                "https://images.unsplash.com/photo-1589666564459-93cdd3ab856a"
            ]
        }
        
        # Seleccionar una imagen aleatoria del tema
        import random
        return random.choice(stock_images[theme])
        
        # NOTA: En producción, aquí deberías usar una API real de generación de imágenes
        # Por ejemplo, podrías usar esto (comentado por ahora):
        """
        response = client_ai.images.generate(
            model="imagegeneration",
            prompt=image_prompts[theme],
            size="1024x1024",
            n=1
        )
        return response.data[0].url
        """
        
    except Exception as e:
        logger.error(f"Error al generar imagen: {e}")
        return None

# Función para generar contenido con Google AI (mejorado para ser más corto y estético)
async def generate_content(theme):
    # Emojis temáticos para cada categoría
    theme_emojis = {
        "Conexión fitness": ["💪", "🏋️‍♀️", "🏃‍♂️", "🧘‍♀️", "🥗", "🔥", "🏆", "⚡", "🚴‍♂️", "💯"],
        "Criptomonedas": ["💰", "📈", "🚀", "💹", "🔐", "💻", "🌐", "💎", "📊", "🤑"],
        "Vitalidad al límite": ["🌱", "✨", "🧠", "💚", "🌿", "🌞", "🧘", "🍃", "💆‍♀️", "🌈"],
        "Pensamientos de millonarios": ["💎", "💼", "🏆", "💡", "🔝", "👑", "💸", "🌟", "🎯", "💪"]
    }
    
    prompts = {
        "Conexión fitness": f"""Crea una publicación corta y visualmente atractiva sobre fitness o vida saludable.
        
        Requisitos:
        1. Máximo 3-4 oraciones en total (muy conciso)
        2. Incluye un título llamativo en formato HTML <b>Título</b>
        3. Usa HTML para dar formato: <b>negrita</b>, <i>cursiva</i>, <u>subrayado</u> o <blockquote>cita</blockquote>
        4. Incluye al menos 5-6 de estos emojis donde sea apropiado: {"".join(theme_emojis["Conexión fitness"])}
        5. Una frase motivadora entre <blockquote></blockquote>
        6. No excedas las 50-60 palabras en total
        
        Ejemplo de estructura:
        <b>TÍTULO IMPACTANTE</b>
        
        Contenido breve pero poderoso 💪 con emojis estratégicos ✨
        
        <blockquote>Frase motivadora aquí</blockquote>
        """,
        
        "Criptomonedas": f"""Crea una publicación corta y visualmente atractiva sobre criptomonedas.
        
        Requisitos:
        1. Máximo 3-4 oraciones en total (muy conciso)
        2. Incluye un título llamativo en formato HTML <b>Título</b>
        3. Usa HTML para dar formato: <b>negrita</b>, <i>cursiva</i>, <u>subrayado</u> o <blockquote>cita</blockquote>
        4. Incluye al menos 5-6 de estos emojis donde sea apropiado: {"".join(theme_emojis["Criptomonedas"])}
        5. Un consejo o dato interesante entre <blockquote></blockquote>
        6. No excedas las 50-60 palabras en total
        
        Ejemplo de estructura:
        <b>TÍTULO IMPACTANTE</b>
        
        Contenido breve pero informativo 📊 con emojis estratégicos 🚀
        
        <blockquote>Consejo interesante aquí</blockquote>
        """,
        
        "Vitalidad al límite": f"""Crea una publicación corta y visualmente atractiva sobre bienestar y salud holística.
        
        Requisitos:
        1. Máximo 3-4 oraciones en total (muy conciso)
        2. Incluye un título llamativo en formato HTML <b>Título</b>
        3. Usa HTML para dar formato: <b>negrita</b>, <i>cursiva</i>, <u>subrayado</u> o <blockquote>cita</blockquote>
        4. Incluye al menos 5-6 de estos emojis donde sea apropiado: {"".join(theme_emojis["Vitalidad al límite"])}
        5. Un consejo de bienestar entre <blockquote></blockquote>
        6. No excedas las 50-60 palabras en total
        
        Ejemplo de estructura:
        <b>TÍTULO IMPACTANTE</b>
        
        Contenido breve pero inspirador 🌱 con emojis estratégicos ✨
        
        <blockquote>Consejo de bienestar aquí</blockquote>
        """,
        
        "Pensamientos de millonarios": f"""Crea una publicación corta y visualmente atractiva sobre mentalidad de abundancia y éxito.
        
        Requisitos:
        1. Máximo 3-4 oraciones en total (muy conciso)
        2. Incluye un título llamativo en formato HTML <b>Título</b>
        3. Usa HTML para dar formato: <b>negrita</b>, <i>cursiva</i>, <u>subrayado</u> o <blockquote>cita</blockquote>
        4. Incluye al menos 5-6 de estos emojis donde sea apropiado: {"".join(theme_emojis["Pensamientos de millonarios"])}
        5. Una cita inspiradora entre <blockquote></blockquote>
        6. No excedas las 50-60 palabras en total
        
        Ejemplo de estructura:
        <b>TÍTULO IMPACTANTE</b>
        
        Contenido breve pero poderoso 💎 con emojis estratégicos 🔝
        
        <blockquote>Cita inspiradora aquí</blockquote>
        """
    }
    
    try:
        # Usando la API de Google Gemini a través de la interfaz compatible con OpenAI
        response = client_ai.chat.completions.create(
            model="gemini-1.5-flash",
            messages=[
                {"role": "system", "content": "Eres un experto creador de contenido para redes sociales. Creas publicaciones atractivas, concisas y visualmente impactantes con formato HTML."},
                {"role": "user", "content": prompts[theme]}
            ],
            temperature=0.7,
            max_tokens=200
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error al generar contenido: {e}")
        return f"❌ No se pudo generar contenido para {theme} debido a un error. Por favor, intenta más tarde."

# Función para publicar en un canal
async def post_to_channel(context, channel_name, content=None, image_url=None):
    channel_id = CHANNELS[channel_name]["id"]
    emoji = CHANNELS[channel_name]["emoji"]
    
    if content is None:
        content = await generate_content(channel_name)
    
    if image_url is None:
        image_url = await generate_image(channel_name)
    
    # Añadir firma y emoji temático
    current_date = datetime.now().strftime("%d/%m/%Y")
    signature = f"\n\n{emoji} <b>{channel_name}</b> | {current_date}"
    full_content = f"{content}\n{signature}"
    
    try:
        if image_url:
            # Enviar mensaje con imagen
            message = await context.bot.send_photo(
                chat_id=channel_id,
                photo=image_url,
                caption=full_content,
                parse_mode='HTML'
            )
            bot_state["stats"]["with_images"] += 1
        else:
            # Enviar mensaje solo texto
            message = await context.bot.send_message(
                chat_id=channel_id,
                text=full_content,
                parse_mode='HTML'
            )
        
        # Actualizar estadísticas
        bot_state["stats"]["total_posts"] += 1
        bot_state["stats"]["posts_per_channel"][channel_name] += 1
        bot_state["last_posts"][channel_name] = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message_id": message.message_id,
            "has_image": image_url is not None
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
        success, result = await post_to_channel(context, channel)
        results[channel] = "✅ Publicado" if success else f"❌ Error: {result}"
    
    # Notificar al administrador
    admin_message = "<b>Resumen de publicaciones automáticas:</b>\n\n"
    for channel, result in results.items():
        admin_message += f"<b>{channel}</b>: {result}\n"
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_message,
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error al enviar resumen al administrador: {e}")

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "<b>👋 ¡Bienvenido al Bot de Publicaciones Automáticas!</b>\n\n"
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
        parse_mode='HTML'
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
        "<b>🤖 Menú Principal</b>\n\nSelecciona una opción:",
        reply_markup=reply_markup,
        parse_mode='HTML'
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
            "<b>🤖 Menú Principal</b>\n\nSelecciona una opción:",
            reply_markup=reply_markup,
            parse_mode='HTML'
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
            "<b>📝 Publicar Contenido</b>\n\nSelecciona un canal para publicar:",
            reply_markup=reply_markup,
            parse_mode='HTML'
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
                "<b>✅ Publicación Completada</b>\n\nSe ha publicado contenido en todos los canales.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text(f"🔄 Generando contenido para {channel_name}...")
            success, result = await post_to_channel(context, channel_name)
            
            # Mensaje de confirmación con botón para volver
            keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if success:
                await query.edit_message_text(
                    f"<b>✅ Publicación Exitosa</b>\n\nSe ha publicado contenido en el canal {channel_name}.",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            else:
                await query.edit_message_text(
                    f"<b>❌ Error al Publicar</b>\n\nNo se pudo publicar en {channel_name}.\nError: {result}",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
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
            "<b>⚙️ Configuración</b>\n\nAjusta los parámetros del bot:",
            reply_markup=reply_markup,
            parse_mode='HTML'
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
            "<b>⏰ Configurar Hora de Publicación</b>\n\nSelecciona la hora para las publicaciones automáticas:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif callback_data.startswith("time_"):
        selected_time = callback_data.replace("time_", "")
        bot_state["post_time"] = selected_time
        save_state()
        
        await query.edit_message_text(
            f"✅ Hora de publicación establecida a las {selected_time}.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="settings_menu")]]),
            parse_mode='HTML'
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
            "<b>📅 Configurar Frecuencia</b>\n\nSelecciona con qué frecuencia se publicará el contenido:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif callback_data.startswith("freq_"):
        frequency = callback_data.replace("freq_", "")
        bot_state["post_frequency"] = frequency
        save_state()
        
        await query.edit_message_text(
            f"✅ Frecuencia establecida a {frequency}.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="settings_menu")]]),
            parse_mode='HTML'
        )
    
    elif callback_data == "stats":
        total_posts = bot_state["stats"]["total_posts"]
        posts_per_channel = bot_state["stats"]["posts_per_channel"]
        with_images = bot_state.get("stats", {}).get("with_images", 0)
        
        stats_text = "<b>📊 Estadísticas de Publicaciones</b>\n\n"
        stats_text += f"<b>Total de publicaciones:</b> {total_posts}\n"
        stats_text += f"<b>Con imágenes:</b> {with_images}\n\n"
        stats_text += "<b>Publicaciones por canal:</b>\n"
        
        for channel, count in posts_per_channel.items():
            emoji = CHANNELS[channel]["emoji"]
            stats_text += f"{emoji} <b>{channel}:</b> {count}\n"
        
        # Añadir última publicación si existe
        if bot_state["last_posts"]:
            stats_text += "\n<b>Últimas publicaciones:</b>\n"
            for channel, data in bot_state["last_posts"].items():
                if "timestamp" in data:
                    img_icon = "🖼️" if data.get("has_image", False) else ""
                    stats_text += f"{CHANNELS[channel]['emoji']} <b>{channel}:</b> {data['timestamp']} {img_icon}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            stats_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif callback_data == "status":
        auto_post = "✅ Activado" if bot_state["auto_post"] else "❌ Desactivado"
        post_time = bot_state["post_time"]
        frequency = bot_state["post_frequency"]
        
        status_text = "<b>🔄 Estado Actual del Bot</b>\n\n"
        status_text += f"<b>Auto-publicación:</b> {auto_post}\n"
        status_text += f"<b>Hora de publicación:</b> {post_time}\n"
        status_text += f"<b>Frecuencia:</b> {frequency}\n\n"
        
        status_text += "<b>Canales configurados:</b>\n"
        for channel, data in CHANNELS.items():
            status_text += f"{data['emoji']} <b>{channel}</b>\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            status_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif callback_data == "help":
        help_text = (
            "<b>❓ Ayuda del Bot</b>\n\n"
            "<b>Comandos disponibles:</b>\n"
            "/start - Iniciar el bot\n"
            "/menu - Mostrar menú principal\n"
            "/post - Publicar contenido manualmente\n"
            "/settings - Configurar el bot\n"
            "/status - Ver estado actual\n"
            "/help - Mostrar esta ayuda\n\n"
            
            "<b>Funcionalidades:</b>\n"
            "• Publicación automática en canales temáticos\n"
            "• Generación de contenido con IA\n"
            "• Imágenes atractivas para cada publicación\n"
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
        "<b>📝 Publicar Contenido</b>\n\nSelecciona un canal para publicar:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

# Comando /settings
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Verificar si es administrador
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ Solo el administrador puede modificar la configuración.")
        return
    
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
    
    await update.message.reply_text(
        "<b>⚙️ Configuración</b>\n\nAjusta los parámetros del bot:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

# Comando /status
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Verificar si es administrador
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ Solo el administrador puede ver el estado.")
        return
    
    auto_post = "✅ Activado" if bot_state["auto_post"] else "❌ Desactivado"
    post_time = bot_state["post_time"]
    frequency = bot_state["post_frequency"]
    
    status_text = "<b>🔄 Estado Actual del Bot</b>\n\n"
    status_text += f"<b>Auto-publicación:</b> {auto_post}\n"
    status_text += f"<b>Hora de publicación:</b> {post_time}\n"
    status_text += f"<b>Frecuencia:</b> {frequency}\n\n"
    
    status_text += "<b>Canales configurados:</b>\n"
    for channel, data in CHANNELS.items():
        status_text += f"{data['emoji']} <b>{channel}</b>\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        status_text,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

# Comando /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "<b>❓ Ayuda del Bot</b>\n\n"
        "<b>Comandos disponibles:</b>\n"
        "/start - Iniciar el bot\n"
        "/menu - Mostrar menú principal\n"
        "/post - Publicar contenido manualmente\n"
        "/settings - Configurar el bot\n"
        "/status - Ver estado actual\n"
        "/help - Mostrar esta ayuda\n\n"
        
        "<b>Funcionalidades:</b>\n"
        "• Publicación automática en canales temáticos\n"
        "• Generación de contenido con IA\n"
        "• Imágenes atractivas para cada publicación\n"
        "• Programación de publicaciones\n"
        "• Estadísticas de publicaciones\n\n"
        
        "<b>Temáticas disponibles:</b>\n"
        "💪 Conexión fitness\n"
        "💰 Criptomonedas\n"
        "🌱 Vitalidad al límite\n"
        "💎 Pensamientos de millonarios\n\n"
        
        "Para más información o soporte, contacta al administrador."
    )
    
    keyboard = [[InlineKeyboardButton("📋 Menú Principal", callback_data="menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        help_text,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

# Tarea programada para publicar contenido
async def scheduled_post(context):
    if bot_state["auto_post"]:
        logger.info("Ejecutando publicación programada")
        await post_to_all_channels(context)

# Función para mantener el bot activo (necesario en Render)
async def keep_alive(context):
    while True:
        logger.info("Bot activo - Keep alive ping")
        current_hour = datetime.now().hour
        current_minute = datetime.now().minute
        
        # Verificar si es hora de publicación
        post_hour, post_minute = map(int, bot_state["post_time"].split(":"))
        
        if current_hour == post_hour and current_minute == post_minute and bot_state["auto_post"]:
            logger.info("Ejecutando publicación programada")
            await post_to_all_channels(context)
        
        # Esperar 60 segundos antes de la siguiente verificación
        await asyncio.sleep(60)

# Función para hacer una solicitud de imagen real a Google Gemini
async def generate_real_image(theme, client_ai, api_key):
    # Prompts específicos para cada tema
    image_prompts = {
        "Conexión fitness": "A beautiful minimalist fitness motivation image with vibrant colors, showing athletic silhouettes, inspirational, Instagram-worthy, professional quality",
        "Criptomonedas": "A sleek cryptocurrency illustration with modern design, digital currency symbols, blockchain visualization, futuristic, professional financial graphic, clean lines",
        "Vitalidad al límite": "A serene wellness image showing natural elements, peaceful zen garden, holistic health symbols, organic colors, minimal design, high-quality photography style",
        "Pensamientos de millonarios": "An elegant luxury minimalist image representing success and wealth mindset, gold accents, modern entrepreneur aesthetic, professional quality, inspirational design"
    }
    
    try:
        # Para una implementación real usando Gemini Pro Vision, necesitaríamos una API específica que soporte generación de imágenes
        # Esta es una implementación de ejemplo que debería adaptarse según la API disponible
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateImage"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "prompt": {
                "text": image_prompts[theme]
            },
            "size": {
                "width": 1024,
                "height": 1024
            }
        }
        
        # Nota: Esta parte es teórica, la implementación real dependería de la API específica
        # response = requests.post(url, json=data, headers=headers)
        # if response.status_code == 200:
        #     return response.json().get("image", {}).get("url")
        
        # Por ahora volvemos al método de imágenes de stock
        stock_images = {
            "Conexión fitness": [
                "https://images.unsplash.com/photo-1517836357463-d25dfeac3438",
                "https://images.unsplash.com/photo-1518611012118-696072aa579a",
                "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b"
            ],
            "Criptomonedas": [
                "https://images.unsplash.com/photo-1621504450181-5d356f61d307",
                "https://images.unsplash.com/photo-1621761191319-c6fb62004040",
                "https://images.unsplash.com/photo-1621501103258-3e135c8c1fda"
            ],
            "Vitalidad al límite": [
                "https://images.unsplash.com/photo-1532187643603-ba119ca4109e",
                "https://images.unsplash.com/photo-1545205597-3d9d02c29597",
                "https://images.unsplash.com/photo-1600618528240-fb9fc964eca8"
            ],
            "Pensamientos de millonarios": [
                "https://images.unsplash.com/photo-1626266063343-838d5a257e3a",
                "https://images.unsplash.com/photo-1634757439914-e7ffd8866a56",
                "https://images.unsplash.com/photo-1589666564459-93cdd3ab856a"
            ]
        }
        
        import random
        return random.choice(stock_images[theme])
        
    except Exception as e:
        logger.error(f"Error al generar imagen real: {e}")
        return None

# Función principal
async def main():
    # Cargar estado previo
    load_state()
    
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
    
    # Iniciar el bot
    await application.initialize()
    await application.start()
    
    # Iniciar tarea de keep alive
    asyncio.create_task(keep_alive(application))
    
    # Iniciar el polling
    await application.updater.start_polling()
    
    # Mantener el bot ejecutándose
    try:
        await asyncio.Future()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot detenido manualmente")
    finally:
        # Guardar el estado antes de salir
        save_state()
        await application.updater.stop()
        await application.stop()

if __name__ == "__main__":
    asyncio.run(main())
