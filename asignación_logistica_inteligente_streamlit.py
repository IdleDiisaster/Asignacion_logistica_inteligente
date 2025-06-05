import streamlit as st
import pandas as pd
import sqlite3

def ejecutar_sql(query):
    conn = sqlite3.connect('db_envios.db.db')
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def main():
    st.title("Asignador de Proveedores de Envío")

    opcion = st.radio("¿Cómo quieres ingresar los datos del producto?", ["Por ID de producto", "Manual"])

    largo = ancho = alto = peso_real = m3 = CP_DESTINO = None

    if opcion == "Por ID de producto":
        ID_PRODUCTO = st.text_input("ID del producto")
        CP_DESTINO = st.text_input("Código Postal de destino").zfill(5)

        if ID_PRODUCTO and CP_DESTINO:
            query_producto = f"SELECT * FROM productos WHERE ID_PRODUCTO = '{ID_PRODUCTO}'"
            df_producto = ejecutar_sql(query_producto)

            if not df_producto.empty:
                producto = df_producto.iloc[0]
                largo = producto['LARGO_CM']
                ancho = producto['ANCHO_CM']
                alto = producto['ALTO_CM']
                peso_real = producto['PESO_KG']
                m3 = producto['M3']
            else:
                st.warning("❌ Producto no encontrado.")

    elif opcion == "Manual":
        CP_DESTINO = st.text_input("Código Postal de destino").zfill(5)
        largo = st.number_input("Largo (cm)", min_value=0.0, format="%.2f")
        ancho = st.number_input("Ancho (cm)", min_value=0.0, format="%.2f")
        alto = st.number_input("Alto (cm)", min_value=0.0, format="%.2f")
        peso_real = st.number_input("Peso real (kg)", min_value=0.0, format="%.2f")
        m3 = (largo * ancho * alto) / 1_000_000 if largo and ancho and alto else None

    if all([CP_DESTINO, largo, ancho, alto, peso_real, m3]):
        peso_vol = max(peso_real, (largo * ancho * alto) / 5000)

        st.markdown(f"""
        ### 📦 Datos del envío
        - **Dimensiones**: {largo}x{ancho}x{alto} cm
        - **Peso real**: {peso_real:.2f} kg
        - **Peso volumétrico**: {peso_vol:.2f} kg
        - **Volumen (m³)**: {m3:.3f}
        """)

        query_dimensiones = f"""
        SELECT * FROM cobertura_transportistas
        WHERE cp = '{CP_DESTINO}'
        AND (validacion_tipo = 'DIMENSIONES' OR validacion_tipo IS NULL)
        AND largo_max_cm >= {largo}
        AND ancho_max_cm >= {ancho}
        AND alto_max_cm >= {alto}
        AND peso_max_kg >= {peso_real}
        """
        query_volumen = f"""
        SELECT * FROM cobertura_transportistas
        WHERE cp = '{CP_DESTINO}'
        AND validacion_tipo = 'VOLUMEN'
        AND peso_max_kg >= {peso_real}
        AND volumen_max_m3 >= {m3}
        """
        df_dimensiones = ejecutar_sql(query_dimensiones)
        df_volumen = ejecutar_sql(query_volumen)
        df_cobertura = pd.concat([df_dimensiones, df_volumen], ignore_index=True)

        if df_cobertura.empty:
            st.error("❌ Ningún proveedor cubre este código postal o acepta el producto.")
            return

        proveedores = df_cobertura['proveedor'].unique().tolist()
        query_tarifas = f"""
        SELECT * FROM tarifas_envio
        WHERE proveedor IN ({','.join(f"'{p}'" for p in proveedores)})
        """
        df_tarifas = ejecutar_sql(query_tarifas)

        opciones_envio = []

        for _, row in df_cobertura.iterrows():
            proveedor = row['proveedor']
            zona = row['zona']
            periodicidad = row['periodicidad']

            tarifas_prov_zona = df_tarifas[(df_tarifas['proveedor'] == proveedor) & (df_tarifas['zona'] == zona)]

            tarifas_volumetricas = tarifas_prov_zona[tarifas_prov_zona['tipo_tarifa'] == 'volumetrico']
            for _, tarifa_vol in tarifas_volumetricas.iterrows():
                peso_a_usar = max(peso_real, peso_vol)
                if tarifa_vol['rango_peso_min'] <= peso_a_usar <= tarifa_vol['rango_peso_max']:
                    adicional = 0
                    if pd.notna(tarifa_vol['umbral_kg_adicional']) and peso_a_usar > tarifa_vol['umbral_kg_adicional']:
                        adicional = (peso_a_usar - tarifa_vol['umbral_kg_adicional']) * tarifa_vol['costo_kg_adicional']
                    costo_envio = tarifa_vol['precio_base'] + adicional
                    opciones_envio.append({
                        'proveedor': proveedor,
                        'zona': zona,
                        'tipo_tarifa': 'volumetrico',
                        'precio_envio': costo_envio,
                        'periodicidad': periodicidad
                    })

            tarifas_m3 = tarifas_prov_zona[tarifas_prov_zona['tipo_tarifa'].str.lower() == 'm3'].sort_values(by=['rango_peso_min'])
            tarifa_m3_valida = None
            for _, fila_tarifa_m3 in tarifas_m3.iterrows():
                excede_peso = peso_real > fila_tarifa_m3['rango_peso_max'] if pd.notna(fila_tarifa_m3['rango_peso_max']) else False
                excede_m3 = m3 > fila_tarifa_m3['m3_amparado'] if pd.notna(fila_tarifa_m3['m3_amparado']) else False
                if not (excede_peso or excede_m3):
                    tarifa_m3_valida = fila_tarifa_m3
                    break

            if tarifa_m3_valida is not None:
                opciones_envio.append({
                    'proveedor': proveedor,
                    'zona': zona,
                    'tipo_tarifa': 'm3',
                    'precio_envio': round(tarifa_m3_valida['precio_base'], 2),
                    'periodicidad': periodicidad
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
