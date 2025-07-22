# -------------------- PARTE 1: CONFIGURACIÓN, CONEXIÓN, SESIÓN Y LOGIN --------------------
import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import os
import hashlib
import json
import uuid
from supabase import create_client, Client

# 📆 Conexión a Supabase
SUPABASE_URL = "https://wbilookfnxmgvyasamex.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndiaWxvb2tmbnhtZ3Z5YXNhbWV4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI1OTk4OTYsImV4cCI6MjA2ODE3NTg5Nn0.Onez-QnxLI5xtIgFQoHYokkTSqPv66H5jdTV4u2swu0"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 📁 Rutas
EXCEL_PATH = "inventario_suolmex.xlsx"
LOGO_PATH = "logo_suolmex.jpg"
SELLO_PATH = "aprobado.png"
PDF_RETIROS_PATH = "pdfs_retiros"
PDF_INVENTARIO_PATH = "pdfs_inventario"
BACKUP_PATH = "backups"
for path in [PDF_RETIROS_PATH, PDF_INVENTARIO_PATH, BACKUP_PATH]:
    os.makedirs(path, exist_ok=True)

# 🎨 Estética
st.set_page_config(page_title="Control de Refacciones", layout="centered")
st.markdown("""
<style>
.stApp {
    font-family: 'Segoe UI', sans-serif;
    background-color: #f4f6f9;
}
h1, h2, h3 {
    color: #00264d;
    font-weight: 600;
    margin-bottom: 0.5rem;
}
.stButton > button, .stDownloadButton > button {
    background-color: #00264d;
    color: white;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
}
.stFileUploader {
    border: 1px solid #ccc;
    border-radius: 6px;
    padding: 10px;
    background-color: #fff;
}
.stTextInput > div > div > input {
    background-color: #ffffff;
}
.stExpander > summary {
    font-size: 1rem;
    font-weight: 600;
    color: #00264d;
    background-color: #e7ecf2;
    border-radius: 4px;
    padding: 10px;
    margin-top: 5px;
}
.stExpanderContent {
    background-color: #ffffff;
    padding: 10px;
    border: 1px solid #ddd;
    border-top: none;
}
</style>
""", unsafe_allow_html=True)

st.image(LOGO_PATH, width=250)
st.markdown("## Control de Refacciones SUOLMEX")

# 🧠 Persistencia de sesión
def obtener_session_id():
    if "session_id" not in st.session_state:
        st.session_state.session_id = uuid.uuid4().hex
    return st.session_state.session_id

def path_sesion_local():
    return f"session_{obtener_session_id()}.json"

def guardar_sesion():
    with open(path_sesion_local(), "w") as f:
        json.dump({
            "logueado": st.session_state.logueado,
            "usuario_id": st.session_state.usuario_id,
            "codigo": st.session_state.codigo,
            "rol": st.session_state.rol
        }, f)

def cargar_sesion():
    ruta = path_sesion_local()
    if os.path.exists(ruta):
        with open(ruta, "r") as f:
            data = json.load(f)
            st.session_state.logueado = data.get("logueado", False)
            st.session_state.usuario_id = data.get("usuario_id", None)
            st.session_state.codigo = data.get("codigo", None)
            st.session_state.rol = data.get("rol", None)

# 🔐 Seguridad
def encriptar_contrasena(contra): return hashlib.sha256(contra.encode()).hexdigest()

# 🛠️ Crear usuario admin si no existe
admin = supabase.table("empleados").select("*").eq("codigo", "admin").execute()
if not admin.data:
    supabase.table("empleados").insert({
        "codigo": "admin", "contrasena": encriptar_contrasena("admin123"), "rol": "admin"
    }).execute()

# 🔐 Login
if "logueado" not in st.session_state:
    cargar_sesion()
    if "logueado" not in st.session_state:
        st.session_state.logueado = False

if not st.session_state.logueado:
    with st.form("login_form"):
        st.subheader("Iniciar sesión")
        codigo = st.text_input("Código de empleado")
        contrasena = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            res = supabase.table("empleados").select("*").eq("codigo", codigo).execute()
            if res.data:
                r = res.data[0]
                if encriptar_contrasena(contrasena) == r["contrasena"]:
                    st.session_state.update({
                        "logueado": True,
                        "usuario_id": r["id"],
                        "codigo": codigo,
                        "rol": r["rol"]
                    })
                    guardar_sesion()
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta.")
            else:
                st.error("Usuario no encontrado.")

# -------------------- PARTE 2: FUNCIONES PARA EMPLEADOS --------------------

def menu_empleado():
    st.subheader("Solicitar refacción")

# Obtener refacciones disponibles (únicos nombres)
    refacciones = supabase.table("refacciones").select("id, nombre, cantidad").eq("estado", "disponible").execute().data
    nombres_unicos = sorted(set([r["nombre"] for r in refacciones]))

    if nombres_unicos:
        seleccion = st.selectbox("Selecciona una refacción para solicitar:", nombres_unicos)

        if seleccion:
            ref = next((r for r in refacciones if r["nombre"] == seleccion), None)
            if ref:
                ref_id = ref["id"]
                disponibles = ref["cantidad"]

                with st.form(f"form_solicitud_{ref_id}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        cantidad = st.number_input("Cantidad a solicitar", min_value=1, max_value=disponibles, key=f"cant_{ref_id}")
                    with col2:
                        maquina = st.selectbox("Máquina", ["Máquina 1", "Máquina 2", "Máquina 3", "Máquina 4"], key=f"maq_{ref_id}")

                    if st.form_submit_button("Enviar solicitud"):
                        ya_existe = supabase.table("solicitudes").select("*")\
                            .eq("empleado_id", st.session_state.usuario_id)\
                            .eq("refaccion_id", ref_id).execute().data
                        if ya_existe:
                            st.warning("Ya tienes una solicitud pendiente para esta refacción.")
                        else:
                            supabase.table("solicitudes").insert({
                                "empleado_id": st.session_state.usuario_id,
                                "refaccion_id": ref_id,
                                "cantidad": cantidad,
                                "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "maquina": maquina
                            }).execute()
                            st.success("Solicitud enviada correctamente.")
                            st.rerun()
    else:
        st.info("No hay refacciones disponibles.")

        if resultados:
            for ref in resultados:
                ref_id = ref["id"]
                nombre = ref["nombre"]
                disponibles = ref["cantidad"]

                with st.expander(f"{nombre} (Disponibles: {disponibles})"):
                    with st.form(f"form_solicitud_{ref_id}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            cantidad = st.number_input("Cantidad a solicitar", min_value=1, max_value=disponibles, key=f"cant_{ref_id}")
                        with col2:
                            maquina = st.selectbox("Máquina", ["Máquina 1", "Máquina 2", "Máquina 3", "Máquina 4"], key=f"maq_{ref_id}")

                        if st.form_submit_button("Enviar solicitud"):
                            # Verifica si ya existe una solicitud igual pendiente
                            ya_existe = supabase.table("solicitudes").select("*")\
                                .eq("empleado_id", st.session_state.usuario_id)\
                                .eq("refaccion_id", ref_id).execute().data
                            if ya_existe:
                                st.warning("Ya tienes una solicitud pendiente para esta refacción.")
                            else:
                                supabase.table("solicitudes").insert({
                                    "empleado_id": st.session_state.usuario_id,
                                    "refaccion_id": ref_id,
                                    "cantidad": cantidad,
                                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    "maquina": maquina
                                }).execute()
                                st.success("Solicitud enviada correctamente.")
                                st.rerun()
        else:
            st.info("No se encontraron refacciones disponibles con ese nombre.")

    st.markdown("---")
    st.subheader("Sugerir nueva refacción")
    with st.form("form_sugerencia"):
        nombre = st.text_input("Nombre sugerido de la refacción")
        comentario = st.text_area("Justificación o comentario adicional")
        if st.form_submit_button("Enviar sugerencia"):
            supabase.table("sugerencias").insert({
                "empleado_id": st.session_state.usuario_id,
                "nombre_refaccion": nombre,
                "comentario": comentario,
                "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
            }).execute()
            st.success("Gracias por tu sugerencia. Será evaluada por el administrador.")
# -------------------- PARTE 3: FUNCIONES PARA ADMINISTRADOR (1/2) --------------------

def generar_pdf_retiro(usuario, detalles, fecha_actual, maquina):
    class PDF(FPDF):
        def header(self):
            if os.path.exists(LOGO_PATH):
                self.image(LOGO_PATH, 10, 8, 40)
            self.set_font("Arial", "B", 14)
            self.cell(0, 10, "RETIRO DE REFACCIONES - SUOLMEX", ln=True, align="C")
            self.ln(10)
        def footer(self):
            if os.path.exists(SELLO_PATH):
                self.image(SELLO_PATH, x=160, y=250, w=30)

    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Fecha y hora: {fecha_actual}", ln=True)
    pdf.cell(0, 10, f"Empleado: {usuario}", ln=True)
    pdf.cell(0, 10, f"Máquina: {maquina}", ln=True)
    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(130, 10, "Nombre", border=1)
    pdf.cell(30, 10, "Cantidad", border=1)
    pdf.ln()
    pdf.set_font("Arial", "", 12)
    for nombre, cantidad in detalles:
        pdf.cell(130, 10, nombre, border=1)
        pdf.cell(30, 10, str(cantidad), border=1)
        pdf.ln()

    nombre_archivo = f"retiro_{usuario}_{fecha_actual.replace(':','-').replace(' ','_')}.pdf"
    ruta = os.path.join(PDF_RETIROS_PATH, nombre_archivo)
    pdf.output(ruta)


def menu_admin():
    st.subheader("Solicitudes pendientes")
    pendientes = supabase.table("solicitudes").select("id, cantidad, fecha, maquina, refacciones(nombre), empleados(codigo)").order("fecha", desc=True).execute().data

    for solicitud in pendientes:
        sid = solicitud["id"]
        emp = solicitud["empleados"]["codigo"]
        nombre = solicitud["refacciones"]["nombre"]
        cantidad = solicitud["cantidad"]
        maquina = solicitud["maquina"]
        fecha = solicitud["fecha"]

        with st.expander(f"{emp} solicita {cantidad} de {nombre} para {maquina}"):
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"Aprobar solicitud #{sid}", key=f"aprobar_{sid}"):
                    ref = supabase.table("refacciones").select("id, cantidad").eq("nombre", nombre).execute().data[0]
                    nueva = ref["cantidad"] - cantidad
                    supabase.table("refacciones").update({"cantidad": nueva}).eq("id", ref["id"]).execute()

                    eid = supabase.table("empleados").select("id").eq("codigo", emp).execute().data[0]["id"]
                    supabase.table("movimientos").insert({
                        "empleado_id": eid,
                        "refaccion_id": ref["id"],
                        "cantidad": cantidad,
                        "fecha": fecha,
                        "maquina": maquina
                    }).execute()

                    generar_pdf_retiro(emp, [(nombre, cantidad)], fecha, maquina)
                    supabase.table("solicitudes").delete().eq("id", sid).execute()
                    st.success("Solicitud aprobada.")
                    st.rerun()
            with col2:
                if st.button(f"Rechazar solicitud #{sid}", key=f"rechazar_{sid}"):
                    supabase.table("solicitudes").delete().eq("id", sid).execute()
                    st.warning("Solicitud rechazada.")
                    st.rerun()

    st.markdown("---")
    st.subheader("Historial de movimientos")
    movs = supabase.table("movimientos").select("fecha, cantidad, maquina, empleados(codigo), refacciones(nombre)").order("fecha", desc=True).execute().data
    df_mov = pd.DataFrame([{
        "fecha": m["fecha"],
        "usuario": m["empleados"]["codigo"],
        "nombre": m["refacciones"]["nombre"],
        "cantidad": m["cantidad"],
        "maquina": m["maquina"]
    } for m in movs])
    st.dataframe(df_mov, use_container_width=True)

    st.subheader("Inventario actual")
    inventario = supabase.table("refacciones").select("*").execute().data
    df = pd.DataFrame(inventario)
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("No hay refacciones cargadas.")
 
 # 🔧 Refacciones en reparación
    if "estado" in df.columns:
        st.subheader("Refacciones en reparación")
        en_reparacion = df[df["estado"] == "en_reparacion"]
        if not en_reparacion.empty:
            for _, row in en_reparacion.iterrows():
                nombre = row["nombre"]
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"Liberar {nombre}", key=f"lib_{nombre}"):
                        supabase.table("refacciones").update({"estado": "disponible"}).eq("nombre", nombre).execute()
                        st.success(f"{nombre} liberada.")
                        st.rerun()
                with col2:
                    if st.button(f"Eliminar {nombre}", key=f"elim_{nombre}"):
                        supabase.table("refacciones").update({"estado": "eliminada"}).eq("nombre", nombre).execute()
                        st.warning(f"{nombre} marcada como eliminada.")
                        st.rerun()
        else:
            st.info("No hay refacciones en reparación.")
    with st.expander("Enviar refacción a reparación"):
        busq_rep = st.text_input("Buscar refacción por nombre", key="busq_reparacion")
        if busq_rep:
            refacciones = supabase.table("refacciones").select("*").ilike("nombre", f"%{busq_rep}%").eq("estado", "disponible").execute().data
            for ref in refacciones:
                if st.button(f"Enviar a reparación: {ref['nombre']}", key=f"rep_{ref['id']}"):
                    supabase.table("refacciones").update({"estado": "en_reparacion"}).eq("id", ref["id"]).execute()
                    st.success(f"{ref['nombre']} marcada como en reparación.")
                    st.rerun()

    with st.expander("Editar nombre de una refacción"):
        busq_edit = st.text_input("Buscar refacción por nombre actual", key="busq_edit_nombre")
        if busq_edit:
            refacciones = supabase.table("refacciones").select("*").ilike("nombre", f"%{busq_edit}%").execute().data
            for ref in refacciones:
                with st.form(f"form_edit_nombre_{ref['id']}"):
                    nuevo_nombre = st.text_input(f"Nuevo nombre para {ref['nombre']}", key=f"nuevo_nombre_{ref['id']}")
                    if st.form_submit_button("Actualizar nombre"):
                        try:
                            supabase.table("refacciones").update({"nombre": nuevo_nombre}).eq("id", ref["id"]).execute()
                            st.success(f"{ref['nombre']} → {nuevo_nombre}")
                            st.rerun()
                        except:
                            st.error("Error al actualizar el nombre.")

    with st.expander("Administrar usuarios existentes"):
        try:
            response = supabase.table("empleados").select("id, codigo, rol").execute()
            usuarios_df = pd.DataFrame(response.data)

        # Filtros
            filtro_codigo = st.text_input("Filtrar por código")
            filtro_rol = st.selectbox("Filtrar por rol", ["Todos", "admin", "empleado"])

            filtrados = usuarios_df.copy()
            if filtro_codigo:
                filtrados = filtrados[filtrados["codigo"].str.contains(filtro_codigo, case=False)]
            if filtro_rol != "Todos":
                filtrados = filtrados[filtrados["rol"] == filtro_rol]

            st.dataframe(filtrados, use_container_width=True)

        # -------------------- ACTUALIZAR CONTRASEÑA --------------------
            if not filtrados.empty:
                usuario_sel = st.selectbox("Selecciona usuario", filtrados["codigo"].tolist(), key="user_sel")
                nueva_pass = st.text_input("Nueva contraseña", type="password", key="nueva_pass")

                if st.button("Actualizar contraseña"):
                    if not nueva_pass or len(nueva_pass) < 6:
                        st.error("La contraseña debe tener al menos 6 caracteres.")
                    else:
                        nuevo_hash = encriptar_contrasena(nueva_pass)
                        user_id = filtrados[filtrados["codigo"] == usuario_sel]["id"].values[0]

                        supabase.table("empleados").update({"contrasena": nuevo_hash}).eq("id", user_id).execute()
                        st.success(f"Contraseña de {usuario_sel} actualizada.")

        # -------------------- ELIMINAR USUARIO --------------------
            eliminables = filtrados[filtrados["codigo"] != "admin"]
            if not eliminables.empty:
                usuario_eliminar = st.selectbox("Selecciona usuario a eliminar", eliminables["codigo"].tolist(), key="user_del")

                if st.button("Eliminar usuario"):
                    user_id = eliminables[eliminables["codigo"] == usuario_eliminar]["id"].values[0]
                    supabase.table("empleados").delete().eq("id", user_id).execute()
                    st.warning(f"Usuario {usuario_eliminar} eliminado.")

        except Exception as e:
            st.error(f"Ocurrió un error al consultar usuarios: {e}")

    with st.expander("Crear nuevo usuario"):
        with st.form("crear_usuario"):
            nuevo_codigo = st.text_input("Código de usuario")
            nueva_contra = st.text_input("Contraseña", type="password")
            nuevo_rol = st.selectbox("Rol", ["admin", "empleado"])

            if st.form_submit_button("Crear usuario"):
                if not nuevo_codigo or not nueva_contra:
                    st.error("Todos los campos son obligatorios.")
                elif len(nueva_contra) < 6:
                    st.error("La contraseña debe tener al menos 6 caracteres.")
                else:
                    try:
                    # Verificar si ya existe ese código
                        existing = supabase.table("empleados").select("id").eq("codigo", nuevo_codigo).execute()
                        if existing.data:
                            st.error("El código ya existe.")
                        else:
                            nuevo_hash = encriptar_contrasena(nueva_contra)
                            supabase.table("empleados").insert({
                                "codigo": nuevo_codigo,
                                "contrasena": nuevo_hash,
                                "rol": nuevo_rol
                            }).execute()
                            st.success("Usuario agregado correctamente.")
                    except Exception as e:
                        st.error(f"Ocurrió un error al crear el usuario: {e}")
                        
# ➕ Agregar nueva refacción
    with st.expander("Agregar nueva refacción"):
        with st.form("form_agregar"):
            nombre = st.text_input("Nombre")
            cantidad = st.number_input("Cantidad inicial", min_value=1)
            estado = st.selectbox("Estado", ["disponible", "en_reparacion", "eliminada"])
            if st.form_submit_button("Agregar / Actualizar"):
                if nombre.strip() != "":
                    supabase.table("refacciones").upsert({
                        "nombre": nombre,
                        "cantidad": cantidad,
                        "estado": estado
                    }, on_conflict="nombre").execute()
                    st.success("Refacción agregada o actualizada.")
                    st.rerun()
                else:
                    st.error("El nombre no puede estar vacío.")

    # ➕ Sumar stock
    with st.expander("Sumar stock a refacción existente"):
        busq = st.text_input("Buscar por nombre")
        if busq:
            resultados = supabase.table("refacciones").select("*").ilike("nombre", f"%{busq}%").execute().data
            for ref in resultados:
                with st.form(f"sumar_{ref['id']}"):
                    cant = st.number_input(f"Sumar cantidad para {ref['nombre']}", min_value=1)
                    if st.form_submit_button("Actualizar"):
                        nueva = ref["cantidad"] + cant
                        supabase.table("refacciones").update({"cantidad": nueva}).eq("id", ref["id"]).execute()
                        st.success("Cantidad actualizada.")
                        st.rerun()

    # 🧾 PDF de inventario
    with st.expander("Generar PDF del inventario"):
        if st.button("Generar PDF de inventario actual"):
            df_inv = pd.DataFrame(supabase.table("refacciones").select("*").execute().data)

            class PDFInv(FPDF):
                def header(self):
                    if os.path.exists(LOGO_PATH):
                        self.image(LOGO_PATH, 10, 8, 40)
                    self.set_font("Arial", "B", 14)
                    self.cell(0, 10, "INVENTARIO ACTUAL - SUOLMEX", ln=True, align="C")
                    self.ln(10)

            pdf = PDFInv()
            pdf.add_page()
            pdf.set_font("Arial", "", 12)
            pdf.cell(0, 10, f"Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
            pdf.ln(5)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(80, 10, "Nombre", border=1)
            pdf.cell(30, 10, "Cantidad", border=1)
            pdf.cell(40, 10, "Estado", border=1)
            pdf.ln()
            pdf.set_font("Arial", "", 12)

            for _, row in df_inv.iterrows():
                pdf.cell(80, 10, row["nombre"], border=1)
                pdf.cell(30, 10, str(row["cantidad"]), border=1)
                pdf.cell(40, 10, row.get("estado", "disponible"), border=1)
                pdf.ln()

            nombre_pdf = f"inventario_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            ruta_pdf = os.path.join(PDF_INVENTARIO_PATH, nombre_pdf)
            pdf.output(ruta_pdf)

            with open(ruta_pdf, "rb") as f:
                st.download_button("Descargar PDF generado", data=f.read(), file_name=nombre_pdf)

    # 🧑‍💼 Historial por refacción o máquina
    with st.expander("Historial por refacción o máquina"):
        tab1, tab2 = st.tabs(["Por refacción", "Por máquina"])

        with tab1:
            nombre = st.text_input("Buscar refacción exacta")
            if nombre:
                datos = supabase.table("movimientos").select("fecha, cantidad, maquina, empleados(codigo), refacciones(nombre)")\
                    .eq("refacciones.nombre", nombre).order("fecha", desc=True).execute().data
                df = pd.DataFrame([{
                    "fecha": d["fecha"],
                    "usuario": d["empleados"]["codigo"],
                    "nombre": d["refacciones"]["nombre"],
                    "cantidad": d["cantidad"],
                    "maquina": d["maquina"]
                } for d in datos])
                if not df.empty:
                    st.dataframe(df, use_container_width=True)
                    st.success(f"Total retirado: {df['cantidad'].sum()}")
                else:
                    st.info("No hay registros.")

        with tab2:
            maq = st.selectbox("Máquina", ["Máquina 1", "Máquina 2", "Máquina 3", "Máquina 4"])
            datos = supabase.table("movimientos").select("fecha, cantidad, empleados(codigo), refacciones(nombre)")\
                .eq("maquina", maq).order("fecha", desc=True).execute().data
            df = pd.DataFrame([{
                "fecha": d["fecha"],
                "usuario": d["empleados"]["codigo"],
                "refaccion": d["refacciones"]["nombre"],
                "cantidad": d["cantidad"]
            } for d in datos])
            if not df.empty:
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No hay movimientos en esta máquina.")
    
    with st.expander("Generar PDF de Retiros"):
        st.subheader("Generar PDF de retiros anteriores")
        
        # Consultar datos incluyendo las relaciones necesarias
        movimientos = supabase.table("movimientos").select(
            "fecha, cantidad, maquina, empleados(codigo), refacciones(nombre)"
        ).order("fecha", desc=True).execute().data
        
        df_movs = pd.DataFrame(movimientos)
        
        if df_movs.empty:
            st.info("No hay movimientos registrados aún.")
        else:
            # Convertir la columna de fecha a datetime y extraer solo la fecha
            df_movs["fecha_hora"] = pd.to_datetime(df_movs["fecha"])
            df_movs["fecha_solo"] = df_movs["fecha_hora"].dt.strftime('%Y-%m-%d')
        
            # Extraer el código del empleado como 'usuario'
            df_movs["usuario"] = df_movs["empleados"].apply(
                lambda x: x.get("codigo", "desconocido") if isinstance(x, dict) else "desconocido"
            )
        
            # Extraer el nombre de la refacción para cada fila
            df_movs["nombre_refaccion"] = df_movs["refacciones"].apply(
                lambda x: x.get("nombre", "¿?") if isinstance(x, dict) else "¿?"
            )
        
            # Agrupar por fecha, usuario y máquina
            grupos = df_movs.groupby(["fecha", "usuario", "maquina"])
        
            for (fecha, usuario, maquina), group in grupos:
                detalles = list(zip(group["nombre_refaccion"], group["cantidad"]))
                nombre_archivo = f"retiro_{usuario}_{fecha.replace(':','-').replace(' ','_')}.pdf"
                ruta = os.path.join(PDF_RETIROS_PATH, nombre_archivo)
        
                # Evitar duplicados
                if not os.path.exists(ruta):
                    generar_pdf_retiro(usuario, detalles, fecha, maquina)
        
                with open(ruta, "rb") as f:
                    st.download_button(
                        f"Descargar retiro de {usuario} - {fecha}",
                        data=f.read(),
                        file_name=nombre_archivo
                    )



   # 📥 Subir inventario desde Excel (actualiza por nombre)
    st.subheader("Subir archivo Excel para actualizar inventario")
    archivo_excel = st.file_uploader("Selecciona archivo Excel", type=["xlsx"])
    if archivo_excel:
        df_excel = pd.read_excel(archivo_excel)
        for _, row in df_excel.iterrows():
            supabase.table("refacciones").upsert({
                "nombre": row["nombre"],
                "cantidad": row["cantidad"],
                "estado": row.get("estado", "disponible")
            }, on_conflict="nombre").execute()
        st.success("Inventario actualizado desde Excel.")
        st.rerun()
# -------------------- PARTE 4: FLUJO PRINCIPAL Y CIERRE DE SESIÓN --------------------

if st.session_state.logueado:
    st.success(f"Sesión iniciada como: **{st.session_state.codigo}** ({st.session_state.rol})")

    # Menú según rol
    if st.session_state.rol == "admin":
        menu_admin()
    else:
        menu_empleado()

    st.markdown("---")
    # Botón de cierre de sesión
    if st.button("Cerrar sesión "):
        ruta = path_sesion_local()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        if os.path.exists(ruta):
            os.remove(ruta)
        st.rerun()
