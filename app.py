import os
from datetime import datetime
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from dotenv import load_dotenv

app = Flask(__name__)

print("🔍 Base de datos:", os.getenv("SQL_DATABASE"))


@app.route("/")
def dashboard():
    # obtener datos desde db
    kpi = {'containers_active':120, 'critical_alerts':3, 'avg_fill':47.5, 'measurements_today': 2450}
    containers = []  # lista con lat,lng,id,tipo
    chart = {
        'fill': {'labels': ['Org','Plast','Vidrio'], 'data':[45,50,30]},
        'temp': {
            'labels': list(range(24)),  # 0-23 horas
            'data': [22,22,21,20,19,18,17,16,17,19,21,23,24,25,26,25,24,23,22,21,20,19,18,17]
        }
    }
    return render_template('dashboard.html', kpi=kpi, containers=containers, chart=chart)

# Construcción dinámica de la cadena de conexión
if os.getenv("SQL_TRUSTED_CONNECTION") == "yes":
    connection_string = (
        f"mssql+pyodbc://@{os.getenv('SQL_SERVER')}/{os.getenv('SQL_DATABASE')}?"
        f"driver={os.getenv('SQL_DRIVER').replace(' ', '+')}&trusted_connection=yes"
    )
else:
    connection_string = (
        f"mssql+pyodbc://{os.getenv('SQL_USER')}:{os.getenv('SQL_PASSWORD')}"
        f"@{os.getenv('SQL_SERVER')}/{os.getenv('SQL_DATABASE')}?"
        f"driver={os.getenv('SQL_DRIVER').replace(' ', '+')}"
    )

# Configuración de SQLAlchemy
app.config["SQLALCHEMY_DATABASE_URI"] = connection_string
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

@app.route("/testdb")
def test_db():
    try:
        result = db.session.execute(text("SELECT TOP 1 * FROM Mediciones"))
        row = result.fetchone()
        return f"✅ Conexión exitosa. Ejemplo de dato: {row}"
    except Exception as e:
        return f"❌ Error en la conexión: {e}"

