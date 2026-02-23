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
    page.title = "REPUESTERA HAFID"
    page.theme_mode = "light"
    page.scroll = "always"
    page.padding = 15
    page.window.width = 400 
    page.window.height = 850
    page.window.always_on_top = True

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

    # --- FUNCIONALIDAD DE REAPERTURA Y BACKUP (ADMIN) ---
    def reabrir_caja(e):
        nonlocal caja_cerrada_hoy, bd
        bd["cierres"] = [c for c in bd["cierres"] if c.get("fecha") != hoy_str]
        guardar_datos(bd)
        caja_cerrada_hoy = False
        habilirar_inputs(True)
        txt_estado_caja.value = "ESTADO: CAJA ABIERTA 🟢"
        txt_estado_caja.color = "green"
        btn_reabrir.visible = False 
        page.update()
        mostrar_alerta("¡Caja reabierta con éxito!", "green")

    def hacer_backup(e):
        try:
            datos_nube = cargar_datos() # Traemos lo más fresco de la nube
            nombre_archivo = f"Backup_Caja_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(nombre_archivo, "w", encoding="utf-8") as f:
                json.dump(datos_nube, f, indent=4)
            mostrar_alerta(f"Backup guardado en tu PC: {nombre_archivo}", "green")
        except Exception as ex:
            mostrar_alerta(f"Error al crear backup: {ex}")

    btn_reabrir = ft.Button("🔓 REABRIR CAJA HOY", on_click=reabrir_caja, bgcolor="orange", color="white", visible=False)
    btn_backup = ft.Button("💾 DESCARGAR BACKUP", on_click=hacer_backup, bgcolor="blue_grey_800", color="white", width=300)

    def habilirar_inputs(habilitar):
        estado = not habilitar
        inp_ing_concepto.disabled = estado
        inp_ing_monto.disabled = estado
        sel_ing_medio.disabled = estado
        btn_add_ingreso.disabled = estado
        sel_gas_tipo_registro.disabled = estado
        inp_gas_concepto.disabled = estado
        inp_gas_monto.disabled = estado
        sel_gas_cat.disabled = estado
        sel_gas_medio.disabled = estado
        btn_add_gasto.disabled = estado
        inp_arqueo.disabled = estado
        btn_cerrar.disabled = estado

    # --- TEXTOS VISUALES ---
    txt_fecha_op1 = ft.Text(f"📅 Turno: {hoy_formateado}", size=18, weight="bold", color="blue_900")
    txt_fecha_op2 = ft.Text(f"📅 Turno: {hoy_formateado}", size=18, weight="bold", color="blue_900")
    
    txt_op_efectivo_esperado = ft.Text("EFECTIVO EN CAJA: $0.0", color="green_700", weight="bold", size=16)
    txt_op_virtual_esperado = ft.Text("TOTAL VIRTUAL: $0.0", color="blue_700", weight="bold", size=16)
    txt_op_gastos_hoy = ft.Text("Gastos pagados hoy: $0.0", color="red", size=13)
    txt_op_retiros_hoy = ft.Text("Retiros de caja: $0.0", color="orange_700", size=13)

    txt_fecha_resumen = ft.Text(f"📅 Resumen del Día: {hoy_formateado}", size=20, weight="bold", color="blue_900")
    txt_estado_caja = ft.Text("ESTADO: CAJA CERRADA 🔴" if caja_cerrada_hoy else "ESTADO: CAJA ABIERTA 🟢", size=14, weight="bold", color="red" if caja_cerrada_hoy else "green")
    
    txt_fisico_esperado = ft.Text("$0.0", size=24, weight="bold", color="green_700")
    txt_detalle_cajon = ft.Text("", size=13, color="black54")
    
    txt_virtual_esperado = ft.Text("$0.0", size=24, weight="bold", color="blue_700")
    txt_detalle_virtual = ft.Text("", size=13, color="black54")

    txt_ventas_reales = ft.Text("Ventas Totales: $0.0", size=14)
    txt_gastos_reales = ft.Text("Gastos Totales: $0.0", size=14)
    txt_ganancia_neta = ft.Text("GANANCIA DEL DÍA: $0.0", size=18, weight="bold", color="blue")
    txt_acum_semanal = ft.Text("Balance Semanal: $0.0", size=14, weight="bold", color="blue_700")
    txt_acum_mensual = ft.Text("Balance Mensual: $0.0", size=14, weight="bold", color="blue_900")
    txt_stat_retiros = ft.Text("Extracciones/Retiros: $0.0", size=14, color="orange_700")
    ui_stat_gastos = ft.Column(spacing=2)
    txt_stat_porcentajes = ft.Text("Efectivo: 0% | Virtual: 0%", size=14, weight="bold")

    lista_efectivo_ui = ft.Column(spacing=5)
    lista_virtual_ui = ft.Column(spacing=5)
    lista_gastos_ui = ft.Column(spacing=5)
    lista_alertas_ui = ft.Column(spacing=10)

    # --- LÓGICA DE ANULACIÓN ---
    item_a_anular = None
    inp_motivo_anulacion = ft.TextField(label="Motivo de la anulación")
    
    def confirmar_anulacion(e):
        if not inp_motivo_anulacion.value: return mostrar_alerta("El motivo es obligatorio.")
        if item_a_anular:
            item_a_anular["anulado"] = True
            item_a_anular["motivo_anulacion"] = inp_motivo_anulacion.value
            item_a_anular["anulado_por"] = rol_actual
            guardar_datos(bd)
            dlg_anular.open = False
            actualizar_resumenes()
            mostrar_alerta("Registro anulado y subido a la nube.", "orange")

    dlg_anular = ft.AlertDialog(
        title=ft.Text("⚠️ Anular Registro"),
        content=ft.Column([ft.Text("No se borrará, quedará tachado."), inp_motivo_anulacion], tight=True),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: setattr(dlg_anular, 'open', False) or page.update()),
            ft.TextButton("Confirmar", on_click=confirmar_anulacion, style=ft.ButtonStyle(color="red")),
        ]
    )
    page.overlay.append(dlg_anular)

    def abrir_anular(item):
        nonlocal item_a_anular
        if caja_cerrada_hoy and rol_actual != "ADMIN": return mostrar_alerta("Solo Admin anula con caja cerrada.")
        item_a_anular = item
        inp_motivo_anulacion.value = ""
        dlg_anular.open = True
        page.update()

    # --- LÓGICA DE VENCIMIENTOS ---
    factura_seleccionada = None
    inp_fecha_venc = ft.TextField(label="Vencimiento (DD/MM/YYYY)", hint_text="Ej: 25/02/2026")

    def guardar_vencimiento(e):
        if factura_seleccionada:
            try:
                datetime.strptime(inp_fecha_venc.value, "%d/%m/%Y")
                factura_seleccionada["vencimiento"] = inp_fecha_venc.value
                guardar_datos(bd)
                dlg_vencimiento.open = False
                actualizar_resumenes()
                mostrar_alerta("Fecha asignada y sincronizada.", "green")
            except ValueError:
                mostrar_alerta("Formato incorrecto. Use DD/MM/YYYY")

    dlg_vencimiento = ft.AlertDialog(
        title=ft.Text("📅 Asignar Vencimiento"),
        content=ft.Column([ft.Text("Ingresá cuándo vence esta factura:"), inp_fecha_venc], tight=True),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: setattr(dlg_vencimiento, 'open', False) or page.update()),
            ft.TextButton("Guardar", on_click=guardar_vencimiento, style=ft.ButtonStyle(color="blue")),
        ]
    )
    page.overlay.append(dlg_vencimiento)

    def abrir_vencimiento(factura):
        nonlocal factura_seleccionada
        factura_seleccionada = factura
        inp_fecha_venc.value = factura.get("vencimiento", "")
        dlg_vencimiento.open = True
        page.update()

    def marcar_factura_pagada(factura):
        factura["estado"] = "PAGADA"
        guardar_datos(bd)
        actualizar_resumenes()
        mostrar_alerta("Factura marcada como pagada en la nube.", "green")

    # --- FUNCIONES LÓGICAS ---
    def calcular_acumulados():
        inicio_semana = hoy_dt - timedelta(days=hoy_dt.weekday())
        inicio_mes = hoy_dt.replace(day=1)

        def obtener_ingresos_periodo(f_inicio):
            return sum(abs(i.get("monto", 0)) for i in bd["movimientos"] if not i.get("anulado") and datetime.strptime(i["fecha"], "%Y-%m-%d").date() >= f_inicio and i.get("tipo", "INGRESO") == "INGRESO")
        def obtener_gastos_periodo(f_inicio):
            return sum(abs(g.get("monto", 0)) for g in bd["gastos"] if not g.get("anulado") and datetime.strptime(g["fecha"], "%Y-%m-%d").date() >= f_inicio)

        txt_acum_semanal.value = f"Ganancia Semanal: ${obtener_ingresos_periodo(inicio_semana) - obtener_gastos_periodo(inicio_semana):,.2f}"
        txt_acum_mensual.value = f"Ganancia Mensual: ${obtener_ingresos_periodo(inicio_mes) - obtener_gastos_periodo(inicio_mes):,.2f}"

    def actualizar_resumenes():
        movs_hoy_validos = [m for m in bd["movimientos"] if m.get("fecha") == hoy_str and not m.get("anulado")]
        gastos_hoy_validos = [g for g in bd["gastos"] if g.get("fecha") == hoy_str and not g.get("anulado")]

        ventas_efectivo = sum(m.get("monto", 0) for m in movs_hoy_validos if m.get("medio", "EFECTIVO") == "EFECTIVO" and m.get("tipo", "INGRESO") == "INGRESO")
        ventas_virtual = sum(m.get("monto", 0) for m in movs_hoy_validos if m.get("medio", "EFECTIVO") != "EFECTIVO" and m.get("tipo", "INGRESO") == "INGRESO")
        
        retiros_efectivo = sum(abs(m.get("monto", 0)) for m in movs_hoy_validos if m.get("medio", "EFECTIVO") == "EFECTIVO" and m.get("tipo") == "RETIRO / EXTRACCIÓN")
        retiros_virtual = sum(abs(m.get("monto", 0)) for m in movs_hoy_validos if m.get("medio", "EFECTIVO") != "EFECTIVO" and m.get("tipo") == "RETIRO / EXTRACCIÓN")
        
        gastos_efectivo = sum(g.get("monto", 0) for g in gastos_hoy_validos if g.get("medio", "EFECTIVO (Del Cajón)") == "EFECTIVO (Del Cajón)")
        gastos_virtual = sum(g.get("monto", 0) for g in gastos_hoy_validos if g.get("medio", "EFECTIVO (Del Cajón)") != "EFECTIVO (Del Cajón)")

        esperado_cajon = ventas_efectivo - retiros_efectivo - gastos_efectivo
        esperado_virtual = ventas_virtual - retiros_virtual - gastos_virtual
        
        ventas_totales = ventas_efectivo + ventas_virtual
        gastos_totales = gastos_efectivo + gastos_virtual
        retiros_totales = retiros_efectivo + retiros_virtual
        ganancia_diaria = ventas_totales - gastos_totales

        txt_op_efectivo_esperado.value = f"💵 EFECTIVO EN CAJA: ${esperado_cajon:,.2f}"
        txt_op_virtual_esperado.value = f"💳 TOTAL VIRTUAL: ${esperado_virtual:,.2f}"
        txt_op_gastos_hoy.value = f"Gastos descontados: ${gastos_totales:,.2f}"
        txt_op_retiros_hoy.value = f"Retiros descontados: ${retiros_totales:,.2f}"

        txt_fisico_esperado.value = f"${esperado_cajon:,.2f}"
        txt_detalle_cajon.value = f"(Ventas Efvo: ${ventas_efectivo:,.2f} - Retiros: ${retiros_efectivo:,.2f} - Gastos Efvo: ${gastos_efectivo:,.2f})"
        
        txt_virtual_esperado.value = f"${esperado_virtual:,.2f}"
        txt_detalle_virtual.value = f"(Ventas Virt: ${ventas_virtual:,.2f} - Retiros: ${retiros_virtual:,.2f} - Gastos Virt: ${gastos_virtual:,.2f})"

        txt_ventas_reales.value = f"📈 Ventas Totales: ${ventas_totales:,.2f}"
        txt_gastos_reales.value = f"📉 Gastos Pagados Hoy: ${gastos_totales:,.2f}"
        txt_ganancia_neta.value = f"💵 GANANCIA NETA DE HOY: ${ganancia_diaria:,.2f}"
        txt_ganancia_neta.color = "red" if ganancia_diaria < 0 else "blue"

        ui_stat_gastos.controls.clear()
        desglose = {}
        for g in gastos_hoy_validos:
            cat = g.get("categoria", g.get("concepto", "VARIOS -").split(" - ")[0])
            desglose[cat] = desglose.get(cat, 0) + g.get("monto", 0)
        for cat, monto in desglose.items(): ui_stat_gastos.controls.append(ft.Text(f"• {cat}: ${monto:,.2f}", size=13, color="black87"))

        if ventas_totales > 0: txt_stat_porcentajes.value = f"Medios: Efectivo {(ventas_efectivo/ventas_totales)*100:.1f}% | Virtual {(ventas_virtual/ventas_totales)*100:.1f}%"
        else: txt_stat_porcentajes.value = "Medios: Efectivo 0% | Virtual 0%"
        
        lista_efectivo_ui.controls.clear()
        lista_virtual_ui.controls.clear()
        lista_gastos_ui.controls.clear()

        def crear_fila_ui(item, es_gasto=False):
            anulado = item.get("anulado", False)
            color_txt = "grey" if anulado else ("red" if es_gasto else ("green" if item.get("tipo", "INGRESO") == "INGRESO" else "orange"))
            signo = "-" if es_gasto or item.get("monto", 0) < 0 else "+"
            texto = f"{item.get('hora', '')} | {item.get('concepto', '')}: {signo}${abs(item.get('monto', 0)):,.2f}"
            if anulado: texto += f" [ANULADO]"
            txt_control = ft.Text(texto, color=color_txt, size=13, style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH if anulado else ft.TextDecoration.NONE))
            btn_del = ft.TextButton("❌ Anular", on_click=lambda e, i=item: abrir_anular(i), visible=not anulado, style=ft.ButtonStyle(color="red"))
            return ft.Row([txt_control, btn_del], alignment="spaceBetween")

        for m in reversed([m for m in bd["movimientos"] if m.get("fecha") == hoy_str]):
            if m.get("medio", "EFECTIVO") == "EFECTIVO": lista_efectivo_ui.controls.append(crear_fila_ui(m))
            else: lista_virtual_ui.controls.append(crear_fila_ui(m))

        for g in reversed([g for g in bd["gastos"] if g.get("fecha") == hoy_str]):
            lista_gastos_ui.controls.append(crear_fila_ui(g, es_gasto=True))

        lista_alertas_ui.controls.clear()
        facturas_pendientes = [f for f in bd["facturas"] if f.get("estado") == "PENDIENTE" and not f.get("anulado")]
        if not facturas_pendientes: lista_alertas_ui.controls.append(ft.Text("✅ No hay facturas pendientes.", color="green", weight="bold"))
        
        for f in facturas_pendientes:
            venc = f.get("vencimiento")
            estado_texto, color_txt, bg_color = "⚪ Sin fecha asignada", "grey", "#F5F5F5"
            if venc:
                try:
                    v_date = datetime.strptime(venc, "%d/%m/%Y").date()
                    dias_restantes = (v_date - hoy_dt).days
                    if dias_restantes < 0: estado_texto, color_txt, bg_color = f"🔴 VENCIDA hace {abs(dias_restantes)} días", "red", "#FFEBEE"
                    elif dias_restantes == 0: estado_texto, color_txt, bg_color = "🔴 ¡VENCE HOY!", "red", "#FFEBEE"
                    elif dias_restantes <= 3: estado_texto, color_txt, bg_color = f"🟡 Vence en {dias_restantes} días ({venc})", "orange", "#FFF3E0"
                    else: estado_texto, color_txt, bg_color = f"🟢 Vence el {venc}", "green", "#E8F5E9"
                except ValueError: pass
            
            fila_factura = ft.Container(
                bgcolor=bg_color, padding=10, border_radius=5,
                content=ft.Column([
                    ft.Text(f.get("concepto", ""), weight="bold"), ft.Text(f"Monto a pagar: ${f.get('monto', 0):,.2f}", size=13),
                    ft.Text(estado_texto, color=color_txt, weight="bold", size=13),
                    ft.Row([
                        ft.Button("📅 Asignar", on_click=lambda e, fac=f: abrir_vencimiento(fac), height=30),
                        ft.TextButton("✅ Pagada", on_click=lambda e, fac=f: marcar_factura_pagada(fac), style=ft.ButtonStyle(color="green"))
                    ])
                ], spacing=2)
            )
            lista_alertas_ui.controls.append(fila_factura)

        calcular_acumulados()
        page.update()

    def forzar_sincronizacion(e):
        nonlocal bd
        bd = cargar_datos()
        actualizar_resumenes()
        mostrar_alerta("Actualizado con la nube.", "green")

    # --- REGISTRO DE VENTAS ---
    def registrar_ingreso(e):
        if caja_cerrada_hoy: return mostrar_alerta("Caja cerrada.")
        if not inp_ing_concepto.value or not inp_ing_monto.value: return mostrar_alerta("Completá todos los campos")
        try:
            monto = float(inp_ing_monto.value)
            bd["movimientos"].append({
                "fecha": hoy_str, "hora": datetime.now().strftime('%H:%M'), "usuario": rol_actual,
                "concepto": inp_ing_concepto.value, "monto": monto,
                "tipo": "INGRESO", "medio": sel_ing_medio.value, "anulado": False
            })
            guardar_datos(bd)
            inp_ing_concepto.value = ""; inp_ing_monto.value = ""
            actualizar_resumenes()
        except ValueError: mostrar_alerta("Monto inválido")

    # --- REGISTRO DE EGRESOS ---
    def registrar_gasto(e):
        if caja_cerrada_hoy: return mostrar_alerta("Caja cerrada.")
        if not inp_gas_concepto.value or not inp_gas_monto.value: return mostrar_alerta("Faltan datos.")
        try:
            val = sel_gas_tipo_registro.value
            monto = float(inp_gas_monto.value)

            if val == "Retiro / Extracción de Caja":
                bd["movimientos"].append({
                    "fecha": hoy_str, "hora": datetime.now().strftime('%H:%M'), "usuario": rol_actual,
                    "concepto": "RETIRO - " + inp_gas_concepto.value, "monto": -monto,
                    "tipo": "RETIRO / EXTRACCIÓN", "medio": sel_gas_medio.value, "anulado": False
                })
                mostrar_alerta("Retiro sincronizado.", "orange")
            elif val == "Gasto Pagado Ahora":
                bd["gastos"].append({
                    "fecha": hoy_str, "hora": datetime.now().strftime('%H:%M'), "usuario": rol_actual,
                    "categoria": sel_gas_cat.value, "concepto": f"{sel_gas_cat.value} - {inp_gas_concepto.value}", 
                    "monto": monto, "medio": sel_gas_medio.value, "anulado": False
                })
                mostrar_alerta("Gasto sincronizado.", "orange")
            else:
                bd["facturas"].append({
                    "fecha": hoy_str, "hora": datetime.now().strftime('%H:%M'), "usuario": rol_actual,
                    "categoria": sel_gas_cat.value, "concepto": f"{sel_gas_cat.value} - {inp_gas_concepto.value}", 
                    "monto": monto, "estado": "PENDIENTE", "vencimiento": "", "anulado": False
                })
                mostrar_alerta("Factura guardada en la nube.", "blue")

            guardar_datos(bd)
            inp_gas_concepto.value = ""; inp_gas_monto.value = ""
            actualizar_resumenes()
        except ValueError: mostrar_alerta("Monto numérico requerido.")

    def procesar_cierre(e):
        nonlocal caja_cerrada_hoy
        if caja_cerrada_hoy: return mostrar_alerta("La caja ya está cerrada.")
        if not inp_arqueo.value: return mostrar_alerta("Ingrese el efectivo contado.")
        try:
            efectivo_real = float(inp_arqueo.value)
            movs_hoy = [m for m in bd["movimientos"] if m.get("fecha") == hoy_str and not m.get("anulado")]
            gastos_hoy = [g for g in bd["gastos"] if g.get("fecha") == hoy_str and not g.get("anulado")]
            v_efvo = sum(m.get("monto", 0) for m in movs_hoy if m.get("medio", "EFECTIVO") == "EFECTIVO" and m.get("tipo", "INGRESO") == "INGRESO")
            r_efvo = sum(abs(m.get("monto", 0)) for m in movs_hoy if m.get("medio", "EFECTIVO") == "EFECTIVO" and m.get("tipo") == "RETIRO / EXTRACCIÓN")
            g_efvo = sum(g.get("monto", 0) for g in gastos_hoy if g.get("medio", "EFECTIVO (Del Cajón)") == "EFECTIVO (Del Cajón)")
            
            efectivo_sistema = v_efvo - r_efvo - g_efvo
            diferencia = efectivo_real - efectivo_sistema

            bd["cierres"].append({
                "fecha": hoy_str, "hora": datetime.now().strftime('%H:%M'), "cerrado_por": rol_actual,
                "efectivo_sistema": efectivo_sistema, "efectivo_real": efectivo_real, "diferencia": diferencia
            })
            guardar_datos(bd)
            caja_cerrada_hoy = True
            habilirar_inputs(False) 
            txt_estado_caja.value = "ESTADO: CAJA CERRADA 🔴"
            txt_estado_caja.color = "red"
            actualizar_resumenes()
            
            if rol_actual == "OPERARIO": mostrar_alerta("¡Turno cerrado y enviado al servidor!", "green")
            else: mostrar_alerta(f"CAJA CERRADA. Diferencia: ${diferencia:,.2f}", "blue" if diferencia >= 0 else "red")
        except ValueError: mostrar_alerta("Monto inválido")

    def exportar_excel(e):
        try:
            with pd.ExcelWriter("Reporte_Auditoria.xlsx", engine="openpyxl") as writer:
                if bd["movimientos"]: pd.DataFrame(bd["movimientos"]).to_excel(writer, sheet_name="Movimientos", index=False)
                if bd["gastos"]: pd.DataFrame(bd["gastos"]).to_excel(writer, sheet_name="Gastos_Pagados", index=False)
                if bd["facturas"]: pd.DataFrame(bd["facturas"]).to_excel(writer, sheet_name="Facturas_Pendientes", index=False)
            mostrar_alerta("Excel exportado.", "green")
        except Exception as ex: mostrar_alerta(f"Error: {ex}")

    # --- INPUTS INGRESOS ---
    inp_ing_concepto = ft.TextField(label="Detalle de Venta", border_color="blue", disabled=caja_cerrada_hoy)
    inp_ing_monto = ft.TextField(label="Monto ($)", keyboard_type="number", border_color="blue", disabled=caja_cerrada_hoy)
    sel_ing_medio = ft.Dropdown(label="Cobrado en:", options=[ft.dropdown.Option("EFECTIVO"), ft.dropdown.Option("TARJETA / VIRTUAL")], value="EFECTIVO", disabled=caja_cerrada_hoy)
    btn_add_ingreso = ft.Button("REGISTRAR VENTA", on_click=registrar_ingreso, width=300, disabled=caja_cerrada_hoy, bgcolor="blue", color="white")

    # --- INPUTS EGRESOS ---
    sel_gas_tipo_registro = ft.Dropdown(
        label="¿Qué vas a registrar?", 
        options=[ft.dropdown.Option("Gasto Pagado Ahora"), ft.dropdown.Option("Retiro / Extracción de Caja"), ft.dropdown.Option("Factura a Pagar (A futuro)")], 
        value="Gasto Pagado Ahora", disabled=caja_cerrada_hoy
    )
    
    inp_gas_concepto = ft.TextField(label="Detalle del Gasto", border_color="red", disabled=caja_cerrada_hoy)
    inp_gas_monto = ft.TextField(label="Monto ($)", keyboard_type="number", border_color="red", disabled=caja_cerrada_hoy)
    sel_gas_cat = ft.Dropdown(label="Categoría", options=[ft.dropdown.Option("PROVEEDORES"), ft.dropdown.Option("ALQUILER"), ft.dropdown.Option("SUELDOS"), ft.dropdown.Option("SERVICIOS"), ft.dropdown.Option("VARIOS")], value="PROVEEDORES", disabled=caja_cerrada_hoy)
    sel_gas_medio = ft.Dropdown(label="Salió de:", options=[ft.dropdown.Option("EFECTIVO (Del Cajón)"), ft.dropdown.Option("TRANSFERENCIA / BANCO")], value="EFECTIVO (Del Cajón)", disabled=caja_cerrada_hoy)
    
    def cambiar_tipo_gasto(e):
        val = sel_gas_tipo_registro.value
        if val == "Gasto Pagado Ahora":
            sel_gas_medio.visible = True; sel_gas_cat.visible = True; inp_gas_concepto.label = "Detalle del Gasto"
        elif val == "Retiro / Extracción de Caja":
            sel_gas_medio.visible = True; sel_gas_cat.visible = False; inp_gas_concepto.label = "Motivo del Retiro"
        else:
            sel_gas_medio.visible = False; sel_gas_cat.visible = True; inp_gas_concepto.label = "Nombre Proveedor y Nº Factura"
        page.update()
        
    sel_gas_tipo_registro.on_change = cambiar_tipo_gasto
    btn_add_gasto = ft.Button("REGISTRAR EGRESO", on_click=registrar_gasto, width=300, disabled=caja_cerrada_hoy, bgcolor="red", color="white")

    # --- CIERRE ---
    inp_arqueo = ft.TextField(label="💰 ¿Efectivo físico real contado ahora mismo?", keyboard_type="number", border_color="green", disabled=caja_cerrada_hoy)
    btn_cerrar = ft.Button("CERRAR CAJA Y ENVIAR", on_click=procesar_cierre, bgcolor="red", color="white", width=300, disabled=caja_cerrada_hoy)
    btn_excel = ft.Button("📊 EXPORTAR A EXCEL", on_click=exportar_excel, bgcolor="green", color="white", width=300)

    # --- VISTAS ---
    vista_ingresos = ft.Column([
        # SOLUCIÓN ERROR ROJO: Botón de texto simple para sincronizar
        ft.Row([txt_fecha_op1, ft.TextButton("🔄 Actualizar Nube", on_click=forzar_sincronizacion)], alignment="spaceBetween"), 
        ft.Text("Módulo de Ventas", size=20, weight="bold", color="blue"),
        inp_ing_concepto, inp_ing_monto, sel_ing_medio, 
        ft.Row([btn_add_ingreso], alignment="center"), ft.Divider(),
        
        ft.Card(content=ft.Container(padding=15, bgcolor="#F1F8E9", content=ft.Column([
            ft.Text("📋 RESUMEN DE TU TURNO", weight="bold"),
            txt_op_efectivo_esperado, txt_op_virtual_esperado,
            txt_op_gastos_hoy, txt_op_retiros_hoy,
        ]))),
        
        ft.Text("🔒 ARQUEO DE TURNO", weight="bold", size=16),
        inp_arqueo, ft.Row([btn_cerrar], alignment="center"), ft.Divider(),
        
        ft.Text("GRILLA EFECTIVO 💵", weight="bold"), lista_efectivo_ui, ft.Divider(),
        ft.Text("GRILLA VIRTUAL 💳", weight="bold"), lista_virtual_ui, ft.Container(height=20)
    ], visible=False) 

    vista_gastos = ft.Column([
        txt_fecha_op2,
        ft.Text("Egresos y Proveedores", size=20, weight="bold", color="red"),
        sel_gas_tipo_registro, inp_gas_concepto, inp_gas_monto, sel_gas_cat, sel_gas_medio,
        ft.Row([btn_add_gasto], alignment="center"), ft.Divider(),
        ft.Text("Historial de Hoy", weight="bold"), lista_gastos_ui
    ], visible=False)

    vista_resumen = ft.Column([
        # SOLUCIÓN ERROR ROJO: Botón de texto simple para sincronizar
        ft.Row([txt_fecha_resumen, ft.TextButton("🔄 Actualizar Nube", on_click=forzar_sincronizacion)], alignment="spaceBetween"),
        
        ft.Row([txt_estado_caja, btn_reabrir], alignment="spaceBetween"),
        
        # AGREGAMOS EL BOTON DE BACKUP AL LADO DEL DE EXCEL
        ft.Column([btn_excel, btn_backup], horizontal_alignment="center"),
        
        ft.Card(content=ft.Container(padding=15, content=ft.Column([
            ft.Text("🔔 ALERTAS Y VENCIMIENTOS", weight="bold", size=16, color="orange_900"),
            lista_alertas_ui
        ]))),
        ft.Card(content=ft.Container(padding=15, content=ft.Column([
            ft.Text("📅 BALANCE ACUMULADO", weight="bold", size=16),
            txt_acum_semanal, txt_acum_mensual
        ]))),
        ft.Card(content=ft.Container(padding=15, content=ft.Column([
            ft.Text("📦 CONTROL DEL CAJÓN FÍSICO", weight="bold", size=16),
            ft.Text("Efectivo que debe haber ahora:", size=13),
            txt_fisico_esperado, txt_detalle_cajon
        ]))),
        ft.Card(content=ft.Container(padding=15, content=ft.Column([
            ft.Text("💳 CONTROL DE DINERO VIRTUAL", weight="bold", size=16, color="blue_700"),
            ft.Text("Saldo virtual que ingresó hoy:", size=13),
            txt_virtual_esperado, txt_detalle_virtual
        ]))),
        ft.Card(content=ft.Container(padding=15, content=ft.Column([
            ft.Text("📊 RENTABILIDAD DEL DÍA", weight="bold", size=16),
            txt_ventas_reales, txt_gastos_reales, ft.Divider(), txt_ganancia_neta
        ]))),
        ft.Card(content=ft.Container(padding=15, content=ft.Column([
            ft.Text("🔎 ESTADÍSTICAS", weight="bold", size=16),
            txt_stat_retiros, ft.Divider(),
            ft.Text("Gastos por Categoría:", weight="bold", size=14),
            ui_stat_gastos, ft.Divider(), txt_stat_porcentajes
        ])))
    ], visible=False)

    # --- NAVEGACIÓN ---
    btn_nav_resumen = ft.Button("📊 RESUMEN (ADMIN)", on_click=lambda _: cambiar_vista(2), expand=True, bgcolor="green", color="white")
    
    barra_botones = ft.Row([
        ft.Button("💰 VENTAS", on_click=lambda _: cambiar_vista(0), expand=True, bgcolor="blue", color="white"),
        ft.Button("📉 EGRESOS", on_click=lambda _: cambiar_vista(1), expand=True, bgcolor="red", color="white"),
        btn_nav_resumen
    ], spacing=5, visible=False)

    def cambiar_vista(indice):
        vista_ingresos.visible = (indice == 0)
        vista_gastos.visible = (indice == 1)
        vista_resumen.visible = (indice == 2)
        page.update()

    # --- PANTALLA DE LOGIN ---
    inp_pin = ft.TextField(label="PIN Contable", password=True, can_reveal_password=True, width=200, visible=False)
    
    def loguear(rol):
        nonlocal rol_actual
        if rol == "ADMIN":
            if inp_pin.value != "181214": return mostrar_alerta("PIN incorrecto.")
        rol_actual = rol
        pantalla_login.visible = False
        barra_botones.visible = True
        vista_ingresos.visible = True
        
        if rol_actual == "OPERARIO": btn_nav_resumen.visible = False 
        
        if rol == "ADMIN" and caja_cerrada_hoy:
             btn_reabrir.visible = True

        actualizar_resumenes()
        page.update()

    btn_entrar_admin = ft.Button("Entrar al Módulo Contable", on_click=lambda _: loguear("ADMIN"), bgcolor="black", color="white", visible=False)

    pantalla_login = ft.Column([
        ft.Text("Acceso al Sistema", size=24, weight="bold"), ft.Divider(),
        ft.Button("Entrar como OPERARIO", on_click=lambda _: loguear("OPERARIO"), width=300, height=50, bgcolor="blue", color="white"),
        ft.Container(height=30),
        ft.Button("Soy Administrador", on_click=lambda _: setattr(inp_pin, 'visible', True) or setattr(btn_entrar_admin, 'visible', True) or page.update(), width=300, bgcolor="blue_grey_50", color="black"),
        inp_pin, btn_entrar_admin
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    page.add(pantalla_login, barra_botones, ft.Divider(), vista_ingresos, vista_gastos, vista_resumen)

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 8080))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=puerto, host="0.0.0.0")