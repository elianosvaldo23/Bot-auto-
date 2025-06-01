import os
import logging
import asyncio
import time
import random
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import BadRequest
from openai import OpenAI
import json
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
    "use_images": True,  # Opción para controlar si se usan imágenes
    "stats": {
        "total_posts": 0,
        "posts_per_channel": {channel: 0 for channel in CHANNELS},
        "with_images": 0
    },
    "content_cache": {}  # Cache para evitar repetición de contenido
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
        
        # Asegurar que existen las claves necesarias
        if "use_images" not in bot_state:
            bot_state["use_images"] = True
        if "content_cache" not in bot_state:
            bot_state["content_cache"] = {}
        if "with_images" not in bot_state.get("stats", {}):
            if "stats" not in bot_state:
                bot_state["stats"] = {}
            bot_state["stats"]["with_images"] = 0
            
    except FileNotFoundError:
        logger.info("Archivo de estado no encontrado, usando valores predeterminados")
        save_state()
    except Exception as e:
        logger.error(f"Error al cargar estado: {e}")

# Función para verificar URL de imagen
def is_valid_image_url(url):
    try:
        response = requests.head(url, timeout=5)
        return response.status_code == 200 and response.headers.get('content-type', '').startswith('image/')
    except Exception:
        return False

# Función para obtener imágenes de stock confiables
def get_safe_image_url(theme):
    # URLs de imágenes verificadas y seguras
    safe_images = {
        "Conexión fitness": [
            "https://cdn.pixabay.com/photo/2017/08/07/14/02/man-2604149_640.jpg",
            "https://cdn.pixabay.com/photo/2014/12/20/09/18/running-573762_640.jpg",
            "https://cdn.pixabay.com/photo/2016/11/22/22/25/adventure-1850912_640.jpg"
        ],
        "Criptomonedas": [
            "https://cdn.pixabay.com/photo/2018/01/18/07/31/bitcoin-3089728_640.jpg",
            "https://cdn.pixabay.com/photo/2017/12/12/12/44/bitcoin-3014614_640.jpg",
            "https://cdn.pixabay.com/photo/2018/01/27/09/36/crypto-3111490_640.jpg"
        ],
        "Vitalidad al límite": [
            "https://cdn.pixabay.com/photo/2017/03/26/21/54/yoga-2176668_640.jpg",
            "https://cdn.pixabay.com/photo/2017/04/08/22/26/buddhism-2214532_640.jpg",
            "https://cdn.pixabay.com/photo/2016/11/18/13/47/spa-1834731_640.jpg"
        ],
        "Pensamientos de millonarios": [
            "https://cdn.pixabay.com/photo/2018/01/17/04/14/stock-exchange-3087396_640.jpg",
            "https://cdn.pixabay.com/photo/2016/10/09/19/19/coins-1726618_640.jpg",
            "https://cdn.pixabay.com/photo/2016/08/20/20/45/startup-1608642_640.jpg"
        ]
    }
    
    return random.choice(safe_images[theme])

# Función para limpiar y validar HTML
def clean_html(content):
    """
    Limpia el contenido HTML para que sea compatible con Telegram.
    Telegram solo soporta las etiquetas: b, i, u, s, strike, del, 
    code, pre, a, tg-spoiler, ins, em, strong, blockquote
    """
    # Reemplazar etiquetas no soportadas
    replacements = [
        ("<h1>", "<b>"),
        ("</h1>", "</b>"),
        ("<h2>", "<b>"),
        ("</h2>", "</b>"),
        ("<h3>", "<b>"),
        ("</h3>", "</b>"),
        ("<h4>", "<b>"),
        ("</h4>", "</b>"),
        ("<h5>", "<b>"),
        ("</h5>", "</b>"),
        ("<h6>", "<b>"),
        ("</h6>", "</b>"),
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    # Eliminar la palabra "html" si aparece
    content = content.replace("html", "").replace("HTML", "")
    
    # Eliminar dobles saltos de línea
    content = content.replace("\n\n\n", "\n\n")
    
    return content

# Función para generar contenido con Google AI (mejorado para ser más corto y estético)
async def generate_content(theme):
    # Comprobar si tenemos contenido en caché para este tema
    if theme in bot_state["content_cache"]:
        # Eliminar el contenido de la caché después de usarlo
        content = bot_state["content_cache"].pop(theme)
        save_state()
        return content
    
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
        2. Incluye un título llamativo usando <b>negrita</b>
        3. Usa solo estas etiquetas HTML permitidas: <b>negrita</b>, <i>cursiva</i>, <u>subrayado</u> o <blockquote>cita</blockquote>
        4. Incluye al menos 5-6 de estos emojis donde sea apropiado: {"".join(theme_emojis["Conexión fitness"])}
        5. Una frase motivadora entre etiquetas <blockquote></blockquote>
        6. No excedas las 50-60 palabras en total
        7. NO uses etiquetas h1, h2, h3, etc. - solo las etiquetas especificadas arriba
        
        Ejemplo de estructura:
        <b>TÍTULO IMPACTANTE</b>
        
        Contenido breve pero poderoso 💪 con emojis estratégicos ✨
        
        <blockquote>Frase motivadora aquí</blockquote>
        """,
        
        "Criptomonedas": f"""Crea una publicación corta y visualmente atractiva sobre criptomonedas.
        
        Requisitos:
        1. Máximo 3-4 oraciones en total (muy conciso)
        2. Incluye un título llamativo usando <b>negrita</b>
        3. Usa solo estas etiquetas HTML permitidas: <b>negrita</b>, <i>cursiva</i>, <u>subrayado</u> o <blockquote>cita</blockquote>
        4. Incluye al menos 5-6 de estos emojis donde sea apropiado: {"".join(theme_emojis["Criptomonedas"])}
        5. Un consejo o dato interesante entre etiquetas <blockquote></blockquote>
        6. No excedas las 50-60 palabras en total
        7. NO uses etiquetas h1, h2, h3, etc. - solo las etiquetas especificadas arriba
        
        Ejemplo de estructura:
        <b>TÍTULO IMPACTANTE</b>
        
        Contenido breve pero informativo 📊 con emojis estratégicos 🚀
        
        <blockquote>Consejo interesante aquí</blockquote>
        """,
        
        "Vitalidad al límite": f"""Crea una publicación corta y visualmente atractiva sobre bienestar y salud holística.
        
        Requisitos:
        1. Máximo 3-4 oraciones en total (muy conciso)
        2. Incluye un título llamativo usando <b>negrita</b>
        3. Usa solo estas etiquetas HTML permitidas: <b>negrita</b>, <i>cursiva</i>, <u>subrayado</u> o <blockquote>cita</blockquote>
        4. Incluye al menos 5-6 de estos emojis donde sea apropiado: {"".join(theme_emojis["Vitalidad al límite"])}
        5. Un consejo de bienestar entre etiquetas <blockquote></blockquote>
        6. No excedas las 50-60 palabras en total
        7. NO uses etiquetas h1, h2, h3, etc. - solo las etiquetas especificadas arriba
        
        Ejemplo de estructura:
        <b>TÍTULO IMPACTANTE</b>
        
        Contenido breve pero inspirador 🌱 con emojis estratégicos ✨
        
        <blockquote>Consejo de bienestar aquí</blockquote>
        """,
        
        "Pensamientos de millonarios": f"""Crea una publicación corta y visualmente atractiva sobre mentalidad de abundancia y éxito.
        
        Requisitos:
        1. Máximo 3-4 oraciones en total (muy conciso)
        2. Incluye un título llamativo usando <b>negrita</b>
        3. Usa solo estas etiquetas HTML permitidas: <b>negrita</b>, <i>cursiva</i>, <u>subrayado</u> o <blockquote>cita</blockquote>
        4. Incluye al menos 5-6 de estos emojis donde sea apropiado: {"".join(theme_emojis["Pensamientos de millonarios"])}
        5. Una cita inspiradora entre etiquetas <blockquote></blockquote>
        6. No excedas las 50-60 palabras en total
        7. NO uses etiquetas h1, h2, h3, etc. - solo las etiquetas especificadas arriba
        
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
                {"role": "system", "content": "Eres un experto creador de contenido para redes sociales. Crea publicaciones atractivas, concisas y visualmente impactantes con formato HTML. Solo usar etiquetas HTML permitidas por Telegram: b, i, u, blockquote. No usar etiquetas h1, h2, h3, etc."},
                {"role": "user", "content": prompts[theme]}
            ],
            temperature=0.7,
            max_tokens=200
        )
        content = response.choices[0].message.content
        
        # Limpiar y validar el HTML
        content = clean_html(content)
        
        return content
    except Exception as e:
        logger.error(f"Error al generar contenido: {e}")
        return f"<b>¡Inspiración diaria!</b>\n\n{CHANNELS[theme]['emoji']} No pudimos generar contenido personalizado esta vez, ¡pero seguimos adelante con energía positiva! {CHANNELS[theme]['emoji']}\n\n<blockquote>La constancia es la clave del éxito.</blockquote>"

# Función para publicar en un canal
async def post_to_channel(context, channel_name, content=None, use_image=None):
    channel_id = CHANNELS[channel_name]["id"]
    emoji = CHANNELS[channel_name]["emoji"]
    
    # Si use_image no se especifica, usar la configuración global
    if use_image is None:
        use_image = bot_state["use_images"]
    
    if content is None:
        content = await generate_content(channel_name)
    
    # Limpiar y validar el HTML
    content = clean_html(content)
    
    # Obtener URL de imagen si se requiere
    image_url = None
    if use_image:
        image_url = get_safe_image_url(channel_name)
    
    # Añadir firma sin espacios innecesarios
    current_date = datetime.now().strftime("%d/%m/%Y")
    signature = f"\n{emoji} <b>{channel_name}</b> | {current_date}"
    full_content = f"{content}{signature}"
    
    try:
        if use_image and image_url:
            # Verificar que la URL de la imagen es válida
            if is_valid_image_url(image_url):
                # Enviar mensaje con imagen
                message = await context.bot.send_photo(
                    chat_id=channel_id,
                    photo=image_url,
                    caption=full_content,
                    parse_mode='HTML'
                )
                bot_state["stats"]["with_images"] += 1
            else:
                # Si la URL de la imagen no es válida, enviar solo texto
                message = await context.bot.send_message(
                    chat_id=channel_id,
                    text=full_content,
                    parse_mode='HTML'
                )
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
            "has_image": use_image and image_url is not None
        }
        save_state()
        
        return True, message.message_id
    except Exception as e:
        logger.error(f"Error al publicar en {channel_name}: {e}")
        return False, str(e)

# Función para publicar en todos los canales
async def post_to_all_channels(context):
    results = {}
    
    # Pre-generar contenido para todos los canales para evitar repetición
    for channel in CHANNELS:
        bot_state["content_cache"][channel] = await generate_content(channel)
    save_state()
    
    for channel in CHANNELS:
        success, result = await post_to_channel(context, channel)
        results[channel] = "✅ Publicado" if success else f"❌ Error: {result}"
    
    # Limpiar caché si quedó algo
    bot_state["content_cache"] = {}
    save_state()
    
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

# Función para editar un mensaje de manera segura
async def safe_edit_message_text(query, text, reply_markup=None, parse_mode=None):
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except BadRequest as e:
        if "Message is not modified" in str(e):
            # Esto es normal, no es un error real
            logger.info("Mensaje no modificado, contenido idéntico")
        else:
            # Otros errores de BadRequest son importantes
            logger.error(f"Error al editar mensaje: {e}")
            # Intentar enviar un mensaje alternativo
            try:
                await query.edit_message_text(
                    text=f"{text}\n\n(Actualizado: {datetime.now().strftime('%H:%M:%S')})",
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            except Exception:
                pass  # Si esto también falla, simplemente continuamos
    except Exception as e:
        logger.error(f"Error inesperado al editar mensaje: {e}")

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
        await safe_edit_message_text(query, "⚠️ Solo el administrador puede usar esta función.")
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
        
        await safe_edit_message_text(
            query,
            "<b>🤖 Menú Principal</b>\n\nSelecciona una opción:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif callback_data == "publish_menu":
        keyboard = []
        # Botón para cada canal
        for channel in CHANNELS:
            keyboard.append([InlineKeyboardButton(f"{CHANNELS[channel]['emoji']} {channel}", callback_data=f"publish_select_{channel}")])
        
        # Botón para publicar en todos los canales
        keyboard.append([InlineKeyboardButton("🔄 Publicar en Todos", callback_data="publish_select_all")])
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_edit_message_text(
            query,
            "<b>📝 Publicar Contenido</b>\n\nSelecciona un canal para publicar:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif callback_data.startswith("publish_select_"):
        channel_or_all = callback_data.replace("publish_select_", "")
        
        # Mostrar opciones para incluir imagen o no
        keyboard = [
            [InlineKeyboardButton("📷 Con imagen", callback_data=f"publish_with_image_{channel_or_all}")],
            [InlineKeyboardButton("📝 Solo texto", callback_data=f"publish_without_image_{channel_or_all}")],
            [InlineKeyboardButton("🔙 Volver", callback_data="publish_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_edit_message_text(
            query,
            "<b>🔄 Opciones de publicación</b>\n\n¿Deseas incluir una imagen en esta publicación?",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif callback_data.startswith("publish_with_image_"):
        channel_or_all = callback_data.replace("publish_with_image_", "")
        
        if channel_or_all == "all":
            await safe_edit_message_text(query, "🔄 Publicando en todos los canales con imágenes... Esto puede tomar un momento.", parse_mode='HTML')
            # Pre-generar contenido para todos los canales para evitar repetición
            for channel in CHANNELS:
                bot_state["content_cache"][channel] = await generate_content(channel)
            save_state()
            
            results = {}
            for channel in CHANNELS:
                success, result = await post_to_channel(context, channel, use_image=True)
                results[channel] = "✅ Publicado" if success else f"❌ Error: {result}"
            
            # Limpiar caché si quedó algo
            bot_state["content_cache"] = {}
            save_state()
            
            # Notificar al administrador
            admin_message = "<b>Resumen de publicaciones automáticas:</b>\n\n"
            for channel, result in results.items():
                admin_message += f"<b>{channel}</b>: {result}\n"
            
            # Mensaje de confirmación con botón para volver
            keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await safe_edit_message_text(
                query,
                f"<b>✅ Publicación Completada</b>\n\n{admin_message}",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await safe_edit_message_text(query, f"🔄 Generando contenido para {channel_or_all} con imagen...", parse_mode='HTML')
            success, result = await post_to_channel(context, channel_or_all, use_image=True)
            
            # Mensaje de confirmación con botón para volver
            keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if success:
                await safe_edit_message_text(
                    query,
                    f"<b>✅ Publicación Exitosa</b>\n\nSe ha publicado contenido con imagen en el canal {channel_or_all}.",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            else:
                await safe_edit_message_text(
                    query,
                    f"<b>❌ Error al Publicar</b>\n\nNo se pudo publicar en {channel_or_all}.\nError: {result}",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
    
    elif callback_data.startswith("publish_without_image_"):
        channel_or_all = callback_data.replace("publish_without_image_", "")
        
        if channel_or_all == "all":
            await safe_edit_message_text(query, "🔄 Publicando en todos los canales sin imágenes... Esto puede tomar un momento.", parse_mode='HTML')
            # Pre-generar contenido para todos los canales para evitar repetición
            for channel in CHANNELS:
                bot_state["content_cache"][channel] = await generate_content(channel)
            save_state()
            
            results = {}
            for channel in CHANNELS:
                success, result = await post_to_channel(context, channel, use_image=False)
                results[channel] = "✅ Publicado" if success else f"❌ Error: {result}"
            
            # Limpiar caché si quedó algo
            bot_state["content_cache"] = {}
            save_state()
            
            # Notificar al administrador
            admin_message = "<b>Resumen de publicaciones automáticas:</b>\n\n"
            for channel, result in results.items():
                admin_message += f"<b>{channel}</b>: {result}\n"
            
            # Mensaje de confirmación con botón para volver
            keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await safe_edit_message_text(
                query,
                f"<b>✅ Publicación Completada</b>\n\n{admin_message}",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await safe_edit_message_text(query, f"🔄 Generando contenido para {channel_or_all} sin imagen...", parse_mode='HTML')
            success, result = await post_to_channel(context, channel_or_all, use_image=False)
            
            # Mensaje de confirmación con botón para volver
            keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if success:
                await safe_edit_message_text(
                    query,
                    f"<b>✅ Publicación Exitosa</b>\n\nSe ha publicado contenido sin imagen en el canal {channel_or_all}.",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            else:
                await safe_edit_message_text(
                    query,
                    f"<b>❌ Error al Publicar</b>\n\nNo se pudo publicar en {channel_or_all}.\nError: {result}",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
    
    elif callback_data == "settings_menu":
        auto_post_status = "✅ Activado" if bot_state["auto_post"] else "❌ Desactivado"
        post_time = bot_state["post_time"]
        frequency = bot_state["post_frequency"]
        use_images_status = "✅ Activado" if bot_state["use_images"] else "❌ Desactivado"
        
        keyboard = [
            [InlineKeyboardButton(f"🔄 Auto-publicación: {auto_post_status}", callback_data="toggle_auto_post")],
            [InlineKeyboardButton(f"📷 Usar imágenes: {use_images_status}", callback_data="toggle_use_images")],
            [InlineKeyboardButton(f"⏰ Hora de publicación: {post_time}", callback_data="set_post_time")],
            [InlineKeyboardButton(f"📅 Frecuencia: {frequency}", callback_data="set_frequency")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_edit_message_text(
            query,
            "<b>⚙️ Configuración</b>\n\nAjusta los parámetros del bot:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif callback_data == "toggle_auto_post":
        bot_state["auto_post"] = not bot_state["auto_post"]
        save_state()
        
        # Redireccionar al menú de configuración con un timestamp para evitar error de mensaje no modificado
        await safe_edit_message_text(
            query,
            f"<b>⚙️ Configuración actualizada</b>\n\nAuto-publicación: {'✅ Activada' if bot_state['auto_post'] else '❌ Desactivada'}\n\n<i>Volviendo al menú de configuración...</i>",
            parse_mode='HTML'
        )
        # Pequeña pausa para mostrar la confirmación
        await asyncio.sleep(1.5)
        # Redirigir
        callback_data = "settings_menu"
        await button_callback(update, context)
    
    elif callback_data == "toggle_use_images":
        bot_state["use_images"] = not bot_state["use_images"]
        save_state()
        
        # Redireccionar al menú de configuración con un timestamp para evitar error de mensaje no modificado
        await safe_edit_message_text(
            query,
            f"<b>⚙️ Configuración actualizada</b>\n\nUsar imágenes: {'✅ Activado' if bot_state['use_images'] else '❌ Desactivado'}\n\n<i>Volviendo al menú de configuración...</i>",
            parse_mode='HTML'
        )
        # Pequeña pausa para mostrar la confirmación
        await asyncio.sleep(1.5)
        # Redirigir
        callback_data = "settings_menu"
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
        
        await safe_edit_message_text(
            query,
            "<b>⏰ Configurar Hora de Publicación</b>\n\nSelecciona la hora para las publicaciones automáticas:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif callback_data.startswith("time_"):
        selected_time = callback_data.replace("time_", "")
        bot_state["post_time"] = selected_time
        save_state()
        
        await safe_edit_message_text(
            query,
            f"✅ Hora de publicación establecida a las {selected_time}.\n\n<i>Volviendo al menú de configuración...</i>",
            parse_mode='HTML'
        )
        # Pequeña pausa para mostrar la confirmación
        await asyncio.sleep(1.5)
        # Redirigir al menú de configuración
        callback_data = "settings_menu"
        await button_callback(update, context)
    
    elif callback_data == "set_frequency":
        keyboard = [
            [
                InlineKeyboardButton("📅 Diario", callback_data="freq_daily"),
                InlineKeyboardButton("📆 Semanal", callback_data="freq_weekly")
            ],
            [InlineKeyboardButton("🔙 Volver", callback_data="settings_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_edit_message_text(
            query,
            "<b>📅 Configurar Frecuencia</b>\n\nSelecciona con qué frecuencia se publicará el contenido:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif callback_data.startswith("freq_"):
        frequency = callback_data.replace("freq_", "")
        bot_state["post_frequency"] = frequency
        save_state()
        
        await safe_edit_message_text(
            query,
            f"✅ Frecuencia establecida a {frequency}.\n\n<i>Volviendo al menú de configuración...</i>",
            parse_mode='HTML'
        )
        # Pequeña pausa para mostrar la confirmación
        await asyncio.sleep(1.5)
        # Redirigir
        callback_data = "settings_menu"
        await button_callback(update, context)
    
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
        
        await safe_edit_message_text(
            query,
            stats_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif callback_data == "status":
        auto_post = "✅ Activado" if bot_state["auto_post"] else "❌ Desactivado"
        post_time = bot_state["post_time"]
        frequency = bot_state["post_frequency"]
        use_images = "✅ Activado" if bot_state["use_images"] else "❌ Desactivado"
        
        status_text = "<b>🔄 Estado Actual del Bot</b>\n\n"
        status_text += f"<b>Auto-publicación:</b> {auto_post}\n"
        status_text += f"<b>Usar imágenes:</b> {use_images}\n"
        status_text += f"<b>Hora de publicación:</b> {post_time}\n"
        status_text += f"<b>Frecuencia:</b> {frequency}\n\n"
        
        status_text += "<b>Canales configurados:</b>\n"
        for channel, data in CHANNELS.items():
            status_text += f"{data['emoji']} <b>{channel}</b>\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_edit_message_text(
            query,
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
            
            "<b>Temáticas disponibles:</b>\n"
            "💪 Conexión fitness\n"
            "💰 Criptomonedas\n"
            "🌱 Vitalidad al límite\n"
            "💎 Pensamientos de millonarios\n\n"
            
            "Para más información o soporte, contacta al administrador."
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_edit_message_text(
            query,
            help_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
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
        keyboard.append([InlineKeyboardButton(f"{CHANNELS[channel]['emoji']} {channel}", callback_data=f"publish_select_{channel}")])
    
    # Botón para publicar en todos los canales
    keyboard.append([InlineKeyboardButton("🔄 Publicar en Todos", callback_data="publish_select_all")])
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
    use_images_status = "✅ Activado" if bot_state["use_images"] else "❌ Desactivado"
    
    keyboard = [
        [InlineKeyboardButton(f"🔄 Auto-publicación: {auto_post_status}", callback_data="toggle_auto_post")],
        [InlineKeyboardButton(f"📷 Usar imágenes: {use_images_status}", callback_data="toggle_use_images")],
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
    use_images = "✅ Activado" if bot_state["use_images"] else "❌ Desactivado"
    
    status_text = "<b>🔄 Estado Actual del Bot</b>\n\n"
    status_text += f"<b>Auto-publicación:</b> {auto_post}\n"
    status_text += f"<b>Usar imágenes:</b> {use_images}\n"
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
