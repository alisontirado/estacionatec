import os
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Usuarios, Vehiculos, Pagos, CodigosQr, RegistroAcceso
from datetime import datetime

# --- Configuración de la Base de Datos ---
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "estacionatec")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "12345")
DB_PORT = os.environ.get("DB_PORT", "5432")

# --- Inicialización de la Aplicación ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = secrets.token_hex(16)

# Inicializar la base de datos y el administrador
db.init_app(app)
admin = Admin(app, name='EstacionaTec Admin',  url='/admin')

# --- Clases de Vista de Flask-Admin ---
class ProtectedModelView(ModelView):
    def is_accessible(self):
        return 'logged_in' in session and session.get('is_admin', False)

    column_exclude_list = ['contraseña']
    form_excluded_columns = ['contraseña']

    def on_model_change(self, form, model, is_created):
        if is_created and hasattr(model, 'contraseña'):
            if form.contraseña.data:
                model.contraseña = generate_password_hash(form.contraseña.data)
        elif not is_created and 'contraseña' in form:
            if form.contraseña.data:
                model.contraseña = generate_password_hash(form.contraseña.data)
            else:
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
    # 🚨 CORRECCIÓN: Se usa 'iniciosesion.html' que es el archivo que subiste.
    return render_template('iniciosesion.html', titulo_pagina="Inicio de Sesión")


@app.route('/perfil_usuario', methods=['GET', 'POST'])
# 🚨 ESTA ES LA ÚNICA FUNCIÓN QUE DEBE EXISTIR EN app.py
def perfil_usuario():
    # Obtención de credenciales
    nombre_usuario = request.form.get('nombre_usuario') or request.args.get('nombre_usuario')
    contraseña = request.form.get('contraseña') or request.args.get('contraseña')

    if not nombre_usuario or not contraseña:
        return redirect(url_for('inicio_sesion'))

    user = Usuarios.query.filter_by(nombre_usuario=nombre_usuario).first()

    if user and check_password_hash(user.contraseña, contraseña):
        session['logged_in'] = True
        session['user_id'] = user.usuario_id
        
        # 1. Definir si es Administrador
        ADMIN_USERNAME = 'admin@tec.edu'
        is_admin = (user.nombre_usuario.lower() == ADMIN_USERNAME)
        session['is_admin'] = is_admin

        if is_admin:
            return redirect(url_for('admin.index'))
        
        
        # --- LÓGICA DE ROLES: Estudiante/Maestro vs. Vigilante ---
        
        # Identifica a Vigilantes por el prefijo en el nombre_usuario.
        is_vigilante = user.nombre_usuario.lower().startswith('vig_') or \
                       user.nombre_usuario.lower().startswith('seg_') or \
                       (user.nombre_usuario.lower() == 'usuario_seguridad_especial') 

        # 🚨 ROL VIGILANTE: Si tipo_usuario es FALSE (Staff) Y cumple el patrón de Vigilante
        if user.tipo_usuario == False and is_vigilante: 
            return render_template('homevigilantes.html', usuario=user, titulo_pagina="Estacionatec Vigilancia")
        
        # ✅ ROL UNIFICADO: Estudiante (TRUE) O Profesor (FALSE, pero SIN prefijo Vigilante)
        else: 
            return render_template('homeusuarios.html', usuario=user, titulo_pagina="Estacionatec Usuarios")
    
    # Si las credenciales son inválidas
    return "Credenciales inválidas. <a href='/'>Volver</a>"


@app.route('/registro_usuario', methods=['GET', 'POST'])
def registro_usuario():
    if request.method == 'POST':
        # 1. Obtener datos clave
        nombre_usuario_raw = request.form['nombre_usuario']
        # tipo_usuario_raw debe ser 'TRUE' (Estudiante) o 'FALSE' (Staff)
        tipo_usuario_raw = request.form['tipo_usuario'] 
        
        is_estudiante = tipo_usuario_raw == 'TRUE'
        
        # --- LÓGICA DE REGISTRO PARA VIGILANTE ---
        # El formulario debe enviar 'rol_staff_detalle' si el tipo_usuario es FALSE
        if not is_estudiante:
            rol_enviado = request.form.get('rol_staff_detalle') 
            
            # Si el rol enviado es 'vigilante'
            if rol_enviado and rol_enviado.lower() == 'vigilante':
                # Validar que el nombre de usuario cumpla la convención
                if not nombre_usuario_raw.lower().startswith('vig_') and \
                   not nombre_usuario_raw.lower().startswith('seg_'):
                    
                    return "Error de Registro: Los vigilantes deben usar un Nombre de Usuario que empiece con 'vig_' o 'seg_'. <a href='/registro_usuario'>Volver</a>"
            
        
        # 3. Proceder con el registro
        hashed_password = generate_password_hash(request.form['contraseña'])
        nombre_completo = request.form['nombre_completo'].split()
        
        # Asegurarse de que al menos haya 2 partes para nombre y apellido paterno
        nombres = nombre_completo[0]
        apellido_paterno = nombre_completo[1] if len(nombre_completo) > 1 else ''
        apellido_materno = nombre_completo[2] if len(nombre_completo) > 2 else ''
        
        new_user = Usuarios(
            nombre_usuario=nombre_usuario_raw, 
            contraseña=hashed_password,
            tipo_usuario=is_estudiante, # Se guarda TRUE o FALSE
            nombres=nombres,
            apellido_paterno=apellido_paterno,
            apellido_materno=apellido_materno,
            correo_electronico=request.form['correo_electronico'],
            telefono=request.form['telefono'],
            rfc_o_num_control=request.form['rfc_num_control'],
            carrera=request.form.get('carrera') if is_estudiante else None
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('inicio_sesion'))
        except Exception as e:
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
    user.foto_url = url_for('static', filename='placeholder.png') 
    return render_template('perfilusuario.html', usuario=user, titulo_pagina="Mi Perfil")

@app.route('/resumen/pago')
def resumen_pago():
    if 'user_id' not in session:
        return redirect(url_for('inicio_sesion'))

    user_id = session['user_id']
    pagos = Pagos.query.filter_by(usuario_id=user_id).all()
    pagos_data = [(p.numero_recibo, p.concepto, p.cantidad, p.fecha_pago, p.ruta_prueba_pago) for p in pagos]
    
    # 🚨 CORRECCIÓN DE NOMBRE DE PLANTILLA: Usa 'pago.html' o 'resumenpago.html' de forma consistente
    # Usaremos 'pago.html' ya que tiene lógica de listado.
    return render_template('pago.html', pagos=pagos_data, titulo_pagina="Historial de Pagos")

@app.route('/carga/vehiculo')
def carga_vehiculo():
    if 'user_id' not in session:
        return redirect(url_for('inicio_sesion'))
    return render_template('cag_vehiculo.html', titulo_pagina="Carga de Vehículo")

# --- Rutas de Seguridad (Vigilancia) ---

@app.route('/scanner')
def scanner():
    if 'user_id' not in session:
        return redirect(url_for('inicio_sesion'))
    
    user = Usuarios.query.get(session['user_id'])
    
    # 🚨 Verificación de Rol
    is_vigilante = user.nombre_usuario.lower().startswith('vig_') or \
                   user.nombre_usuario.lower().startswith('seg_') or \
                   (user.nombre_usuario.lower() == 'usuario_seguridad_especial')

    # Solo los Vigilantes deben acceder (tipo_usuario=FALSE Y cumple el patrón)
    if user and user.tipo_usuario == False and is_vigilante: 
        return render_template('qr.html', titulo_pagina="Scanner QR")
    else: 
        # Si no es un Vigilante, redirigir a su perfil
        return redirect(url_for('mi_perfil'))

@app.route('/obtener_info/<placa>')
def obtener_info(placa):
    vehiculo = Vehiculos.query.filter_by(placa=placa).first()
    
    if vehiculo and vehiculo.propietario.esta_activo:
        estado = "Activo"
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
        db.create_all()
        
        # --- Creación de la cuenta de administrador inicial (opcional) ---
        ADMIN_USERNAME_ID = 'admin@tec.edu'
        ADMIN_PASSWORD_RAW = '12345'

        if Usuarios.query.filter_by(nombre_usuario=ADMIN_USERNAME_ID).first() is None:
            admin_user = Usuarios(
                nombre_usuario=ADMIN_USERNAME_ID,
                contraseña=generate_password_hash(ADMIN_PASSWORD_RAW), 
                tipo_usuario=False, 
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