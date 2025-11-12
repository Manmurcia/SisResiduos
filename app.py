from flask import Flask, render_template, request
import pyodbc
import os

app = Flask(__name__)


# Configuración de la conexión a SQL Server
app.config['SQL_SERVER_HOST'] = 'localhost'
app.config['SQL_SERVER_USER'] = 'sa'
app.config['SQL_SERVER_PASSWORD'] = ''
app.config['SQL_SERVER_DB'] = 'SisResiduos'

# Conexión a SQL Server
app.config['SQLALCHEMY_DATABASE_URI'] = f'mssql+pyodbc://{app.config["SQL_SERVER_USER"]}:{app.config["SQL_SERVER_PASSWORD"]}@{app.config["SQL_SERVER_HOST"]}/{app.config["SQL_SERVER_DB"]}?driver=ODBC+Driver+17+for+SQL+Server'


# --- SQL Server connection helper (Windows Authentication) ---
def get_mssql_connection():
    """Return a new pyodbc connection using Trusted_Connection (Windows Auth)."""
    driver = os.environ.get('MSSQL_DRIVER', 'ODBC Driver 17 for SQL Server')
    server = app.config.get('SQL_SERVER_HOST', 'localhost')
    database = app.config.get('SQL_SERVER_DB', '')
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        "Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)


class DictCursor:
    """Wrapper around a pyodbc cursor that returns rows as dicts (colname->value)."""
    def __init__(self, cursor):
        self.cursor = cursor
        self._colnames = None

    def execute(self, sql, params=None):
        if params is None:
            res = self.cursor.execute(sql)
        else:
            res = self.cursor.execute(sql, params)
        # set column names after execute
        try:
            self._colnames = [col[0] for col in self.cursor.description]
        except Exception:
            self._colnames = None
        return res

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return dict(zip(self._colnames, row)) if self._colnames else row

    def fetchall(self):
        rows = self.cursor.fetchall()
        if not rows:
            return []
        return [dict(zip(self._colnames, r)) for r in rows]

    def close(self):
        try:
            self.cursor.close()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self.cursor, name)


def get_column_for_table(cur, schema, table, candidates):
    """Return the first candidate column name that exists in the given table.

    cur: open cursor (DictCursor)
    schema: database name
    table: table name
    candidates: list of candidate column names (strings)
    """
    # INFORMATION_SCHEMA in SQL Server: TABLE_CATALOG = database name
    cur.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_CATALOG=? AND TABLE_NAME=?",
        (schema, table),
    )
    rows = cur.fetchall()
    cols = [r['COLUMN_NAME'] for r in rows]
    for cand in candidates:
        if cand in cols:
            return cand
    return None


# Helper function for both dashboard and index
def get_dashboard_kpi():
    """Fetch KPI data from SQL Server and return dict."""
    conn = get_mssql_connection()
    cur = DictCursor(conn.cursor())

    # KPI 1: contenedores activos
    estado_col = get_column_for_table(cur, app.config['SQL_SERVER_DB'], 'contenedores',
                                      ['estado', 'Estado', 'estado_contenedor', 'EstadoContenedor', 'estadoContenedor'])
    if estado_col:
        q = f"SELECT COUNT(*) AS total FROM contenedores WHERE [{estado_col}] = ?"
        cur.execute(q, ('Activo',))
        total_cont = cur.fetchone()['total']
    else:
        cur.execute("SELECT COUNT(*) AS total FROM contenedores")
        total_cont = cur.fetchone()['total']

    # KPI 2: mediciones del día
    cur.execute("SELECT COUNT(*) AS total FROM mediciones WHERE CONVERT(date, FechaHora) = CONVERT(date, GETDATE())")
    mediciones_hoy = cur.fetchone()['total']

    # KPI 3: Promedio de llenado
    cur.execute("SELECT ROUND(AVG(PorcentajeLlenado), 2) AS promedio FROM mediciones")
    result = cur.fetchone()
    promedio_llenado = result['promedio'] if result and result['promedio'] is not None else 0

    # KPI 4: alertas críticas (contenedores con >85% llenado)
    cur.execute("SELECT COUNT(*) AS total FROM mediciones WHERE PorcentajeLlenado > 85")
    critical_alerts = cur.fetchone()['total']

    # Datos para gráficas (por ahora vacíos para que no falle la plantilla)
    containers = []
    chart_fill_data = []
    chart_fill_labels = []
    chart_temp_data = []
    chart_temp_labels = []

    cur.close()
    conn.close()

    return {
        'containers_active': total_cont,
        'measurements_today': mediciones_hoy,
        'avg_fill': promedio_llenado,
        'critical_alerts': critical_alerts
    }


def get_chart_and_container_data():
    """Fetch chart and container data from SQL Server."""
    conn = get_mssql_connection()
    cur = DictCursor(conn.cursor())

    # Containers con coordenadas (para el mapa)
    # Obtiene ubicación del contenedor desde la tabla ubicaciones
    cur.execute("""
        SELECT TOP 100 c.IdContenedor AS id, t.TipoResiduo AS tipo,
               ISNULL((
                   SELECT TOP 1 PorcentajeLlenado FROM mediciones m 
                   WHERE m.IdSensor IN (SELECT IdSensor FROM sensores WHERE IdContenedor = c.IdContenedor)
                   ORDER BY m.FechaHora DESC
               ), 0) AS nivel_llenado,
               ISNULL(u.Latitud, 4.7) AS lat, 
               ISNULL(u.Longitud, -74.01) AS lng,
               'Activo' AS estado
        FROM contenedores c
        LEFT JOIN tiposresiduos t ON c.IdTipoResiduo = t.IdTipoResiduo
        LEFT JOIN ubicaciones u ON c.IdUbicacion = u.IdUbicacion
    """)
    containers = cur.fetchall()

    # Promedio llenado por tipo de residuo
    cur.execute("""
        SELECT TOP 10 t.TipoResiduo, ROUND(AVG(m.PorcentajeLlenado), 1) AS avg_fill
        FROM mediciones m
        JOIN sensores s ON m.IdSensor = s.IdSensor
        JOIN contenedores c ON s.IdContenedor = c.IdContenedor
        JOIN tiposresiduos t ON c.IdTipoResiduo = t.IdTipoResiduo
        GROUP BY t.TipoResiduo
        ORDER BY avg_fill DESC
    """)
    fill_data = cur.fetchall()
    fill_labels = [row['TipoResiduo'] for row in fill_data]
    fill_values = [row['avg_fill'] for row in fill_data]

    # Temperatura promedio por hora
    cur.execute("""
        SELECT TOP 24 DATEPART(HOUR, FechaHora) AS hora,
               ROUND(AVG(Temperatura), 1) AS temp_avg
        FROM mediciones
        WHERE Temperatura IS NOT NULL AND Temperatura > -50 AND Temperatura < 100
        GROUP BY DATEPART(HOUR, FechaHora)
        ORDER BY hora ASC
    """)
    temp_data_raw = cur.fetchall()
    temp_labels = [f"{row['hora']}:00" for row in temp_data_raw]
    temp_values = [row['temp_avg'] for row in temp_data_raw]

    cur.close()
    conn.close()

    return {
        'containers': containers,
        'chart': {
            'fill_data': fill_values,
            'fill_labels': fill_labels,
            'temp_data': temp_values,
            'temp_labels': temp_labels
        }
    }

@app.route('/')
def index():
    """Endpoint 'index' para la página de inicio."""
    return render_template('index.html')

# RUTA: DASHBOARD
@app.route('/dashboard')
def dashboard():
    kpi = get_dashboard_kpi()
    chart_data = get_chart_and_container_data()
    context = {
        'kpi': kpi,
        **chart_data
    }
    return render_template('dashboard.html', **context)


# RUTA: CONTENEDORES
@app.route('/contenedores')
def contenedores():
    conn = get_mssql_connection()
    cur = DictCursor(conn.cursor())
    # obtener lista de tipos y ubicaciones para el formulario de creación
    cur.execute("SELECT IdTipoResiduo AS id, TipoResiduo AS nombre FROM tiposresiduos ORDER BY TipoResiduo")
    tipos = cur.fetchall()
    cur.execute("SELECT IdUbicacion AS id, Direccion AS nombre FROM ubicaciones ORDER BY Direccion")
    ubicaciones = cur.fetchall()

    sql = """
        SELECT c.IdContenedor AS id, t.TipoResiduo AS tipo, c.Capacidad AS capacidad, 
               u.Direccion AS ubicacion, 'Activo' AS estado,
               ROUND(AVG(m.PorcentajeLlenado), 1) AS promedio_ll
        FROM contenedores c
        JOIN tiposresiduos t ON c.IdTipoResiduo = t.IdTipoResiduo
        JOIN ubicaciones u ON c.IdUbicacion = u.IdUbicacion
        LEFT JOIN sensores s ON s.IdContenedor = c.IdContenedor
        LEFT JOIN mediciones m ON m.IdSensor = s.IdSensor
        GROUP BY c.IdContenedor, t.TipoResiduo, u.Direccion, c.Capacidad
        ORDER BY c.IdContenedor ASC
    """
    cur.execute(sql)
    data = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('contenedores.html', contenedores=data, tipos=tipos, ubicaciones=ubicaciones)


# RUTA: SENSORES
@app.route('/sensores')
def sensores():
    conn = get_mssql_connection()
    cur = DictCursor(conn.cursor())
    # obtener tipos de sensores y contenedores para el formulario
    cur.execute("SELECT IdTipoSensor AS id, TipoSensor AS nombre FROM tipossensores ORDER BY TipoSensor")
    tipos = cur.fetchall()
    cur.execute("SELECT IdContenedor AS id, IdContenedor AS nombre FROM contenedores ORDER BY IdContenedor")
    conts = cur.fetchall()

    cur.execute("""
        SELECT s.IdSensor AS id, ts.TipoSensor AS tipo, s.Modelo AS modelo, 
               c.IdContenedor AS contenedor, s.IdEstado AS estado, 
               s.FechaInstalacion AS fecha_instalacion
        FROM sensores s
        JOIN tipossensores ts ON s.IdTipoSensor = ts.IdTipoSensor
        JOIN contenedores c ON s.IdContenedor = c.IdContenedor
        ORDER BY s.IdSensor ASC
    """)
    data = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('sensores.html', sensores=data, tipos=tipos, contenedores=conts)



# RUTA: MEDICIONES
# RUTA: MEDICIONES
@app.route('/mediciones')
def mediciones():
    conn = get_mssql_connection()
    cur = DictCursor(conn.cursor())
    cur.execute("""
        SELECT TOP 500 m.IdMedicion AS id, s.IdSensor AS sensor, m.FechaHora AS fecha_hora, 
               m.PorcentajeLlenado AS porcentaje, m.PesoKg AS peso, m.Temperatura AS temp
        FROM mediciones m
        JOIN sensores s ON m.IdSensor = s.IdSensor
        ORDER BY m.FechaHora DESC
    """)
    data = cur.fetchall()
    
    # Obtener lista de ubicaciones para el filtro
    cur.execute("""
        SELECT DISTINCT u.IdUbicacion AS id, u.Direccion AS nombre
        FROM ubicaciones u
        ORDER BY u.Direccion
    """)
    ubicaciones = cur.fetchall()
    
    cur.close()
    conn.close()
    return render_template('mediciones.html', mediciones=data, ubicaciones=ubicaciones)


# RUTA: Agregar contenedor (POST)
@app.route('/contenedores/agregar', methods=['POST'])
def agregar_contenedor():
    """Inserta un nuevo contenedor en la BD."""
    try:
        tipo_residuo = request.form.get('tipo_residuo')
        capacidad = request.form.get('capacidad')
        ubicacion = request.form.get('ubicacion')

        conn = get_mssql_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO contenedores (IdTipoResiduo, Capacidad, IdUbicacion, IdEstado)
            VALUES (?, ?, ?, ?)
        """, (int(tipo_residuo), int(capacidad), int(ubicacion), 1))
        conn.commit()
        cur.close()
        conn.close()

        return {'success': True, 'message': 'Contenedor agregado correctamente'}, 200
    except Exception as e:
        return {'success': False, 'message': str(e)}, 400


# RUTA: Agregar sensor (POST)
@app.route('/sensores/agregar', methods=['POST'])
def agregar_sensor():
    """Inserta un nuevo sensor en la BD."""
    try:
        tipo_sensor = request.form.get('tipo_sensor')
        modelo = request.form.get('modelo')
        contenedor = request.form.get('contenedor')

        conn = get_mssql_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sensores (IdTipoSensor, Modelo, IdContenedor, IdEstado, FechaInstalacion)
            VALUES (?, ?, ?, ?, CAST(GETDATE() AS date))
        """, (int(tipo_sensor), modelo, int(contenedor), 1))
        conn.commit()
        cur.close()
        conn.close()

        return {'success': True, 'message': 'Sensor agregado correctamente'}, 200
    except Exception as e:
        return {'success': False, 'message': str(e)}, 400


# RUTA: Exportar CSV de contenedores
@app.route('/contenedores/exportar_csv')
def exportar_contenedores_csv():
    """Exporta contenedores a CSV."""
    import csv
    from io import StringIO

    try:
        conn = get_mssql_connection()
        cur = DictCursor(conn.cursor())

        sql = """
            SELECT c.IdContenedor AS id, t.TipoResiduo AS tipo, c.Capacidad AS capacidad, 
                   u.Direccion AS ubicacion,
                   ROUND(AVG(m.PorcentajeLlenado), 1) AS promedio_llenado
            FROM contenedores c
            JOIN tiposresiduos t ON c.IdTipoResiduo = t.IdTipoResiduo
            JOIN ubicaciones u ON c.IdUbicacion = u.IdUbicacion
            LEFT JOIN sensores s ON s.IdContenedor = c.IdContenedor
            LEFT JOIN mediciones m ON m.IdSensor = s.IdSensor
            GROUP BY c.IdContenedor, t.TipoResiduo, u.Direccion, c.Capacidad
            ORDER BY c.IdContenedor ASC
        """
        cur.execute(sql)
        data = cur.fetchall()
        cur.close()
        conn.close()

        # Crear CSV en memoria
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=['id', 'tipo', 'capacidad', 'ubicacion', 'promedio_llenado'])
        writer.writeheader()
        writer.writerows(data)

        response = app.response_class(
            response=output.getvalue(),
            status=200,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename="contenedores.csv"'}
        )
        return response
    except Exception as e:
        return {'error': str(e)}, 400


# RUTA: Exportar CSV de mediciones
@app.route('/mediciones/exportar_csv')
def exportar_mediciones_csv():
    """Exporta mediciones a CSV."""
    import csv
    from io import StringIO

    try:
        conn = get_mssql_connection()
        cur = DictCursor(conn.cursor())

        cur.execute("""
            SELECT TOP 5000 m.IdMedicion AS id, s.IdSensor AS sensor, m.FechaHora AS fecha_hora, 
                   m.PorcentajeLlenado AS porcentaje, m.PesoKg AS peso, m.Temperatura AS temp
            FROM mediciones m
            JOIN sensores s ON m.IdSensor = s.IdSensor
            ORDER BY m.FechaHora DESC
        """)
        data = cur.fetchall()
        cur.close()
        conn.close()

        # Crear CSV en memoria
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=['id', 'sensor', 'fecha_hora', 'porcentaje', 'peso', 'temp'])
        writer.writeheader()
        writer.writerows(data)

        response = app.response_class(
            response=output.getvalue(),
            status=200,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename="mediciones.csv"'}
        )
        return response
    except Exception as e:
        return {'error': str(e)}, 400


if __name__ == '__main__':
    app.run(debug=True)
