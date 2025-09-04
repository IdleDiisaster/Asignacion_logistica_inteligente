import sqlite3

def actualizar_columna_zona():
    conn = sqlite3.connect('db_envios.db.db')
    cursor = conn.cursor()

    try:
        # SQL command to update the 'zona' column for all existing rows
        cursor.execute("UPDATE descuentos_usuario SET zona = '1'")
        conn.commit()
        print("✅ Columna 'zona' actualizada en todos los registros.")
    except sqlite3.OperationalError as e:
        print(f"❌ Error al actualizar la columna: {e}")
        
    conn.close()

if __name__ == '__main__':
    actualizar_columna_zona()