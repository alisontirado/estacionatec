from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
import bcrypt

app = Flask(__name__)
app.secret_key = "clave_secreta_segura"

# Configuración de conexión a PostgreSQL
DB_HOST = "localhost"
DB_NAME = "estacionatec"
DB_USER = "postgres"
DB_PASSWORD = "alisongt"

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn

# Página principal
@app.route("/")
def index():
    if "usuario" in session:
        return f"Bienvenido, {session['usuario']}! <br><a href='/logout'>Cerrar sesión</a>"
    return redirect(url_for("login"))

# Registro de usuarios
@app.route("/registro/alumno", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre = request.form["nombre"]
        correo = request.form["correo"]
        password = request.form["password"]

        conn = get_db_connection()
        cur = conn.cursor()

        # Verificar si el correo ya existe
        cur.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
        existente = cur.fetchone()
        if existente:
            flash("El correo ya está registrado", "error")
            cur.close()
            conn.close()
            return redirect(url_for("registro"))

        # Hashear la contraseña
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        # Insertar en la BD
        cur.execute(
            "INSERT INTO usuarios (nombre, correo, password) VALUES (%s, %s, %s)",
            (nombre, correo, hashed.decode("utf-8"))
        )
        conn.commit()
        cur.close()
        conn.close()

        flash("Usuario registrado con éxito", "success")
        return redirect(url_for("login"))

    return render_template("registroalumno.html")

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form["correo"]
        password = request.form["password"]

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id, nombre, password FROM usuarios WHERE correo = %s", (correo,))
        usuario = cur.fetchone()
        cur.close()
        conn.close()

        if usuario:
            user_id, nombre, hashed_pw = usuario
            if bcrypt.checkpw(password.encode("utf-8"), hashed_pw.encode("utf-8")):
                session["usuario"] = nombre
                flash("Has iniciado sesión correctamente", "success")
                return redirect(url_for("index"))
            else:
                flash("Contraseña incorrecta", "error")
        else:
            flash("El correo no está registrado", "error")

    return render_template("iniciosesion.html")

# Logout
@app.route("/logout")
def logout():
    session.pop("usuario", None)
    flash("Has cerrado sesión", "info")
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
