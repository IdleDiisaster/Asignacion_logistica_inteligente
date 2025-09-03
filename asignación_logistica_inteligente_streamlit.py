import streamlit as st
import pandas as pd
import sqlite3

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
    
def main():
    # Cargar SKUs disponibles desde la base de datos
    df_skus = ejecutar_sql("SELECT ID_PRODUCTO FROM productos")
    lista_skus = df_skus['ID_PRODUCTO'].dropna().unique().tolist()

    # Sidebar con SKUs
    with st.sidebar:
        st.header("📦 Productos disponibles")
        sku_seleccionado = st.selectbox("Selecciona un SKU", options=[""] + lista_skus)
        st.title("Asignador de Proveedores de Envío")
    
    opcion = st.radio("¿Cómo quieres ingresar los datos del producto?", ["Por ID de producto", "Manual"])
    largo = ancho = alto = peso_real = m3 = CP_DESTINO = None
    
    ID_PRODUCTO = None  # Inicializar ID_PRODUCTO aquí
    
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
        peso_max = max(peso_real, peso_vol)

        st.markdown(f"""
        ### 📦 Datos del envío
        - **Dimensiones**: {largo}x{ancho}x{alto} cm
        - **Peso real**: {peso_real:.2f} kg
        - **Peso volumétrico**: {peso_vol:.2f} kg
        - **Peso Max**: {peso_max:.2f} kg
        - **Volumen (m³)**: {m3:.3f}
        """)

        # Consulta única para obtener cobertura y tarifas con un JOIN
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
        
        # Parámetros para la consulta de dimensiones
        params_dimensiones = (CP_DESTINO, largo, ancho, alto, peso_real)
        df_opciones_dimensiones = ejecutar_sql(query_cobertura_tarifas, params=params_dimensiones)

        # Consulta para validación por volumen
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
        
        # Parámetros para la consulta de volumen
        params_volumen = (CP_DESTINO, peso_real, m3)
        df_opciones_volumen = ejecutar_sql(query_cobertura_volumen, params=params_volumen)
        
        # Unir los resultados
        df_cobertura_tarifas = pd.concat([df_opciones_dimensiones, df_opciones_volumen], ignore_index=True)

        if df_cobertura_tarifas.empty:
            st.error("❌ No se encontraron opciones de envío viables con tarifas aplicables.")
            return

        # Calcular el costo de envío directamente desde el DataFrame
        opciones_envio = []
        for _, row in df_cobertura_tarifas.iterrows():
            if row['tipo_tarifa'] == 'volumetrico':
                peso_a_usar = max(peso_real, peso_vol)
                if row['rango_peso_min'] <= peso_a_usar <= row['rango_peso_max']:
                    adicional = 0
                    if pd.notna(row['umbral_kg_adicional']) and peso_a_usar > row['umbral_kg_adicional']:
                        adicional = (peso_a_usar - row['umbral_kg_adicional']) * row['costo_kg_adicional']
                    costo_envio = row['precio_base'] + adicional
                    opciones_envio.append({
                        'proveedor': row['proveedor'],
                        'zona': row['zona'],
                        'tipo_tarifa': 'volumetrico',
                        'precio_envio': costo_envio,
                        'periodicidad': row['periodicidad']
                    })
            
            elif row['tipo_tarifa'].lower() == 'm3':
                excede_peso = peso_real > row['rango_peso_max'] if pd.notna(row['rango_peso_max']) else False
                excede_m3 = m3 > row['m3_amparado'] if pd.notna(row['m3_amparado']) else False
                
                if not (excede_peso or excede_m3):
                    opciones_envio.append({
                        'proveedor': row['proveedor'],
                        'zona': row['zona'],
                        'tipo_tarifa': 'm3',
                        'precio_envio': round(row['precio_base'], 2),
                        'periodicidad': row['periodicidad']
                    })

        if not opciones_envio:
            st.error("❌ No se encontraron opciones de envío viables con tarifas aplicables.")
            return

        df_opciones = pd.DataFrame(opciones_envio)
        df_opciones = df_opciones.sort_values('precio_envio').reset_index(drop=True)

        st.success("✅ Opciones viables ordenadas por precio:")
        st.dataframe(df_opciones[['proveedor', 'zona', 'tipo_tarifa', 'precio_envio', 'periodicidad']])

if __name__ == "__main__":
    main()
