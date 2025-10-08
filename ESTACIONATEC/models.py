from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Usuarios(db.Model):
    __tablename__ = 'usuarios'
    usuario_id = db.Column(db.Integer, primary_key=True)
    nombre_usuario = db.Column(db.String(50), unique=True, nullable=False)
    contraseña = db.Column(db.String(255), nullable=False)
    tipo_usuario = db.Column(db.Boolean, nullable=False)  # TRUE: Estudiante, FALSE: Profesor/Seguridad
    nombres = db.Column(db.String(100), nullable=False)
    apellido_paterno = db.Column(db.String(100), nullable=False)
    apellido_materno = db.Column(db.String(100), nullable=False)
    correo_electronico = db.Column(db.String(100), unique=True, nullable=False)
    telefono = db.Column(db.String(15))
    
    # Columna problemática: Se simplifica su declaración para mayor robustez.
    # El nombre de la columna en la base de datos será 'rfc_o_num_control'
    rfc_o_num_control = db.Column(db.String(20), unique=True, nullable=False) 
    
    fecha_registro = db.Column(db.TIMESTAMP, nullable=False, default=datetime.utcnow)
    esta_activo = db.Column(db.Boolean, nullable=False, default=True)
    carrera = db.Column(db.String(50))
    ruta_archivo_carga_academica = db.Column(db.String(255))
    
    # Relationships
    vehiculos = db.relationship('Vehiculos', backref='propietario', lazy=True)
    pagos = db.relationship('Pagos', backref='usuario', lazy=True)
    codigos_qr = db.relationship('CodigosQr', backref='usuario', lazy=True)
    registros_acceso = db.relationship('RegistroAcceso', backref='usuario', lazy=True)

    def __repr__(self):
        return f'<Usuario {self.nombre_usuario}>'

class Vehiculos(db.Model):
    __tablename__ = 'vehiculos'
    vehiculo_id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.usuario_id'), nullable=False)
    tipo_vehiculo = db.Column(db.String(20), nullable=False)
    placa = db.Column(db.String(20), unique=True, nullable=False)
    ruta_foto_vehiculo = db.Column(db.String(255))
    ruta_tarjeta_circulacion = db.Column(db.String(255))

    def __repr__(self):
        return f'<Vehiculo {self.placa}>'

class Pagos(db.Model):
    __tablename__ = 'pagos'
    pago_id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.usuario_id'), nullable=False)
    numero_recibo = db.Column(db.String(50), unique=True, nullable=False)
    concepto = db.Column(db.String(100), nullable=False)
    cantidad = db.Column(db.DECIMAL(10, 2), nullable=False)
    fecha_pago = db.Column(db.TIMESTAMP, nullable=False)
    ruta_prueba_pago = db.Column(db.String(255))

    def __repr__(self):
        return f'<Pago {self.numero_recibo}>'

class CodigosQr(db.Model):
    __tablename__ = 'codigos_qr'
    codigo_qr_id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.usuario_id'), unique=True, nullable=False)
    datos_codigo_qr = db.Column(db.String(255), unique=True, nullable=False)
    generado_en = db.Column(db.TIMESTAMP, nullable=False)
    esta_activo = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f'<Codigo QR {self.datos_codigo_qr}>'

class RegistroAcceso(db.Model):
    __tablename__ = 'registro_acceso'
    registro_id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.usuario_id'), nullable=False)
    tipo_acceso = db.Column(db.String(10), nullable=False)
    timestamp = db.Column(db.TIMESTAMP, nullable=False)

    def __repr__(self):
        return f'<Registro {self.registro_id}>'
