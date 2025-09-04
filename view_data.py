import sqlite3
import pandas as pd

def ver_datos_tablas():
    conn = sqlite3.connect('db_envios.db.db')

    tablas = [
        'usuarios',
        'descuentos_usuario',
        'cobertura_transportistas',
        'tarifas_envio',
    ]

    for tabla in tablas:
        print(f"--- Datos de la tabla '{tabla}' ---")
        try:
            df = pd.read_sql_query(f"SELECT * FROM {tabla}", conn)
            if df.empty:
                print("La tabla está vacía.")
            else:
                print(df)
        except pd.io.sql.DatabaseError as e:
            print(f"Error al leer la tabla: {e}")
        print("\n")

    conn.close()

if __name__ == '__main__':
    ver_datos_tablas()