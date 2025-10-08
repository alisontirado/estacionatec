import os
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Usuarios, Vehiculos, Pagos, CodigosQr, RegistroAcceso
from datetime import datetime

# --- Configuración de la Base de Datos ---
# Se utiliza PostgreSQL y se toman las credenciales de variables de entorno o valores por defecto.
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "estacionatec")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "12345")
DB_PORT = os.environ.get("DB_PORT", "5432")

# --- Inicialización de la Aplicación ---
app = Flask(__name__)
# Configuración de la URI de la base de datos para Flask-SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Clave secreta para la sesión de Flask (IMPORTANTE: ¡Cambiar en producción!)
app.config['SECRET_KEY'] = secrets.token_hex(16)

# Inicializar la base de datos y el administrador con la aplicación Flask
db.init_app(app)
admin = Admin(app, name='EstacionaTec Admin', template_mode='bootstrap3', url='/admin')

# --- Clases de Vista de Flask-Admin ---
class ProtectedModelView(ModelView):
    """
    Vista base para los modelos en el panel de administración.
    Solo accesible si el usuario ha iniciado sesión y es administrador.
    """
    def is_accessible(self):
        # Asegura que solo el administrador pueda acceder a estas vistas
        return 'logged_in' in session and session.get('is_admin', False)

    # Configuración de columnas visibles y editables (opcional, pero recomendado)
    column_exclude_list = ['contraseña']
    form_excluded_columns = ['contraseña']

    def on_model_change(self, form, model, is_created):
        # Manejo especial para el campo de contraseña
        if is_created and hasattr(model, 'contraseña'):
             # Al crear, si hay un campo de contraseña en el formulario (aunque no se muestre)
            if form.contraseña.data:
                model.contraseña = generate_password_hash(form.contraseña.data)
        elif not is_created and 'contraseña' in form:
            # Al editar, si el campo de contraseña se modifica, hashear la nueva
            if form.contraseña.data:
                model.contraseña = generate_password_hash(form.contraseña.data)
            else:
                # Si el campo se deja vacío al editar, mantener la contraseña anterior
                delattr(form, 'contraseña')

# --- Registro de Vistas en Flask-Admin ---
admin.add_view(ProtectedModelView(Usuarios, db.session, name='Usuarios'))
admin.add_view(ProtectedModelView(Vehiculos, db.session, name='Vehículos'))
admin.add_view(ProtectedModelView(Pagos, db.session, name='Pagos'))
admin.add_view(ProtectedModelView(CodigosQr, db.session, name='Códigos QR'))
admin.add_view(ProtectedModelView(RegistroAcceso, db.session, name='Registros de Acceso'))

# --- Rutas de la Aplicación ---

@app.route('/')
def inicio_sesion():
    # Ruta de inicio, muestra el formulario de login.
    return render_template('iniciosesion.html')

@app.route('/perfil_usuario', methods=['GET', 'POST'])
def perfil_usuario():
    # Esta ruta gestiona el inicio de sesión del usuario.
    nombre_usuario = request.form.get('nombre_usuario') or request.args.get('nombre_usuario')
    contraseña = request.form.get('contraseña') or request.args.get('contraseña')

    if not nombre_usuario or not contraseña:
        return redirect(url_for('inicio_sesion'))

    # Se busca el usuario por nombre_usuario (que ahora será 'admin@tec.edu' para el admin)
    user = Usuarios.query.filter_by(nombre_usuario=nombre_usuario).first()

    if user and check_password_hash(user.contraseña, contraseña):
        session['logged_in'] = True
        session['user_id'] = user.usuario_id
        
        # 1. Definir si es Administrador (ahora se verifica contra 'admin@tec.edu')
        ADMIN_USERNAME = 'admin@tec.edu'
        is_admin = (user.nombre_usuario.lower() == ADMIN_USERNAME)
        session['is_admin'] = is_admin

        # 2. Redirección basada en el tipo de usuario/administrador
        if is_admin:
            # Si es el administrador, redirigir al panel de Flask-Admin
            return redirect(url_for('admin.index'))
        
        elif user.tipo_usuario:  # TRUE: Estudiante
            return render_template('homeusuarios.html', usuario=user, titulo_pagina="Estacionatec Estudiantes")
        
        else:  # FALSE: Profesor/Seguridad
            return render_template('homevigilantes.html', usuario=user, titulo_pagina="Estacionatec Vigilancia")
    
    # Si las credenciales son inválidas
    return "Credenciales inválidas. <a href='/'>Volver</a>"


@app.route('/registro_usuario', methods=['GET', 'POST'])
def registro_usuario():
    if request.method == 'POST':
        # Hashear la contraseña antes de guardarla
        hashed_password = generate_password_hash(request.form['contraseña'])
        
        # Separar el nombre completo
        nombre_completo = request.form['nombre_completo'].split()
        
        # Crear nuevo usuario
        new_user = Usuarios(
            nombre_usuario=request.form['nombre_usuario'],
            contraseña=hashed_password,
            tipo_usuario=request.form['tipo_usuario'] == 'TRUE',
            nombres=nombre_completo[0],
            apellido_paterno=nombre_completo[1],
            # Manejar si el apellido materno no se proporciona
            apellido_materno=nombre_completo[2] if len(nombre_completo) > 2 else '', 
            correo_electronico=request.form['correo_electronico'],
            telefono=request.form['telefono'],
            rfc_o_num_control=request.form['rfc_num_control'],
            carrera=request.form.get('carrera') if request.form['tipo_usuario'] == 'TRUE' else None
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('inicio_sesion'))
        except Exception as e:
            # En caso de error (ej. nombre de usuario o correo duplicado)
            db.session.rollback()
            return f"Error al registrar usuario: {e}. <a href='/registro_usuario'>Volver a intentar</a>"
            
    return render_template('registro.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('inicio_sesion'))

# --- Rutas de Usuario (Estudiante/Profesor) ---

@app.route('/miperfil')
def mi_perfil():
    if 'user_id' not in session:
        return redirect(url_for('inicio_sesion'))
    
    user = Usuarios.query.get(session['user_id'])
    # Se añade un placeholder de URL de foto, ya que no existe en el modelo base
    user.foto_url = url_for('static', filename='placeholder.png') 
    return render_template('perfilusuario.html', usuario=user, titulo_pagina="Mi Perfil")

@app.route('/resumen/pago')
def resumen_pago():
    if 'user_id' not in session:
        return redirect(url_for('inicio_sesion'))

    user_id = session['user_id']
    # Se obtienen todos los pagos del usuario
    pagos = Pagos.query.filter_by(usuario_id=user_id).all()
    # Se mapean los datos para la plantilla (recibo, concepto, cantidad, fecha, archivo)
    pagos_data = [(p.numero_recibo, p.concepto, p.cantidad, p.fecha_pago, p.ruta_prueba_pago) for p in pagos]
    
    return render_template('pago.html', pagos=pagos_data, titulo_pagina="Historial de Pagos")

@app.route('/carga/vehiculo')
def carga_vehiculo():
    if 'user_id' not in session:
        return redirect(url_for('inicio_sesion'))
    # Lógica para cargar vehículos (pendiente de implementar POST)
    return render_template('cag_vehiculo.html', titulo_pagina="Carga de Vehículo")

# --- Rutas de Seguridad (Vigilancia) ---

@app.route('/scanner')
def scanner():
    if 'user_id' not in session:
        return redirect(url_for('inicio_sesion'))
    # Solo los usuarios de tipo Profesor/Seguridad deberían acceder aquí
    user = Usuarios.query.get(session['user_id'])
    # Si es estudiante (tipo_usuario=True), no puede acceder
    if user and user.tipo_usuario: 
        return redirect(url_for('mi_perfil')) 
        
    return render_template('qr.html', titulo_pagina="Scanner QR")

@app.route('/obtener_info/<placa>')
def obtener_info(placa):
    """API para que el scanner QR obtenga la información del vehículo."""
    vehiculo = Vehiculos.query.filter_by(placa=placa).first()
    
    if vehiculo and vehiculo.propietario.esta_activo:
        estado = "Activo"
        # Asumiendo que hay una columna para la foto de perfil del usuario
        imagen_conductor_url = url_for('static', filename='placeholder_user.png')
        
        return jsonify({
            'placas': vehiculo.placa,
            'modelo': vehiculo.tipo_vehiculo,
            'estado': estado,
            'imagen_vehiculo': vehiculo.ruta_foto_vehiculo or url_for('static', filename='placeholder_car.png'),
            'imagen_conductor': imagen_conductor_url
        })
    elif vehiculo:
        return jsonify({'error': 'Vehículo Registrado pero Usuario Inactivo'}), 403
    else:
        return jsonify({'error': 'Vehículo no encontrado'}), 404

# --- Ejecución de la Aplicación ---

if __name__ == '__main__':
    with app.app_context():
        # Crear las tablas en la base de datos si no existen
        db.create_all()
        
        # --- Creación de la cuenta de administrador inicial (opcional) ---
        ADMIN_USERNAME_ID = 'admin@tec.edu'
        ADMIN_PASSWORD_RAW = '12345'

        # Verifica si el usuario 'admin@tec.edu' existe, si no, lo crea.
        if Usuarios.query.filter_by(nombre_usuario=ADMIN_USERNAME_ID).first() is None:
            admin_user = Usuarios(
                nombre_usuario=ADMIN_USERNAME_ID,
                # Contraseña hasheada para '12345'
                contraseña=generate_password_hash(ADMIN_PASSWORD_RAW), 
                tipo_usuario=False, # No es estudiante (Staff/Seguridad)
                nombres='Admin',
                apellido_paterno='Principal',
                apellido_materno='Tec',
                correo_electronico=ADMIN_USERNAME_ID,
                rfc_o_num_control='ADMINTEC001',
                fecha_registro=datetime.utcnow()
            )
            db.session.add(admin_user)
            db.session.commit()
            print(f"¡Cuenta de Administrador '{ADMIN_USERNAME_ID}' creada con contraseña '{ADMIN_PASSWORD_RAW}'!")
            
    app.run(debug=True)
