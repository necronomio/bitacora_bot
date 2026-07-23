import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import requests
import json
from datetime import datetime, timedelta
import os
import sys

# ============================================
# CONFIGURACIÓN
# ============================================
TOKEN = os.environ.get('TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')

if not TOKEN:
    print("❌ ERROR: TOKEN no configurado")
    sys.exit(1)
if not WEBHOOK_URL:
    print("❌ ERROR: WEBHOOK_URL no configurado")
    sys.exit(1)
if not SPREADSHEET_ID:
    print("❌ ERROR: SPREADSHEET_ID no configurado")
    sys.exit(1)

# Categorías
CATEGORIAS = [
    ('Operaciones', '🔫'),
    ('Reunion de Informacion', '📋'),
    ('Contrainteligencia', '🕵️'),
    ('Personal/administracion', '👤'),
    ('Analisis Criminal', '🔍'),
    ('DDIC Moron', '🏛️'),
    ('Informacion General', '📢')
]

# Diccionario para mensajes pendientes
mensajes_pendientes = {}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# FUNCIONES DEL DASHBOARD
# ============================================
def obtener_datos_hoja():
    try:
        url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:json"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None
        texto = response.text
        if texto.startswith('/*O_o*/'):
            texto = texto[7:]
        if texto.startswith('google.visualization.Query.setResponse('):
            texto = texto[40:-2]
        data = json.loads(texto)
        return data['table']['rows']
    except Exception as e:
        logger.error(f"Error obteniendo datos: {e}")
        return None

def procesar_datos_para_dashboard(rows):
    if not rows or len(rows) < 2:
        return None
    datos = rows[1:]
    total = len(datos)
    señalamientos = 0
    categorias = {}
    ultima_hora = 0
    ultimos_10 = []
    ahora = datetime.now()
    hace_24h = ahora - timedelta(hours=24)
    
    for row in datos:
        cols = row.get('c', [])
        timestamp_str = cols[0].get('v', '') if len(cols) > 0 else ''
        categoria = cols[1].get('v', 'Sin Clasificar') if len(cols) > 1 else 'Sin Clasificar'
        mensaje = cols[3].get('v', '') if len(cols) > 3 else ''
        señalamiento = cols[7].get('v', False) if len(cols) > 7 else False
        
        if señalamiento == True or señalamiento == 'TRUE':
            señalamientos += 1
        categorias[categoria] = categorias.get(categoria, 0) + 1
        
        if timestamp_str:
            try:
                fecha = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                if fecha > hace_24h:
                    ultima_hora += 1
            except:
                pass
        
        if len(ultimos_10) < 10:
            ultimos_10.append({
                'mensaje': mensaje[:50] + '...' if len(mensaje) > 50 else mensaje,
                'categoria': categoria,
                'señalamiento': señalamiento
            })
    
    return {
        'total': total,
        'señalamientos': señalamientos,
        'categorias': categorias,
        'ultima_hora': ultima_hora,
        'ultimos_10': ultimos_10
    }

# ============================================
# COMANDOS DEL BOT
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bitácora Bot v2*\n\n"
        "📝 *Cómo funciona:*\n"
        "1. Envía un mensaje\n"
        "2. Elige la categoría en el menú\n"
        "3. Se guardará automáticamente\n\n"
        "⌛ Si no eliges en 5 min, se guarda como 'Sin Clasificar'\n\n"
        "📊 *Comandos:*\n"
        "/stats - Mini dashboard\n"
        "/graficos - Gráficos ASCII\n"
        "/dashboard - Dashboard completo",
        parse_mode='Markdown'
    )

async def mini_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje_cargando = await update.message.reply_text("🔄 Cargando datos...")
    try:
        rows = obtener_datos_hoja()
        if not rows:
            await mensaje_cargando.edit_text("❌ No se pudo obtener datos.")
            return
        stats = procesar_datos_para_dashboard(rows)
        if not stats or stats['total'] == 0:
            await mensaje_cargando.edit_text("📊 No hay registros aún.")
            return
        
        mensaje = "📊 *BITÁCORA - DASHBOARD RESUMEN*\n"
        mensaje += "═" * 30 + "\n\n"
        mensaje += f"📝 *Total registros:* {stats['total']}\n"
        mensaje += f"⚠️ *Señalamientos:* {stats['señalamientos']}\n"
        mensaje += f"🕐 *Últimas 24h:* {stats['ultima_hora']}\n\n"
        mensaje += "*📂 Por categoría:*\n"
        
        categorias_ordenadas = sorted(stats['categorias'].items(), key=lambda x: x[1], reverse=True)
        for cat, count in categorias_ordenadas:
            emoji = '📌'
            for c, e in CATEGORIAS:
                if c == cat:
                    emoji = e
                    break
            porcentaje = int((count / stats['total']) * 100)
            mensaje += f"{emoji} {cat}: {count} ({porcentaje}%)\n"
        
        if stats['ultimos_10']:
            mensaje += "\n*📨 Últimos mensajes:*\n"
            for i, msg in enumerate(stats['ultimos_10'][:5], 1):
                señal = '⚠️ ' if msg['señalamiento'] else ''
                mensaje += f"{i}. {señal}{msg['mensaje']}\n"
        
        mensaje += "\n📊 *Dashboard completo:* /dashboard"
        await mensaje_cargando.edit_text(mensaje, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error: {e}")
        await mensaje_cargando.edit_text(f"❌ Error: {str(e)}")

async def dashboard_grafico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje_cargando = await update.message.reply_text("🔄 Generando gráficos...")
    try:
        rows = obtener_datos_hoja()
        if not rows:
            await mensaje_cargando.edit_text("❌ Error obteniendo datos")
            return
        stats = procesar_datos_para_dashboard(rows)
        if not stats or stats['total'] == 0:
            await mensaje_cargando.edit_text("📊 No hay registros aún.")
            return
        
        max_count = max(stats['categorias'].values()) if stats['categorias'] else 1
        escala = 20 / max_count if max_count > 0 else 1
        
        mensaje = "📊 *GRÁFICO DE CATEGORÍAS*\n"
        mensaje += "═" * 30 + "\n\n"
        
        categorias_ordenadas = sorted(stats['categorias'].items(), key=lambda x: x[1], reverse=True)
        for cat, count in categorias_ordenadas:
            emoji = '📌'
            for c, e in CATEGORIAS:
                if c == cat:
                    emoji = e
                    break
            barras = '█' * int(count * escala)
            if count > 0 and int(count * escala) == 0:
                barras = '▏'
            mensaje += f"{emoji} {cat[:15]:<15} | {barras} {count}\n"
        
        mensaje += "\n" + "═" * 30 + "\n"
        mensaje += f"📝 Total: {stats['total']}  "
        mensaje += f"⚠️ Señales: {stats['señalamientos']}  "
        mensaje += f"🕐 24h: {stats['ultima_hora']}"
        
        await mensaje_cargando.edit_text(mensaje, parse_mode='Markdown')
    except Exception as e:
        await mensaje_cargando.edit_text(f"❌ Error: {e}")

async def dashboard_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url_sheets = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
    keyboard = [
        [InlineKeyboardButton("📝 Hoja de Cálculo", url=url_sheets)],
        [InlineKeyboardButton("📈 Mini Dashboard", callback_data="mini_dashboard")],
        [InlineKeyboardButton("📊 Gráficos", callback_data="graficos")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📊 *DASHBOARD BITÁCORA*\n\nElige cómo ver los datos:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ============================================
# MANEJO DE MENSAJES
# ============================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = update.message.text
    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name
    
    keyboard = []
    for categoria, emoji in CATEGORIAS:
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {categoria}", 
            callback_data=f"cat_{categoria}_{user_id}"
        )])
    keyboard.append([InlineKeyboardButton(
        "⏭️ Sin Clasificar",
        callback_data=f"cat_Sin Clasificar_{user_id}"
    )])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    mensajes_pendientes[user_id] = {
        'texto': mensaje,
        'username': username,
        'timestamp': datetime.now(),
        'chat_id': update.message.chat_id
    }
    
    await update.message.reply_text(
        f"📨 *Mensaje:*\n\"{mensaje}\"\n\n👇 *Elige categoría:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    context.job_queue.run_once(
        timeout_registro,
        300,
        data={'user_id': user_id, 'chat_id': update.message.chat_id},
        name=f"timeout_{user_id}"
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data in ["mini_dashboard", "graficos"]:
        if data == "mini_dashboard":
            await mini_dashboard(update, context)
        else:
            await dashboard_grafico(update, context)
        return
    
    parts = data.split('_')
    if len(parts) < 3:
        await query.edit_message_text("Error en la selección.")
        return
    
    categoria = parts[1]
    user_id = int(parts[2])
    
    if user_id != query.from_user.id:
        await query.edit_message_text("⛔ No puedes clasificar este mensaje.")
        return
    
    mensaje_data = mensajes_pendientes.get(user_id)
    if not mensaje_data:
        await query.edit_message_text("⏰ El mensaje ya fue procesado.")
        return
    
    try:
        payload = {
            'message': {
                'text': mensaje_data['texto'],
                'from': {'username': mensaje_data['username']}
            },
            'categoria_manual': categoria
        }
        response = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        
        if response.status_code == 200:
            if user_id in mensajes_pendientes:
                del mensajes_pendientes[user_id]
            if context.job_queue:
                job_name = f"timeout_{user_id}"
                for job in context.job_queue.get_jobs_by_name(job_name):
                    job.schedule_removal()
            await query.edit_message_text(
                f"✅ *Registrado!*\n📂 {categoria}",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ Error al registrar.")
    except Exception as e:
        logger.error(f"Error: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")

async def timeout_registro(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    user_id = job_data['user_id']
    chat_id = job_data['chat_id']
    
    mensaje_data = mensajes_pendientes.get(user_id)
    if mensaje_data:
        try:
            payload = {
                'message': {
                    'text': mensaje_data['texto'],
                    'from': {'username': mensaje_data['username']}
                },
                'categoria_manual': 'Sin Clasificar'
            }
            requests.post(WEBHOOK_URL, json=payload, timeout=10)
            if user_id in mensajes_pendientes:
                del mensajes_pendientes[user_id]
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏰ Tiempo agotado. Registrado como 'Sin Clasificar'."
            )
        except Exception as e:
            logger.error(f"Error en timeout: {e}")

# ============================================
# MAIN
# ============================================
def main():
    try:
        app = Application.builder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("stats", mini_dashboard))
        app.add_handler(CommandHandler("graficos", dashboard_grafico))
        app.add_handler(CommandHandler("dashboard", dashboard_url))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(CallbackQueryHandler(handle_callback))
        
        logger.info("🤖 Bitácora Bot iniciado correctamente")
        logger.info("📊 Comandos: /stats /graficos /dashboard")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Error: {e}")
        raise

if __name__ == '__main__':
    main()
