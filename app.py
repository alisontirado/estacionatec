import os
import secrets
import stripe
import random
import string
# Configurar Stripe

stripe.api_key = "sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
STRIPE_PUBLIC_KEY = "pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename  # ✅ IMPORTANTE: Agregar esta importación
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

# ✅ CONFIGURACIÓN PARA SUBIDA DE ARCHIVOS
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB máximo
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Asegurar que la carpeta de uploads existe
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

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

# --- Funciones auxiliares ---

def generar_numero_recibo():
    """Genera un número de recibo único"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = ''.join(random.choices(string.digits, k=4))
    return f"REC-{timestamp}-{random_str}"

def procesar_pago_stripe(token, monto, descripcion):
    """
    Procesa un pago REAL con Stripe
    """
    try:
        print(f"💳 Procesando con Stripe: ${monto} MXN")
        
        # Crear un cargo en Stripe (el monto va en centavos)
        charge = stripe.Charge.create(
            amount=int(monto * 100),  # Convertir a centavos
            currency='mxn',
            source=token,
            description=f'Tarjetón EstacionaTec - {descripcion}',
            metadata={
                'numero_recibo': descripcion,
                'producto': 'tarjeton_estacionamiento'
            }
        )
        
        print(f"✅ Stripe charge creado: {charge.id}")
        
        return {
            'success': True,
            'transaccion_id': charge.id,
            'estado': 'completado'
        }
        
    except stripe.error.CardError as e:
        error_message = f'Tarjeta rechazada: {e.error.message}'
        print(f"❌ {error_message}")
        return {
            'success': False,
            'error': error_message
        }
    except stripe.error.StripeError as e:
        error_message = f'Error de Stripe: {e.error.message}'
        print(f"❌ {error_message}")
        return {
            'success': False,
            'error': error_message
        }
    except Exception as e:
        error_message = f'Error inesperado: {str(e)}'
        print(f"💥 {error_message}")
        return {
            'success': False,
            'error': error_message
        }

# --- Rutas de la Aplicación ---

@app.route('/')
def inicio_sesion():
    return render_template('iniciosesion.html', titulo_pagina="Inicio de Sesión")

@app.route('/perfil_usuario', methods=['GET', 'POST'])
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
        
        # --- LÓGICA CORREGIDA DE ROLES ---
        
        # Identifica a Vigilantes SOLO por el prefijo en el nombre_usuario
        is_vigilante = user.nombre_usuario.lower().startswith('vig_') or \
                       user.nombre_usuario.lower().startswith('seg_') or \
                       (user.nombre_usuario.lower() == 'usuario_seguridad_especial')

        # 🚨 ROL VIGILANTE: Solo si cumple el patrón de Vigilante (independientemente de tipo_usuario)
        if is_vigilante: 
            return render_template('homevigilantes.html', usuario=user, titulo_pagina="Estacionatec Vigilancia")
        
        # ✅ ROL UNIFICADO: Todos los demás (Estudiantes TRUE y Profesores FALSE que NO son vigilantes)
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

@app.route('/miperfil', methods=['GET', 'POST'])
def mi_perfil():
    if 'user_id' not in session:
        return redirect(url_for('inicio_sesion'))
    
    user = Usuarios.query.get(session['user_id'])
    
    if request.method == 'POST':
        # Procesar la subida de foto
        if 'foto_perfil' in request.files:
            file = request.files['foto_perfil']
            if file and file.filename != '' and allowed_file(file.filename):
                # ✅ CORREGIDO: Usar secure_filename importado correctamente
                filename = secure_filename(f"user_{user.usuario_id}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # Actualizar la base de datos con la nueva ruta de la foto
                user.foto_perfil = f"uploads/{filename}"
                db.session.commit()
                
                return redirect(url_for('mi_perfil'))
    
    # Para GET requests, usar la foto del usuario o placeholder
    user.foto_url = url_for('static', filename=user.foto_perfil)
    return render_template('perfilusuario.html', usuario=user, titulo_pagina="Mi Perfil")

@app.route('/resumen/pago')
def resumen_pago():
    if 'user_id' not in session:
        return redirect(url_for('inicio_sesion'))

    user_id = session['user_id']
    print(f"🔍 Buscando pagos para usuario_id: {user_id}")  # DEBUG
    
    pagos = Pagos.query.filter_by(usuario_id=user_id).order_by(Pagos.fecha_pago.desc()).all()
    print(f"🔍 Pagos encontrados: {len(pagos)}")  # DEBUG
    
    # Preparar datos para el template
    pagos_data = []
    for pago in pagos:
        pagos_data.append({
            'numero_recibo': pago.numero_recibo,
            'concepto': pago.concepto,
            'cantidad': float(pago.cantidad),
            'fecha_pago': pago.fecha_pago.strftime("%d/%m/%Y %H:%M") if pago.fecha_pago else "N/A",
            'estado': pago.estado,
            'metodo_pago': pago.metodo_pago,
            'transaccion_id': getattr(pago, 'transaccion_id', 'N/A')
        })
    
    return render_template('pago.html', pagos=pagos_data, titulo_pagina="Historial de Pagos")

@app.route('/carga/vehiculo')
def carga_vehiculo():
    if 'user_id' not in session:
        return redirect(url_for('inicio_sesion'))
    return render_template('cag_vehiculo.html', titulo_pagina="Carga de Vehículo")

# --- Rutas de Pago ---

@app.route('/pago/vehiculo')
def pago_vehiculo():
    if 'user_id' not in session:
        return redirect(url_for('inicio_sesion'))
    return render_template('pago_vehiculo.html', titulo_pagina="Pago de Tarjetón")

@app.route('/procesar_pago', methods=['POST'])
def procesar_pago():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'No autenticado'})
    
    try:
        data = request.get_json()
        metodo_pago = data.get('metodo')
        monto = 150.00
        stripe_token = data.get('stripe_token')
        
        # Generar número de recibo único
        numero_recibo = generar_numero_recibo()
        
        print(f"🔔 Procesando pago: {metodo_pago}, Token: {stripe_token}")
        
        if metodo_pago == 'tarjeta' and stripe_token:
            # Procesar pago REAL con Stripe
            resultado_pago = procesar_pago_stripe(stripe_token, monto, numero_recibo)
        elif metodo_pago == 'paypal':
            # Simular PayPal por ahora
            resultado_pago = {
                'success': True, 
                'transaccion_id': f"PAYPAL-{numero_recibo}",
                'estado': 'completado'
            }
        elif metodo_pago == 'transferencia':
            # Para transferencias, marcamos como pendiente
            resultado_pago = {
                'success': True, 
                'transaccion_id': f"TRANSFER-{numero_recibo}",
                'estado': 'pendiente'
            }
        else:
            return jsonify({'success': False, 'error': 'Método de pago no válido'})
        
        if resultado_pago['success']:
            # Crear registro de pago
            nuevo_pago = Pagos(
                usuario_id=session['user_id'],
                numero_recibo=numero_recibo,
                concepto='Tarjetón de Estacionamiento - 1 Mes',
                cantidad=monto,
                estado=resultado_pago.get('estado', 'completado'),
                metodo_pago=metodo_pago,
                transaccion_id=resultado_pago['transaccion_id']
            )
            
            db.session.add(nuevo_pago)
            db.session.commit()
            
            print(f"✅ Pago exitoso: {numero_recibo}, Transacción: {resultado_pago['transaccion_id']}")
            
            return jsonify({
                'success': True, 
                'pago_id': nuevo_pago.pago_id,
                'numero_recibo': numero_recibo,
                'transaccion_id': resultado_pago['transaccion_id']
            })
        else:
            print(f"❌ Error en pago: {resultado_pago.get('error')}")
            return jsonify({'success': False, 'error': resultado_pago['error']})
            
    except Exception as e:
        print(f"💥 Error general: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/pagos/historial')
def api_historial_pagos():
    """API para obtener historial de pagos"""
    if 'user_id' not in session:
        return jsonify({'error': 'No autenticado'})
    
    pagos = Pagos.query.filter_by(usuario_id=session['user_id']).order_by(Pagos.fecha_pago.desc()).all()
    
    pagos_data = []
    for pago in pagos:
        pagos_data.append({
            'pago_id': pago.pago_id,
            'numero_recibo': pago.numero_recibo,
            'concepto': pago.concepto,
            'cantidad': float(pago.cantidad),
            'fecha_pago': pago.fecha_pago.strftime("%d/%m/%Y %H:%M"),
            'estado': pago.estado,
            'metodo_pago': pago.metodo_pago
        })
    
    return jsonify({'pagos': pagos_data})

# --- Rutas de Seguridad (Vigilancia) ---

@app.route('/scanner')
def scanner():
    if 'user_id' not in session:
        return redirect(url_for('inicio_sesion'))
    
    user = Usuarios.query.get(session['user_id'])
    
    # 🚨 LÓGICA CORREGIDA: Solo Vigilantes pueden acceder
    is_vigilante = user.nombre_usuario.lower().startswith('vig_') or \
                   user.nombre_usuario.lower().startswith('seg_') or \
                   (user.nombre_usuario.lower() == 'usuario_seguridad_especial')

    # Solo los Vigilantes deben acceder
    if is_vigilante: 
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

# --- Rutas adicionales ---

@app.route('/recibo')
def recibo():
    if 'user_id' not in session:
        return redirect(url_for('inicio_sesion'))
    
    user = Usuarios.query.get(session['user_id'])
    return render_template('recibo.html', 
                         titulo_pagina="Voucher",
                         usuario=user,
                         fecha_actual=datetime.now().strftime("%d/%m/%Y %H:%M"))

@app.route('/guardar_vehiculo', methods=['POST'])
def guardar_vehiculo():
    if 'user_id' not in session:
        return redirect(url_for('inicio_sesion'))
    
    try:
        # Obtener datos del formulario
        tipo_vehiculo = request.form.get('tipo')
        placa = request.form.get('placa')
        nombre_conductor = request.form.get('nombre')
        
        # Verificar si el vehículo ya existe
        vehiculo_existente = Vehiculos.query.filter_by(placa=placa).first()
        if vehiculo_existente:
            return "Error: Ya existe un vehículo con esta placa. <a href='/carga/vehiculo'>Volver</a>"
        
        # Procesar archivos subidos
        ruta_foto_vehiculo = ""
        ruta_tarjeta_circulacion = ""
        ruta_identificacion = ""
        
        if 'vehiculo' in request.files:
            file = request.files['vehiculo']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"vehiculo_{placa}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                ruta_foto_vehiculo = f"uploads/{filename}"
        
        if 'tarjeta' in request.files:
            file = request.files['tarjeta']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"tarjeta_{placa}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                ruta_tarjeta_circulacion = f"uploads/{filename}"
        
        # Crear nuevo vehículo
        nuevo_vehiculo = Vehiculos(
            usuario_id=session['user_id'],
            tipo_vehiculo=tipo_vehiculo,
            placa=placa,
            ruta_foto_vehiculo=ruta_foto_vehiculo,
            ruta_tarjeta_circulacion=ruta_tarjeta_circulacion
        )
        
        db.session.add(nuevo_vehiculo)
        db.session.commit()
        
        # Redirigir con mensaje de éxito
        return redirect(url_for('carga_vehiculo'))
        
    except Exception as e:
        db.session.rollback()
        return f"Error al guardar vehículo: {str(e)}. <a href='/carga/vehiculo'>Volver</a>"

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