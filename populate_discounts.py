import sqlite3

def populate_discounts():
    conn = sqlite3.connect('db_envios.db.db')
    cursor = conn.cursor()

    try:
        # Obtener el id_usuario del 'testuser'
        cursor.execute("SELECT id_usuario FROM usuarios WHERE nombre_usuario = 'testuser'")
        user_id = cursor.fetchone()[0]

        # Limpiar la tabla para evitar duplicados en la prueba
        cursor.execute("DELETE FROM descuentos_usuario WHERE id_usuario = ?", (user_id,))

        # Insertar los descuentos de prueba
        descuentos_data = [
            (user_id, 'PROVEEDOR 1', 0.10, '1'),
            (user_id, 'PROVEEDOR 2', 0.15, '1'),
            (user_id, 'PROVEEDOR 3', 0.25, '1'),
            (user_id, 'PROVEEDOR 4', 0.10, '1'),
        ]

        cursor.executemany("INSERT INTO descuentos_usuario (id_usuario, proveedor, descuento_porcentaje, zona) VALUES (?, ?, ?, ?)", descuentos_data)
        conn.commit()
        print("✅ Datos de descuentos de prueba re-insertados exitosamente.")

    except Exception as e:
        print(f"❌ Ocurrió un error al insertar los datos de descuento: {e}")
        conn.rollback()

    finally:
        conn.close()

if __name__ == '__main__':
    populate_discounts()