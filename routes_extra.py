# Rutas adicionales para agregar contenedor, sensor y exportar CSV
# Copia estas funciones al final de app.py antes de if __name__ == '__main__':

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
