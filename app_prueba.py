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
    page.title = "Magnum Valores SAS - Gestión Financiera"
    page.theme_mode = "light"
    page.scroll = "always"
    page.padding = 20
    page.window.width = 450 
    page.window.height = 900

    bd = cargar_datos()
    hoy_dt = date.today()
    hoy_str = str(hoy_dt)
    hoy_formateado = datetime.now().strftime("%d/%m/%Y")
    
    caja_cerrada_hoy = any(c.get("fecha") == hoy_str for c in bd.get("cierres", []))
    rol_actual = None 

    def mostrar_alerta(mensaje, color="red"):
        snack = ft.SnackBar(ft.Text(mensaje, color="white"), bgcolor=color)
        page.overlay.append(snack)
        snack.open = True
        page.update()

    # --- CINTA DE TOTALES SUPERIOR ---
    txt_tot_ingresos = ft.Text("$0.00", size=20, weight="bold", color="green_700")
    txt_tot_egresos = ft.Text("$0.00", size=20, weight="bold", color="red_700")
    txt_tot_saldo = ft.Text("$0.00", size=20, weight="bold", color="blue_700")

    cinta_totales = ft.Row([
        ft.Card(ft.Container(ft.Column([ft.Text("Ingresos", size=12), txt_tot_ingresos]), padding=10, width=120)),
        ft.Card(ft.Container(ft.Column([ft.Text("Egresos", size=12), txt_tot_egresos]), padding=10, width=120)),
        ft.Card(ft.Container(ft.Column([ft.Text("Diferencia", size=12), txt_tot_saldo]), padding=10, width=120))
    ], alignment="spaceBetween")

    # --- GRILLAS DE DATOS (ESTILO EXCEL) ---
    tabla_ventas = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Hora")),
            ft.DataColumn(ft.Text("Concepto")),
            ft.DataColumn(ft.Text("Medio")),
            ft.DataColumn(ft.Text("Monto", text_align="right")),
        ],
        rows=[]
    )
    
    tabla_egresos = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Hora")),
            ft.DataColumn(ft.Text("Categoría")),
            ft.DataColumn(ft.Text("Medio")),
            ft.DataColumn(ft.Text("Monto", text_align="right")),
        ],
        rows=[]
    )

    # Contenedores con scroll horizontal para evitar errores visuales (restricción técnica)
    contenedor_tabla_ventas = ft.Row([tabla_ventas], scroll="always")
    contenedor_tabla_egresos = ft.Row([tabla_egresos], scroll="always")

    # --- ACTUALIZACIÓN DE INTERFAZ Y LÓGICA DE NEGOCIO ---
    def actualizar_ui():
        # Cálculos del día
        movs_hoy = [m for m in bd["movimientos"] if m.get("fecha") == hoy_str and not m.get("anulado")]
        gastos_hoy = [g for g in bd["gastos"] if g.get("fecha") == hoy_str and not g.get("anulado")]

        tot_ingresos = sum(m.get("monto", 0) for m in movs_hoy)
        tot_egresos = sum(g.get("monto", 0) for g in gastos_hoy)
        saldo_neto = tot_ingresos - tot_egresos

        txt_tot_ingresos.value = f"${tot_ingresos:,.2f}"
        txt_tot_egresos.value = f"${tot_egresos:,.2f}"
        txt_tot_saldo.value = f"${saldo_neto:,.2f}"
        txt_tot_saldo.color = "blue_700" if saldo_neto >= 0 else "red_700"

        # Llenar grilla de Ventas
        tabla_ventas.rows.clear()
        for m in reversed(movs_hoy):
            tabla_ventas.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(m.get("hora", ""))),
                ft.DataCell(ft.Text(m.get("concepto", ""))),
                ft.DataCell(ft.Text(m.get("medio", ""))),
                ft.DataCell(ft.Text(f"${m.get('monto', 0):,.2f}", color="green"))
            ]))

        # Llenar grilla de Egresos con Agrupación Inteligente de Retiros
        tabla_egresos.rows.clear()
        
        gastos_normales = [g for g in gastos_hoy if g.get("categoria") != "Retiro de Caja"]
        retiros = [g for g in gastos_hoy if g.get("categoria") == "Retiro de Caja"]
        
        for g in reversed(gastos_normales):
            detalle = g.get("detalle", "")
            cat_desc = f"{g.get('categoria')} - {detalle}" if detalle else g.get('categoria')
            tabla_egresos.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(g.get("hora", ""))),
                ft.DataCell(ft.Text(cat_desc)),
                ft.DataCell(ft.Text(g.get("medio", ""))),
                ft.DataCell(ft.Text(f"${g.get('monto', 0):,.2f}", color="red"))
            ]))

        # Agrupación de retiros en una sola línea (si hay)
        if retiros:
            total_retiros = sum(r.get("monto", 0) for r in retiros)
            tabla_egresos.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text("--:--")),
                ft.DataCell(ft.Text("RETIROS DE CAJA (Acumulado)", weight="bold")),
                ft.DataCell(ft.Text("Múltiple")),
                ft.DataCell(ft.Text(f"${total_retiros:,.2f}", color="orange", weight="bold"))
            ]))

        page.update()

    # --- MÓDULO RÁPIDO DE VENTAS ---
    inp_venta_monto = ft.TextField(label="Monto de la Venta ($)", keyboard_type="number", border_color="green", disabled=caja_cerrada_hoy)
    sel_venta_medio = ft.Dropdown(options=[ft.dropdown.Option("EFECTIVO"), ft.dropdown.Option("VIRTUAL")], value="EFECTIVO", width=150, disabled=caja_cerrada_hoy)
    
    def registrar_venta(e):
        if caja_cerrada_hoy: return mostrar_alerta("Caja cerrada.")
        if not inp_venta_monto.value: return mostrar_alerta("Ingresá un monto.")
        try:
            monto = float(inp_venta_monto.value)
            bd["movimientos"].append({
                "fecha": hoy_str, "hora": datetime.now().strftime('%H:%M'), "usuario": rol_actual,
                "concepto": "Venta de Mostrador", "monto": monto,
                "medio": sel_venta_medio.value, "anulado": False
            })
            guardar_datos(bd)
            inp_venta_monto.value = ""
            actualizar_ui()
            mostrar_alerta("Venta rápida registrada.", "green")
        except ValueError:
            mostrar_alerta("Monto inválido.")

    btn_add_venta = ft.ElevatedButton("Cobrar Venta", on_click=registrar_venta, bgcolor="green", color="white", disabled=caja_cerrada_hoy)

    # --- MÓDULO DISCRIMINADO DE EGRESOS ---
    sel_gasto_cat = ft.Dropdown(
        label="Categoría",
        options=[ft.dropdown.Option("Proveedor"), ft.dropdown.Option("Retiro de Caja"), ft.dropdown.Option("Gastos Varios")],
        value="Gastos Varios", disabled=caja_cerrada_hoy
    )
    inp_gasto_detalle = ft.TextField(label="Detalle Opcional", disabled=caja_cerrada_hoy)
    inp_gasto_monto = ft.TextField(label="Monto ($)", keyboard_type="number", border_color="red", disabled=caja_cerrada_hoy)
    sel_gasto_medio = ft.Dropdown(options=[ft.dropdown.Option("EFECTIVO (Del Cajón)"), ft.dropdown.Option("TRANSFERENCIA")], value="EFECTIVO (Del Cajón)", width=200, disabled=caja_cerrada_hoy)

    def registrar_egreso(e):
        if caja_cerrada_hoy: return mostrar_alerta("Caja cerrada.")
        if not inp_gasto_monto.value: return mostrar_alerta("El monto es obligatorio.")
        try:
            monto = float(inp_gasto_monto.value)
            bd["gastos"].append({
                "fecha": hoy_str, "hora": datetime.now().strftime('%H:%M'), "usuario": rol_actual,
                "categoria": sel_gasto_cat.value, "detalle": inp_gasto_detalle.value,
                "monto": monto, "medio": sel_gasto_medio.value, "anulado": False
            })
            guardar_datos(bd)
            inp_gasto_monto.value = ""; inp_gasto_detalle.value = ""
            actualizar_ui()
            mostrar_alerta("Egreso registrado y sincronizado.", "orange")
        except ValueError:
            mostrar_alerta("Monto numérico requerido.")

    btn_add_gasto = ft.ElevatedButton("Registrar Egreso", on_click=registrar_egreso, bgcolor="red", color="white", disabled=caja_cerrada_hoy)

    # --- SISTEMA DE LOGIN Y VISTAS ---
    vista_operativa = ft.Column([
        ft.Text("Cinta de Totales del Día", weight="bold"),
        cinta_totales,
        ft.Divider(),
        
        ft.Text("Módulo Rápido de Ventas", size=18, weight="bold", color="green"),
        ft.Row([inp_venta_monto, sel_venta_medio]),
        btn_add_venta,
        ft.Divider(),

        ft.Text("Módulo Discriminado de Egresos", size=18, weight="bold", color="red"),
        sel_gasto_cat, inp_gasto_detalle, 
        ft.Row([inp_gasto_monto, sel_gasto_medio]),
        btn_add_gasto,
        ft.Divider(),

        ft.Text("Flujo de Ingresos", weight="bold"),
        contenedor_tabla_ventas,
        
        ft.Text("Detalle de Salidas y Retiros", weight="bold"),
        contenedor_tabla_egresos
    ], visible=False)

    inp_pin = ft.TextField(label="PIN Contable", password=True, can_reveal_password=True, width=200, visible=False)
    
    def loguear(rol):
        nonlocal rol_actual
        if rol == "ADMIN":
            if inp_pin.value != "181214": return mostrar_alerta("PIN incorrecto.")
        rol_actual = rol
        pantalla_login.visible = False
        vista_operativa.visible = True
        actualizar_ui()

    btn_entrar_admin = ft.ElevatedButton("Entrar al Sistema Contable", on_click=lambda _: loguear("ADMIN"), bgcolor="black", color="white", visible=False)

    pantalla_login = ft.Column([
        ft.Text("Magnum Valores SAS", size=26, weight="bold", color="blue_900"), 
        ft.Text("Plataforma de Gestión Integrada", size=14, color="grey"),
        ft.Divider(),
        ft.ElevatedButton("Acceso Operativo (Mostrador)", on_click=lambda _: loguear("OPERARIO"), width=300, height=50, bgcolor="blue", color="white"),
        ft.Container(height=30),
        ft.ElevatedButton("Acceso Administración", on_click=lambda _: setattr(inp_pin, 'visible', True) or setattr(btn_entrar_admin, 'visible', True) or page.update(), width=300),
        inp_pin, btn_entrar_admin
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    page.add(pantalla_login, vista_operativa)

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 8080))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=puerto, host="0.0.0.0")