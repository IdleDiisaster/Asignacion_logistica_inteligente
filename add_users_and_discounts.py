import sqlite3
import hashlib

def agregar_usuarios_y_descuentos():
    conn = sqlite3.connect('db_envios.db.db')
    cursor = conn.cursor()

    # 1. Crear la tabla de usuarios
    print("Creando tabla 'usuarios'...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id_usuario INTEGER PRIMARY KEY,
            nombre_usuario TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)
    
    # Insertar usuarios de prueba si no existen
    password_hash = hashlib.sha256("testpass".encode()).hexdigest()
    try:
        cursor.execute("INSERT INTO usuarios (nombre_usuario, password_hash) VALUES (?, ?)", ('testuser', password_hash))
        print("Usuario 'testuser' creado.")
    except sqlite3.IntegrityError:
        print("Usuario 'testuser' ya existe. Omitiendo inserción.")
        
    password_hash_admin = hashlib.sha256("adminpass".encode()).hexdigest()
    try:
        cursor.execute("INSERT INTO usuarios (nombre_usuario, password_hash) VALUES (?, ?)", ('admin', password_hash_admin))
        print("Usuario 'admin' creado.")
    except sqlite3.IntegrityError:
        print("Usuario 'admin' ya existe.")

    # 2. Crear la tabla de descuentos de usuario
    print("Creando tabla 'descuentos_usuario'...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS descuentos_usuario (
            id_descuento INTEGER PRIMARY KEY,
            id_usuario INTEGER,
            proveedor TEXT,
            descuento_porcentaje REAL NOT NULL,
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
        )
    """)

    # Insertar descuentos de prueba
    cursor.execute("SELECT id_usuario FROM usuarios WHERE nombre_usuario = 'testuser'")
    user_id = cursor.fetchone()[0]

    # --- CAMBIO AQUI ---
    # Actualizar los nombres de los proveedores para que coincidan con tu base de datos
    descuentos_data = [
        ('PROVEEDOR 1', 0.10), # 10% de descuento
        ('PROVEEDOR 2', 0.05), # 5% de descuento
        ('PROVEEDOR 3', 0.15), # 15% de descuento
        ('PROVEEDOR 4', 0.20) # 20% de descuento
    ]
    
    for proveedor_descuento, porcentaje in descuentos_data:
        # Prevenir inserciones duplicadas de descuentos para el mismo usuario y proveedor
        cursor.execute("SELECT COUNT(*) FROM descuentos_usuario WHERE id_usuario = ? AND proveedor = ?", (user_id, proveedor_descuento))
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO descuentos_usuario (id_usuario, proveedor, descuento_porcentaje) VALUES (?, ?, ?)", (user_id, proveedor_descuento, porcentaje))
            print(f"Descuento para el usuario ID {user_id} y proveedor '{proveedor_descuento}' creado.")
        else:
            print(f"Descuento para el usuario ID {user_id} y proveedor '{proveedor_descuento}' ya existe. Omitiendo inserción.")

    conn.commit()
    conn.close()
    print("¡Tablas 'usuarios' y 'descuentos_usuario' y sus datos de prueba creados exitosamente!")

if __name__ == '__main__':
    agregar_usuarios_y_descuentos()