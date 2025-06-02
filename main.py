import os
import logging
import asyncio
import time
import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import BadRequest
from openai import OpenAI
import json
import aiohttp

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

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
        "posts_per_channel": {channel: 0 for channel in CHANNELS}
    },
    "content_history": {channel: [] for channel in CHANNELS}  # Historial de contenido por canal
}

def run_web_server():
    # Usar waitress como servidor WSGI
    serve(app, host='0.0.0.0', port=8080)

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
        if "content_history" not in bot_state:
            bot_state["content_history"] = {channel: [] for channel in CHANNELS}
            
    except FileNotFoundError:
        logger.info("Archivo de estado no encontrado, usando valores predeterminados")
        save_state()
    except Exception as e:
        logger.error(f"Error al cargar estado: {e}")

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

# Función para generar contenido único y diferente
async def generate_content(theme):
    # Obtener historial de contenido para este tema
    content_history = bot_state["content_history"].get(theme, [])
    
    # Limitar el historial a las últimas 5 publicaciones
    if len(content_history) > 5:
        content_history = content_history[-5:]
    
    # Emojis temáticos para cada categoría
    theme_emojis = {
        "Conexión fitness": ["💪", "🏋️‍♀️", "🏃‍♂️", "🧘‍♀️", "🥗", "🔥", "🏆", "⚡", "🚴‍♂️", "💯"],
        "Criptomonedas": ["💰", "📈", "🚀", "💹", "🔐", "💻", "🌐", "💎", "📊", "🤑"],
        "Vitalidad al límite": ["🌱", "✨", "🧠", "💚", "🌿", "🌞", "🧘", "🍃", "💆‍♀️", "🌈"],
        "Pensamientos de millonarios": ["💎", "💼", "🏆", "💡", "🔝", "👑", "💸", "🌟", "🎯", "💪"]
    }
    
    # Temas específicos para cada canal para asegurar variedad
    topic_options = {
        "Conexión fitness": [
            "entrenamiento de fuerza", "cardio", "nutrición deportiva", 
            "recuperación muscular", "yoga", "flexibilidad", "deporte al aire libre", 
            "entrenamiento en casa", "meditación deportiva", "hábitos saludables",
            "rutinas matutinas", "planificación de entrenamientos", "hidratación",
            "alimentación previa al ejercicio", "suplementos naturales", "running",
            "natación", "ciclismo", "crossfit", "pilates"
        ],
        "Criptomonedas": [
            "inversión a largo plazo", "trading diario", "análisis técnico", 
            "blockchain", "NFTs", "DeFi", "staking", "halving", "wallets", 
            "exchanges", "altcoins", "tokenomics", "minería", "seguridad",
            "regulación", "adopción masiva", "contratos inteligentes", "metaverso",
            "finanzas descentralizadas", "patrones de mercado"
        ],
        "Vitalidad al límite": [
            "alimentación consciente", "meditación", "descanso de calidad", 
            "suplementos naturales", "ayuno intermitente", "terapias alternativas", 
            "baños de bosque", "caminatas meditativas", "respiración consciente", "detox digital",
            "tés medicinales", "alimentación orgánica", "medicina natural", "equilibrio emocional",
            "descanso reparador", "terapia de sonido", "baños de sol", "contacto con la naturaleza",
            "ejercicio mindful", "rutinas de bienestar"
        ],
        "Pensamientos de millonarios": [
            "mentalidad de abundancia", "inversión", "educación continua", 
            "networking", "disciplina financiera", "emprendimiento", "liderazgo", 
            "gestión del tiempo", "hábitos de éxito", "inteligencia emocional",
            "libros recomendados", "mentalidad a largo plazo", "sistemas de productividad",
            "gestión del fracaso", "definición de objetivos", "creación de equipos",
            "delegación efectiva", "mentores", "visualización", "resiliencia"
        ]
    }
    
    # Escoger un tema específico que no se haya usado recientemente
    used_topics = [post.get("topic", "") for post in content_history]
    available_topics = [topic for topic in topic_options[theme] if topic not in used_topics]
    
    # Si todos los temas han sido usados, reiniciar
    if not available_topics:
        available_topics = topic_options[theme]
    
    selected_topic = random.choice(available_topics)
    
    # Asegurarnos de tener variedad en los formatos
    formats = ["consejos", "reflexión", "pregunta retórica", "cita inspiradora", "dato interesante", "desafío"]
    used_formats = [post.get("format", "") for post in content_history]
    available_formats = [fmt for fmt in formats if fmt not in used_formats[-3:]]  # Evitar repetir los últimos 3 formatos
    
    if not available_formats:
        available_formats = formats
    
    selected_format = random.choice(available_formats)
    
    # Crear un prompt específico y único
    prompt_base = f"""Crea una publicación corta y original sobre {theme} enfocada en {selected_topic}, usando el formato de {selected_format}.
    
    Requisitos:
    1. Máximo 3-4 oraciones en total (muy conciso)
    2. Incluye un título llamativo usando <b>negrita</b>
    3. Usa solo estas etiquetas HTML permitidas: <b>negrita</b>, <i>cursiva</i>, <u>subrayado</u> o <blockquote>cita</blockquote>
    4. Incluye al menos 5-6 de estos emojis donde sea apropiado: {"".join(theme_emojis[theme])}
    5. Una frase motivadora o consejo entre etiquetas <blockquote></blockquote>
    6. No excedas las 50-60 palabras en total
    7. IMPORTANTE: Asegúrate que esta publicación sea COMPLETAMENTE DIFERENTE en tema, tono y estructura a estas publicaciones anteriores:
    """
    
    # Añadir ejemplos de publicaciones anteriores para evitar repetición
    if content_history:
        for i, prev_post in enumerate(content_history[-3:]):  # Últimas 3 publicaciones
            if "content" in prev_post:
                prompt_base += f"\n\nPublicación anterior {i+1}:\n{prev_post['content']}"
    
    prompt_base += "\n\nCrea algo completamente nuevo y diferente a lo anterior. Usa un enfoque único, un ángulo distinto y un tono diferente."
    
    try:
        # Usar temperatura alta para mayor variedad
        response = client_ai.chat.completions.create(
            model="gemini-1.5-flash",
            messages=[
                {"role": "system", "content": "Eres un experto creador de contenido para redes sociales. Crea publicaciones atractivas, concisas y ÚNICAS. Nunca repitas ideas o conceptos. Cada publicación debe tener un ángulo completamente diferente. Solo usar etiquetas HTML permitidas por Telegram: b, i, u, blockquote."},
                {"role": "user", "content": prompt_base}
            ],
            temperature=0.9,  # Alta temperatura para más creatividad y variedad
            max_tokens=200
        )
        content = response.choices[0].message.content
        
        # Limpiar y validar el HTML
        content = clean_html(content)
        
        # Guardar en el historial
        bot_state["content_history"][theme].append({
            "content": content,
            "topic": selected_topic,
            "format": selected_format,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Limitar el tamaño del historial
        if len(bot_state["content_history"][theme]) > 10:
            bot_state["content_history"][theme] = bot_state["content_history"][theme][-10:]
        
        save_state()
        
        return content
    except Exception as e:
        logger.error(f"Error al generar contenido: {e}")
        # Generar contenido de emergencia único
        emergency_content = f"<b>¡{random.choice(['Inspiración', 'Ideas', 'Reflexión', 'Motivación', 'Sabiduría'])} del día!</b>\n\n"
        emergency_content += f"{CHANNELS[theme]['emoji']} {random.choice(['Cada día es una nueva oportunidad', 'El éxito comienza hoy', 'La constancia es clave', 'Pequeños pasos, grandes logros', 'La disciplina vence al talento'])}"
        emergency_content += f" {random.choice(theme_emojis[theme])} {random.choice(['¡Mantente enfocado!', '¡Sigue adelante!', '¡No te rindas!', '¡Tú puedes!', '¡Confía en el proceso!'])}\n\n"
        emergency_content += f"<blockquote>{random.choice(['La constancia es la clave del éxito.', 'Cada día cuenta en tu camino.', 'Las metas se logran paso a paso.', 'La disciplina te llevará lejos.', 'El éxito es la suma de pequeños esfuerzos.'])}</blockquote>"
        
        # También guardamos este contenido en el historial
        bot_state["content_history"][theme].append({
            "content": emergency_content,
            "topic": "contenido de emergencia",
            "format": "motivacional",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        save_state()
        
        return emergency_content

# Función para publicar en un canal
async def post_to_channel(context, channel_name, content=None):
    channel_id = CHANNELS[channel_name]["id"]
    emoji = CHANNELS[channel_name]["emoji"]
    
    if content is None:
        content = await generate_content(channel_name)
    
    # Limpiar y validar el HTML
    content = clean_html(content)
    
    # Añadir firma sin espacios innecesarios
    current_date = datetime.now().strftime("%d/%m/%Y")
    signature = f"\n{emoji} <b>{channel_name}</b> | {current_date}"
    full_content = f"{content}{signature}"
    
    try:
        # Enviar mensaje de texto
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
    
    # Generar y publicar para cada canal
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
            keyboard.append([InlineKeyboardButton(f"{CHANNELS[channel]['emoji']} {channel}", callback_data=f"publish_{channel}")])
        
        # Botón para publicar en todos los canales
        keyboard.append([InlineKeyboardButton("🔄 Publicar en Todos", callback_data="publish_all")])
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_edit_message_text(
            query,
            "<b>📝 Publicar Contenido</b>\n\nSelecciona un canal para publicar:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif callback_data.startswith("publish_"):
        channel_or_all = callback_data.replace("publish_", "")
        
        if channel_or_all == "all":
            await safe_edit_message_text(query, "🔄 Publicando en todos los canales... Esto puede tomar un momento.", parse_mode='HTML')
            
            results = {}
            for channel in CHANNELS:
                success, result = await post_to_channel(context, channel)
                results[channel] = "✅ Publicado" if success else f"❌ Error: {result}"
            
            # Notificar resultados
            admin_message = "<b>Resumen de publicaciones:</b>\n\n"
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
            await safe_edit_message_text(query, f"🔄 Generando contenido único para {channel_or_all}...", parse_mode='HTML')
            success, result = await post_to_channel(context, channel_or_all)
            
            # Mensaje de confirmación con botón para volver
            keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if success:
                await safe_edit_message_text(
                    query,
                    f"<b>✅ Publicación Exitosa</b>\n\nSe ha publicado contenido único en el canal {channel_or_all}.",
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
        
        keyboard = [
            [InlineKeyboardButton(f"🔄 Auto-publicación: {auto_post_status}", callback_data="toggle_auto_post")],
            [InlineKeyboardButton(f"⏰ Hora de publicación: {post_time}", callback_data="set_post_time")],
            [InlineKeyboardButton(f"📅 Frecuencia: {frequency}", callback_data="set_frequency")],
            [InlineKeyboardButton("🗑️ Borrar historial de contenido", callback_data="clear_history")],
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
    
    elif callback_data == "clear_history":
        # Borrar historial de contenido
        bot_state["content_history"] = {channel: [] for channel in CHANNELS}
        save_state()
        
        await safe_edit_message_text(
            query,
            "<b>✅ Historial limpio</b>\n\nSe ha borrado el historial de contenido para todos los canales. Las próximas publicaciones serán completamente nuevas.\n\n<i>Volviendo al menú de configuración...</i>",
            parse_mode='HTML'
        )
        # Pequeña pausa para mostrar la confirmación
        await asyncio.sleep(2)
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
        
        stats_text = "<b>📊 Estadísticas de Publicaciones</b>\n\n"
        stats_text += f"<b>Total de publicaciones:</b> {total_posts}\n\n"
        stats_text += "<b>Publicaciones por canal:</b>\n"
        
        for channel, count in posts_per_channel.items():
            emoji = CHANNELS[channel]["emoji"]
            stats_text += f"{emoji} <b>{channel}:</b> {count}\n"
        
        # Añadir información sobre variedad de contenido
        stats_text += "\n<b>Historial de contenido guardado:</b>\n"
        for channel, history in bot_state["content_history"].items():
            stats_text += f"{CHANNELS[channel]['emoji']} <b>{channel}:</b> {len(history)} publicaciones\n"
        
        # Añadir última publicación si existe
        if bot_state["last_posts"]:
            stats_text += "\n<b>Últimas publicaciones:</b>\n"
            for channel, data in bot_state["last_posts"].items():
                if "timestamp" in data:
                    stats_text += f"{CHANNELS[channel]['emoji']} <b>{channel}:</b> {data['timestamp']}\n"
        
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
        
        status_text = "<b>🔄 Estado Actual del Bot</b>\n\n"
        status_text += f"<b>Auto-publicación:</b> {auto_post}\n"
        status_text += f"<b>Hora de publicación:</b> {post_time}\n"
        status_text += f"<b>Frecuencia:</b> {frequency}\n\n"
        
        status_text += "<b>Canales configurados:</b>\n"
        for channel, data in CHANNELS.items():
            status_text += f"{data['emoji']} <b>{channel}</b>\n"
            
        # Añadir información sobre el último contenido generado
        status_text += "\n<b>Último contenido generado:</b>\n"
        for channel, history in bot_state["content_history"].items():
            if history:
                last_topic = history[-1].get("topic", "N/A")
                last_format = history[-1].get("format", "N/A")
                status_text += f"{CHANNELS[channel]['emoji']} <b>{channel}:</b> {last_topic} ({last_format})\n"
            else:
                status_text += f"{CHANNELS[channel]['emoji']} <b>{channel}:</b> Sin contenido reciente\n"
        
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
            "• Contenido único y no repetitivo\n"
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
        [InlineKeyboardButton("🗑️ Borrar historial de contenido", callback_data="clear_history")],
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
        
    # Añadir información sobre el último contenido generado
    status_text += "\n<b>Último contenido generado:</b>\n"
    for channel, history in bot_state["content_history"].items():
        if history:
            last_topic = history[-1].get("topic", "N/A")
            last_format = history[-1].get("format", "N/A")
            status_text += f"{CHANNELS[channel]['emoji']} <b>{channel}:</b> {last_topic} ({last_format})\n"
        else:
            status_text += f"{CHANNELS[channel]['emoji']} <b>{channel}:</b> Sin contenido reciente\n"
    
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
        "• Contenido único y no repetitivo\n"
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
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Hacer un ping a tu aplicación en Render
                app_url = "https://tu-app.onrender.com"  # Reemplaza con tu URL de Render
                async with session.get(app_url) as response:
                    logger.info(f"Keep-alive ping enviado. Status: {response.status}")
                
                # Verificar si es hora de publicación
                current_hour = datetime.now().hour
                current_minute = datetime.now().minute
                post_hour, post_minute = map(int, bot_state["post_time"].split(":"))
                
                if current_hour == post_hour and current_minute == post_minute and bot_state["auto_post"]:
                    logger.info("Ejecutando publicación programada")
                    await post_to_all_channels(context)
                
                # Esperar 10 minutos antes del siguiente ping
                await asyncio.sleep(600)  # 600 segundos = 10 minutos
                
            except Exception as e:
                logger.error(f"Error en keep_alive: {e}")
                # En caso de error, esperar 1 minuto y reintentar
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
    
    # Iniciar el servidor web en un hilo separado
    web_thread = threading.Thread(target=run_web_server)
    web_thread.start()
    
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
