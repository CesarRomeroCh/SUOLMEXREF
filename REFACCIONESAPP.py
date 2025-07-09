import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import os
import hashlib
import json  # ✅ Para sesión persistente

EXCEL_PATH = "inventario_suolmex.xlsx"
LOGO_PATH = "logo_suolmex.jpg"
SELLO_PATH = "aprobado.png"
PDF_RETIROS_PATH = "pdfs_retiros"
PDF_INVENTARIO_PATH = "pdfs_inventario"
BACKUP_PATH = "backups"
SESSION_FILE = "session.json"  # ✅ Archivo de sesión

os.makedirs(PDF_RETIROS_PATH, exist_ok=True)
os.makedirs(PDF_INVENTARIO_PATH, exist_ok=True)
os.makedirs(BACKUP_PATH, exist_ok=True)

st.set_page_config(page_title="Control de Refacciones", layout="centered")
st.markdown("""
<style>
    .stApp { font-family: 'Segoe UI'; background-color: #f4f6f9; }
    h1, h2, h3 { color: #00264d; }
    .stButton>button {
        background-color: #00264d;
        color: white;
        border-radius: 8px;
        padding: 10px;
    }
    .stDownloadButton>button {
        color: white;
        background-color: #444;
    }
</style>
""", unsafe_allow_html=True)

st.image(LOGO_PATH, width=250)
st.title("Control de Refacciones SUOLMEX")

conn = sqlite3.connect("refacciones.db", check_same_thread=False)
c = conn.cursor()

# Funciones de sesión persistente
def guardar_sesion():
    with open(SESSION_FILE, "w") as f:
        json.dump({
            "logueado": st.session_state.logueado,
            "usuario_id": st.session_state.usuario_id,
            "codigo": st.session_state.codigo,
            "rol": st.session_state.rol
        }, f)

def cargar_sesion():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            data = json.load(f)
            st.session_state.logueado = data.get("logueado", False)
            st.session_state.usuario_id = data.get("usuario_id", None)
            st.session_state.codigo = data.get("codigo", None)
            st.session_state.rol = data.get("rol", None)

# Crear tablas si no existen
c.execute("""CREATE TABLE IF NOT EXISTS empleados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL,
    contrasena TEXT NOT NULL,
    rol TEXT NOT NULL
)""")
c.execute("""CREATE TABLE IF NOT EXISTS refacciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL,
    nombre TEXT NOT NULL,
    cantidad INTEGER NOT NULL
)""")
c.execute("""CREATE TABLE IF NOT EXISTS movimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empleado_id INTEGER,
    refaccion_id INTEGER,
    cantidad INTEGER,
    fecha TEXT,
    maquina TEXT,
    FOREIGN KEY (empleado_id) REFERENCES empleados(id),
    FOREIGN KEY (refaccion_id) REFERENCES refacciones(id)
)""")
c.execute("""CREATE TABLE IF NOT EXISTS sugerencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empleado_id INTEGER,
    nombre_refaccion TEXT NOT NULL,
    comentario TEXT,
    fecha TEXT,
    FOREIGN KEY (empleado_id) REFERENCES empleados(id)
)""")
c.execute("""CREATE TABLE IF NOT EXISTS solicitudes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empleado_id INTEGER,
    refaccion_id INTEGER,
    cantidad INTEGER,
    fecha TEXT,
    maquina TEXT,
    FOREIGN KEY (empleado_id) REFERENCES empleados(id),
    FOREIGN KEY (refaccion_id) REFERENCES refacciones(id)
)""")
conn.commit()

def encriptar_contrasena(contra):
    return hashlib.sha256(contra.encode()).hexdigest()

def respaldo_semanal():
    fecha = datetime.now().strftime("%Y%m%d")
    dia_semana = datetime.now().weekday()
    if dia_semana == 0:
        db_dest = os.path.join(BACKUP_PATH, f"refacciones_backup_{fecha}.db")
        excel_dest = os.path.join(BACKUP_PATH, f"inventario_backup_{fecha}.xlsx")
        if not os.path.exists(db_dest):
            with open("refacciones.db", "rb") as original, open(db_dest, "wb") as copia:
                copia.write(original.read())
        if os.path.exists(EXCEL_PATH) and not os.path.exists(excel_dest):
            with open(EXCEL_PATH, "rb") as original, open(excel_dest, "wb") as copia:
                copia.write(original.read())

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
    pdf.cell(50, 10, "Código", border=1)
    pdf.cell(80, 10, "Nombre", border=1)
    pdf.cell(30, 10, "Cantidad", border=1)
    pdf.ln()
    pdf.set_font("Arial", "", 12)
    for cod, nom, cantidad in detalles:
        pdf.cell(50, 10, cod, border=1)
        pdf.cell(80, 10, nom, border=1)
        pdf.cell(30, 10, str(cantidad), border=1)
        pdf.ln()
    nombre_archivo = f"retiro_{usuario}_{fecha_actual.replace(':','-').replace(' ','_')}.pdf"
    ruta = os.path.join(PDF_RETIROS_PATH, nombre_archivo)
    pdf.output(ruta)

# Crear usuario admin por defecto si no existe
if not c.execute("SELECT * FROM empleados WHERE codigo = 'admin'").fetchone():
    c.execute("INSERT INTO empleados (codigo, contrasena, rol) VALUES (?, ?, ?)", ('admin', encriptar_contrasena('admin123'), 'admin'))
    conn.commit()

# Cargar sesión si existe
if "logueado" not in st.session_state:
    cargar_sesion()
    if "logueado" not in st.session_state:
        st.session_state.logueado = False
        st.session_state.usuario_id = None
        st.session_state.codigo = None
        st.session_state.rol = None

if not st.session_state.logueado:
    with st.form("login_form"):
        st.subheader("Iniciar sesión")
        codigo = st.text_input("Código de empleado")
        contrasena = st.text_input("Contraseña", type="password")
        login_submit = st.form_submit_button("Entrar")
        if login_submit:
            r = c.execute("SELECT id, contrasena, rol FROM empleados WHERE codigo = ?", (codigo,)).fetchone()
            if r and encriptar_contrasena(contrasena) == r[1]:
                st.session_state.logueado = True
                st.session_state.usuario_id = r[0]
                st.session_state.codigo = codigo
                st.session_state.rol = r[2]
                guardar_sesion()
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
else:
    if st.button("Cerrar sesión"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
        st.rerun()

    st.success(f"Sesión iniciada como {st.session_state.codigo} ({st.session_state.rol})")

    def menu_admin():
        respaldo_semanal()
        st.subheader("Solicitudes Pendientes")
        pendientes = c.execute("""
            SELECT s.id, e.codigo, r.codigo, r.nombre, s.cantidad, s.maquina, s.fecha
            FROM solicitudes s
            JOIN empleados e ON s.empleado_id = e.id
            JOIN refacciones r ON s.refaccion_id = r.id
            ORDER BY s.fecha DESC
        """).fetchall()
        for sid, emp, cod, nom, cantidad, maquina, fecha in pendientes:
            with st.expander(f"{emp} solicita {cantidad} de {cod} ({nom}) para {maquina}"):
                if st.button(f"Aprobar {sid}", key=f"aprobar_{sid}"):
                    ref = c.execute("SELECT id, cantidad FROM refacciones WHERE codigo = ?", (cod,)).fetchone()
                    nueva = ref[1] - cantidad
                    c.execute("UPDATE refacciones SET cantidad = ? WHERE id = ?", (nueva, ref[0]))
                    eid = c.execute("SELECT id FROM empleados WHERE codigo = ?", (emp,)).fetchone()[0]
                    c.execute("INSERT INTO movimientos (empleado_id, refaccion_id, cantidad, fecha, maquina) VALUES (?, ?, ?, ?, ?)",
                              (eid, ref[0], cantidad, fecha, maquina))
                    generar_pdf_retiro(emp, [(cod, nom, cantidad)], fecha, maquina)
                    c.execute("DELETE FROM solicitudes WHERE id = ?", (sid,))
                    conn.commit()
                    st.success("Solicitud aprobada y registrada.")
                    st.rerun()
                if st.button(f"Rechazar {sid}", key=f"rechazar_{sid}"):
                    c.execute("DELETE FROM solicitudes WHERE id = ?", (sid,))
                    conn.commit()
                    st.warning("Solicitud rechazada.")
                    st.rerun()

        st.subheader("Historial de movimientos")
        df_mov = pd.read_sql_query("""
            SELECT m.fecha, e.codigo AS usuario, r.codigo AS ref_codigo, r.nombre, m.cantidad, m.maquina
            FROM movimientos m
            JOIN empleados e ON m.empleado_id = e.id
            JOIN refacciones r ON m.refaccion_id = r.id
            ORDER BY m.fecha DESC
        """, conn)
        st.dataframe(df_mov, use_container_width=True)

        st.subheader("Inventario actual")
        df = pd.read_sql_query("SELECT codigo, nombre, cantidad FROM refacciones", conn)
        st.dataframe(df, use_container_width=True)

        st.subheader("Refacciones con stock bajo (<5)")
        bajo = df[df["cantidad"] < 5]
        if not bajo.empty:
            st.dataframe(bajo)
        else:
            st.info("No hay refacciones con stock bajo.")

        st.subheader("Subir archivo Excel para actualizar inventario")
        archivo_excel = st.file_uploader("Selecciona archivo Excel", type=["xlsx"])
        if archivo_excel:
            df_nuevo = pd.read_excel(archivo_excel)
            for _, row in df_nuevo.iterrows():
                c.execute("INSERT OR REPLACE INTO refacciones (codigo, nombre, cantidad) VALUES (?, ?, ?)",
                          (row["codigo"], row["nombre"], row["cantidad"]))
            conn.commit()
            st.success("Inventario actualizado desde Excel.")

        with st.expander("Agregar nueva refacción"):
            with st.form("agregar_ref_form"):
                cod = st.text_input("Código nuevo")
                nom = st.text_input("Nombre")
                cant = st.number_input("Cantidad inicial", min_value=1, step=1)
                if st.form_submit_button("Agregar nueva"):
                    try:
                        c.execute("INSERT INTO refacciones (codigo, nombre, cantidad) VALUES (?, ?, ?)", (cod, nom, cant))
                        conn.commit()
                        st.success("Refacción agregada.")
                    except:
                        st.error("Código ya registrado.")

        with st.expander("Sumar stock existente"):
            busqueda_admin = st.text_input("Buscar código parcial para sumar stock")
            if busqueda_admin:
                resultados = c.execute("SELECT codigo, nombre, cantidad FROM refacciones WHERE codigo LIKE ?", (f"%{busqueda_admin}%",)).fetchall()
                for cod, nom, cant_actual in resultados:
                    with st.form(f"sumar_{cod}"):
                        cant_sum = st.number_input(f"Cantidad a sumar para {cod}", min_value=1, step=1)
                        if st.form_submit_button(f"Sumar {cod}"):
                            nueva = cant_actual + cant_sum
                            c.execute("UPDATE refacciones SET cantidad = ? WHERE codigo = ?", (nueva, cod))
                            conn.commit()
                            st.success("Cantidad actualizada.")

        with st.expander("Crear nuevo usuario"):
            with st.form("crear_usuario"):
                nuevo_codigo = st.text_input("Código de usuario")
                nueva_contra = st.text_input("Contraseña", type="password")
                nuevo_rol = st.selectbox("Rol", ["admin", "empleado"])
                if st.form_submit_button("Crear usuario"):
                    try:
                        c.execute("INSERT INTO empleados (codigo, contrasena, rol) VALUES (?, ?, ?)",
                                  (nuevo_codigo, encriptar_contrasena(nueva_contra), nuevo_rol))
                        conn.commit()
                        st.success("Usuario agregado.")
                    except:
                        st.error("El código ya existe.")

        with st.expander("Administrar usuarios existentes"):
            usuarios = pd.read_sql_query("SELECT id, codigo, rol FROM empleados", conn)
            filtro_codigo = st.text_input("Filtrar por código")
            filtro_rol = st.selectbox("Filtrar por rol", ["Todos", "admin", "empleado"])
            filtrados = usuarios.copy()
            if filtro_codigo:
                filtrados = filtrados[filtrados["codigo"].str.contains(filtro_codigo, case=False)]
            if filtro_rol != "Todos":
                filtrados = filtrados[filtrados["rol"] == filtro_rol]
            st.dataframe(filtrados, use_container_width=True)

            if not filtrados.empty:
                usuario_sel = st.selectbox("Selecciona usuario", filtrados["codigo"].tolist(), key="user_sel")
                nueva_pass = st.text_input("Nueva contraseña", type="password", key="nueva_pass")
                if st.button("Actualizar contraseña"):
                    nuevo_hash = encriptar_contrasena(nueva_pass)
                    c.execute("UPDATE empleados SET contrasena = ? WHERE codigo = ?", (nuevo_hash, usuario_sel))
                    conn.commit()
                    st.success(f"Contraseña de {usuario_sel} actualizada.")

                eliminables = [u for u in filtrados["codigo"] if u != "admin"]
                if eliminables:
                    usuario_eliminar = st.selectbox("Selecciona usuario a eliminar", eliminables, key="user_del")
                    if st.button("Eliminar usuario"):
                        c.execute("DELETE FROM empleados WHERE codigo = ?", (usuario_eliminar,))
                        conn.commit()
                        st.warning(f"Usuario {usuario_eliminar} eliminado.")

        with st.expander("PDFs de retiros e inventario"):
            st.markdown("### PDFs de retiros")
            for archivo in os.listdir(PDF_RETIROS_PATH):
                with open(os.path.join(PDF_RETIROS_PATH, archivo), "rb") as f:
                    st.download_button(label=archivo, data=f.read(), file_name=archivo, key=f"ret_{archivo}")
            st.markdown("### PDFs de inventario")
            for archivo in os.listdir(PDF_INVENTARIO_PATH):
                with open(os.path.join(PDF_INVENTARIO_PATH, archivo), "rb") as f:
                    st.download_button(label=archivo, data=f.read(), file_name=archivo, key=f"inv_{archivo}")
        pass

    def menu_empleado():
        st.subheader("Solicitar refacción")
        busqueda = st.text_input("Buscar código de refacción")
        if busqueda:
            resultados = c.execute("SELECT id, codigo, nombre, cantidad FROM refacciones WHERE codigo LIKE ?", (f"%{busqueda}%",)).fetchall()
            for ref_id, cod, nom, cant in resultados:
                with st.form(f"form_{cod}"):
                    st.markdown(f"**{cod} - {nom} (Disponibles: {cant})**")
                    cantidad = st.number_input("Cantidad", min_value=1, max_value=cant, key=f"cant_{cod}")
                    maquina = st.selectbox("Máquina", ["Máquina 1", "Máquina 2", "Máquina 3", "Máquina 4"], key=f"maq_{cod}")
                    if st.form_submit_button("Solicitar"):
                        existe = c.execute("SELECT * FROM solicitudes WHERE empleado_id = ? AND refaccion_id = ?", (st.session_state.usuario_id, ref_id)).fetchone()
                        if existe:
                            st.warning("Ya existe una solicitud pendiente para esta refacción.")
                        else:
                            c.execute("INSERT INTO solicitudes (empleado_id, refaccion_id, cantidad, fecha, maquina) VALUES (?, ?, ?, ?, ?)",
                                      (st.session_state.usuario_id, ref_id, cantidad, datetime.now().strftime("%Y-%m-%d %H:%M"), maquina))
                            conn.commit()
                            st.success(f"Solicitud enviada para {cod}.")

        st.subheader("Sugerir refacción")
        with st.form("form_sugerencia"):
            nombre = st.text_input("Nombre sugerido")
            comentario = st.text_area("Comentario")
            if st.form_submit_button("Enviar sugerencia"):
                c.execute("INSERT INTO sugerencias (empleado_id, nombre_refaccion, comentario, fecha) VALUES (?, ?, ?, ?)",
                          (st.session_state.usuario_id, nombre, comentario, datetime.now().strftime("%Y-%m-%d %H:%M")))
                conn.commit()
                st.success("Sugerencia enviada.")

    if st.session_state.rol == "admin":
        menu_admin()
    else:
        menu_empleado()
