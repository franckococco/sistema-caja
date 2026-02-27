import flet as ft
import requests
import json
import os
from datetime import datetime, date, timedelta
import calendar

# --- CONEXIÓN A FIREBASE EN LA NUBE ---
FIREBASE_URL = "https://cajarepuestos-214aa-default-rtdb.firebaseio.com/caja_repuestos.json"

def cargar_datos():
    try:
        respuesta = requests.get(FIREBASE_URL, timeout=10)
        if respuesta.status_code == 200 and respuesta.json() is not None:
            data = respuesta.json()
            return {
                "movimientos": data.get("movimientos") or [],
                "gastos": data.get("gastos") or [],
                "pendientes": data.get("pendientes") or [] # Para cheques y facturas
            }
    except Exception as e:
        print(f"Alerta: No se pudo conectar a la nube. {e}")
    
    return {"movimientos": [], "gastos": [], "pendientes": []}

def guardar_datos(datos):
    try:
        requests.put(FIREBASE_URL, json=datos, timeout=10)
    except Exception as e:
        print(f"Error crítico al guardar en la nube: {e}")

def main(page: ft.Page):
    page.title = "Repuestera HAFID - Sistema de Gestión"
    page.theme_mode = "light"
    page.scroll = "always"
    page.padding = 20
    page.window.width = 500 
    page.window.height = 900

    bd = cargar_datos()
    hoy_dt = date.today()
    hoy_str = str(hoy_dt)
    
    # Variables de Sesión
    sesion = {"usuario": "", "turno": "", "fecha": hoy_str}

    def mostrar_alerta(mensaje, color="red"):
        snack = ft.SnackBar(ft.Text(mensaje, color="white"), bgcolor=color)
        page.overlay.append(snack)
        snack.open = True
        page.update()

    # --- ELEMENTOS DE CABECERA ---
    txt_info_sesion = ft.Text("", size=16, weight="bold", color="blue_900")
    
    # --- GRILLAS PLANILLA SEMANAL (Estilo Excel) ---
    tabla_semana_ingresos = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("DIA", weight="bold")),
            ft.DataColumn(ft.Text("EFECTIVO", weight="bold")),
            ft.DataColumn(ft.Text("TARJETA", weight="bold")),
            ft.DataColumn(ft.Text("TOTAL", weight="bold")),
        ],
        rows=[], heading_row_color="#E8F5E9"
    )

    tabla_semana_egresos = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("FECHA", weight="bold")),
            ft.DataColumn(ft.Text("PROVEEDOR / DETALLE", weight="bold")),
            ft.DataColumn(ft.Text("PAGO", weight="bold")),
        ],
        rows=[], heading_row_color="#FFEBEE"
    )

    contenedor_ingresos = ft.Row([tabla_semana_ingresos], scroll="always")
    contenedor_egresos = ft.Row([tabla_semana_egresos], scroll="always")

    # --- TEXTOS ESTADÍSTICAS ---
    txt_est_mes_actual = ft.Text("Mes Actual: $0.00", size=16, weight="bold", color="green_700")
    txt_est_mes_anterior = ft.Text("Mes Anterior: $0.00", size=16)
    txt_est_crecimiento = ft.Text("Evolución: 0%", size=16, weight="bold")
    
    lista_alertas_pendientes = ft.Column(spacing=10)

    # --- LÓGICA DE ACTUALIZACIÓN DE VISTAS ---
    def actualizar_ui():
        # 1. Actualizar Cabecera
        txt_info_sesion.value = f"Operador: {sesion['usuario']} | Turno: {sesion['turno']} | Fecha: {datetime.now().strftime('%d/%m/%Y')}"
        
        # 2. Lógica Planilla Semanal (Lunes a Sábado)
        inicio_semana = hoy_dt - timedelta(days=hoy_dt.weekday()) # Lunes
        dias_nombres = ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO"]
        
        tabla_semana_ingresos.rows.clear()
        total_efectivo_sem = 0
        total_tarjeta_sem = 0

        for i in range(6):
            dia_fecha = inicio_semana + timedelta(days=i)
            dia_str = str(dia_fecha)
            
            movs_dia = [m for m in bd["movimientos"] if m.get("fecha") == dia_str]
            efvo_dia = sum(m.get("monto", 0) for m in movs_dia if m.get("medio") == "EFECTIVO")
            tarj_dia = sum(m.get("monto", 0) for m in movs_dia if m.get("medio") == "TARJETA / VIRTUAL")
            total_dia = efvo_dia + tarj_dia
            
            total_efectivo_sem += efvo_dia
            total_tarjeta_sem += tarj_dia

            tabla_semana_ingresos.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(dias_nombres[i])),
                ft.DataCell(ft.Text(f"${efvo_dia:,.2f}")),
                ft.DataCell(ft.Text(f"${tarj_dia:,.2f}")),
                ft.DataCell(ft.Text(f"${total_dia:,.2f}", weight="bold"))
            ]))
        
        # Fila de Totales
        tabla_semana_ingresos.rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Text("TOTAL SEMANA", weight="bold")),
            ft.DataCell(ft.Text(f"${total_efectivo_sem:,.2f}", color="green", weight="bold")),
            ft.DataCell(ft.Text(f"${total_tarjeta_sem:,.2f}", color="green", weight="bold")),
            ft.DataCell(ft.Text(f"${(total_efectivo_sem + total_tarjeta_sem):,.2f}", color="blue", weight="bold"))
        ]))

        # Egresos de la Semana
        tabla_semana_egresos.rows.clear()
        gastos_semana = [g for g in bd["gastos"] if (inicio_semana <= datetime.strptime(g["fecha"], "%Y-%m-%d").date() <= inicio_semana + timedelta(days=6))]
        total_gastos_sem = 0
        
        for g in gastos_semana:
            fecha_formato = datetime.strptime(g["fecha"], "%Y-%m-%d").strftime("%d/%m")
            tabla_semana_egresos.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(fecha_formato)),
                ft.DataCell(ft.Text(g.get("proveedor", "Retiro/Gasto"))),
                ft.DataCell(ft.Text(f"${g.get('monto', 0):,.2f}", color="red"))
            ]))
            total_gastos_sem += g.get("monto", 0)
            
        tabla_semana_egresos.rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Text("GASTO TOTAL SEMANAL", weight="bold")),
            ft.DataCell(ft.Text("")),
            ft.DataCell(ft.Text(f"${total_gastos_sem:,.2f}", color="red", weight="bold"))
        ]))

        # 3. Lógica Estadísticas
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

        # 4. Lógica Alertas/Cheques
        lista_alertas_pendientes.controls.clear()
        pendientes = [p for p in bd["pendientes"] if p.get("estado") == "PENDIENTE"]
        if not pendientes:
            lista_alertas_pendientes.controls.append(ft.Text("✅ No hay cheques ni facturas pendientes.", color="green"))
        
        for p in pendientes:
            try:
                venc_dt = datetime.strptime(p["vencimiento"], "%d/%m/%Y").date()
                dias_restantes = (venc_dt - hoy_dt).days
                if dias_restantes < 0:
                    estado_txt = f"🔴 VENCIDO (hace {abs(dias_restantes)} días)"
                    color_bg = "#FFEBEE"
                elif dias_restantes <= 3:
                    estado_txt = f"🟡 VENCE PRONTO ({dias_restantes} días)"
                    color_bg = "#FFF3E0"
                else:
                    estado_txt = f"🟢 AL DÍA (Vence el {p['vencimiento']})"
                    color_bg = "#E8F5E9"
                
                def marcar_pagado(e, item=p):
                    item["estado"] = "PAGADO"
                    guardar_datos(bd)
                    actualizar_ui()
                    mostrar_alerta("Pago registrado con éxito.", "green")

                lista_alertas_pendientes.controls.append(
                    ft.Container(
                        bgcolor=color_bg, padding=10, border_radius=5,
                        content=ft.Column([
                            ft.Text(f"{p.get('tipo', 'Doc')}: {p.get('concepto')}", weight="bold"),
                            ft.Text(f"Monto: ${p.get('monto', 0):,.2f} | {estado_txt}"),
                            ft.TextButton("✅ Marcar como Pagado", on_click=marcar_pagado)
                        ])
                    )
                )
            except ValueError:
                pass

        page.update()

    # --- FORMULARIOS DE CARGA ---
    # Carga de Ingreso
    inp_venta_monto = ft.TextField(label="Monto Ingreso ($)", keyboard_type="number", border_color="green")
    sel_venta_medio = ft.Dropdown(options=[ft.dropdown.Option("EFECTIVO"), ft.dropdown.Option("TARJETA / VIRTUAL")], value="EFECTIVO")
    
    def registrar_venta(e):
        if not inp_venta_monto.value: return mostrar_alerta("Ingresá un monto.")
        try:
            monto = float(inp_venta_monto.value)
            bd["movimientos"].append({
                "fecha": hoy_str, "usuario": sesion["usuario"], "turno": sesion["turno"],
                "monto": monto, "medio": sel_venta_medio.value
            })
            guardar_datos(bd)
            inp_venta_monto.value = ""
            actualizar_ui()
            mostrar_alerta("Ingreso registrado en la planilla.", "green")
        except ValueError: mostrar_alerta("Monto inválido.")

    # Carga de Egreso
    inp_gasto_prov = ft.TextField(label="Proveedor / Detalle Gasto", border_color="red")
    inp_gasto_monto = ft.TextField(label="Monto Egreso ($)", keyboard_type="number", border_color="red")
    
    def registrar_gasto(e):
        if not inp_gasto_monto.value or not inp_gasto_prov.value: return mostrar_alerta("Completá Proveedor y Monto.")
        try:
            monto = float(inp_gasto_monto.value)
            bd["gastos"].append({
                "fecha": hoy_str, "usuario": sesion["usuario"], "turno": sesion["turno"],
                "proveedor": inp_gasto_prov.value, "monto": monto
            })
            guardar_datos(bd)
            inp_gasto_prov.value = ""; inp_gasto_monto.value = ""
            actualizar_ui()
            mostrar_alerta("Egreso registrado en la planilla.", "orange")
        except ValueError: mostrar_alerta("Monto inválido.")

    # Carga de Cheques/Alertas
    sel_tipo_doc = ft.Dropdown(options=[ft.dropdown.Option("Cheque"), ft.dropdown.Option("Factura")], value="Cheque")
    inp_doc_concepto = ft.TextField(label="Detalle (Ej: Cheque Banco Macro)")
    inp_doc_monto = ft.TextField(label="Monto ($)", keyboard_type="number")
    inp_doc_venc = ft.TextField(label="Vencimiento (DD/MM/YYYY)")

    def registrar_pendiente(e):
        if not inp_doc_monto.value or not inp_doc_venc.value: return mostrar_alerta("Monto y Vencimiento obligatorios.")
        try:
            monto = float(inp_doc_monto.value)
            datetime.strptime(inp_doc_venc.value, "%d/%m/%Y") # Validar formato
            bd["pendientes"].append({
                "tipo": sel_tipo_doc.value, "concepto": inp_doc_concepto.value,
                "monto": monto, "vencimiento": inp_doc_venc.value, "estado": "PENDIENTE",
                "cargado_por": sesion["usuario"]
            })
            guardar_datos(bd)
            inp_doc_concepto.value = ""; inp_doc_monto.value = ""; inp_doc_venc.value = ""
            actualizar_ui()
            mostrar_alerta("Programación guardada con éxito.", "blue")
        except ValueError: mostrar_alerta("Revisá que el monto sea un número y la fecha DD/MM/YYYY.")

    # --- VISTAS PRINCIPALES ---
    vista_planilla = ft.Column([
        ft.Row([txt_info_sesion], alignment="center"), ft.Divider(),
        
        ft.Text("Módulo de Carga Rápida", size=18, weight="bold"),
        ft.Card(ft.Container(padding=10, content=ft.Column([
            ft.Row([inp_venta_monto, sel_venta_medio]),
            ft.ElevatedButton("➕ Agregar Ingreso", on_click=registrar_venta, bgcolor="green", color="white"),
            ft.Divider(),
            ft.Row([inp_gasto_prov, inp_gasto_monto]),
            ft.ElevatedButton("➖ Agregar Egreso a Proveedor/Caja", on_click=registrar_gasto, bgcolor="red", color="white")
        ]))),
        
        ft.Divider(),
        ft.Text("Planilla Semanal - Ingresos", size=18, weight="bold", color="green_700"),
        contenedor_ingresos,
        ft.Text("Planilla Semanal - Egresos", size=18, weight="bold", color="red_700"),
        contenedor_egresos,
    ], visible=False, scroll="always")

    vista_estadisticas = ft.Column([
        ft.Text("Evolución Comercial", size=22, weight="bold", color="blue_900"),
        ft.Divider(),
        ft.Card(ft.Container(padding=20, content=ft.Column([
            txt_est_mes_actual, txt_est_mes_anterior, ft.Divider(), txt_est_crecimiento
        ]))),
        ft.Text("Nota: Se irán sumando comparativas anuales a medida que se acumulen datos.", size=12, color="grey")
    ], visible=False)

    vista_agenda = ft.Column([
        ft.Text("Agenda de Cheques y Facturas", size=22, weight="bold", color="orange_900"),
        ft.Divider(),
        ft.Text("Programar Nuevo Pago", weight="bold"),
        ft.Row([sel_tipo_doc, inp_doc_concepto]),
        ft.Row([inp_doc_monto, inp_doc_venc]),
        ft.ElevatedButton("Programar Alerta", on_click=registrar_pendiente, bgcolor="blue", color="white"),
        ft.Divider(),
        ft.Text("Tablero de Vencimientos Pendientes", weight="bold"),
        lista_alertas_pendientes
    ], visible=False, scroll="always")

    # --- NAVEGACIÓN ---
    barra_navegacion = ft.Row([
        ft.ElevatedButton("📊 Planilla", on_click=lambda _: cambiar_vista(0), expand=True),
        ft.ElevatedButton("📈 Estadísticas", on_click=lambda _: cambiar_vista(1), expand=True),
        ft.ElevatedButton("📅 Agenda", on_click=lambda _: cambiar_vista(2), expand=True)
    ], visible=False)

    def cambiar_vista(indice):
        vista_planilla.visible = (indice == 0)
        vista_estadisticas.visible = (indice == 1)
        vista_agenda.visible = (indice == 2)
        page.update()

    # --- PANTALLA DE LOGIN ---
    sel_usuario = ft.Dropdown(label="Seleccionar Usuario", options=[
        ft.dropdown.Option("Mamá"), ft.dropdown.Option("Julián"), ft.dropdown.Option("Sergio")
    ], width=300)
    
    sel_turno = ft.Dropdown(label="Turno", options=[
        ft.dropdown.Option("Mañana"), ft.dropdown.Option("Tarde")
    ], width=300)
    
    inp_clave = ft.TextField(label="Clave de Acceso", password=True, can_reveal_password=True, width=300)
    
    def loguear(e):
        if not sel_usuario.value or not sel_turno.value: return mostrar_alerta("Elegí usuario y turno.")
        if inp_clave.value != "181214": return mostrar_alerta("Clave incorrecta.") # Usamos la misma clave por ahora
        
        sesion["usuario"] = sel_usuario.value
        sesion["turno"] = sel_turno.value
        
        pantalla_login.visible = False
        barra_navegacion.visible = True
        vista_planilla.visible = True
        actualizar_ui()

    btn_entrar = ft.ElevatedButton("Iniciar Sesión", on_click=loguear, width=300, bgcolor="blue_900", color="white")

    pantalla_login = ft.Column([
        ft.Text("REPUESTERA HAFID", size=30, weight="bold", color="blue_900"), 
        ft.Text("Sistema de Gestión y Planilla Diaria", size=16, color="grey"),
        ft.Divider(),
        sel_usuario,
        sel_turno,
        inp_clave,
        ft.Container(height=10),
        btn_entrar
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    page.add(pantalla_login, barra_navegacion, ft.Divider(), vista_planilla, vista_estadisticas, vista_agenda)

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 8080))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=puerto, host="0.0.0.0")