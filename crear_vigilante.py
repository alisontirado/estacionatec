from app import app, db
from models import Usuarios
from werkzeug.security import generate_password_hash
from datetime import datetime

def crear_vigilante():
    with app.app_context():
        try:
            # Verificar si el vigilante ya existe
            if Usuarios.query.filter_by(nombre_usuario='vig_guardia1').first():
                print("⚠️ El usuario vigilante ya existe")
                return
            
            # Crear nuevo vigilante
            vigilante = Usuarios(
                nombre_usuario='vig_guardia1',
                contraseña=generate_password_hash('12345'),
                tipo_usuario=False,  # Staff (no estudiante)
                nombres='Juan',
                apellido_paterno='Vigilante',
                apellido_materno='Seguridad',
                correo_electronico='vigilante@tec.edu',
                telefono='1234567890',
                rfc_o_num_control='VIG001',
                carrera=None,  # Los vigilantes no tienen carrera
                fecha_registro=datetime.utcnow(),
                esta_activo=True
            )
            
            db.session.add(vigilante)
            db.session.commit()
            print("✅ Vigilante creado exitosamente")
            print("Usuario: vig_guardia1")
            print("Contraseña: 12345")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error al crear vigilante: {e}")

if __name__ == '__main__':
    crear_vigilante()