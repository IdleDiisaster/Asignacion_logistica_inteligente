import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import math

# --- LÓGICA DE AUTENTICACIÓN ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'user_id' not in st.session_state:
    st.session_state.user_id = None

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def ejecutar_sql(query, params=()):
    conn = sqlite3.connect('db_envios.db.db')
    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception as e:
        st.error(f"Error al ejecutar la consulta: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def get_discounts(user_id):
    if user_id is None:
        return pd.DataFrame()
    user_id_str = str(user_id)
    query = "SELECT proveedor, descuento_porcentaje, zona FROM descuentos_usuario WHERE id_usuario = ?"
    return ejecutar_sql(query, params=(user_id,))

def authenticate():
    st.sidebar.header("🔑 Acceso")
    username = st.sidebar.text_input("Nombre de usuario")
    password = st.sidebar.text_input("Contraseña", type="password")
    
    if st.sidebar.button("Iniciar Sesión"):
        hashed_password = hash_password(password)
        query = "SELECT id_usuario, nombre_usuario FROM usuarios WHERE nombre_usuario = ? AND password_hash = ?"
        user_df = ejecutar_sql(query, params=(username, hashed_password))
        if not user_df.empty:
            st.session_state.authenticated = True
            st.session_state.username = user_df.iloc[0]['nombre_usuario']
            st.session_state.user_id = int(user_df.iloc[0]['id_usuario'])
            st.rerun()
        else:
            st.sidebar.error("Nombre de usuario o contraseña incorrectos.")

def main_app():
    df_skus = ejecutar_sql("SELECT ID_PRODUCTO FROM productos")
    lista_skus = df_skus['ID_PRODUCTO'].dropna().unique().tolist()
    
    with st.sidebar:
        st.header(f"¡Hola, {st.session_state.username}!")
        st.header("📦 Productos disponibles")
        sku_seleccionado = st.selectbox("Selecciona un SKU", options=[""] + lista_skus)
        st.title("Asignador de Proveedores de Envío")
        if st.button("Cerrar Sesión"):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.session_state.user_id = None
            st.rerun()

    opcion = st.radio("¿Cómo quieres ingresar los datos del producto?", ["Por ID de producto", "Manual"])
    largo = ancho = alto = peso_real = m3 = CP_DESTINO = None
    ID_PRODUCTO = None
    
    if opcion == "Por ID de producto":
        ID_PRODUCTO = sku_seleccionado
        CP_DESTINO = st.text_input("Código Postal de destino").zfill(5)
        if ID_PRODUCTO and CP_DESTINO:
            query_producto = "SELECT * FROM productos WHERE ID_PRODUCTO = ?"
            df_producto = ejecutar_sql(query_producto, params=(ID_PRODUCTO,))
            if not df_producto.empty:
                producto = df_producto.iloc[0]
                largo = float(producto['LARGO_CM'])
                ancho = float(producto['ANCHO_CM'])
                alto = float(producto['ALTO_CM'])
                peso_real = float(producto['PESO_KG'])
                m3 = float(producto['M3'])
            else:
                st.warning("❌ Producto no encontrado.")
    elif opcion == "Manual":
        CP_DESTINO = st.text_input("Código Postal de destino").zfill(5)
        largo = st.number_input("Largo (cm)", min_value=0.0, format="%.2f")
        ancho = st.number_input("Ancho (cm)", min_value=0.0, format="%.2f")
        alto = st.number_input("Alto (cm)", min_value=0.0, format="%.2f")
        peso_real = st.number_input("Peso real (kg)", min_value=0.0, format="%.2f")
        m3 = (largo * ancho * alto) / 1_000_000 if all([largo, ancho, alto]) else None

    if all([CP_DESTINO, largo, ancho, alto, peso_real, m3]):
        peso_vol = (largo * ancho * alto) / 5000
        
        # Redondeamos el peso_max al siguiente entero.
        peso_max = math.ceil(max(peso_real, peso_vol))

        st.markdown(f"""
        ### 📦 Datos del envío
        - **Dimensiones**: {largo}x{ancho}x{alto} cm
        - **Peso real**: {peso_real:.2f} kg
        - **Peso volumétrico**: {peso_vol:.2f} kg
        - **Peso a considerar (redondeado)**: {peso_max:.2f} kg
        - **Volumen (m³)**: {m3:.3f}
        """)
        
        query_cobertura_tarifas = """
        SELECT
            c.proveedor,
            c.zona,
            c.periodicidad,
            t.tipo_tarifa,
            t.rango_peso_min,
            t.rango_peso_max,
            t.m3_amparado,
            t.precio_base,
            t.umbral_kg_adicional,
            t.costo_kg_adicional
        FROM cobertura_transportistas AS c
        JOIN tarifas_envio AS t
            ON c.proveedor = t.proveedor
            AND c.zona = t.zona
        WHERE
            c.cp = ?
            AND (c.validacion_tipo = 'DIMENSIONES' OR c.validacion_tipo IS NULL)
            AND c.largo_max_cm >= ?
            AND c.ancho_max_cm >= ?
            AND c.alto_max_cm >= ?
            AND c.peso_max_kg >= ?
        """
        params_dimensiones = (CP_DESTINO, largo, ancho, alto, peso_real)
        df_opciones_dimensiones = ejecutar_sql(query_cobertura_tarifas, params=params_dimensiones)

        query_cobertura_volumen = """
        SELECT
            c.proveedor,
            c.zona,
            c.periodicidad,
            t.tipo_tarifa,
            t.rango_peso_min,
            t.rango_peso_max,
            t.m3_amparado,
            t.precio_base,
            t.umbral_kg_adicional,
            t.costo_kg_adicional
        FROM cobertura_transportistas AS c
        JOIN tarifas_envio AS t
            ON c.proveedor = t.proveedor
            AND c.zona = t.zona
        WHERE
            c.cp = ?
            AND c.validacion_tipo = 'VOLUMEN'
            AND c.peso_max_kg >= ?
            AND c.volumen_max_m3 >= ?
        """
        params_volumen = (CP_DESTINO, peso_real, m3)
        df_opciones_volumen = ejecutar_sql(query_cobertura_volumen, params=params_volumen)
        
        df_cobertura_tarifas = pd.concat([df_opciones_dimensiones, df_opciones_volumen], ignore_index=True)
        if df_cobertura_tarifas.empty:
            st.error("❌ No se encontraron opciones de envío viables con tarifas aplicables.")
            return

        # --- LÓGICA DE CÁLCULO DE COSTO Y MERGE ---
        
        df_filtrado = df_cobertura_tarifas.copy()
        df_filtrado['rango_peso_min'] = pd.to_numeric(df_filtrado['rango_peso_min'], errors='coerce')
        df_filtrado['rango_peso_max'] = pd.to_numeric(df_filtrado['rango_peso_max'], errors='coerce')
        df_filtrado['m3_amparado'] = pd.to_numeric(df_filtrado['m3_amparado'], errors='coerce')
        df_filtrado['precio_calculado'] = 0.0

        # Tarifa volumétrica
        volumetrico_cond = (df_filtrado['tipo_tarifa'] == 'volumetrico') & (df_filtrado['rango_peso_min'] <= peso_max) & (df_filtrado['rango_peso_max'] >= peso_max)
        df_volumetrico = df_filtrado[volumetrico_cond].copy()
        if not df_volumetrico.empty:
            df_volumetrico['precio_calculado'] = df_volumetrico['precio_base']
            cond_adicional = (peso_max > df_volumetrico['umbral_kg_adicional']) & pd.notna(df_volumetrico['umbral_kg_adicional'])
            if cond_adicional.any():
                df_volumetrico.loc[cond_adicional, 'precio_calculado'] += (peso_max - df_volumetrico['umbral_kg_adicional']) * df_volumetrico['costo_kg_adicional']
        
        # Tarifa m3
        m3_base = df_filtrado[df_filtrado['tipo_tarifa'] == 'm3'].copy()
        m3_base = m3_base.sort_values(by=['rango_peso_min'])
        
        m3_valid_cond = (m3_base['rango_peso_min'] <= peso_real) & (m3_base['rango_peso_max'] >= peso_real) & (m3_base['m3_amparado'] >= m3)
        
        df_m3 = pd.DataFrame()
        if m3_valid_cond.any():
            primer_match_idx = m3_valid_cond.idxmax()
            df_m3 = m3_base.loc[[primer_match_idx]].copy()
            df_m3['precio_calculado'] = df_m3['precio_base']

        # Unir las tarifas calculadas
        df_tarifas_calculadas = pd.concat([df_volumetrico, df_m3], ignore_index=True)

        if df_tarifas_calculadas.empty:
            st.error("❌ No se encontraron opciones de envío viables con tarifas aplicables.")
            return
        
        df_tarifas_calculadas = df_tarifas_calculadas.dropna(subset=['precio_calculado'])

        # Normalizar las columnas para el merge final
        df_tarifas_calculadas['proveedor'] = df_tarifas_calculadas['proveedor'].astype(str).str.strip().str.upper().str.replace(' ', '')
        df_tarifas_calculadas['zona'] = df_tarifas_calculadas['zona'].astype(str)

        # Obtener y normalizar los descuentos
        df_descuentos = get_discounts(st.session_state.user_id)
        df_descuentos['proveedor'] = df_descuentos['proveedor'].astype(str).str.strip().str.upper().str.replace(' ', '')
        df_descuentos['zona'] = df_descuentos['zona'].astype(str)

        # --- LÍNEAS DE DEPURACIÓN AGREGADAS ---
        st.write("---")
        st.write("### 🐛 Depuración de Descuentos")
        st.write(f"ID de Usuario: **{st.session_state.user_id}**")
        if df_descuentos.empty:
            st.warning("⚠️ El DataFrame de descuentos está vacío. El ID de usuario podría no tener descuentos.")
        else:
            st.write("DataFrame de descuentos (antes del merge):")
            st.dataframe(df_descuentos)
        st.write("---")
        # --- FIN DE LAS LÍNEAS DE DEPURACIÓN ---

        # Realizar el merge (unir) los dataframes
        df_final = pd.merge(df_tarifas_calculadas, df_descuentos, on=['proveedor', 'zona'], how='left')

        # Aplicar el descuento
        df_final['descuento_aplicado'] = df_final['descuento_porcentaje'].apply(lambda x: 'Sí' if pd.notna(x) else 'No')
        df_final['descuento_porcentaje'] = df_final['descuento_porcentaje'].fillna(0)
        df_final['precio_envio'] = df_final['precio_calculado'] * (1 - df_final['descuento_porcentaje'])

        # Formatear y mostrar el resultado
        df_opciones = df_final[['proveedor', 'zona', 'tipo_tarifa', 'precio_envio', 'periodicidad', 'descuento_aplicado']]
        df_opciones['precio_envio'] = df_opciones['precio_envio'].round(2)
        df_opciones = df_opciones.sort_values('precio_envio').reset_index(drop=True)

        st.success("✅ Opciones viables ordenadas por precio:")
        st.dataframe(df_opciones)

# --- Flujo principal de la aplicación ---
if not st.session_state.authenticated:
    st.title("Asignador de Proveedores de Envío - Iniciar Sesión")
    authenticate()
else:
    main_app()