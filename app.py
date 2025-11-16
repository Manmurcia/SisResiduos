from flask import Flask, render_template, request
import pyodbc
import os


def crear_app():
    app = Flask(__name__)

    # ========= CONFIGURACIÓN SQL SERVER (WINDOWS AUTH) =========
    app.config['SQL_SERVER_HOST'] = r'MANUEL'      # Servidor
    app.config['SQL_SERVER_DB'] = 'SisResiduos'
    app.config['SQL_DRIVER'] = 'ODBC Driver 17 for SQL Server'

    # ========== CONEXIÓN SQL SERVER (Windows Auth) ==========
    def get_mssql_connection():
        driver = app.config['SQL_DRIVER']
        server = app.config['SQL_SERVER_HOST']
        database = app.config['SQL_SERVER_DB']

        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"Trusted_Connection=yes;"
        )
        return pyodbc.connect(conn_str)

    # ========= CURSOR QUE RETORNA DICCIONARIOS =========
    class DictCursor:
        def __init__(self, cursor):
            self.cursor = cursor
            self._colnames = None

        def execute(self, sql, params=None):
            if params is None:
                res = self.cursor.execute(sql)
            else:
                res = self.cursor.execute(sql, params)
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
            try: self.cursor.close()
            except: pass

        def __getattr__(self, name):
            return getattr(self.cursor, name)

    # ========= UTILIDAD PARA DETECTAR COLUMNA =========
    def get_column_for_table(cur, schema, table, candidates):
        cur.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_CATALOG=? AND TABLE_NAME=?",
            (schema, table),
        )
        rows = cur.fetchall()
        cols = [r['COLUMN_NAME'] for r in rows]
        for cand in candidates:
            if cand in cols:
                return cand
        return None

    # ========= KPIs DEL DASHBOARD =========
    def get_dashboard_kpi():
        conn = get_mssql_connection()
        cur = DictCursor(conn.cursor())

        estado_col = get_column_for_table(
            cur,
            app.config['SQL_SERVER_DB'],
            'contenedores',
            ['estado', 'Estado', 'estado_contenedor',
             'EstadoContenedor', 'estadoContenedor']
        )

        if estado_col:
            q = f"SELECT COUNT(*) AS total FROM contenedores WHERE [{estado_col}] = ?"
            cur.execute(q, ('Activo',))
            total_cont = cur.fetchone()['total']
        else:
            cur.execute("SELECT COUNT(*) AS total FROM contenedores")
            total_cont = cur.fetchone()['total']

        cur.execute("""
            SELECT COUNT(*) AS total 
            FROM mediciones 
            WHERE CONVERT(date, FechaHora) = CONVERT(date, GETDATE())
        """)
        mediciones_hoy = cur.fetchone()['total']

        cur.execute("SELECT ROUND(AVG(PorcentajeLlenado), 2) AS promedio FROM mediciones")
        result = cur.fetchone()
        promedio_llenado = result['promedio'] if result['promedio'] else 0

        cur.execute("SELECT COUNT(*) AS total FROM mediciones WHERE PorcentajeLlenado > 85")
        critical_alerts = cur.fetchone()['total']

        cur.close()
        conn.close()

        return {
            'containers_active': total_cont,
            'measurements_today': mediciones_hoy,
            'avg_fill': promedio_llenado,
            'critical_alerts': critical_alerts
        }

    # ========= DATOS PARA GRÁFICAS =========
    def get_chart_and_container_data():
        conn = get_mssql_connection()
        cur = DictCursor(conn.cursor())

        cur.execute("""
            SELECT TOP 100 c.IdContenedor AS id, t.TipoResiduo AS tipo,
                ISNULL((
                    SELECT TOP 1 PorcentajeLlenado 
                    FROM mediciones m 
                    WHERE m.IdSensor IN (
                        SELECT IdSensor FROM sensores WHERE IdContenedor = c.IdContenedor
                    )
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

        cur.execute("""
            SELECT TOP 24 DATEPART(HOUR, FechaHora) AS hora,
                ROUND(AVG(Temperatura), 1) AS temp_avg
            FROM mediciones
            WHERE Temperatura IS NOT NULL AND Temperatura > -50 AND Temperatura < 100
            GROUP BY DATEPART(HOUR, FechaHora)
            ORDER BY hora ASC
        """)
        temp_rows = cur.fetchall()
        temp_labels = [f"{r['hora']}:00" for r in temp_rows]
        temp_values = [r['temp_avg'] for r in temp_rows]

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

    # ========= RUTAS =========

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/dashboard')
    def dashboard():
        kpi = get_dashboard_kpi()
        chart_data = get_chart_and_container_data()
        return render_template('dashboard.html', kpi=kpi, containers=chart_data['containers'], chart=chart_data['chart'])

    @app.route('/contenedores')
    def contenedores():
        conn = get_mssql_connection()
        cur = DictCursor(conn.cursor())

        cur.execute("SELECT IdTipoResiduo AS id, TipoResiduo AS nombre FROM tiposresiduos ORDER BY TipoResiduo")
        tipos = cur.fetchall()

        cur.execute("SELECT IdUbicacion AS id, Direccion AS nombre FROM ubicaciones ORDER BY Direccion")
        ubicaciones = cur.fetchall()

        cur.execute("""
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
        """)
        data = cur.fetchall()

        cur.close()
        conn.close()

        return render_template('contenedores.html', contenedores=data, tipos=tipos, ubicaciones=ubicaciones)

    @app.route('/sensores')
    def sensores():
        conn = get_mssql_connection()
        cur = DictCursor(conn.cursor())

        cur.execute("SELECT IdTipoSensor AS id, TipoSensor AS nombre FROM tipossensores ORDER BY TipoSensor")
        tipos = cur.fetchall()

        cur.execute("SELECT IdContenedor AS id, IdContenedor AS nombre FROM contenedores ORDER BY IdContenedor")
        conts = cur.fetchall()

        cur.execute("""
            SELECT s.IdSensor AS id, ts.TipoSensor AS tipo, s.Modelo AS modelo, 
                c.IdContenedor AS contenedor, s.IdEstado AS estado, s.FechaInstalacion AS fecha_instalacion
            FROM sensores s
            JOIN tipossensores ts ON s.IdTipoSensor = ts.IdTipoSensor
            JOIN contenedores c ON s.IdContenedor = c.IdContenedor
            ORDER BY s.IdSensor ASC
        """)
        data = cur.fetchall()

        cur.close()
        conn.close()

        return render_template('sensores.html', sensores=data, tipos=tipos, contenedores=conts)

    @app.route('/mediciones')
    def mediciones():
        conn = get_mssql_connection()
        cur = DictCursor(conn.cursor())

        cur.execute("""
            SELECT TOP 500 m.IdMedicion AS id, s.IdSensor AS sensor, m.FechaHora AS fecha_hora, 
                m.PorcentajeLlenado AS porcentaje, m.PesoKg As peso, m.Temperatura AS temp
            FROM mediciones m
            JOIN sensores s ON m.IdSensor = s.IdSensor
            ORDER BY m.FechaHora DESC
        """)
        data = cur.fetchall()

        cur.execute("""
            SELECT DISTINCT u.IdUbicacion AS id, u.Direccion AS nombre
            FROM ubicaciones u
            ORDER BY u.Direccion
        """)
        ubicaciones = cur.fetchall()

        cur.close()
        conn.close()

        return render_template('mediciones.html', mediciones=data, ubicaciones=ubicaciones)

    # ========= INSERTAR CONTENEDOR =========
    @app.route('/contenedores/agregar', methods=['POST'])
    def agregar_contenedor():
        try:
            tipo = request.form.get('tipo_residuo')
            capacidad = request.form.get('capacidad')
            ubicacion = request.form.get('ubicacion')

            conn = get_mssql_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO contenedores (IdTipoResiduo, Capacidad, IdUbicacion, IdEstado)
                VALUES (?, ?, ?, ?)
            """, (int(tipo), int(capacidad), int(ubicacion), 1))
            conn.commit()
            cur.close()
            conn.close()
            return {'success': True, 'message': 'Contenedor agregado'}, 200
        except Exception as e:
            return {'success': False, 'message': str(e)}, 400

    # ========= INSERTAR SENSOR =========
    @app.route('/sensores/agregar', methods=['POST'])
    def agregar_sensor():
        try:
            tipo = request.form.get('tipo_sensor')
            modelo = request.form.get('modelo')
            contenedor = request.form.get('contenedor')

            conn = get_mssql_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO sensores (IdTipoSensor, Modelo, IdContenedor, IdEstado, FechaInstalacion)
                VALUES (?, ?, ?, ?, CAST(GETDATE() AS date))
            """, (int(tipo), modelo, int(contenedor), 1))

            conn.commit()
            cur.close()
            conn.close()
            return {'success': True, 'message': 'Sensor agregado'}, 200
        except Exception as e:
            return {'success': False, 'message': str(e)}, 400

    # ========= EXPORTAR CSV CONTENEDORES =========
    @app.route('/contenedores/exportar_csv')
    def exportar_contenedores_csv():
        import csv
        from io import StringIO

        try:
            conn = get_mssql_connection()
            cur = DictCursor(conn.cursor())

            cur.execute("""
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
            """)
            data = cur.fetchall()

            cur.close()
            conn.close()

            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=['id', 'tipo', 'capacidad', 'ubicacion', 'promedio_llenado'])
            writer.writeheader()
            writer.writerows(data)

            return app.response_class(
                response=output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment; filename="contenedores.csv"'}
            )
        except Exception as e:
            return {'error': str(e)}, 400

    # ========= EXPORTAR CSV MEDICIONES =========
    @app.route('/mediciones/exportar_csv')
    def exportar_mediciones_csv():
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

            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=['id', 'sensor', 'fecha_hora', 'porcentaje', 'peso', 'temp'])
            writer.writeheader()
            writer.writerows(data)

            return app.response_class(
                response=output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment; filename="mediciones.csv"'}
            )
        except Exception as e:
            return {'error': str(e)}, 400

    return app


if __name__ == '__main__':
    app = crear_app()
    app.run(debug=True)
