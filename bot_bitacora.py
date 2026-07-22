import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import requests
import json
from datetime import datetime, timedelta
import asyncio
import re

# ============================================
# CONFIGURACIÓN
# ============================================
TOKEN = '8950143739:AAHGT40j-l9prBUlcUTF0h1V9287CV4EPQU'
WEBHOOK_URL = 'https://script.google.com/macros/s/AKfycbx5SuiE6FXUL8a106IpIKzTa61lge-Ca0ji1216M-xT3NyHGa-AwyPqd5H5T6G0cAy9/exec'

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

logging.basicConfig(level=logging.INFO)

# ============================================
# FUNCIÓN PARA OBTENER DATOS DE LA HOJA
# ============================================
def obtener_datos_hoja():
    """Obtiene datos de la hoja para el dashboard"""
    try:
        url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:json"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return None
            
        # Parsear el JSON de Google
        texto = response.text
        json_str = texto[47:-2]  # Quitar prefijo y sufijo de Google
        data = json.loads(json_str)
        
        return data['table']['rows']
        
    except Exception as e:
        logging.error(f"Error obteniendo datos: {e}")
        return None

def procesar_datos_para_dashboard(rows):
    """Procesa los datos para el mini dashboard"""
    if not rows or len(rows) < 2:  # Si solo tiene headers
        return None
    
    # Saltar la primera fila (headers)
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
        
        # Extraer valores
        timestamp_str = cols[0].get('v', '') if len(cols) > 0 else ''
        categoria = cols[1].get('v', 'Sin Clasificar') if len(cols) > 1 else 'Sin Clasificar'
        mensaje = cols[3].get('v', '') if len(cols) > 3 else ''
        señalamiento = cols[7].get('v', False) if len(cols) > 7 else False
        
        # Contar señalamientos
        if señalamiento == True or señalamiento == 'TRUE':
            señalamientos += 1
        
        # Contar por categoría
        categorias[categoria] = categorias.get(categoria, 0) + 1
        
        # Contar última hora
        if timestamp_str:
            try:
                fecha = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                if fecha > hace_24h:
                    ultima_hora += 1
            except:
                pass
        
        # Guardar últimos 10 mensajes
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
# COMANDO: MINI DASHBOARD
# ============================================
async def mini_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra un resumen en Telegram"""
    mensaje_cargando = await update.message.reply_text("🔄 Cargando datos...")
    
    try:
        # Obtener datos de la hoja
        rows = obtener_datos_hoja()
        
        if not rows:
            await mensaje_cargando.edit_text(
                "❌ No se pudo obtener datos de la hoja.\n"
                "Verifica que el ID de la hoja sea correcto."
            )
            return
        
        stats = procesar_datos_para_dashboard(rows)
        
        if not stats or stats['total'] == 0:
            await mensaje_cargando.edit_text(
                "📊 *Dashboard - Bitácora*\n\n"
                "No hay registros aún.\n"
                "Envía un mensaje para comenzar.",
                parse_mode='Markdown'
            )
            return
        
        # Construir mensaje
        mensaje = "📊 *BITÁCORA - DASHBOARD RESUMEN*\n\n"
        mensaje += f"📝 *Total registros:* {stats['total']}\n"
        mensaje += f"⚠️ *Señalamientos:* {stats['señalamientos']}\n"
        mensaje += f"🕐 *Últimas 24h:* {stats['ultima_hora']}\n\n"
        
        mensaje += "*📂 Por categoría:*\n"
        # Ordenar categorías por cantidad (descendente)
        categorias_ordenadas = sorted(stats['categorias'].items(), key=lambda x: x[1], reverse=True)
        for cat, count in categorias_ordenadas:
            # Buscar emoji
            emoji = '📌'
            for c, e in CATEGORIAS:
                if c == cat:
                    emoji = e
                    break
            barra = '█' * min(count, 20)  # Barra visual
            mensaje += f"{emoji} {cat}: {count} {barra}\n"
        
        # Últimos mensajes
        if stats['ultimos_10']:
            mensaje += "\n*📨 Últimos mensajes:*\n"
            for i, msg in enumerate(stats['ultimos_10'][:5], 1):
                señal = '⚠️ ' if msg['señalamiento'] else ''
                mensaje += f"{i}. {señal}{msg['mensaje']}\n"
        
        mensaje += "\n📊 *Dashboard completo:* /dashboard"
        
        await mensaje_cargando.edit_text(mensaje, parse_mode='Markdown')
        
    except Exception as e:
        logging.error(f"Error en dashboard: {e}")
        await mensaje_cargando.edit_text(
            f"❌ Error cargando dashboard: {str(e)}"
        )

# ============================================
# COMANDO: DASHBOARD CON GRÁFICOS (ASCII)
# ============================================
async def dashboard_grafico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra dashboard con gráficos de barras ASCII"""
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
        
        # Encontrar el máximo para escala
        max_count = max(stats['categorias'].values()) if stats['categorias'] else 1
        escala = 20 / max_count if max_count > 0 else 1
        
        mensaje = "📊 *GRÁFICO DE CATEGORÍAS*\n"
        mensaje += "═" * 30 + "\n\n"
        
        # Ordenar por cantidad
        categorias_ordenadas = sorted(stats['categorias'].items(), key=lambda x: x[1], reverse=True)
        
        for cat, count in categorias_ordenadas:
            # Buscar emoji
            emoji = '📌'
            for c, e in CATEGORIAS:
                if c == cat:
                    emoji = e
                    break
            
            barras = '█' * int(count * escala)
            if count > 0 and int(count * escala) == 0:
                barras = '▏'  # Barra pequeña
            
            mensaje += f"{emoji} {cat[:15]:<15} | {barras} {count}\n"
        
        # Estadísticas adicionales
        mensaje += "\n" + "═" * 30 + "\n"
        mensaje += f"📝 Total: {stats['total']}  "
        mensaje += f"⚠️ Señales: {stats['señalamientos']}  "
        mensaje += f"🕐 24h: {stats['ultima_hora']}"
        
        await mensaje_cargando.edit_text(mensaje, parse_mode='Markdown')
        
    except Exception as e:
        await mensaje_cargando.edit_text(f"❌ Error: {e}")

# ============================================
# COMANDO: DASHBOARD COMPLETO (URL)
# ============================================
async def dashboard_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la URL del dashboard HTML"""
    # URL de tu dashboard (reemplazar con la tuya)
    url_dashboard = f"https://tu-usuario.github.io/bitacora/dashboard.html"
    # O si usas Google Sheets publicada
    url_sheets = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
    
    keyboard = [
        [
            InlineKeyboardButton("📊 Dashboard HTML", url=url_dashboard),
            InlineKeyboardButton("📝 Hoja de Cálculo", url=url_sheets)
        ],
        [
            InlineKeyboardButton("📈 Mini Dashboard", callback_data="mini_dashboard"),
            InlineKeyboardButton("📊 Gráficos", callback_data="graficos")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📊 *DASHBOARD BITÁCORA*\n\n"
        "Elige cómo quieres ver los datos:\n\n"
        "🔗 *Links externos:*\n"
        "• HTML Dashboard (interactivo)\n"
        "• Hoja de cálculo (editable)\n\n"
        "🤖 *En Telegram:*\n"
        "• Mini Dashboard (resumen)\n"
        "• Gráficos ASCII",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ============================================
# HANDLER PARA CALLBACKS DEL DASHBOARD
# ============================================
async def dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los botones del dashboard"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "mini_dashboard":
        # Simular comando /stats
        await mini_dashboard(update, context)
    elif query.data == "graficos":
        # Simular comando /graficos
        await dashboard_grafico(update, context)

# ============================================
# FUNCIONES PRINCIPALES DEL BOT
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = update.message.text
    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name
    
    # Crear teclado con categorías
    keyboard = []
    for categoria, emoji in CATEGORIAS:
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {categoria}", 
            callback_data=f"cat_{categoria}_{user_id}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        "⏭️ Sin Clasificar (guardar igual)",
        callback_data=f"cat_Sin Clasificar_{user_id}"
    )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Guardar mensaje temporalmente
    mensajes_pendientes[user_id] = {
        'texto': mensaje,
        'username': username,
        'timestamp': datetime.now(),
        'chat_id': update.message.chat_id
    }
    
    await update.message.reply_text(
        f"📨 *Mensaje recibido:*\n\n\"{mensaje}\"\n\n"
        "👇 *Elige la categoría:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Timeout de 5 minutos
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
    
    # Verificar si es callback del dashboard
    if data in ["mini_dashboard", "graficos"]:
        if data == "mini_dashboard":
            await mini_dashboard(update, context)
        else:
            await dashboard_grafico(update, context)
        return
    
    # Procesar selección de categoría
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
        resultado = await registrar_en_hoja(
            mensaje_data['texto'],
            mensaje_data['username'],
            categoria
        )
        
        if resultado:
            del mensajes_pendientes[user_id]
            
            job_name = f"timeout_{user_id}"
            current_jobs = context.job_queue.get_jobs_by_name(job_name)
            for job in current_jobs:
                job.schedule_removal()
            
            await query.edit_message_text(
                f"✅ *Registrado correctamente!*\n\n"
                f"📝 Mensaje: \"{mensaje_data['texto']}\"\n"
                f"📂 Categoría: {categoria}\n\n"
                f"📊 Usa /stats para ver el dashboard.",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ Error al registrar. Intenta nuevamente.")
            
    except Exception as e:
        logging.error(f"Error: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")

async def timeout_registro(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    user_id = job_data['user_id']
    chat_id = job_data['chat_id']
    
    mensaje_data = mensajes_pendientes.get(user_id)
    if mensaje_data:
        try:
            await registrar_en_hoja(
                mensaje_data['texto'],
                mensaje_data['username'],
                'Sin Clasificar'
            )
            
            del mensajes_pendientes[user_id]
            
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏰ *Tiempo agotado!*\n\n"
                     "El mensaje se registró automáticamente como 'Sin Clasificar'.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logging.error(f"Error en timeout: {e}")

async def registrar_en_hoja(mensaje, username, categoria):
    try:
        payload = {
            'message': {
                'text': mensaje,
                'from': {'username': username}
            },
            'categoria_manual': categoria
        }
        
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        return response.status_code == 200
        
    except Exception as e:
        logging.error(f"Error registrando: {e}")
        return False

# ============================================
# MAIN
# ============================================
def main():
    app = Application.builder().token(TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", mini_dashboard))
    app.add_handler(CommandHandler("graficos", dashboard_grafico))
    app.add_handler(CommandHandler("dashboard", dashboard_url))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    print("🤖 Bot v2 iniciado con dashboard integrado...")
    print("📊 Comandos disponibles: /stats /graficos /dashboard")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()