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
    page.padding = 15
    
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

    # --- CINTA DE TOTALES ---
    txt_ing_cinta = ft.Text("$0.0", size=20, weight="bold", color="green_700")
    txt_gas_cinta = ft.Text("$0.0", size=20, weight="bold", color="red_700")
    txt_saldo_cinta = ft.Text("$0.0", size=20, weight="bold", color="blue_700")

    cinta_totales = ft.Row([
        ft.Container(ft.Column([ft.Text("INGRESOS", size=10), txt_ing_cinta]), bgcolor="#E8F5E9", padding=10, border_radius=8, expand=True),
        ft.Container(ft.Column([ft.Text("EGRESOS", size=10), txt_gas_cinta]), bgcolor="#FFEBEE", padding=10, border_radius=8, expand=True),
        ft.Container(ft.Column([ft.Text("SALDO", size=10, weight="bold"), txt_saldo_cinta]), bgcolor="#E3F2FD", padding=10, border_radius=8, expand=True),
    ])

    # --- TABLAS OPERATIVAS ---
    tabla_ventas = ft.DataTable(
        columns=[ft.DataColumn(ft.Text("DÍA")), ft.DataColumn(ft.Text("EFECTIVO")), ft.DataColumn(ft.Text("TARJETA")), ft.DataColumn(ft.Text("TOTAL"))],
        rows=[], column_spacing=10, heading_row_color="#E8F5E9"
    )
    tabla_gastos = ft.DataTable(
        columns=[ft.DataColumn(ft.Text("FECHA")), ft.DataColumn(ft.Text("CONCEPTO")), ft.DataColumn(ft.Text("PAGO"))],
        rows=[], column_spacing=10, heading_row_color="#FFEBEE"
    )

    # --- ELEMENTOS DE RESUMEN ADMIN ---
    txt_fisico_esperado = ft.Text("$0.0", size=24, weight="bold", color="green_700")
    txt_virtual_esperado = ft.Text("$0.0", size=24, weight="bold", color="blue_700")
    txt_ganancia_neta = ft.Text("GANANCIA DEL DÍA: $0.0", size=18, weight="bold", color="blue")
    lista_alertas_ui = ft.Column(spacing=10)

    def actualizar_resumenes():
        # Limpiar Tablas
        tabla_ventas.rows.clear()
        tabla_gastos.rows.clear()
        
        movs_hoy = [m for m in bd["movimientos"] if m.get("fecha") == hoy_str and not m.get("anulado")]
        gastos_hoy = [g for g in bd["gastos"] if g.get("fecha") == hoy_str and not g.get("anulado")]

        v_efvo = sum(m.get("monto", 0) for m in movs_hoy if m.get("medio") == "EFECTIVO" and m.get("tipo") == "INGRESO")
        v_virt = sum(m.get("monto", 0) for m in movs_hoy if m.get("medio") != "EFECTIVO" and m.get("tipo") == "INGRESO")
        g_tot = sum(g.get("monto", 0) for g in gastos_hoy)
        
        # Actualizar Cinta
        txt_ing_cinta.value = f"${v_efvo + v_virt:,.2f}"
        txt_gas_cinta.value = f"${g_tot:,.2f}"
        txt_saldo_cinta.value = f"${(v_efvo + v_virt) - g_tot:,.2f}"

        # Llenar Tablas
        tabla_ventas.rows.append(ft.DataRow([ft.DataCell(ft.Text("HOY")), ft.DataCell(ft.Text(f"${v_efvo:,.2f}")), ft.DataCell(ft.Text(f"${v_virt:,.2f}")), ft.DataCell(ft.Text(f"${v_efvo + v_virt:,.2f}", weight="bold"))]))
        
        # Agrupación de Gastos/Retiros
        agrupados = {}
        for g in gastos_hoy:
            cat = g.get("categoria", "VARIOS")
            agrupados[cat] = agrupados.get(cat, 0) + g.get("monto", 0)
        for cat, monto in agrupados.items():
            tabla_gastos.rows.append(ft.DataRow([ft.DataCell(ft.Text(hoy_formateado)), ft.DataCell(ft.Text(cat)), ft.DataCell(ft.Text(f"${monto:,.2f}"))]))

        # Panel Admin
        txt_fisico_esperado.value = f"${v_efvo - sum(g.get('monto', 0) for g in gastos_hoy if g.get('medio') == 'EFECTIVO (Del Cajón)'):,.2f}"
        txt_ganancia_neta.value = f"GANANCIA DEL DÍA: ${(v_efvo + v_virt) - g_tot:,.2f}"
        
        # Alertas de Facturas
        lista_alertas_ui.controls.clear()
        for f in [f for f in bd["facturas"] if f.get("estado") == "PENDIENTE"]:
            lista_alertas_ui.controls.append(ft.Text(f"⚠️ {f.get('concepto')}: ${f.get('monto'):,.2f}", color="orange"))

        page.update()

    # --- INPUTS ---
    inp_ing_monto = ft.TextField(label="Monto Venta ($)", keyboard_type="number")
    sel_ing_medio = ft.Dropdown(label="Medio:", options=[ft.dropdown.Option("EFECTIVO"), ft.dropdown.Option("TARJETA / VIRTUAL")], value="EFECTIVO")
    
    sel_gas_tipo = ft.Dropdown(label="Categoría Egreso:", options=[ft.dropdown.Option("Proveedor"), ft.dropdown.Option("Retiro de Caja"), ft.dropdown.Option("Gastos Varios")], value="Proveedor")
    inp_gas_monto = ft.TextField(label="Monto Egreso ($)", keyboard_type="number")
    inp_gas_det = ft.TextField(label="Detalle")

    def registrar_ingreso():
        try:
            monto = float(inp_ing_monto.value)
            bd["movimientos"].append({"fecha": hoy_str, "hora": datetime.now().strftime('%H:%M'), "concepto": "Venta Mostrador", "monto": monto, "tipo": "INGRESO", "medio": sel_ing_medio.value, "anulado": False})
            guardar_datos(bd); inp_ing_monto.value = ""; actualizar_resumenes()
            mostrar_alerta("Venta grabada", "green")
        except: mostrar_alerta("Monto inválido")

    def registrar_gasto():
        try:
            monto = float(inp_gas_monto.value)
            bd["gastos"].append({"fecha": hoy_str, "categoria": sel_gas_tipo.value, "concepto": inp_gas_det.value, "monto": monto, "medio": "EFECTIVO (Del Cajón)", "anulado": False})
            guardar_datos(bd); inp_gas_monto.value = ""; inp_gas_det.value = ""; actualizar_resumenes()
            mostrar_alerta("Egreso grabado", "orange")
        except: mostrar_alerta("Monto inválido")

    # --- VISTAS ---
    vista_operativa = ft.Column([
        cinta_totales,
        ft.ResponsiveRow([
            ft.Column([ft.Text("CARGA VENTAS", weight="bold"), inp_ing_monto, sel_ing_medio, ft.ElevatedButton("GRABAR VENTA", on_click=lambda _: registrar_ingreso(), bgcolor="blue", color="white"), ft.Row([tabla_ventas], scroll="auto")], col={"sm": 12, "md": 6}),
            ft.Column([ft.Text("CARGA EGRESOS", weight="bold"), sel_gas_tipo, inp_gas_det, inp_gas_monto, ft.ElevatedButton("GRABAR EGRESO", on_click=lambda _: registrar_gasto(), bgcolor="red", color="white"), ft.Row([tabla_gastos], scroll="auto")], col={"sm": 12, "md": 6}),
        ])
    ], visible=False)

    vista_resumen = ft.Column([
        ft.Text("PANEL ADMINISTRATIVO", size=20, weight="bold"),
        ft.Card(ft.Container(ft.Column([ft.Text("EFECTIVO ESPERADO"), txt_fisico_esperado]), padding=15)),
        ft.Card(ft.Container(ft.Column([ft.Text("ALERTAS"), lista_alertas_ui]), padding=15)),
        ft.ElevatedButton("EXPORTAR EXCEL", on_click=lambda _: None, bgcolor="green", color="white")
    ], visible=False)

    barra_nav = ft.Row([
        ft.ElevatedButton("OPERACIÓN", on_click=lambda _: cambiar_vista(0), expand=True),
        ft.ElevatedButton("ADMIN", on_click=lambda _: cambiar_vista(1), expand=True),
    ], visible=False)

    def cambiar_vista(i):
        vista_operativa.visible = (i == 0); vista_resumen.visible = (i == 1); page.update()

    inp_pin = ft.TextField(label="PIN", password=True, width=200)
    def acceder(e):
        if inp_pin.value == "181214":
            pantalla_login.visible = False; barra_nav.visible = True; vista_operativa.visible = True
            actualizar_resumenes()
    
    pantalla_login = ft.Column([ft.Text("SISTEMA MAGNUM", size=24), inp_pin, ft.ElevatedButton("ENTRAR", on_click=acceder)], horizontal_alignment="center")
    page.add(pantalla_login, barra_nav, vista_operativa, vista_resumen)

if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=int(os.environ.get("PORT", 8080)), host="0.0.0.0")