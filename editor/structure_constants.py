import re

# Patrones basicos para detectar datos clave
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
URL_RE = re.compile(r"(https?://[^\s]+|www\.[^\s]+)", re.IGNORECASE)
BULLET_RE = re.compile(r"^\s*[\u2022\u2023\u25cf\u25a0\u25aa\u25cb\u25e6\u2043\u2219\-\*]\s+")
LOCATION_RE = re.compile(r"(?P<city>[A-Za-zÀ-ÿ.'\-\s]+),\s*(?P<country>[A-Za-zÀ-ÿ.'\-\s]+)$")

DATE_TOKEN = r"(?:\d{1,2}/\d{4}|\d{4}|[A-Za-z]{3,}\s+\d{4})"
DATE_RANGE_RE = re.compile(
    rf"(?P<start>{DATE_TOKEN})\s*(?:-|\u2013|\u2014|a|to|hasta)\s*(?P<end>{DATE_TOKEN}|actualidad|presente|hoy|current|present)",
    re.IGNORECASE,
)

# Palabras clave para detectar titulos de seccion
SECTION_KEYWORDS = {
    "experience": [
        "experiencia",
        "experiencia profesional",
        "experiencia laboral",
        "work experience",
        "professional experience",
    ],
    "education": ["educacion", "formacion", "education"],
    "skills": ["habilidades", "skills", "competencias", "tecnologias"],
}

# Encabezados extra comunes (cuando no encajan en las 3 secciones base)
EXTRA_KEYWORDS = [
    "proyectos",
    "certificaciones",
    "idiomas",
    "publicaciones",
    "voluntariado",
    "premios",
    "logros",
    "referencias",
]

# Pistas para detectar organizaciones e instituciones
ORG_HINTS = [
    "universidad",
    "instituto",
    "company",
    "corp",
    "ltda",
    "spa",
    "limitada",
    "s.a.",
    "s.a",
    "academia",
    "academy",
    "bootcamp",
    "college",
    "escuela",
    "school",
]

# Conectores y prefijos utiles para separar ubicaciones cuando el PDF mezcla columnas.
_CITY_CONNECTORS = {
    "de",
    "del",
    "la",
    "las",
    "los",
    "y",
    "da",
    "do",
    "das",
    "dos",
    "el",
}
_CITY_PREFIXES = {
    "san",
    "santa",
    "santo",
    "sta",
    "st",
    "saint",
    "puerto",
    "villa",
    "ciudad",
    "new",
    "los",
    "las",
    "la",
    "el",
}
_NON_CITY_HINTS = set(ORG_HINTS) | {
    "empresa",
    "proyecto",
    "proyectos",
    "project",
    "projects",
}

# Pistas para detectar titulos academicos
DEGREE_HINTS = [
    "ingenier",
    "licenc",
    "magister",
    "maestr",
    "doctor",
    "master",
    "phd",
    "bachelor",
    "degree",
]

# Meses para normalizar fechas
MONTHS = {
    "ene": "01",
    "enero": "01",
    "jan": "01",
    "january": "01",
    "feb": "02",
    "febrero": "02",
    "february": "02",
    "mar": "03",
    "marzo": "03",
    "march": "03",
    "abr": "04",
    "abril": "04",
    "apr": "04",
    "april": "04",
    "may": "05",
    "mayo": "05",
    "jun": "06",
    "junio": "06",
    "june": "06",
    "jul": "07",
    "julio": "07",
    "july": "07",
    "ago": "08",
    "agosto": "08",
    "aug": "08",
    "august": "08",
    "sep": "09",
    "sept": "09",
    "septiembre": "09",
    "september": "09",
    "oct": "10",
    "octubre": "10",
    "october": "10",
    "nov": "11",
    "noviembre": "11",
    "november": "11",
    "dic": "12",
    "diciembre": "12",
    "dec": "12",
    "december": "12",
}

# Meses para mostrar fechas en formato corto
MONTHS_REVERSE = {
    "01": "Ene",
    "02": "Feb",
    "03": "Mar",
    "04": "Abr",
    "05": "May",
    "06": "Jun",
    "07": "Jul",
    "08": "Ago",
    "09": "Sep",
    "10": "Oct",
    "11": "Nov",
    "12": "Dic",
}
