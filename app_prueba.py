import flet as ft
import requests
import os
from datetime import datetime, date, timedelta

# --- CONEXIÓN A FIREBASE EN LA NUBE ---
FIREBASE_URL = "https://cajarepuestos-214aa-default-rtdb.firebaseio.com/caja_repuestos.json"

def cargar_datos():
    try:
        respuesta = requests.get(FIREBASE_URL, timeout=10)
        if respuesta.status_code == 200:
            data = respuesta.json()
            if data is None:
                return {"movimientos": [], "gastos": [], "facturas_pendientes": [], "cierres": []}
            return {
                "movimientos": data.get("movimientos") or [],
                "gastos": data.get("gastos") or [],
                "facturas_pendientes": data.get("facturas_pendientes") or [],
                "cierres": data.get("cierres") or []
            }
    except Exception as e:
        print(f"Alerta: No se pudo conectar a la nube. {e}")
    
    return {"movimientos": [], "gastos": [], "facturas_pendientes": [], "cierres": []}

def guardar_datos(datos):
    try:
        requests.put(FIREBASE_URL, json=datos, timeout=10)
    except Exception as e:
        print(f"Error crítico al guardar en la nube: {e}")

def main(page: ft.Page):
    page.title = "Repuestera HAFID - Sistema de Gestión"
    page.theme_mode = "light"
    # El scroll general de la página se encarga de todo el movimiento vertical
    page.scroll = "always"
    page.padding = 20
    page.window.width = 500 
    page.window.height = 900

    bd = cargar_datos()
    hoy_dt = date.today()
    hoy_str = str(hoy_dt)
    
    sesion = {"usuario": "", "fecha": hoy_str}

    def mostrar_alerta(mensaje, color="red"):
        snack = ft.SnackBar(ft.Text(mensaje, color="white"), bgcolor=color)
        page.overlay.append(snack)
        snack.open = True
        page.update()

    # --- ELEMENTOS VISUALES PRINCIPALES ---
    txt_info_sesion = ft.Text("", size=16, weight="bold", color="blue_900")
    
    txt_ingresos_hoy = ft.Text("Ingresos Hoy: $0.00", size=16, color="green_700")
    txt_egresos_hoy = ft.Text("Egresos Hoy: $0.00", size=16, color="red_700")
    txt_saldo_dia = ft.Text("SALDO DEL DÍA (CAJA): $0.00", size=22, weight="bold", color="blue_700")
    txt_saldo_semana = ft.Text("SALDO NETO SEMANAL: $0.00", size=16, weight="bold")

    # --- GRILLAS PLANILLA SEMANAL ---
    tabla_semana_ingresos = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Container(ft.Text("DIA", weight="bold"), width=90)),
            ft.DataColumn(ft.Text("EFECTIVO", weight="bold")),
            ft.DataColumn(ft.Text("TARJETA", weight="bold")),
            ft.DataColumn(ft.Text("TOTAL", weight="bold")),
        ],
        rows=[], heading_row_color="#E8F5E9", column_spacing=15
    )

    tabla_semana_egresos = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("FECHA", weight="bold")),
            ft.DataColumn(ft.Text("CATEGORÍA Y DETALLE", weight="bold")),
            ft.DataColumn(ft.Text("MONTO", weight="bold")),
        ],
        rows=[], heading_row_color="#FFEBEE"
    )

    # El scroll "auto" solo activa la barra horizontal si la pantalla es muy chica
    contenedor_ingresos = ft.Row([tabla_semana_ingresos], scroll="auto")
    contenedor_egresos = ft.Row([tabla_semana_egresos], scroll="auto")

    # --- TEXTOS ESTADÍSTICAS ---
    txt_est_mes_actual = ft.Text("Mes Actual: $0.00", size=16, weight="bold", color="green_700")
    txt_est_mes_anterior = ft.Text("Mes Anterior: $0.00", size=16)
    txt_est_crecimiento = ft.Text("Evolución: 0%", size=16, weight="bold")
    
    lista_facturas_pendientes = ft.Column(spacing=10)

    # --- LÓGICA DE ACTUALIZACIÓN DE VISTAS ---
    def actualizar_ui():
        txt_info_sesion.value = f"Operador: {sesion['usuario']} | Fecha: {datetime.now().strftime('%d/%m/%Y')}"
        
        inicio_semana = hoy_dt - timedelta(days=hoy_dt.weekday()) 
        dias_nombres = ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO"]
        
        tabla_semana_ingresos.rows.clear()
        total_efectivo_sem = 0
        total_tarjeta_sem = 0
        ingresos_hoy = 0

        for i in range(6):
            dia_fecha = inicio_semana + timedelta(days=i)
            dia_str = str(dia_fecha)
            
            movs_dia = [m for m in bd["movimientos"] if m.get("fecha") == dia_str]
            efvo_dia = sum(m.get("monto", 0) for m in movs_dia if m.get("medio") == "EFECTIVO")
            tarj_dia = sum(m.get("monto", 0) for m in movs_dia if m.get("medio") == "TARJETA / VIRTUAL")
            total_dia = efvo_dia + tarj_dia
            
            total_efectivo_sem += efvo_dia
            total_tarjeta_sem += tarj_dia

            if dia_str == hoy_str:
                ingresos_hoy = total_dia

            tabla_semana_ingresos.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Container(ft.Text(dias_nombres[i]), width=90)),
                ft.DataCell(ft.Text(f"${efvo_dia:,.2f}")),
                ft.DataCell(ft.Text(f"${tarj_dia:,.2f}")),
                ft.DataCell(ft.Text(f"${total_dia:,.2f}", weight="bold"))
            ]))
        
        total_ingresos_sem = total_efectivo_sem + total_tarjeta_sem
        tabla_semana_ingresos.rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Text("TOTAL SEM", weight="bold")),
            ft.DataCell(ft.Text(f"${total_efectivo_sem:,.2f}", color="green", weight="bold")),
            ft.DataCell(ft.Text(f"${total_tarjeta_sem:,.2f}", color="green", weight="bold")),
            ft.DataCell(ft.Text(f"${total_ingresos_sem:,.2f}", color="blue", weight="bold"))
        ]))

        tabla_semana_egresos.rows.clear()
        gastos_semana = [g for g in bd["gastos"] if (inicio_semana <= datetime.strptime(g["fecha"], "%Y-%m-%d").date() <= inicio_semana + timedelta(days=6))]
        total_gastos_sem = 0
        egresos_hoy = 0
        
        for g in gastos_semana:
            fecha_formato = datetime.strptime(g["fecha"], "%Y-%m-%d").strftime("%d/%m")
            detalle_completo = f"[{g.get('categoria', '')}] {g.get('detalle', '')}"
            monto_gasto = g.get("monto", 0)
            
            if g.get("fecha") == hoy_str:
                egresos_hoy += monto_gasto

            tabla_semana_egresos.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(fecha_formato)),
                ft.DataCell(ft.Text(detalle_completo)),
                ft.DataCell(ft.Text(f"${monto_gasto:,.2f}", color="red"))
            ]))
            total_gastos_sem += monto_gasto
            
        tabla_semana_egresos.rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Text("TOTAL EGRESOS", weight="bold")),
            ft.DataCell(ft.Text("")),
            ft.DataCell(ft.Text(f"${total_gastos_sem:,.2f}", color="red", weight="bold"))
        ]))

        saldo_dia = ingresos_hoy - egresos_hoy
        txt_ingresos_hoy.value = f"Ingresos Hoy: ${ingresos_hoy:,.2f}"
        txt_egresos_hoy.value = f"Egresos Hoy: ${egresos_hoy:,.2f}"
        txt_saldo_dia.value = f"SALDO DEL DÍA (CAJA): ${saldo_dia:,.2f}"
        txt_saldo_dia.color = "blue_700" if saldo_dia >= 0 else "red_700"
        
        saldo_semana = total_ingresos_sem - total_gastos_sem
        txt_saldo_semana.value = f"SALDO NETO SEMANAL: ${saldo_semana:,.2f}"

        mes_actual = hoy_dt.month
        año_actual = hoy_dt.year
        mes_anterior = mes_actual - 1 if mes_actual > 1 else 12
        año_anterior = año_actual if mes_actual > 1 else año_actual - 1

        ingresos_mes_actual = sum(m.get("monto", 0) for m in bd["movimientos"] if datetime.strptime(m["fecha"], "%Y-%m-%d").month == mes_actual and datetime.strptime(m["fecha"], "%Y-%m-%d").year == año_actual)
        ingresos_mes_ant = sum(m.get("monto", 0) for m in bd["movimientos"] if datetime.strptime(m["fecha"], "%Y-%m-%d").month == mes_anterior and datetime.strptime(m["fecha"], "%Y-%m-%d").year == año_anterior)

        txt_est_mes_actual.value = f"Ingresos Mes Actual: ${ingresos_mes_actual:,.2f}"
        txt_est_mes_anterior.value = f"Ingresos Mes Anterior: ${ingresos_mes_ant:,.2f}"
        
        if ingresos_mes_ant > 0:
            crecimiento = ((ingresos_mes_actual - ingresos_mes_ant) / ingresos_mes_ant) * 100
            txt_est_crecimiento.value = f"Evolución: {crecimiento:+.2f}%"
            txt_est_crecimiento.color = "green" if crecimiento >= 0 else "red"
        else:
            txt_est_crecimiento.value = "Evolución: N/A (Faltan datos previos)"
            txt_est_crecimiento.color = "grey"

        lista_facturas_pendientes.controls.clear()
        facturas = [f for f in bd["facturas_pendientes"] if f.get("estado") == "PENDIENTE"]
        if not facturas:
            lista_facturas_pendientes.controls.append(ft.Text("✅ No hay facturas de proveedores pendientes.", color="green"))
        
        for f in facturas:
            try:
                venc_dt = datetime.strptime(f["vencimiento"], "%d/%m/%Y").date()
                dias_restantes = (venc_dt - hoy_dt).days
                
                if dias_restantes < 0:
                    estado_txt = f"🔴 VENCIDA (hace {abs(dias_restantes)} días)"
                    color_bg = "#FFEBEE"
                elif dias_restantes == 0:
                    estado_txt = "🔴 VENCE HOY"
                    color_bg = "#FFEBEE"
                elif dias_restantes <= 3:
                    estado_txt = f"🟡 VENCE PRONTO ({dias_restantes} días)"
                    color_bg = "#FFF3E0"
                else:
                    estado_txt = f"🟢 AL DÍA (Vence el {f['vencimiento']})"
                    color_bg = "#E8F5E9"
                
                def marcar_pagado(e, item=f):
                    item["estado"] = "PAGADO"
                    guardar_datos(bd)
                    actualizar_ui()
                    mostrar_alerta("Factura marcada como pagada.", "green")

                lista_facturas_pendientes.controls.append(
                    ft.Container(
                        bgcolor=color_bg, padding=10, border_radius=5,
                        content=ft.Column([
                            ft.Text(f"Proveedor: {f.get('proveedor')}", weight="bold"),
                            ft.Text(f"Monto: ${f.get('monto', 0):,.2f} | {estado_txt}"),
                            ft.TextButton("✅ Marcar como Pagada", on_click=marcar_pagado)
                        ])
                    )
                )
            except ValueError:
                pass

        page.update()

    def forzar_sincronizacion(e):
        nonlocal bd
        bd = cargar_datos()
        actualizar_ui()
        mostrar_alerta("Base de datos actualizada correctamente con la nube.", "blue")

    btn_actualizar = ft.ElevatedButton("🔄 Actualizar Base de Datos", on_click=forzar_sincronizacion, bgcolor="blue_grey_50")

    def procesar_cierre_diario(e):
        bd["cierres"].append({
            "fecha": hoy_str,
            "hora_cierre": datetime.now().strftime('%H:%M'),
            "cerrado_por": sesion["usuario"],
            "ingresos_dia": txt_ingresos_hoy.value,
            "egresos_dia": txt_egresos_hoy.value,
            "saldo_dia": txt_saldo_dia.value
        })
        guardar_datos(bd)
        mostrar_alerta("Día cerrado y guardado correctamente en la base de datos.", "green")
        
    btn_cierre_dia = ft.ElevatedButton("🔒 REALIZAR CIERRE DIARIO", on_click=procesar_cierre_diario, bgcolor="black", color="white", width=300)

    def revisar_alertas_emergentes():
        facturas_criticas = []
        for f in bd["facturas_pendientes"]:
            if f.get("estado") == "PENDIENTE":
                try:
                    venc_dt = datetime.strptime(f["vencimiento"], "%d/%m/%Y").date()
                    if venc_dt <= hoy_dt: 
                        facturas_criticas.append(f)
                except ValueError:
                    pass
        
        if facturas_criticas:
            contenido_alerta = ft.Column([ft.Text("¡Atención! Las siguientes facturas requieren pago inmediato:", weight="bold")])
            for fc in facturas_criticas:
                contenido_alerta.controls.append(ft.Text(f"- {fc['proveedor']} por ${fc['monto']:,.2f} (Venc: {fc['vencimiento']})", color="red"))
            
            dlg_alerta = ft.AlertDialog(
                title=ft.Text("⚠️ AVISO DE VENCIMIENTOS", color="red"),
                content=contenido_alerta,
                actions=[ft.TextButton("Entendido", on_click=lambda e: cerrar_alerta(dlg_alerta))]
            )
            page.overlay.append(dlg_alerta)
            dlg_alerta.open = True
            page.update()

    def cerrar_alerta(dialogo):
        dialogo.open = False
        page.update()

    # --- FORMULARIOS DE CARGA ---
    inp_venta_monto = ft.TextField(label="Monto Ingreso ($)", keyboard_type="number", border_color="green")
    sel_venta_medio = ft.Dropdown(options=[ft.dropdown.Option("EFECTIVO"), ft.dropdown.Option("TARJETA / VIRTUAL")], value="EFECTIVO")
    
    def registrar_venta(e):
        if not inp_venta_monto.value: return mostrar_alerta("Ingresá un monto.")
        try:
            monto = float(inp_venta_monto.value)
            bd["movimientos"].append({
                "fecha": hoy_str, "usuario": sesion["usuario"],
                "monto": monto, "medio": sel_venta_medio.value
            })
            guardar_datos(bd)
            inp_venta_monto.value = ""
            actualizar_ui()
            mostrar_alerta("Ingreso registrado en la planilla.", "green")
        except ValueError: mostrar_alerta("Monto inválido.")

    sel_gasto_cat = ft.Dropdown(
        label="Categoría de Salida", 
        options=[
            ft.dropdown.Option("Pago a Proveedor"), 
            ft.dropdown.Option("Gasto Vario"), 
            ft.dropdown.Option("Retiro de Caja")
        ], 
        value="Pago a Proveedor"
    )
    inp_gasto_detalle = ft.TextField(label="Detalle Opcional (Ej: Filtros Mann / Retiro Sergio)", border_color="red")
    inp_gasto_monto = ft.TextField(label="Monto Salida ($)", keyboard_type="number", border_color="red")
    
    def registrar_gasto(e):
        if not inp_gasto_monto.value: return mostrar_alerta("El monto es obligatorio.")
        try:
            monto = float(inp_gasto_monto.value)
            bd["gastos"].append({
                "fecha": hoy_str, "usuario": sesion["usuario"],
                "categoria": sel_gasto_cat.value, "detalle": inp_gasto_detalle.value, "monto": monto
            })
            guardar_datos(bd)
            inp_gasto_detalle.value = ""; inp_gasto_monto.value = ""
            actualizar_ui()
            mostrar_alerta("Egreso/Retiro registrado.", "orange")
        except ValueError: mostrar_alerta("Monto inválido.")

    inp_fac_proveedor = ft.TextField(label="Nombre del Proveedor")
    inp_fac_monto = ft.TextField(label="Monto de la Factura ($)", keyboard_type="number")
    inp_fac_venc = ft.TextField(label="Vencimiento (DD/MM/YYYY)")

    def registrar_factura(e):
        if not inp_fac_monto.value or not inp_fac_venc.value or not inp_fac_proveedor.value: 
            return mostrar_alerta("Todos los campos son obligatorios.")
        try:
            monto = float(inp_fac_monto.value)
            datetime.strptime(inp_fac_venc.value, "%d/%m/%Y")
            if "facturas_pendientes" not in bd: bd["facturas_pendientes"] = []
            bd["facturas_pendientes"].append({
                "proveedor": inp_fac_proveedor.value, "monto": monto, 
                "vencimiento": inp_fac_venc.value, "estado": "PENDIENTE",
                "cargado_por": sesion["usuario"]
            })
            guardar_datos(bd)
            inp_fac_proveedor.value = ""; inp_fac_monto.value = ""; inp_fac_venc.value = ""
            actualizar_ui()
            mostrar_alerta("Factura guardada para futuras alertas.", "blue")
        except ValueError: mostrar_alerta("Revisá que el monto sea número y la fecha DD/MM/YYYY.")

    # --- VISTAS PRINCIPALES ---
    # Se quitó el atributo scroll="always" de las columnas de vista para evitar el choque con page.scroll
    vista_planilla = ft.Column([
        ft.Row([txt_info_sesion, btn_actualizar], alignment="spaceBetween"), ft.Divider(),
        
        ft.Container(
            content=ft.Column([
                ft.Row([txt_ingresos_hoy, txt_egresos_hoy], alignment="center", spacing=20),
                ft.Row([txt_saldo_dia], alignment="center"),
                ft.Row([btn_cierre_dia], alignment="center"),
                ft.Divider(),
                ft.Row([txt_saldo_semana], alignment="center")
            ]), 
            bgcolor="#E3F2FD", padding=15, border_radius=10
        ),
        ft.Divider(),

        ft.Text("Registro de Caja / Mostrador", size=18, weight="bold"),
        ft.Card(ft.Container(padding=10, content=ft.Column([
            ft.Row([inp_venta_monto, sel_venta_medio]),
            ft.ElevatedButton("➕ Agregar Ingreso", on_click=registrar_venta, bgcolor="green", color="white"),
            ft.Divider(),
            sel_gasto_cat,
            ft.Row([inp_gasto_detalle, inp_gasto_monto]),
            ft.ElevatedButton("➖ Extraer / Registrar Salida", on_click=registrar_gasto, bgcolor="red", color="white")
        ]))),
        
        ft.Divider(),
        ft.Text("Planilla Semanal - Ingresos", size=18, weight="bold", color="green_700"),
        contenedor_ingresos,
        ft.Text("Planilla Semanal - Egresos (Discriminados)", size=18, weight="bold", color="red_700"),
        contenedor_egresos,
    ], visible=False)

    vista_estadisticas = ft.Column([
        ft.Text("Evolución Comercial", size=22, weight="bold", color="blue_900"),
        ft.Divider(),
        ft.Card(ft.Container(padding=20, content=ft.Column([
            txt_est_mes_actual, txt_est_mes_anterior, ft.Divider(), txt_est_crecimiento
        ]))),
        ft.Text("Nota: Se irán sumando comparativas anuales a medida que se acumulen datos.", size=12, color="grey")
    ], visible=False)

    vista_proveedores = ft.Column([
        ft.Text("Gestión de Pago a Proveedores", size=22, weight="bold", color="orange_900"),
        ft.Divider(),
        ft.Text("Cargar Nueva Factura", weight="bold"),
        inp_fac_proveedor,
        ft.Row([inp_fac_monto, inp_fac_venc]),
        ft.ElevatedButton("Guardar Factura", on_click=registrar_factura, bgcolor="blue", color="white"),
        ft.Divider(),
        ft.Text("Facturas Pendientes de Pago", weight="bold"),
        lista_facturas_pendientes
    ], visible=False)

    # --- NAVEGACIÓN ---
    barra_navegacion = ft.Row([
        ft.ElevatedButton("📊 Planilla", on_click=lambda _: cambiar_vista(0), expand=True),
        ft.ElevatedButton("📈 Estadísticas", on_click=lambda _: cambiar_vista(1), expand=True),
        ft.ElevatedButton("🚚 Proveedores", on_click=lambda _: cambiar_vista(2), expand=True)
    ], visible=False)

    def cambiar_vista(indice):
        vista_planilla.visible = (indice == 0)
        vista_estadisticas.visible = (indice == 1)
        vista_proveedores.visible = (indice == 2)
        page.update()

    # --- PANTALLA DE LOGIN ---
    sel_usuario = ft.Dropdown(label="Seleccionar Usuario", options=[
        ft.dropdown.Option("Mamá"), ft.dropdown.Option("Julián"), ft.dropdown.Option("Sergio")
    ], width=300)
    
    inp_clave = ft.TextField(label="Clave de Acceso", password=True, can_reveal_password=True, width=300)
    
    def loguear(e):
        if not sel_usuario.value: return mostrar_alerta("Elegí un usuario.")
        if inp_clave.value != "181214": return mostrar_alerta("Clave incorrecta.")
        
        sesion["usuario"] = sel_usuario.value
        
        pantalla_login.visible = False
        barra_navegacion.visible = True
        vista_planilla.visible = True
        
        actualizar_ui()
        revisar_alertas_emergentes() 

    btn_entrar = ft.ElevatedButton("Iniciar Sesión", on_click=loguear, width=300, bgcolor="blue_900", color="white")

    pantalla_login = ft.Column([
        ft.Text("REPUESTERA HAFID", size=30, weight="bold", color="blue_900"), 
        ft.Text("Sistema de Gestión y Planilla Diaria", size=16, color="grey"),
        ft.Divider(),
        sel_usuario,
        inp_clave,
        ft.Container(height=10),
        btn_entrar
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    page.add(pantalla_login, barra_navegacion, ft.Divider(), vista_planilla, vista_estadisticas, vista_proveedores)

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 8080))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=puerto, host="0.0.0.0")