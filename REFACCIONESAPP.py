import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import os
import hashlib
import json
import uuid

EXCEL_PATH = "inventario_suolmex.xlsx"
LOGO_PATH = "logo_suolmex.jpg"
SELLO_PATH = "aprobado.png"
PDF_RETIROS_PATH = "pdfs_retiros"
PDF_INVENTARIO_PATH = "pdfs_inventario"
BACKUP_PATH = "backups"

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

def obtener_session_id():
    if "session_id" not in st.session_state:
        st.session_state.session_id = uuid.uuid4().hex
    return st.session_state.session_id

def path_sesion_local():
    session_id = obtener_session_id()
    return f"session_{session_id}.json"

def guardar_sesion():
    ruta = path_sesion_local()
    with open(ruta, "w") as f:
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

c.execute("""CREATE TABLE IF NOT EXISTS empleados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL,
    contrasena TEXT NOT NULL,
    rol TEXT NOT NULL
)""")

c.execute("""CREATE TABLE IF NOT EXISTS refacciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT UNIQUE NOT NULL,
    cantidad INTEGER NOT NULL,
    estado TEXT DEFAULT 'disponible'
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

try:
    c.execute("ALTER TABLE refacciones ADD COLUMN estado TEXT DEFAULT 'disponible'")
    conn.commit()
except:
    pass

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

if not c.execute("SELECT * FROM empleados WHERE codigo = 'admin'").fetchone():
    c.execute("INSERT INTO empleados (codigo, contrasena, rol) VALUES (?, ?, ?)", ('admin', encriptar_contrasena('admin123'), 'admin'))
    conn.commit()

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
        ruta = path_sesion_local()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        if os.path.exists(ruta):
            os.remove(ruta)
        st.rerun()

    st.success(f"Sesión iniciada como {st.session_state.codigo} ({st.session_state.rol})")

    def menu_admin():
        respaldo_semanal()
        st.subheader("Solicitudes Pendientes")
        pendientes = c.execute("""
            SELECT s.id, e.codigo, r.nombre, s.cantidad, s.maquina, s.fecha
            FROM solicitudes s
            JOIN empleados e ON s.empleado_id = e.id
            JOIN refacciones r ON s.refaccion_id = r.id
            ORDER BY s.fecha DESC
        """).fetchall()
        for sid, emp, nombre, cantidad, maquina, fecha in pendientes:
            with st.expander(f"{emp} solicita {cantidad} de {nombre} para {maquina}"):
                if st.button(f"Aprobar {sid}", key=f"aprobar_{sid}"):
                    ref = c.execute("SELECT id, cantidad FROM refacciones WHERE nombre = ?", (nombre,)).fetchone()
                    nueva = ref[1] - cantidad
                    c.execute("UPDATE refacciones SET cantidad = ? WHERE id = ?", (nueva, ref[0]))
                    eid = c.execute("SELECT id FROM empleados WHERE codigo = ?", (emp,)).fetchone()[0]
                    c.execute("INSERT INTO movimientos (empleado_id, refaccion_id, cantidad, fecha, maquina) VALUES (?, ?, ?, ?, ?)",
                              (eid, ref[0], cantidad, fecha, maquina))
                    generar_pdf_retiro(emp, [(nombre, cantidad)], fecha, maquina)
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
            SELECT m.fecha, e.codigo AS usuario, r.nombre, m.cantidad, m.maquina
            FROM movimientos m
            JOIN empleados e ON m.empleado_id = e.id
            JOIN refacciones r ON m.refaccion_id = r.id
            ORDER BY m.fecha DESC
        """, conn)
        st.dataframe(df_mov, use_container_width=True)

        st.subheader("Inventario actual")
        df = pd.read_sql_query("SELECT nombre, cantidad, estado FROM refacciones", conn)
        st.dataframe(df, use_container_width=True)

        st.subheader("Refacciones con stock bajo (<1)")
        bajo = df[df["cantidad"] < 1]
        if not bajo.empty:
            st.dataframe(bajo)
        else:
            st.info("No hay refacciones con stock bajo.")

        st.subheader("Subir archivo Excel para actualizar inventario")
        archivo_excel = st.file_uploader("Selecciona archivo Excel", type=["xlsx"])
        if archivo_excel:
            df_nuevo = pd.read_excel(archivo_excel)
            for _, row in df_nuevo.iterrows():
                c.execute("INSERT OR REPLACE INTO refacciones (nombre, cantidad, estado) VALUES (?, ?, COALESCE(?, 'disponible'))",
                          (row["nombre"], row["cantidad"], row.get("estado", "disponible")))
            conn.commit()
            st.success("Inventario actualizado desde Excel.")

        with st.expander("Agregar nueva refacción"):
            with st.form("agregar_ref_form"):
                nombre = st.text_input("Nombre")
                cant = st.number_input("Cantidad inicial", min_value=1, step=1)
                estado = st.selectbox("Estado", ["disponible", "en_reparacion", "eliminada"])
                if st.form_submit_button("Agregar nueva"):
                    try:
                        c.execute("INSERT INTO refacciones (nombre, cantidad, estado) VALUES (?, ?, ?)", (nombre, cant, estado))
                        conn.commit()
                        st.success("Refacción agregada.")
                    except:
                        st.error("Nombre ya registrado.")

        with st.expander("Sumar stock existente"):
            busqueda_admin = st.text_input("Buscar por nombre parcial para sumar stock")
            if busqueda_admin:
                resultados = c.execute("SELECT nombre, cantidad FROM refacciones WHERE nombre LIKE ?", (f"%{busqueda_admin}%",)).fetchall()
                for nombre, cant_actual in resultados:
                    with st.form(f"sumar_{nombre}"):
                        cant_sum = st.number_input(f"Cantidad a sumar para {nombre}", min_value=1, step=1)
                        if st.form_submit_button(f"Sumar {nombre}"):
                            nueva = cant_actual + cant_sum
                            c.execute("UPDATE refacciones SET cantidad = ? WHERE nombre = ?", (nueva, nombre))
                            conn.commit()
                            st.success("Cantidad actualizada.")
       
        with st.expander("Editar nombre de una refacción existente"):
            busqueda_edit = st.text_input("Buscar refacción por nombre actual")
            if busqueda_edit:
                resultados = c.execute("SELECT id, nombre FROM refacciones WHERE nombre LIKE ?", (f"%{busqueda_edit}%",)).fetchall()
                if resultados:
                    for ref_id, nombre_actual in resultados:
                        with st.form(f"edit_nombre_{ref_id}"):
                            st.write(f"Nombre actual: **{nombre_actual}**")
                            nuevo_nombre = st.text_input("Nuevo nombre", key=f"nuevo_{ref_id}")
                            if st.form_submit_button("Actualizar nombre"):
                                try:
                                    c.execute("UPDATE refacciones SET nombre = ? WHERE id = ?", (nuevo_nombre, ref_id))
                                    conn.commit()
                                    st.success(f"Nombre actualizado: {nombre_actual} → {nuevo_nombre}")
                                    st.rerun()
                                except sqlite3.IntegrityError:
                                    st.error("Ya existe una refacción con ese nombre.")
                else:
                    st.info("No se encontraron refacciones con ese nombre.")
                    
        with st.expander("Enviar refacción a reparación"):
            busq_rep = st.text_input("Buscar nombre para enviar a reparación")
            if busq_rep:
                items = c.execute("SELECT id, nombre, cantidad FROM refacciones WHERE nombre LIKE ? AND estado = 'disponible'", (f"%{busq_rep}%",)).fetchall()
                for rid, nombre, cant in items:
                    if st.button(f"Enviar a reparación: {nombre}", key=f"rep_{rid}"):
                        c.execute("UPDATE refacciones SET estado = 'en_reparacion' WHERE id = ?", (rid,))
                        conn.commit()
                        st.success("Marcada como en reparación.")
                        st.rerun()

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
            archivos_inventario = os.listdir(PDF_INVENTARIO_PATH)
            if archivos_inventario:
                for archivo in archivos_inventario:
                    with open(os.path.join(PDF_INVENTARIO_PATH, archivo), "rb") as f:
                        st.download_button(label=archivo, data=f.read(), file_name=archivo, key=f"inv_{archivo}")
            else:
                st.info("No hay PDFs de inventario todavía.")

            st.markdown("### Generar nuevo PDF del inventario")
            if st.button("Generar PDF de inventario"):
                df_inventario = pd.read_sql_query("SELECT nombre, cantidad, estado FROM refacciones", conn)

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

                for _, row in df_inventario.iterrows():
                    pdf.cell(80, 10, row["nombre"], border=1)
                    pdf.cell(30, 10, str(row["cantidad"]), border=1)
                    pdf.cell(40, 10, row["estado"], border=1)
                    pdf.ln()

                archivo_pdf = f"inventario_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                ruta_pdf = os.path.join(PDF_INVENTARIO_PATH, archivo_pdf)
                pdf.output(ruta_pdf)

                with open(ruta_pdf, "rb") as f:
                    st.download_button("Descargar PDF generado", data=f.read(), file_name=archivo_pdf, key=f"invgen_{archivo_pdf}")

                st.success("¡PDF de inventario generado correctamente!")

        with st.expander("Refacciones en reparación"):
            en_reparacion = c.execute("SELECT id, nombre, cantidad FROM refacciones WHERE estado = 'en_reparacion'").fetchall()
            if not en_reparacion:
                st.info("No hay refacciones en reparación.")
            else:
                for ref_id, nombre, cant in en_reparacion:
                    st.markdown(f"**{nombre} (Cantidad: {cant})**")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"Liberar {ref_id}", key=f"lib_{ref_id}"):
                            c.execute("UPDATE refacciones SET estado = 'disponible' WHERE id = ?", (ref_id,))
                            conn.commit()
                            st.success("Refacción liberada.")
                            st.rerun()
                    with col2:
                        if st.button(f"Eliminar {ref_id}", key=f"elim_{ref_id}"):
                            c.execute("UPDATE refacciones SET estado = 'eliminada' WHERE id = ?", (ref_id,))
                            conn.commit()
                            st.warning("Refacción eliminada.")
                            st.rerun()
                            
        with st.expander("Historial por refacción o máquina"):
            tab1, tab2 = st.tabs(["Por refacción", "Por máquina"])

            with tab1:
                busq_ref = st.text_input("Buscar refacción por nombre exacto")
                if busq_ref:
                    datos = pd.read_sql_query("""
                        SELECT m.fecha, e.codigo AS usuario, r.nombre, m.cantidad, m.maquina
                        FROM movimientos m
                        JOIN empleados e ON m.empleado_id = e.id
                        JOIN refacciones r ON m.refaccion_id = r.id
                        WHERE r.nombre = ?
                        ORDER BY m.fecha DESC
                    """, conn, params=(busq_ref,))
                    if not datos.empty:
                        st.dataframe(datos, use_container_width=True)
                        total = datos["cantidad"].sum()
                        st.success(f"Total retirado históricamente: {total}")
                    else:
                        st.info("No hay retiros registrados para esa refacción.")

            with tab2:
                maq_sel = st.selectbox("Selecciona una máquina", ["Máquina 1", "Máquina 2", "Máquina 3", "Máquina 4"])
                datos_m = pd.read_sql_query("""
                    SELECT m.fecha, e.codigo AS usuario, r.nombre AS refaccion, m.cantidad
                    FROM movimientos m
                    JOIN empleados e ON m.empleado_id = e.id
                    JOIN refacciones r ON m.refaccion_id = r.id
                    WHERE m.maquina = ?
                    ORDER BY m.fecha DESC
                """, conn, params=(maq_sel,))
                if not datos_m.empty:
                    st.dataframe(datos_m, use_container_width=True)
                else:
                    st.info("No hay movimientos para esa máquina.")

    def menu_empleado():
        st.markdown("""
            <style>
            .ref-card {
                background-color: #f0f4f7;
                padding: 1rem;
                border-radius: 10px;
                margin-bottom: 1rem;
                box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
            }
            .ref-card h4 {
                color: #00264d;
                margin-bottom: 0.5rem;
            }
            </style>
        """, unsafe_allow_html=True)

        st.subheader("Solicitar refacción")

        busqueda = st.text_input("Escribe parte del nombre de la refacción:")

        if busqueda:
            resultados = c.execute("""
                SELECT id, nombre, cantidad 
                FROM refacciones 
                WHERE nombre LIKE ? AND estado = 'disponible'
            """, (f"%{busqueda}%",)).fetchall()

            if resultados:
                st.markdown("### Coincidencias encontradas:")
                for ref_id, nombre, cant_disp in resultados:
                    st.markdown(f"""
                        <div class="ref-card">
                            <h4>{nombre}</h4>
                            <p><strong>Disponibles:</strong> {cant_disp}</p>
                    """, unsafe_allow_html=True)

                    with st.form(f"form_{ref_id}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            cantidad = st.number_input("Cantidad", min_value=1, max_value=cant_disp, key=f"cant_{ref_id}")
                        with col2:
                            maquina = st.selectbox("Máquina", ["Máquina 1", "Máquina 2", "Máquina 3", "Máquina 4"], key=f"maq_{ref_id}")

                        if st.form_submit_button("Solicitar"):
                            existe = c.execute(
                                "SELECT * FROM solicitudes WHERE empleado_id = ? AND refaccion_id = ?",
                                (st.session_state.usuario_id, ref_id)
                            ).fetchone()
                            if existe:
                                st.warning("Ya existe una solicitud pendiente para esta refacción.")
                            else:
                                c.execute("""
                                    INSERT INTO solicitudes 
                                    (empleado_id, refaccion_id, cantidad, fecha, maquina) 
                                    VALUES (?, ?, ?, ?, ?)""",
                                    (st.session_state.usuario_id, ref_id, cantidad,
                                     datetime.now().strftime("%Y-%m-%d %H:%M"), maquina)
                                )
                                conn.commit()
                                st.success(f"Solicitud enviada para: {nombre}")
                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.warning("No se encontraron refacciones con ese nombre.")

        st.markdown("---")
        st.subheader("Sugerir nueva refacción")
        with st.form("form_sugerencia"):
            nombre = st.text_input("Nombre sugerido")
            comentario = st.text_area("Comentario o justificación")
            if st.form_submit_button("Enviar sugerencia"):
                c.execute("""
                    INSERT INTO sugerencias 
                    (empleado_id, nombre_refaccion, comentario, fecha) 
                    VALUES (?, ?, ?, ?)""",
                    (st.session_state.usuario_id, nombre, comentario, datetime.now().strftime("%Y-%m-%d %H:%M"))
                )
                conn.commit()
                st.success("Sugerencia enviada correctamente.")


    if st.session_state.rol == "admin":
        menu_admin()
    else:
        menu_empleado()
