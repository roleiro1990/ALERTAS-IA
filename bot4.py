import requests
import time
import os

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID_PREMIUM")
API_KEY = os.getenv("API_KEY")

API_BASE = "https://v3.football.api-sports.io"

alertas_eventos = set()
alertas_tarjetas = set()
alertas_tarjetas_bajas = set()
alertas_tarjetas_equipo = set()
alertas_corners = set()
alertas_remates = set()
alertas_remates_totales_altos = set()

primera_vuelta_eventos = True
primera_vuelta_mercados = True

LIGA_PENALES_PERMITIDA = "Torneo Federal A"

ULTIMA_REVISION_EVENTOS = 0
ULTIMA_REVISION_MERCADOS = 0

INTERVALO_EVENTOS = 30
INTERVALO_MERCADOS = 30


def bandera_pais(pais):
    pais_a_iso = {
        "Argentina": "AR",
        "Spain": "ES",
        "Mexico": "MX",
        "USA": "US",
        "Brazil": "BR",
        "England": "GB",
        "Italy": "IT",
        "Germany": "DE",
        "France": "FR",
        "Portugal": "PT",
        "Netherlands": "NL",
        "Turkey": "TR",
        "Chile": "CL",
        "Colombia": "CO",
        "Uruguay": "UY",
        "Paraguay": "PY",
        "Peru": "PE",
        "Nicaragua": "NI",
        "El Salvador": "SV",
        "Costa Rica": "CR",
        "Honduras": "HN",
        "Guatemala": "GT",
        "Panama": "PA",
        "Dominican Republic": "DO",
        "Belgium": "BE",
        "Denmark": "DK",
        "Croatia": "HR",
        "Slovenia": "SI",
        "Czech Republic": "CZ",
        "Czech-Republic": "CZ",
        "Ghana": "GH",
        "Iceland": "IS",
        "World": "🌍",
        "Jamaica": "JM",
        "Venezuela": "VE",
    }

    codigo = pais_a_iso.get(pais)

    if codigo == "🌍":
        return "🌍"

    if not codigo:
        return "🌍"

    return "".join(chr(127397 + ord(c)) for c in codigo)


def enviar_mensaje(texto):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "HTML",
    }
    requests.post(url, data=data, timeout=20)


def obtener_partidos_en_vivo():
    url = f"{API_BASE}/fixtures?live=all"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.json().get("response", [])


def obtener_eventos(fixture_id):
    url = f"{API_BASE}/fixtures/events?fixture={fixture_id}"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.json().get("response", [])


def obtener_estadisticas(fixture_id):
    url = f"{API_BASE}/fixtures/statistics?fixture={fixture_id}"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.json().get("response", [])


def get_stat(stats, nombre):
    for s in stats:
        if s.get("type") == nombre:
            valor = s.get("value")

            if valor is None:
                return 0

            if isinstance(valor, int):
                return valor

            if isinstance(valor, str):
                valor = valor.replace("%", "").strip()
                return int(valor) if valor.isdigit() else 0

    return 0


def obtener_remates(stats):
    candidatos = [
        get_stat(stats, "Total Shots"),
        get_stat(stats, "Shots Total"),
        get_stat(stats, "Shots"),
    ]
    return max(candidatos)


def obtener_corners(stats):
    candidatos = [
        get_stat(stats, "Corner Kicks"),
        get_stat(stats, "Corners"),
        get_stat(stats, "Corner"),
        get_stat(stats, "Corner kicks"),
        get_stat(stats, "corner kicks"),
        get_stat(stats, "Saques de esquina"),
        get_stat(stats, "Tiros de esquina"),
    ]
    return max(candidatos)


def obtener_corners_stats(home_stats, away_stats):
    home_corners = obtener_corners(home_stats)
    away_corners = obtener_corners(away_stats)
    return home_corners + away_corners


def es_roja(evento):
    tipo = str(evento.get("type", "")).lower()
    detalle = str(evento.get("detail", "")).lower()
    comentario = str(evento.get("comments", "")).lower()

    palabras_roja = [
        "red card",
        "yellow red card",
        "second yellow",
        "2nd yellow",
        "red",
    ]

    return (
        any(p in tipo for p in palabras_roja)
        or any(p in detalle for p in palabras_roja)
        or any(p in comentario for p in palabras_roja)
    )


def es_penal(evento):
    tipo = str(evento.get("type", "")).lower()
    detalle = str(evento.get("detail", "")).lower()
    comentario = str(evento.get("comments", "")).lower()

    palabras_penal = ["penalty", "penal"]

    return (
        any(p in tipo for p in palabras_penal)
        or any(p in detalle for p in palabras_penal)
        or any(p in comentario for p in palabras_penal)
    )


def liga_tarjetas_permitida(liga, pais):
    liga = str(liga).strip().lower()
    pais = str(pais).strip().lower()

    return (
        (liga == "premier league" and pais == "england")
        or (liga == "la liga" and pais == "spain")
        or (liga == "serie a" and pais == "italy")
        or (liga == "bundesliga" and pais == "germany")
        or (liga == "ligue 1" and pais == "france")
        or (liga == "liga mx" and pais == "mexico")
        or (liga == "mls" and pais == "usa")
        or (liga in ["brasileirao serie a", "serie a"] and pais == "brazil")
        or (liga == "liga profesional argentina" and pais == "argentina")
    )


def liga_penal_permitida(liga):
    return LIGA_PENALES_PERMITIDA.lower() in liga.lower()


def es_evento_primer_tiempo(evento):
    tiempo = evento.get("time", {}) or {}
    elapsed = tiempo.get("elapsed")
    extra = tiempo.get("extra", 0)

    if elapsed is None:
        return False

    if extra is None:
        extra = 0

    try:
        elapsed = int(elapsed)
        extra = int(extra)
    except (TypeError, ValueError):
        return False

    return elapsed < 45 or (elapsed == 45 and extra >= 0)


def formato_minuto_evento(evento):
    tiempo = evento.get("time", {}) or {}
    elapsed = tiempo.get("elapsed")
    extra = tiempo.get("extra", 0)

    try:
        elapsed = int(elapsed)
    except (TypeError, ValueError):
        return "?"

    try:
        extra = int(extra) if extra is not None else 0
    except (TypeError, ValueError):
        extra = 0

    if elapsed == 45 and extra > 0:
        return f"45+{extra}"

    return str(elapsed)


def es_amarilla(evento):
    tipo = str(evento.get("type", "")).lower()
    detalle = str(evento.get("detail", "")).lower()

    return (
        ("card" in tipo or "yellow" in tipo or "yellow" in detalle)
        and "yellow" in detalle
    )


def es_corner(evento):
    tipo = str(evento.get("type", "")).lower()
    detalle = str(evento.get("detail", "")).lower()
    comentario = str(evento.get("comments", "")).lower()

    return "corner" in tipo or "corner" in detalle or "corner" in comentario


def contar_amarillas_primer_tiempo(eventos, equipo=None):
    total = 0
    for evento in eventos:
        if not es_evento_primer_tiempo(evento):
            continue
        if not es_amarilla(evento):
            continue
        if equipo is not None:
            nombre = evento.get("team", {}).get("name")
            if nombre != equipo:
                continue
        total += 1
    return total


def contar_corners_eventos_primer_tiempo(eventos):
    total = 0
    for evento in eventos:
        if not es_evento_primer_tiempo(evento):
            continue
        if es_corner(evento):
            total += 1
    return total


def en_ventana_primer_tiempo(partido):
    estado = partido.get("fixture", {}).get("status", {}).get("short", "")
    minuto_actual = partido.get("fixture", {}).get("status", {}).get("elapsed", 0) or 0
    return estado in ["1H", "HT"] or (estado == "2H" and minuto_actual <= 46)


def log_stats_partido(
    fixture_id,
    liga,
    pais,
    home,
    away,
    estado_corto,
    minuto_actual,
    total_tarjetas,
    tarjetas_home,
    tarjetas_away,
    corners_eventos,
    corners_stats,
    total_corners,
    remates_home,
    remates_away,
    total_remates,
    stats_len,
):
    print(
        "DEBUG 1T | "
        f"fixture={fixture_id} | "
        f"liga={liga} ({pais}) | "
        f"partido={home} vs {away} | "
        f"estado={estado_corto} | "
        f"min={minuto_actual} | "
        f"stats_items={stats_len} | "
        f"tarjetas_total={total_tarjetas} | "
        f"tarjetas_home={tarjetas_home} | "
        f"tarjetas_away={tarjetas_away} | "
        f"corners_eventos={corners_eventos} | "
        f"corners_stats={corners_stats} | "
        f"corners_total={total_corners} | "
        f"remates_home={remates_home} | "
        f"remates_away={remates_away} | "
        f"remates_total={total_remates}"
    )


def revisar_eventos_vivo():
    global primera_vuelta_eventos

    partidos = obtener_partidos_en_vivo()

    for partido in partidos:
        fixture_id = partido["fixture"]["id"]
        home = partido["teams"]["home"]["name"]
        away = partido["teams"]["away"]["name"]
        goles_local = partido["goals"]["home"]
        goles_visitante = partido["goals"]["away"]
        liga = partido["league"]["name"]
        pais = partido["league"]["country"]
        bandera = bandera_pais(pais)

        eventos = obtener_eventos(fixture_id)

        for evento in eventos:
            equipo_evento = evento.get("team", {}).get("name", "Equipo")
            jugador_evento = str(evento.get("player", {}).get("name", "")).strip().lower()
            tipo = str(evento.get("type", "")).strip().lower()
            detalle = str(evento.get("detail", "")).strip().lower()

            clave = f"{fixture_id}-{equipo_evento}-{jugador_evento}-{tipo}-{detalle}"

            if clave in alertas_eventos:
                continue

            if primera_vuelta_eventos:
                alertas_eventos.add(clave)
                continue

            if es_penal(evento) and liga_penal_permitida(liga):
                minuto_formateado = formato_minuto_evento(evento)
                mensaje = (
                    f"<b>⚽ PENAL</b>\n\n"
                    f"🏆 {liga} ({pais}) {bandera}\n"
                    f"{home} vs {away}\n\n"
                    f"⏱ <b>Min {minuto_formateado}</b> | ⚽ <b>Resultado parcial {goles_local}-{goles_visitante}</b>\n"
                    f"⚽ <b>Penal para {equipo_evento}</b>"
                )
                enviar_mensaje(mensaje)
                alertas_eventos.add(clave)

            elif es_roja(evento) and es_evento_primer_tiempo(evento):
                minuto_formateado = formato_minuto_evento(evento)
                mensaje = (
                    f"<b>🟥 EXPULSADO MINUTO {minuto_formateado}</b>\n\n"
                    f"🔴 <b>{equipo_evento}</b>\n\n"
                    f"🏆 {liga} ({pais}) {bandera}\n"
                    f"{home} vs {away}\n\n"
                    f"⚽ <b>Resultado parcial {goles_local}-{goles_visitante}</b>"
                )
                enviar_mensaje(mensaje)
                alertas_eventos.add(clave)

            else:
                alertas_eventos.add(clave)

    primera_vuelta_eventos = False


def revisar_mercados_1t():
    global primera_vuelta_mercados

    partidos = obtener_partidos_en_vivo()

    if primera_vuelta_mercados:
        primera_vuelta_mercados = False
        print("PRIMERA VUELTA MERCADOS OK")
        return

    evaluados = 0
    sin_stats = 0

    for partido in partidos:
        if not en_ventana_primer_tiempo(partido):
            continue

        fixture_id = partido["fixture"]["id"]
        home = partido["teams"]["home"]["name"]
        away = partido["teams"]["away"]["name"]
        goles_local = partido["goals"]["home"]
        goles_visitante = partido["goals"]["away"]
        liga = partido["league"]["name"]
        pais = partido["league"]["country"]
        bandera = bandera_pais(pais)
        estado_corto = partido.get("fixture", {}).get("status", {}).get("short", "")
        minuto_actual = partido.get("fixture", {}).get("status", {}).get("elapsed", 0) or 0

        evaluados += 1

        eventos = obtener_eventos(fixture_id)

        total_tarjetas = contar_amarillas_primer_tiempo(eventos)
        tarjetas_home = contar_amarillas_primer_tiempo(eventos, home)
        tarjetas_away = contar_amarillas_primer_tiempo(eventos, away)
        corners_eventos = contar_corners_eventos_primer_tiempo(eventos)

        estadisticas = obtener_estadisticas(fixture_id)

        remates_home = 0
        remates_away = 0
        total_remates = 0
        corners_stats = 0

        if len(estadisticas) >= 2:
            home_stats = estadisticas[0].get("statistics", [])
            away_stats = estadisticas[1].get("statistics", [])

            remates_home = obtener_remates(home_stats)
            remates_away = obtener_remates(away_stats)
            total_remates = remates_home + remates_away
            corners_stats = obtener_corners_stats(home_stats, away_stats)
        else:
            sin_stats += 1
            print(
                f"DEBUG STATS VACIAS | fixture={fixture_id} | {home} vs {away} | "
                f"liga={liga} ({pais}) | estado={estado_corto} | min={minuto_actual} | "
                f"items_stats={len(estadisticas)}"
            )

        total_corners = max(corners_eventos, corners_stats)
        etiqueta_tiempo = "HT" if estado_corto == "HT" else f"Min {minuto_actual}"

        log_stats_partido(
            fixture_id=fixture_id,
            liga=liga,
            pais=pais,
            home=home,
            away=away,
            estado_corto=estado_corto,
            minuto_actual=minuto_actual,
            total_tarjetas=total_tarjetas,
            tarjetas_home=tarjetas_home,
            tarjetas_away=tarjetas_away,
            corners_eventos=corners_eventos,
            corners_stats=corners_stats,
            total_corners=total_corners,
            remates_home=remates_home,
            remates_away=remates_away,
            total_remates=total_remates,
            stats_len=len(estadisticas),
        )

        if total_tarjetas >= 4 and liga_tarjetas_permitida(liga, pais):
            clave = f"{fixture_id}-tarjetas-altas"
            if clave not in alertas_tarjetas:
                mensaje = (
                    f"<b>🔥 PARTIDO CALIENTE 🔥</b>\n\n"
                    f"🏆 {liga} ({pais}) {bandera}\n"
                    f"{home} vs {away}\n\n"
                    f"⏱ <b>{etiqueta_tiempo}</b> | ⚽ <b>Resultado parcial {goles_local}-{goles_visitante}</b>\n"
                    f"🟨 <b>{total_tarjetas} TARJETAS EN LA PRIMERA MITAD</b>"
                )
                enviar_mensaje(mensaje)
                alertas_tarjetas.add(clave)

        if total_tarjetas == 0 and estado_corto == "HT" and liga_tarjetas_permitida(liga, pais):
            clave = f"{fixture_id}-tarjetas-bajas"
            if clave not in alertas_tarjetas_bajas:
                mensaje = (
                    f"<b>📉 PARTIDO SIN FRICCIÓN</b>\n\n"
                    f"🏆 {liga} ({pais}) {bandera}\n"
                    f"{home} vs {away}\n\n"
                    f"⏱ <b>1T Finalizado</b> | ⚽ <b>Resultado parcial {goles_local}-{goles_visitante}</b>\n"
                    f"🟨 <b>0 TARJETAS EN LA PRIMERA MITAD</b>"
                )
                enviar_mensaje(mensaje)
                alertas_tarjetas_bajas.add(clave)

        if not liga_tarjetas_permitida(liga, pais):
            if tarjetas_home >= 4:
                clave = f"{fixture_id}-tarjetas-equipo-{home}"
                if clave not in alertas_tarjetas_equipo:
                    mensaje = (
                        f"<b>🟨 EXCESO DE TARJETAS</b>\n\n"
                        f"🏆 {liga} ({pais}) {bandera}\n"
                        f"{home} vs {away}\n\n"
                        f"⏱ <b>{etiqueta_tiempo}</b> | ⚽ <b>Resultado parcial {goles_local}-{goles_visitante}</b>\n"
                        f"🟨 <b>{home.upper()} YA TIENE {tarjetas_home} TARJETAS SOLO EN LA PRIMERA MITAD</b>"
                    )
                    enviar_mensaje(mensaje)
                    alertas_tarjetas_equipo.add(clave)

            if tarjetas_away >= 4:
                clave = f"{fixture_id}-tarjetas-equipo-{away}"
                if clave not in alertas_tarjetas_equipo:
                    mensaje = (
                        f"<b>🟨 EXCESO DE TARJETAS</b>\n\n"
                        f"🏆 {liga} ({pais}) {bandera}\n"
                        f"{home} vs {away}\n\n"
                        f"⏱ <b>{etiqueta_tiempo}</b> | ⚽ <b>Resultado parcial {goles_local}-{goles_visitante}</b>\n"
                        f"🟨 <b>{away.upper()} YA TIENE {tarjetas_away} TARJETAS SOLO EN LA PRIMERA MITAD</b>"
                    )
                    enviar_mensaje(mensaje)
                    alertas_tarjetas_equipo.add(clave)

        if total_corners >= 6:
            clave = f"{fixture_id}-corners-altos"
            if clave not in alertas_corners:
                mensaje = (
                    f"<b>🚩 PARTIDO DINÁMICO 🚩</b>\n\n"
                    f"🏆 {liga} ({pais}) {bandera}\n"
                    f"{home} vs {away}\n\n"
                    f"⏱ <b>{etiqueta_tiempo}</b> | ⚽ <b>Resultado parcial {goles_local}-{goles_visitante}</b>\n"
                    f"🚩 <b>YA HAY {total_corners} CÓRNERS EN LA PRIMERA MITAD</b>"
                )
                enviar_mensaje(mensaje)
                alertas_corners.add(clave)

        if remates_home >= 9 or remates_away >= 9:
            clave = f"{fixture_id}-remates-equipo"
            if clave not in alertas_remates:
                lineas_ritmo = []
                lineas_estadisticas = []

                if remates_home >= 9:
                    lineas_ritmo.append(
                        f"⏱ <b>{home.upper()} REMATA CADA 5 MINUTOS O MENOS EN EL PRIMER TIEMPO</b>"
                    )
                    lineas_estadisticas.append(
                        f"🔴 <b>{home.upper()} YA LLEVA {remates_home} REMATES EN LA PRIMERA MITAD</b>"
                    )

                if remates_away >= 9:
                    lineas_ritmo.append(
                        f"⏱ <b>{away.upper()} REMATA CADA 5 MINUTOS O MENOS EN EL PRIMER TIEMPO</b>"
                    )
                    lineas_estadisticas.append(
                        f"🔵 <b>{away.upper()} YA LLEVA {remates_away} REMATES EN LA PRIMERA MITAD</b>"
                    )

                mensaje = (
                    f"<b>🥅 EXCESO DE REMATES 🥅</b>\n\n"
                    f"{chr(10).join(lineas_ritmo).replace(chr(10), chr(10) * 2)}\n\n"
                    f"🏆 {liga} ({pais}) {bandera}\n"
                    f"{home} vs {away}\n\n"
                    f"⏱ <b>{etiqueta_tiempo}</b> | ⚽ <b>Resultado parcial {goles_local}-{goles_visitante}</b>\n\n"
                    f"{chr(10).join(lineas_estadisticas).replace(chr(10), chr(10) * 2)}"
                )
                enviar_mensaje(mensaje)
                alertas_remates.add(clave)

        if total_remates >= 15:
            clave = f"{fixture_id}-remates-totales-altos"
            if clave not in alertas_remates_totales_altos:
                mensaje = (
                    f"<b>🥅 VOLUMEN ALTO DE REMATES 🥅</b>\n\n"
                    f"⏱ <b>REMATES CADA 3 MINUTOS O MENOS EN EL PRIMER TIEMPO</b>\n\n"
                    f"🏆 {liga} ({pais}) {bandera}\n"
                    f"{home} vs {away}\n\n"
                    f"⏱ <b>{etiqueta_tiempo}</b> | ⚽ <b>Resultado parcial {goles_local}-{goles_visitante}</b>\n\n"
                    f"🔴 <b>{home.upper()}: {remates_home} REMATES</b>\n\n"
                    f"🔵 <b>{away.upper()}: {remates_away} REMATES</b>\n\n"
                    f"📊 <b>TOTAL: {total_remates} REMATES EN LA PRIMERA MITAD</b>"
                )
                enviar_mensaje(mensaje)
                alertas_remates_totales_altos.add(clave)

    print(
        f"DEBUG RESUMEN 1T | evaluados={evaluados} | sin_stats={sin_stats}"
    )


def revisar_partidos():
    global ULTIMA_REVISION_EVENTOS, ULTIMA_REVISION_MERCADOS

    while True:
        try:
            ahora = time.time()

            if ahora - ULTIMA_REVISION_EVENTOS >= INTERVALO_EVENTOS:
                revisar_eventos_vivo()
                ULTIMA_REVISION_EVENTOS = ahora

            if ahora - ULTIMA_REVISION_MERCADOS >= INTERVALO_MERCADOS:
                revisar_mercados_1t()
                ULTIMA_REVISION_MERCADOS = ahora

        except Exception as e:
            print("ERROR BOT4:", e)
            time.sleep(10)
            continue

        print("BOT4 ACTIVO | EVENTOS: 30s | MERCADOS 1T: 60s\n")
        time.sleep(5)
