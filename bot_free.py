import requests
import time
import os

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID_FREE")
API_KEY = os.getenv("API_KEY")

API_BASE = "https://v3.football.api-sports.io"

alertas_eventos = set()
alertas_tarjetas = set()
alertas_remates_totales = set()

primera_vuelta_eventos = True
primera_vuelta_mercados = True

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
    except:
        return "?"

    try:
        extra = int(extra) if extra is not None else 0
    except:
        extra = 0

    if elapsed == 45 and extra > 0:
        return f"45+{extra}"

    return str(elapsed)


def en_ventana_primer_tiempo(partido):
    estado = partido.get("fixture", {}).get("status", {}).get("short", "")
    minuto = partido.get("fixture", {}).get("status", {}).get("elapsed", 0) or 0
    return estado in ["1H", "HT"] or (estado == "2H" and minuto <= 46)


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


def es_amarilla(evento):
    tipo = str(evento.get("type", "")).lower()
    detalle = str(evento.get("detail", "")).lower()

    return (
        ("card" in tipo or "yellow" in tipo or "yellow" in detalle)
        and "yellow" in detalle
    )


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
            jugador = str(evento.get("player", {}).get("name", "")).strip().lower()
            tipo = str(evento.get("type", "")).strip().lower()
            detalle = str(evento.get("detail", "")).strip().lower()

            clave = f"{fixture_id}-{equipo_evento}-{jugador}-{tipo}-{detalle}"

            if clave in alertas_eventos:
                continue

            if primera_vuelta_eventos:
                alertas_eventos.add(clave)
                continue

            if es_roja(evento) and es_evento_primer_tiempo(evento):
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

    primera_vuelta_eventos = False


def revisar_mercado_1t():
    global primera_vuelta_mercados

    partidos = obtener_partidos_en_vivo()

    if primera_vuelta_mercados:
        primera_vuelta_mercados = False
        return

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

        eventos = obtener_eventos(fixture_id)
        total_tarjetas = contar_amarillas_primer_tiempo(eventos)

        estadisticas = obtener_estadisticas(fixture_id)

        remates_home = 0
        remates_away = 0
        total_remates = 0

        if len(estadisticas) >= 2:
            home_stats = estadisticas[0]["statistics"]
            away_stats = estadisticas[1]["statistics"]

            remates_home = obtener_remates(home_stats)
            remates_away = obtener_remates(away_stats)
            total_remates = remates_home + remates_away

        etiqueta_tiempo = "HT" if estado_corto == "HT" else f"Min {minuto_actual}"

        # PARTIDO CALIENTE
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

        # PARTIDO CON MUCHOS REMATES
        if total_remates >= 14:
            clave = f"{fixture_id}-remates-totales"
            if clave not in alertas_remates_totales:
                mensaje = (
                    f"<b>🥅 PARTIDO CON MUCHOS REMATES 🥅</b>\n\n"
                    f"🏆 {liga} ({pais}) {bandera}\n"
                    f"{home} vs {away}\n\n"
                    f"⏱ <b>{etiqueta_tiempo}</b> | ⚽ <b>Resultado parcial {goles_local}-{goles_visitante}</b>\n\n"
                    f"📊 <b>YA HAY {total_remates} REMATES EN LA PRIMERA MITAD</b>"
                )

                enviar_mensaje(mensaje)
                alertas_remates_totales.add(clave)


def revisar_partidos():
    global ULTIMA_REVISION_EVENTOS, ULTIMA_REVISION_MERCADOS

    while True:
        try:
            ahora = time.time()

            if ahora - ULTIMA_REVISION_EVENTOS >= INTERVALO_EVENTOS:
                revisar_eventos_vivo()
                ULTIMA_REVISION_EVENTOS = ahora

            if ahora - ULTIMA_REVISION_MERCADOS >= INTERVALO_MERCADOS:
                revisar_mercado_1t()
                ULTIMA_REVISION_MERCADOS = ahora

        except Exception as e:
            print("ERROR BOT_FREE:", e)
            time.sleep(10)
            continue

        print("BOT FREE ACTIVO | EXPULSIONES: 30s | MERCADOS 1T: 30s\n")
        time.sleep(5)
