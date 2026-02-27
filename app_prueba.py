import flet as ft
import requests
import pandas as pd
import json
import os
from datetime import datetime, date, timedelta

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
                "cierres": data.get("cierres") or [],
                "facturas": data.get("facturas") or []
            }
    except Exception as e:
        print(f"Alerta: No se pudo conectar a la nube. {e}")
    return {"movimientos": [], "gastos": [], "cierres": [], "facturas": []}

def guardar_datos(datos):
    try:
        requests.put(FIREBASE_URL, json=datos, timeout=10)
    except Exception as e:
        print(f"Error crítico al guardar en la nube: {e}")

def main(page: ft.Page):
    page.title = "Repuestera - Sistema Integral"
    page.theme_mode = "light"
    page.scroll = "always"
    page.padding = 20
    
    bd = cargar_datos()
    
    hoy_dt = date.today()
    hoy_str = str(hoy_dt)
    hoy_formateado = datetime.now().strftime("%d/%m/%Y")
    
    inicio_semana_dt = hoy_dt - timedelta(days=hoy_dt.weekday()) 
    caja_cerrada_hoy = any(c.get("fecha") == hoy_str for c in bd.get("cierres", []))
    rol_actual = None 

    def mostrar_alerta(mensaje, color="red"):
        snack = ft.SnackBar(ft.Text(mensaje, color="white"), bgcolor=color)
        page.overlay.append(snack)
        snack.open = True
        page.update()

    # --- CINTA DE TOTALES (DIFERENCIA/SALDO) ---
    txt_ingresos_hoy = ft.Text("$0.00", size=20, weight="bold", color="green_900")
    txt_gastos_hoy = ft.Text("$0.00", size=20, weight="bold", color="red_900")
    txt_saldo_hoy = ft.Text("$0.00", size=20, weight="bold", color="blue_900")

    cinta_totales = ft.Row([
        ft.Container(ft.Column([ft.Text("INGRESOS (Hoy)", size=12), txt_ingresos_hoy]), bgcolor="#E8F5E9", padding=10, border_radius=8, expand=True),
        ft.Container(ft.Column([ft.Text("EGRESOS (Hoy)", size=12), txt_gastos_hoy]), bgcolor="#FFEBEE", padding=10, border_radius=8, expand=True),
        ft.Container(ft.Column([ft.Text("SALDO / DIF.", size=12, weight="bold"), txt_saldo_hoy]), bgcolor="#E3F2FD", padding=10, border_radius=8, expand=True),
    ])

    # --- TABLAS ESTILO EXCEL ---
    tabla_ventas = ft.DataTable(
        columns=[
            ft.DataColumn(label=ft.Text("DÍA", weight="bold")),
            ft.DataColumn(label=ft.Text("EFECTIVO", weight="bold"), numeric=True),
            ft.DataColumn(label=ft.Text("TARJETA", weight="bold"), numeric=True),
            ft.DataColumn(label=ft.Text("TOTAL", weight="bold", color="blue_900"), numeric=True),
        ],
        rows=[],
        column_spacing=15,
        heading_row_color="#E8F5E9",
    )

    tabla_gastos = ft.DataTable(
        columns=[
            ft.DataColumn(label=ft.Text("FECHA", weight="bold")),
            ft.DataColumn(label=ft.Text("CATEGORÍA / DETALLE", weight="bold")),
            ft.DataColumn(label=ft.Text("PAGO", weight="bold", color="red_900"), numeric=True),
        ],
        rows=[],
        column_spacing=15,
        heading_row_color="#FFEBEE",
    )
    
    # --- INPUTS DE CARGA ---
    inp_ing_monto = ft.TextField(label="Monto ($)", keyboard_type="number", border_color="blue", disabled=caja_cerrada_hoy)
    sel_ing_medio = ft.Dropdown(label="Cobrado en:", options=[ft.dropdown.Option("EFECTIVO"), ft.dropdown.Option("TARJETA / VIRTUAL")], value="EFECTIVO", disabled=caja_cerrada_hoy)
    btn_add_ingreso = ft.ElevatedButton("REGISTRAR VENTA", on_click=lambda _: registrar_ingreso(), disabled=caja_cerrada_hoy, bgcolor="blue", color="white")

    sel_gas_tipo = ft.Dropdown(label="Categoría:", options=[ft.dropdown.Option("Proveedor"), ft.dropdown.Option("Retiro de Caja"), ft.dropdown.Option("Gastos Varios")], value="Proveedor", disabled=caja_cerrada_hoy)
    inp_gas_detalle = ft.TextField(label="Detalle / Nombre", border_color="red", disabled=caja_cerrada_hoy)
    inp_gas_monto = ft.TextField(label="Pago ($)", keyboard_type="number", border_color="red", disabled=caja_cerrada_hoy)
    sel_gas_medio = ft.Dropdown(label="Salió de:", options=[ft.dropdown.Option("EFECTIVO (Del Cajón)"), ft.dropdown.Option("TRANSFERENCIA / BANCO")], value="EFECTIVO (Del Cajón)", disabled=caja_cerrada_hoy)
    btn_add_gasto = ft.ElevatedButton("REGISTRAR EGRESO", on_click=lambda _: registrar_egreso(), disabled=caja_cerrada_hoy, bgcolor="red", color="white")

    # --- PESTAÑA ADMIN ---
    txt_fisico_esperado = ft.Text("$0.0", size=24, weight="bold", color="green_700")
    txt_ganancia_neta = ft.Text("GANANCIA DEL DÍA: $0.0", size=18, weight="bold", color="blue")

    def actualizar_pantallas():
        tabla_ventas.rows.clear()
        tabla_gastos.rows.clear()
        
        nombres_dias = ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO"]
        total_ingresos_hoy = 0
        total_gastos_hoy = 0

        # Llenar Ventas
        for i in range(6):
            dia_eval = inicio_semana_dt + timedelta(days=i)
            dia_eval_str = str(dia_eval)
            movs_dia = [m for m in bd["movimientos"] if m.get("fecha") == dia_eval_str and not m.get("anulado") and m.get("tipo") == "INGRESO"]
            ef_sum = sum(m.get("monto", 0) for m in movs_dia if m.get("medio") == "EFECTIVO")
            ta_sum = sum(m.get("monto", 0) for m in movs_dia if m.get("medio") != "EFECTIVO")
            total = ef_sum + ta_sum
            if dia_eval_str == hoy_str: total_ingresos_hoy = total
            tabla_ventas.rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text(nombres_dias[i])), ft.DataCell(ft.Text(f"${ef_sum:,.2f}")), ft.DataCell(ft.Text(f"${ta_sum:,.2f}")), ft.DataCell(ft.Text(f"${total:,.2f}", weight="bold"))]))

        # Llenar Gastos (Agrupación de Retiros)
        gastos_hoy = [g for g in bd["gastos"] if g.get("fecha") == hoy_str and not g.get("anulado")]
        gastos_visu = {}
        for g in gastos_hoy:
            cat = g.get("categoria", "Gastos Varios")
            key = cat if cat == "Retiro de Caja" else f"{cat} - {g.get('concepto', '')}"
            gastos_visu[key] = gastos_visu.get(key, 0) + g.get("monto", 0)
            total_gastos_hoy += g.get("monto", 0)

        for conc, mont in gastos_visu.items():
            tabla_gastos.rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text(hoy_formateado)), ft.DataCell(ft.Text(conc)), ft.DataCell(ft.Text(f"${mont:,.2f}", color="red_700"))]))

        txt_ingresos_hoy.value = f"${total_ingresos_hoy:,.2f}"
        txt_gastos_hoy.value = f"${total_gastos_hoy:,.2f}"
        txt_saldo_hoy.value = f"${total_ingresos_hoy - total_gastos_hoy:,.2f}"
        
        # Resumen Admin
        movs_validos = [m for m in bd["movimientos"] if m.get("fecha") == hoy_str and not m.get("anulado")]
        v_efvo = sum(m.get("monto", 0) for m in movs_validos if m.get("medio") == "EFECTIVO" and m.get("tipo") == "INGRESO")
        g_efvo = sum(g.get("monto", 0) for g in gastos_hoy if g.get("medio") == "EFECTIVO (Del Cajón)")
        txt_fisico_esperado.value = f"${v_efvo - g_efvo:,.2f}"
        txt_ganancia_neta.value = f"GANANCIA DEL DÍA: ${total_ingresos_hoy - total_gastos_hoy:,.2f}"
        page.update()

    def registrar_ingreso():
        try:
            monto = float(inp_ing_monto.value)
            bd["movimientos"].append({"fecha": hoy_str, "hora": datetime.now().strftime('%H:%M'), "usuario": rol_actual, "concepto": "Venta", "monto": monto, "tipo": "INGRESO", "medio": sel_ing_medio.value, "anulado": False})
            guardar_datos(bd); inp_ing_monto.value = ""; actualizar_pantallas()
            mostrar_alerta("Venta registrada", "green")
        except: mostrar_alerta("Monto inválido")

    def registrar_egreso():
        try:
            monto = float(inp_gas_monto.value)
            bd["gastos"].append({"fecha": hoy_str, "hora": datetime.now().strftime('%H:%M'), "usuario": rol_actual, "categoria": sel_gas_tipo.value, "concepto": inp_gas_detalle.value, "monto": monto, "medio": sel_gas_medio.value, "anulado": False})
            guardar_datos(bd); inp_gas_monto.value = ""; inp_gas_detalle.value = ""; actualizar_pantallas()
            mostrar_alerta("Egreso registrado", "orange")
        except: mostrar_alerta("Monto inválido")

    seccion_ventas = ft.Container(padding=10, bgcolor="#FAFAFA", border_radius=10, content=ft.Column([
        ft.Text("MÓDULO DE VENTAS", size=18, weight="bold", color="blue_900"),
        ft.Row([inp_ing_monto, sel_ing_medio]), btn_add_ingreso, ft.Divider(),
        ft.Text("📊 FLUJO SEMANAL", weight="bold"), ft.Row([tabla_ventas], scroll="auto")
    ]))

    seccion_gastos = ft.Container(padding=10, bgcolor="#FAFAFA", border_radius=10, content=ft.Column([
        ft.Text("PAGOS / RETIROS", size=18, weight="bold", color="red_900"),
        ft.Row([sel_gas_tipo, inp_gas_detalle]), ft.Row([inp_gas_monto, sel_gas_medio]), btn_add_gasto, ft.Divider(),
        ft.Text("📉 DETALLE DE HOY", weight="bold"), ft.Row([tabla_gastos], scroll="auto")
    ]))

    vista_operativa = ft.Column([cinta_totales, ft.ResponsiveRow([
        ft.Column([seccion_ventas], col={"sm": 12, "md": 6}),
        ft.Column([seccion_gastos], col={"sm": 12, "md": 6})
    ])], visible=False)

    vista_resumen = ft.Column([
        ft.Row([ft.Text("CONTROL ADMIN", size=20, weight="bold"), ft.IconButton(ft.icons.AUTORENEW, on_click=lambda _: actualizar_pantallas())], alignment="spaceBetween"),
        ft.Card(content=ft.Container(padding=15, content=ft.Column([ft.Text("📦 EFECTIVO EN CAJÓN", weight="bold"), txt_fisico_esperado]))),
        ft.Card(content=ft.Container(padding=15, content=ft.Column([ft.Text("📊 RENTABILIDAD", weight="bold"), txt_ganancia_neta]))),
    ], visible=False)

    barra_botones = ft.Row([
        ft.ElevatedButton("📝 CARGA DATOS", on_click=lambda _: cambiar_vista(0), expand=True, bgcolor="blue", color="white"),
        ft.ElevatedButton("📊 ADMIN", on_click=lambda _: cambiar_vista(1), expand=True, bgcolor="green", color="white")
    ], visible=False)

    def cambiar_vista(i):
        vista_operativa.visible = (i == 0); vista_resumen.visible = (i == 1); page.update()

    inp_pin = ft.TextField(label="PIN", password=True, width=200)
    def loguear(e):
        if inp_pin.value == "181214":
            pantalla_login.visible = False; barra_botones.visible = True; vista_operativa.visible = True
            actualizar_pantallas(); page.update()
        else: mostrar_alerta("PIN incorrecto")

    pantalla_login = ft.Column([ft.Text("Acceso al Sistema", size=24, weight="bold"), inp_pin, ft.ElevatedButton("INGRESAR", on_click=loguear)], horizontal_alignment="center")
    page.add(pantalla_login, barra_botones, vista_operativa, vista_resumen)

if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=8080, host="0.0.0.0")