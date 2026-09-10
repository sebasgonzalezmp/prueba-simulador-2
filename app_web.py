import json
import os
import random
import io
from datetime import datetime
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from google import genai

# ==========================================
# CONFIGURACIÓN DE PÁGINA Y OCULTAMIENTO DE UI (DEVELOPER TOOLBAR & MANAGE APP)
# ==========================================
st.set_page_config(
    page_title="Plataforma BPO Multichat",
    page_icon="🌐",
    layout="wide"
)

# Estilos CSS para ocultar el botón 'Manage App', barra de herramientas superior, marcas y menús de Streamlit
ocultar_elementos_ui = """
    <style>
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    header {visibility: hidden !important;}
    .stAppToolbar {display: none !important;}
    [data-testid="stAppToolbar"] {display: none !important;}
    [data-testid="stHeader"] {display: none !important;}
    button[title="Edit with Streamlit"] {display: none !important;}
    button[title="View app source"] {display: none !important;}
    div[data-testid="stDecoration"] {display: none !important;}
    .stDeployButton {display: none !important;}
    </style>
"""
st.markdown(ocultar_elementos_ui, unsafe_allow_html=True)

# ==========================================
# ARCHIVOS DE PERSISTENCIA Y BASE DE DATOS
# ==========================================
ARCHIVO_HISTORIAL = "historial.json"
ARCHIVO_USUARIOS = "usuarios.json"

USUARIOS_INICIALES = {
    "sebastián": {"clave": "1234", "rol": "Supervisor", "nombre": "Sebastián"},
    "agente1": {"clave": "demo123", "rol": "Agente", "nombre": "Agente Demo 1"},
    "agente2": {"clave": "demo123", "rol": "Agente", "nombre": "Agente Demo 2"}
}

def cargar_usuarios():
    if os.path.exists(ARCHIVO_USUARIOS):
        try:
            with open(ARCHIVO_USUARIOS, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:
            return USUARIOS_INICIALES
    return USUARIOS_INICIALES

def guardar_usuarios(usuarios):
    with open(ARCHIVO_USUARIOS, "w", encoding="utf-8") as file:
        json.dump(usuarios, file, indent=4, ensure_ascii=False)

def cargar_historial():
    if os.path.exists(ARCHIVO_HISTORIAL):
        try:
            with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as archivo:
                return json.load(archivo)
        except Exception:
            return []
    return []

def guardar_registro(registro):
    historial = cargar_historial()
    historial.append(registro)
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as archivo:
        json.dump(historial, archivo, indent=4, ensure_ascii=False)

ESCENARIOS_PARTNER = {
    "Orden Demorada": "El rider asignado lleva 40 minutos de retraso y la comida del partner se está enfriando.",
    "Falta de Producto / Stock": "El partner aceptó la orden pero no tiene un insumo clave para la preparación.",
    "Cobro Incorrecto": "El partner afirma que en la última liquidación le descontaron una comisión errónea.",
    "Local Cerrado": "El partner requiere apagar la app de inmediato por una emergencia en cocina."
}

OPCIONES_ESCENARIOS = [
    "Orden Demorada", "Orden Demorada", "Orden Demorada",
    "Falta de Producto / Stock", "Cobro Incorrecto", "Local Cerrado"
]

def obtener_respuesta_dinamica_respaldo(mensaje_agente, ultimo_mensaje):
    msg_low = mensaje_agente.lower()
    
    if any(k in msg_low for k in ["orden", "numero", "número", "id", "código", "codigo"]):
        respuestas = [
            f"El número de orden es #{random.randint(10000, 99999)}. Por favor revisa rápido.",
            f"Es la orden #{random.randint(10000, 99999)}, lleva demasiado tiempo esperando.",
            f"Aparece con el ID #{random.randint(10000, 99999)} en mi pantalla. ¿Qué solución me das?"
        ]
    elif any(k in msg_low for k in ["hola", "buenos dias", "buenas tardes", "gusto", "ayudo"]):
        respuestas = [
            "Hola. Necesito que me ayudes urgentemente, tengo el local colapsado.",
            "Buenas. Por favor verifica de inmediato la situación, no puedo perder más dinero.",
            "Hola, necesito solución concreta ya. ¿Me puedes colaborar?"
        ]
    else:
        respuestas = [
            "Sigo esperando una solución real a mi caso. ¿Me vas a ayudar sí o no?",
            "Por favor verifica bien en la consola BPO, no me hagas perder más tiempo.",
            "Esa respuesta no me resuelve nada. Necesito escalarlo o que me des tiempo estimado.",
            "Por favor sea profesional. Requiero que resuelvan la incidencia ahora mismo."
        ]
    
    opciones_validas = [r for r in respuestas if r != ultimo_mensaje]
    if not opciones_validas:
        opciones_validas = respuestas
    return random.choice(opciones_validas)

def emitir_alerta_sonora():
    js_sound = """
    <script>
    var ctx = new (window.AudioContext || window.webkitAudioContext)();
    var osc = ctx.createOscillator();
    var gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(587.33, ctx.currentTime);
    gain.gain.setValueAtTime(0.05, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.00001, ctx.currentTime + 0.5);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.5);
    </script>
    """
    components.html(js_sound, height=0, width=0)

def generar_csv_bytes(df_data):
    return df_data.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')

def generar_nuevo_chat(id_chat):
    escenario = random.choice(OPCIONES_ESCENARIOS)
    return {
        "id": id_chat,
        "escenario": escenario,
        "mensajes": [{"role": "assistant", "content": f"¡Hola! Hablas con el Restaurante. {ESCENARIOS_PARTNER[escenario]}"}],
        "inicio": datetime.now(),
        "ultimo_msg_partner": datetime.now(),
        "activo": True
    }

# ==========================================
# PANTALLA DE ACCESO (LOGIN / REGISTRO / RECUPERACIÓN)
# ==========================================
if "usuario_autenticado" not in st.session_state:
    st.session_state.usuario_autenticado = None

if not st.session_state.usuario_autenticado:
    st.title("🌐 Portal de Acceso - Plataforma BPO")
    
    tab_login, tab_registro, tab_recovery = st.tabs(["🔑 Iniciar Sesión", "📝 Crear Cuenta", "❓ Recuperar Contraseña"])
    usuarios_db = cargar_usuarios()
    
    with tab_login:
        col_l, _ = st.columns([1, 1])
        with col_l:
            usr = st.text_input("Usuario:", key="login_user").strip().lower()
            pwd = st.text_input("Contraseña:", type="password", key="login_pass")
            
            if st.button("Iniciar Sesión", type="primary", use_container_width=True):
                if usr in usuarios_db and usuarios_db[usr]["clave"] == pwd:
                    st.session_state.usuario_autenticado = usuarios_db[usr]
                    st.success(f"¡Bienvenido, {usuarios_db[usr]['nombre']}!")
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")

    with tab_registro:
        col_r, _ = st.columns([1, 1])
        with col_r:
            new_name = st.text_input("Nombre Completo:")
            new_user = st.text_input("Usuario deseado:").strip().lower()
            new_pass = st.text_input("Contraseña:", type="password", key="reg_pass")
            rol_sel = st.selectbox("Rol en la Plataforma:", options=["Agente", "Supervisor"])
            
            if st.button("Registrar Usuario", type="primary", use_container_width=True):
                if not new_name or not new_user or not new_pass:
                    st.warning("Por favor completa todos los campos.")
                elif new_user in usuarios_db:
                    st.error("El nombre de usuario ya existe. Elige otro.")
                else:
                    usuarios_db[new_user] = {"clave": new_pass, "rol": rol_sel, "nombre": new_name}
                    guardar_usuarios(usuarios_db)
                    st.success("¡Cuenta creada exitosamente! Ahora puedes Iniciar Sesión.")

    with tab_recovery:
        col_rec, _ = st.columns([1, 1])
        with col_rec:
            rec_user = st.text_input("Ingresa tu usuario:", key="rec_user").strip().lower()
            rec_pass = st.text_input("Nueva contraseña:", type="password", key="rec_pass")
            
            if st.button("Actualizar Contraseña", use_container_width=True):
                if rec_user in usuarios_db:
                    usuarios_db[rec_user]["clave"] = rec_pass
                    guardar_usuarios(usuarios_db)
                    st.success("Contraseña restablecida. Procede a Iniciar Sesión.")
                else:
                    st.error("El usuario ingresado no existe.")
    st.stop()

# ==========================================
# BARRA LATERAL Y OBTENCIÓN SEGURA DE API KEY INVISIBLE
# ==========================================
user = st.session_state.usuario_autenticado

st.sidebar.title(f"👤 {user['nombre']}")
st.sidebar.caption(f"Rol: **{user['rol']}**")

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.usuario_autenticado = None
    if "simulacion_activa" in st.session_state:
        del st.session_state.simulacion_activa
    st.rerun()

st.sidebar.markdown("---")

# Obtención completamente segura e invisible de la API Key desde Secrets / Envs
api_key_global = ""
try:
    if "GOOGLE_AI_API_KEY" in st.secrets:
        api_key_global = st.secrets["GOOGLE_AI_API_KEY"]
except Exception:
    api_key_global = os.environ.get("GOOGLE_AI_API_KEY", "")

if user["rol"] == "Supervisor":
    opciones_menu = ["🛠️ Herramienta Operativa (Multichat)", "📊 Panel Supervisor Global"]
else:
    opciones_menu = ["🛠️ Herramienta Operativa (Multichat)", "📋 Mis Resultados QA"]

menu_principal = st.sidebar.radio("Navegación:", options=opciones_menu)

# ==========================================
# SECCIÓN 1: HERRAMIENTA OPERATIVA
# ==========================================
if menu_principal == "🛠️ Herramienta Operativa (Multichat)":
    st.title("🌐 Plataforma de Gestión BPO")
    modo = st.radio("Interruptor de Modo:", options=["🧠 ENTRENAMIENTO MULTICHAT", "🤝 APOYO EN VIVO"], horizontal=True)
    st.markdown("---")

    if modo == "🧠 ENTRENAMIENTO MULTICHAT":
        st.header("🧠 Simulación Multitarea BPO")
        
        if "simulacion_activa" not in st.session_state:
            st.session_state.simulacion_activa = False

        if not st.session_state.simulacion_activa:
            st.info("⚙️ **Configura tu sesión de práctica antes de empezar:**")
            
            col_conf1, col_conf2 = st.columns([1, 2])
            with col_conf1:
                cant_chats = st.slider("Número de chats en paralelo:", min_value=1, max_value=3, value=2)
            
            with col_conf2:
                st.write("")
                st.write("")
                if st.button("▶️ Iniciar Simulador Multichat", type="primary", use_container_width=True):
                    st.session_state.simulacion_activa = True
                    st.session_state.chats = [generar_nuevo_chat(i + 1) for i in range(cant_chats)]
                    st.session_state.contador_total = cant_chats
                    st.rerun()

        else:
            col_header1, col_header2 = st.columns([3, 1])
            with col_header1:
                st.caption("Práctica en curso. Maneja los tiempos de respuesta para evitar alertas de SLA.")
            with col_header2:
                if st.button("⏹️ Detener Simulación", type="secondary"):
                    st.session_state.simulacion_activa = False
                    st.session_state.chats = []
                    st.rerun()

            chats_activos = st.session_state.chats
            
            if chats_activos:
                nombres_tabs = [f"💬 Chat {c['id']} - {c['escenario']}" for c in chats_activos]
                tabs = st.tabs(nombres_tabs)

                for index, chat_data in enumerate(chats_activos):
                    with tabs[index]:
                        ahora = datetime.now()
                        tiempo_tmr_sec = (ahora - chat_data["ultimo_msg_partner"]).total_seconds()
                        tiempo_att_min = (ahora - chat_data["inicio"]).total_seconds() / 60

                        col_m1, col_m2 = st.columns(2)
                        
                        if tiempo_tmr_sec > 60:
                            col_m1.error(f"🚨 **ALERTA TMR Excedido:** {int(tiempo_tmr_sec)}s sin responder (> 60s)")
                            emitir_alerta_sonora()
                        else:
                            col_m1.success(f"⏱️ **TMR Actual:** {int(tiempo_tmr_sec)}s / 60s max")

                        if tiempo_att_min > 5.0:
                            col_m2.error(f"⚠️ **ALERTA ATT Excedido:** {tiempo_att_min:.1f} min de gestión (> 5.0 min)")
                            emitir_alerta_sonora()
                        else:
                            col_m2.info(f"⏳ **ATT Total Chat:** {tiempo_att_min:.1f} min / 5.0 min max")

                        for msg in chat_data["mensajes"]:
                            if msg["role"] == "user":
                                st.chat_message("user").write(msg["content"])
                            else:
                                st.chat_message("assistant", avatar="🏪").write(msg["content"])

                        if resp_user := st.chat_input(f"Responder en Chat {chat_data['id']}...", key=f"input_chat_{chat_data['id']}"):
                            chat_data["mensajes"].append({"role": "user", "content": resp_user})
                            st.chat_message("user").write(resp_user)
                            
                            respuesta_generada = False
                            
                            if api_key_global.strip():
                                with st.spinner("El Partner está escribiendo..."):
                                    try:
                                        client = genai.Client(api_key=api_key_global.strip())
                                        hist_text = "\n".join([f"{'Agente' if m['role']=='user' else 'Partner'}: {m['content']}" for m in chat_data["mensajes"]])
                                        prompt_partner = f"Eres Partner de restaurante. Caso: {chat_data['escenario']}. HISTORIAL: {hist_text}. Responde exigiéndole solución al agente en máximo 2 frases cortas."
                                        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_partner)
                                        resp_partner = response.text.strip()
                                        respuesta_generada = True
                                    except Exception:
                                        pass

                            if not respuesta_generada:
                                ultimo_p = chat_data["mensajes"][-1]["content"] if len(chat_data["mensajes"]) > 1 else ""
                                resp_partner = obtener_respuesta_dinamica_respaldo(resp_user, ultimo_p)

                            chat_data["mensajes"].append({"role": "assistant", "content": resp_partner})
                            chat_data["ultimo_msg_partner"] = datetime.now()
                            st.rerun()

                        st.markdown("---")
                        if st.button(f"🏁 Finalizar Chat {chat_data['id']}", key=f"btn_fin_{chat_data['id']}", type="primary"):
                            
                            mensajes_agente = [m for m in chat_data["mensajes"] if m["role"] == "user"]
                            
                            if len(mensajes_agente) == 0:
                                data_qa = {
                                    "psat_simulado": 1.0,
                                    "empatia": 1.0,
                                    "naturalidad": 1.0,
                                    "claridad": 1.0,
                                    "multitarea": 1.0,
                                    "fortalezas": "Ninguna.",
                                    "oportunidades": "🚨 Cierre abrupto: El agente finalizó el chat sin haber respondido o atendido al Partner."
                                }
                            else:
                                conv_text = "\n".join([f"{'Agente' if m['role']=='user' else 'Partner'}: {m['content']}" for m in chat_data["mensajes"]])
                                data_qa = None
                                
                                if api_key_global.strip():
                                    with st.spinner("Auditando calidad de la atención..."):
                                        try:
                                            client = genai.Client(api_key=api_key_global.strip())
                                            prompt_qa = f"""
                                            Eres un Auditor de Calidad (QA) extremadamente estricto para un BPO.
                                            Evalúa la interacción del Agente con el Partner en una escala del 1.0 al 5.0.

                                            CRITERIOS ESTRICTOS DE PENALIZACIÓN BPO:
                                            1. CIERRE ABRUPTO O ABANDONO: Si el agente cierra el caso sin resolver o despedirse, nota de 1.0.
                                            2. INCITAR A CANCELAR: Si el agente le dice al Partner que cancele la orden en vez de solucionar, PSAT y Claridad DEBEN ser entre 1.0 y 2.0.
                                            3. LECTURA ACTIVA Y EMPATÍA: Si el agente responde con frases genéricas ("comprendo", "entiendo") sin responder lo que el Partner preguntó, la Empatía será máximo 2.0.
                                            4. TRATO CORTANTE O INFORMAL: Si responde "yo lo veo bien", "estás viendo mal" o similares, la calificación global será entre 1.0 y 1.5.

                                            CONVERSACIÓN:
                                            {conv_text}

                                            Responde ÚNICAMENTE un JSON exacto sin markdown:
                                            {{
                                                "psat_simulado": 1.5,
                                                "empatia": 1.0,
                                                "naturalidad": 2.0,
                                                "claridad": 2.0,
                                                "multitarea": 3.0,
                                                "fortalezas": "Puntos positivos reales si existieron",
                                                "oportunidades": "Detalle de faltas de lectura activa, incitación a cancelar o falta de profesionalismo"
                                            }}
                                            """
                                            res_qa = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_qa)
                                            data_qa = json.loads(res_qa.text.strip().replace("```json", "").replace("```", ""))
                                        except Exception:
                                            pass

                                if not data_qa:
                                    conv_low = conv_text.lower()
                                    incita_cancelar = any(f in conv_low for f in ["cancela", "cancelar", "cancela la orden", "anula"])
                                    mala_praxis = any(f in conv_low for f in ["viendo mal", "lo veo bien", "su problema", "no me importa", "espere", "que quiere"])
                                    
                                    if incita_cancelar or mala_praxis:
                                        data_qa = {
                                            "psat_simulado": 1.5,
                                            "empatia": 1.0,
                                            "naturalidad": 1.5,
                                            "claridad": 1.5,
                                            "multitarea": 2.5,
                                            "fortalezas": "Interacción registrada.",
                                            "oportunidades": "Grave: Incitación a la cancelación o trato fuera de protocolo. Aplica contención operativa."
                                        }
                                    else:
                                        data_qa = {
                                            "psat_simulado": 3.0,
                                            "empatia": 2.5,
                                            "naturalidad": 3.0,
                                            "claridad": 3.0,
                                            "multitarea": 3.5,
                                            "fortalezas": "Atención iniciada correctamente.",
                                            "oportunidades": "Aplica lectura activa. Evita respuestas automáticas y brinda solución paso a paso."
                                        }

                            guardar_registro({
                                "agente": user["nombre"],
                                "fecha_hora": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "modo": "ENTRENAMIENTO",
                                "escenario": chat_data['escenario'],
                                "psat_simulado": data_qa["psat_simulado"],
                                "empatia": data_qa["empatia"],
                                "naturalidad": data_qa["naturalidad"],
                                "claridad": data_qa["claridad"],
                                "multitarea": data_qa["multitarea"],
                                "fortalezas": data_qa["fortalezas"],
                                "oportunidades": data_qa["oportunidades"]
                            })

                            st.subheader("📊 Resultado de la Auditoría QA (Escala 1.0 a 5.0)")
                            
                            col_q1, col_q2, col_q3, col_q4, col_q5 = st.columns(5)
                            col_q1.metric("⭐ PSAT", f"{data_qa['psat_simulado']} / 5")
                            col_q2.metric("🤝 Empatía", f"{data_qa['empatia']} / 5")
                            col_q3.metric("💬 Naturalidad", f"{data_qa['naturalidad']} / 5")
                            col_q4.metric("💡 Claridad", f"{data_qa['claridad']} / 5")
                            col_q5.metric("🔀 Multitarea", f"{data_qa['multitarea']} / 5")

                            st.success(f"💪 **Puntos Fuertes:** {data_qa['fortalezas']}")
                            st.warning(f"🎯 **Oportunidad de Mejora:** {data_qa['oportunidades']}")

                            st.session_state.contador_total += 1
                            nuevo_chat = generar_nuevo_chat(st.session_state.contador_total)
                            st.session_state.chats[index] = nuevo_chat
                            
                            st.toast("🔄 Chat auditado y finalizado. Cargando nuevo caso...", icon="✨")

    else:
        st.header("🤝 Modo Apoyo en Vivo con IA")
        cat_p = st.selectbox("Categoría de Incidente Partner:", options=list(ESCENARIOS_PARTNER.keys()))
        msg_p = st.text_input("Mensaje recibido del Partner:", placeholder="Ejemplo: Llevo 30 minutos esperando al rider.")
        
        if st.button("Obtener Respuesta Recomendada", type="primary"):
            if not msg_p.strip():
                st.warning("Por favor ingresa el mensaje del Partner.")
            else:
                respuesta_generada = False
                if api_key_global.strip():
                    with st.spinner("Generando sugerencia con IA..."):
                        try:
                            client = genai.Client(api_key=api_key_global.strip())
                            prompt_ap = f"Genera respuesta corta para Partner. Caso: {cat_p}. Mensaje: '{msg_p}'. Formato JSON estricto: {{\"respuesta\": \"...\", \"tip\": \"...\"}}"
                            res_ap = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_ap)
                            data_ap = json.loads(res_ap.text.strip().replace("```json", "").replace("```", ""))
                            st.subheader("💡 Respuesta Recomendada por IA:")
                            st.code(data_ap["respuesta"], language=None)
                            st.warning(f"📌 **Tip Operativo:** {data_ap['tip']}")
                            respuesta_generada = True
                        except Exception:
                            pass

                if not respuesta_generada:
                    st.subheader("💡 Respuesta Recomendada de Respaldo:")
                    st.code("Comprendo tu molestia con la situación y lamento los inconvenientes causados. Ya me encuentro revisando el estado de la orden en el sistema para darte una solución concreta inmediatamente.", language=None)
                    st.warning("📌 **Tip Operativo:** Valida la orden en la consola BPO antes de dar un tiempo estimado de resolución.")

                guardar_registro({
                    "agente": user["nombre"],
                    "fecha_hora": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "modo": "APOYO",
                    "categoria_problema": cat_p
                })

# ==========================================
# SECCIÓN 2: VISTAS DE REPORTES Y DESCARGAS
# ==========================================
else:
    historial = cargar_historial()
    
    if user["rol"] == "Agente":
        st.title(f"📋 Mis Resultados de Auditoría - {user['nombre']}")
        mis_registros = [r for r in historial if r.get("agente") == user["nombre"] and r.get("modo") == "ENTRENAMIENTO"]
        
        if mis_registros:
            df = pd.DataFrame(mis_registros)
            df_tabla = df[["fecha_hora", "escenario", "psat_simulado", "empatia", "multitarea", "fortalezas", "oportunidades"]]
            df_tabla.columns = ["Fecha/Hora", "Caso", "PSAT (1-5)", "Empatía (1-5)", "Multitarea (1-5)", "Fortaleza", "Área de Mejora"]
            st.dataframe(df_tabla.tail(10), use_container_width=True)
            
            csv_bytes = generar_csv_bytes(df_tabla)
            st.download_button(
                label="📥 Descargar Mis Auditorías (CSV / Excel)",
                data=csv_bytes,
                file_name=f"Mis_Auditorias_{user['nombre']}.csv",
                mime="text/csv"
            )
        else:
            st.info("Aún no tienes evaluaciones registradas.")

    else:
        st.title("📊 Panel Supervisor Global")
        entrenamientos = [r for r in historial if r.get("modo") == "ENTRENAMIENTO"]
        
        if entrenamientos:
            df = pd.DataFrame(entrenamientos)
            agentes_unicos = ["Todos"] + list(df["agente"].unique())
            agente_filtro = st.selectbox("Filtrar por Agente:", options=agentes_unicos)
            
            if agente_filtro != "Todos":
                df = df[df["agente"] == agente_filtro]
                
            df_tabla = df[["fecha_hora", "agente", "escenario", "psat_simulado", "empatia", "multitarea", "fortalezas", "oportunidades"]]
            df_tabla.columns = ["Fecha/Hora", "Agente", "Caso", "PSAT (1-5)", "Empatía (1-5)", "Multitarea (1-5)", "Fortaleza", "Área de Mejora"]
            
            st.dataframe(df_tabla.tail(15), use_container_width=True)
            
            csv_bytes = generar_csv_bytes(df_tabla)
            st.download_button(
                label="📥 Descargar Reporte Supervisor (CSV / Excel)",
                data=csv_bytes,
                file_name=f"Reporte_Supervisor_BPO_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                type="primary"
            )
        else:
            st.info("No hay datos generales en la base de datos.")