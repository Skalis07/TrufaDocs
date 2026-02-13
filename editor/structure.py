import re
from typing import Dict, List, Tuple, Optional, Any

from .structure_constants import DATE_RANGE_RE, EMAIL_RE, PHONE_RE, URL_RE
from .structure_extras import _empty_extra_entry, _has_extra_entry_content, _parse_extras
from .structure_helpers import (
    _append_highlight,
    _clean_bullet,
    _compact_lines,
    _contains_bullet_symbol,
    _extract_date_range_from_line,
    _extract_location_from_line,
    _extract_tech_from_line,
    _first_match,
    _group_entries,
    _is_bullet,
    _is_extra_heading_after_skills,
    _is_extra_keyword_heading,
    _is_heading,
    _is_location_candidate,
    _join_paragraph,
    _looks_like_tech,
    _looks_like_org,
    _match_heading,
    _normalize_ascii,
    _normalize_date_token,
    _normalize_heading_line,
    _parse_location,
    _split_role_company,
)
from .structure_types import ExtraSectionRaw

# Estructura base usada por la UI y el parser
def default_structure() -> Dict:
    return {
        "meta": {"core_order": "experience,education,skills"},
        "basics": {
            "name": "",
            "description": "",
            "email": "",
            "phone": "",
            "linkedin": "",
            "github": "",
            "city": "",
            "country": "",
        },
        "experience": [
            {
                "role": "",
                "company": "",
                "start": "",
                "end": "",
                "city": "",
                "country": "",
                "technologies": "",
                "highlights": [],
            }
        ],
        "education": [
            {
                "degree": "",
                "institution": "",
                "start": "",
                "end": "",
                "city": "",
                "country": "",
                "honors": "",
            }
        ],
        "skills": [
            {
                "category": "",
                "items": "",
            }
        ],
        "extra_sections": [],
    }


def _build_core_order_from_detected(
    detected_order: List[str],
    extra_sections: List[Dict],
) -> str:
    """Construye core_order preservando el orden detectado en import.

    - Mantiene módulos core en el orden observado (experience/education/skills).
    - Inserta extras (`extra-*`) en su posición observada.
    - Completa módulos faltantes al final para mantener compatibilidad.
    """
    default_core = ["experience", "education", "skills"]
    extra_ids = [
        (section.get("section_id") or "").strip()
        for section in (extra_sections or [])
        if (section.get("section_id") or "").strip()
    ]
    known_ids = set(default_core + extra_ids)

    ordered: List[str] = []
    seen: set[str] = set()

    for token in detected_order or []:
        module_id = (token or "").strip()
        if not module_id:
            continue
        if module_id not in known_ids:
            continue
        if module_id in seen:
            continue
        ordered.append(module_id)
        seen.add(module_id)

    for module_id in default_core:
        if module_id not in seen:
            ordered.append(module_id)
            seen.add(module_id)

    for extra_id in extra_ids:
        if extra_id not in seen:
            ordered.append(extra_id)
            seen.add(extra_id)

    return ",".join(ordered) if ordered else ",".join(default_core)


# Entrada principal del parser: texto -> estructura
def parse_resume(text: str) -> Dict:
    data = default_structure()
    lines = _compact_lines([line.strip() for line in text.splitlines()])
    contact = _extract_contact(text)
    data["basics"].update(contact)

    name, description, remaining = _extract_name_and_description(lines, contact)
    data["basics"]["name"] = name
    data["basics"]["description"] = description
    city, country = _extract_location(text, lines, contact)
    data["basics"]["city"] = city
    data["basics"]["country"] = country

    sections, extras, detected_order = _split_sections(remaining)
    data["experience"] = _parse_experience(sections.get("experience", []))
    data["education"] = _parse_education(sections.get("education", []))
    data["skills"] = _parse_skills(sections.get("skills", []))
    data["extra_sections"] = _parse_extras(extras)
    data.setdefault("meta", {})["core_order"] = _build_core_order_from_detected(
        detected_order,
        data["extra_sections"],
    )

    _ensure_minimums(data)
    return data


# Convierte estructura -> texto (vista previa / export libre)
def build_text_from_structure(data: Dict) -> str:
    # Defensive: accept None
    if not data:
        data = {}

    def _fmt_month_year(token: str) -> str:
        token = (token or "").strip()
        if not token:
            return ""
        # Accept YYYY or YYYY-MM
        m = re.match(r"^(\d{4})(?:-(\d{1,2}))?$", token)
        if not m:
            return token
        year = m.group(1)
        month = m.group(2)
        if not month:
            return year
        month_i = int(month)
        months = {
            1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
            7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
        }
        return f"{months.get(month_i, str(month_i).zfill(2))} {year}"

    def _format_date_range(start: Any, end: Any, is_current: bool = False) -> str:
        s0 = _fmt_month_year(str(start or "").strip())
        e0 = _fmt_month_year(str(end or "").strip())
        if is_current and not e0:
            e0 = "Actual"
        if s0 and e0:
            return f"{s0} - {e0}"
        if s0:
            return s0
        if e0:
            return e0
        return ""

    def _format_location(city: Any, country: Any) -> str:
        c1 = (str(city or "").strip())
        c2 = (str(country or "").strip())
        return ", ".join([x for x in [c1, c2] if x])

    def _format_detail_line(value: Any) -> str:
        return str(value or "").strip()

    basics = data.get("basics") or {}
    core_order_raw = ((data.get("meta") or {}).get("core_order")) or "experience,education,skills,extras"
    core_order = [x.strip() for x in str(core_order_raw).split(",") if x.strip()]

    lines: List[str] = []

    # Header
    name = (basics.get("name") or "").strip()
    if name:
        lines.append(name)

    desc = (basics.get("description") or "").strip()
    if desc:
        lines.append(desc)

    # Contacto
    contact_lines: List[str] = []
    email = (basics.get("email") or "").strip()
    phone = (basics.get("phone") or "").strip()
    linkedin = (basics.get("linkedin") or "").strip()
    github = (basics.get("github") or "").strip()
    country = (basics.get("country") or "").strip()
    city = (basics.get("city") or "").strip()

    if email:
        contact_lines.append(f"- Email: {email}")
    if phone:
        contact_lines.append(f"- Telefono: {phone}")
    if linkedin:
        contact_lines.append(f"- LinkedIn: {linkedin}")
    if github:
        contact_lines.append(f"- GitHub: {github}")
    if city or country:
        loc = ", ".join([x for x in [city, country] if x])
        contact_lines.append(f"- Ubicacion: {loc}")

    if contact_lines:
        if lines:
            lines.append("")
        lines.append("Contacto")
        lines.extend(contact_lines)

    def emit_detail_section(title: str, entries: List[Dict], include_current_flag: bool = False):
        if not entries:
            return
        if lines:
            lines.append("")
        lines.append(title)

        for e in entries:
            role = (e.get("role") or "").strip()
            company = (e.get("company") or "").strip()
            degree = (e.get("degree") or "").strip()
            institution = (e.get("institution") or "").strip()

            left = role or degree
            right = company or institution

            date_range = _format_date_range(e.get("start"), e.get("end"), bool(e.get("is_current")) if include_current_flag else False)
            heading = " — ".join([x for x in [left, right] if x])
            if date_range:
                heading = f"{heading} ({date_range})" if heading else f"({date_range})"
            if heading:
                lines.append(heading)

            loc = _format_location(e.get("city"), e.get("country"))
            if loc:
                lines.append(f"Ubicacion: {loc}")

            tech_line = _format_detail_line(e.get("technologies") or e.get("tech"))
            if tech_line:
                lines.append(tech_line)

            highlights = e.get("highlights") or []
            for h in highlights:
                h = str(h).strip()
                if h:
                    lines.append(f"- {h}")

            lines.append("")

        while lines and lines[-1] == "":
            lines.pop()

    def emit_detail_entry(entry: Dict, include_current_flag: bool = True):
        subtitle = (entry.get("subtitle") or "").strip()
        where = (entry.get("where") or "").strip()
        date_range = _format_date_range(
            entry.get("start"),
            entry.get("end"),
            bool(entry.get("is_current")) if include_current_flag else False,
        )
        heading = " — ".join([x for x in [subtitle, where] if x])
        if date_range:
            heading = f"{heading} ({date_range})" if heading else f"({date_range})"
        if heading:
            lines.append(heading)

        loc = _format_location(entry.get("city"), entry.get("country"))
        if loc:
            lines.append(f"Ubicacion: {loc}")

        tech_line = _format_detail_line(entry.get("tech"))
        if tech_line:
            lines.append(tech_line)

        items = entry.get("items") or []
        for it in items:
            it = str(it).strip()
            if it:
                lines.append(f"- {it}")
        lines.append("")

    def emit_subtitle_items_entry(entry: Dict):
        subtitle = (entry.get("subtitle") or "").strip()
        items = entry.get("items") or []

        # Requested: if no subtitle but has 1 item, promote item -> subtitle
        if not subtitle and len(items) == 1:
            subtitle = str(items[0]).strip()
            items = []

        if subtitle:
            if items:
                items_str = ", ".join([str(x).strip() for x in items if str(x).strip()])
                lines.append(f"- {subtitle}: {items_str}" if items_str else f"- {subtitle}")
            else:
                lines.append(f"- {subtitle}")
        else:
            for it in items:
                it = str(it).strip()
                if it:
                    lines.append(f"- {it}")

    def emit_skills_section(title: str, categories: List[Dict]):
        if not categories:
            return
        if lines:
            lines.append("")
        lines.append(title)
        for cat in categories:
            c = (cat.get("category") or "").strip()
            items = cat.get("items") or []
            items_str = ", ".join([str(x).strip() for x in items if str(x).strip()])
            if c and items_str:
                lines.append(f"{c}: {items_str}")
            elif c:
                lines.append(c)
            elif items_str:
                lines.append(items_str)

    def emit_extras(title: str, extra_sections: List[Dict]):
        if not extra_sections:
            return
        if lines:
            lines.append("")
        lines.append(title)

        for sec in extra_sections:
            sec_title = (sec.get("title") or "").strip()
            if sec_title:
                lines.append(sec_title)

            mode = (sec.get("mode") or "").strip() or "subtitle_items"
            entries = sec.get("entries") or []

            for entry in entries:
                if mode == "detailed":
                    emit_detail_entry(entry)
                else:
                    emit_subtitle_items_entry(entry)

            while lines and lines[-1] == "":
                lines.pop()

    experience_entries = data.get("experience") or []
    education_entries = data.get("education") or []
    skills_cats = data.get("skills") or []
    extra_sections = data.get("extra_sections") or data.get("extra") or []

    # Orden: core_order puede incluir ids de secciones extra (extra-xxxx). Si faltan, se agregan al final.
    extra_ids = [s.get("section_id") for s in extra_sections if s.get("section_id")]
    for eid in extra_ids:
        if eid not in core_order:
            core_order.append(eid)

    for module_id in core_order:
        if module_id == "experience":
            emit_detail_section("Experiencia", experience_entries, include_current_flag=True)
        elif module_id == "education":
            emit_detail_section("Educacion", education_entries, include_current_flag=False)
        elif module_id == "skills":
            emit_skills_section("Habilidades", skills_cats)
        elif module_id == "extras":
            # compat: exportar todas las extras en bloque
            emit_extras("Secciones extra", extra_sections)
        else:
            # módulo extra individual
            section = next((s for s in extra_sections if s.get("section_id") == module_id), None)
            if section:
                # cada extra imprime su propio título (y solo si tiene contenido)
                title = (section.get("title") or "").strip()
                entries = section.get("entries") or []
                if title and any(_has_extra_entry_content(e) for e in entries):
                    lines.append("")
                    lines.append(title.upper())
                    lines.append("-" * len(title))
                    # reutilizar renderer por modo
                    mode = section.get("mode") or "detailed"
                    for e in entries:
                        if mode == "subtitle_items":
                            emit_subtitle_items_entry(e)
                        else:
                            emit_detail_entry(e, include_current_flag=False)

    return "\r\n".join(lines)


def structure_from_post(post_data) -> Dict:
    data = default_structure()
    data["basics"] = {
        "name": post_data.get("name", "").strip(),
        "description": post_data.get("description", "").strip(),
        "email": post_data.get("email", "").strip(),
        "phone": post_data.get("phone", "").strip(),
        "linkedin": post_data.get("linkedin", "").strip(),
        "github": post_data.get("github", "").strip(),
        "city": post_data.get("city", "").strip(),
        "country": post_data.get("country", "").strip(),
    }

    # Orden de módulos (Experience/Education/Skills/Extras) según UI
    core_order_raw = (post_data.get("core_order", "") or "").strip()
    module_order_map_raw = (post_data.get("module_order_map", "") or "").strip()

    exp_roles = post_data.getlist("exp_role")
    exp_companies = post_data.getlist("exp_company")
    exp_starts = post_data.getlist("exp_start")
    exp_ends = post_data.getlist("exp_end")
    exp_cities = post_data.getlist("exp_city")
    exp_countries = post_data.getlist("exp_country")
    exp_techs = post_data.getlist("exp_tech")
    exp_highlights = post_data.getlist("exp_highlights")
    experience = []
    for idx, role in enumerate(exp_roles):
        highlights_text = exp_highlights[idx] if idx < len(exp_highlights) else ""
        highlights = [_clean_bullet(line) for line in highlights_text.splitlines() if line.strip()]
        experience.append(
            {
                "role": role.strip(),
                "company": exp_companies[idx].strip() if idx < len(exp_companies) else "",
                "start": _normalize_date_token(exp_starts[idx]) if idx < len(exp_starts) else "",
                "end": _normalize_date_token(exp_ends[idx]) if idx < len(exp_ends) else "",
                "city": exp_cities[idx].strip() if idx < len(exp_cities) else "",
                "country": exp_countries[idx].strip() if idx < len(exp_countries) else "",
                "technologies": exp_techs[idx].strip() if idx < len(exp_techs) else "",
                "highlights": highlights,
            }
        )
    data["experience"] = experience

    edu_degrees = post_data.getlist("edu_degree")
    edu_institutions = post_data.getlist("edu_institution")
    edu_starts = post_data.getlist("edu_start")
    edu_ends = post_data.getlist("edu_end")
    edu_cities = post_data.getlist("edu_city")
    edu_countries = post_data.getlist("edu_country")
    edu_honors = post_data.getlist("edu_honors")
    education = []
    for idx, degree in enumerate(edu_degrees):
        education.append(
            {
                "degree": degree.strip(),
                "institution": edu_institutions[idx].strip() if idx < len(edu_institutions) else "",
                "start": _normalize_date_token(edu_starts[idx]) if idx < len(edu_starts) else "",
                "end": _normalize_date_token(edu_ends[idx]) if idx < len(edu_ends) else "",
                "city": edu_cities[idx].strip() if idx < len(edu_cities) else "",
                "country": edu_countries[idx].strip() if idx < len(edu_countries) else "",
                "honors": edu_honors[idx].strip() if idx < len(edu_honors) else "",
            }
        )
    data["education"] = education

    skill_categories = post_data.getlist("skill_category")
    skill_items = post_data.getlist("skill_items")
    skills = []
    for idx, category in enumerate(skill_categories):
        items = skill_items[idx].strip() if idx < len(skill_items) else ""
        skills.append(
            {
                "category": category.strip(),
                "items": items,
            }
        )
    data["skills"] = skills

    extra_section_ids = post_data.getlist("extra_section_id")
    extra_titles = post_data.getlist("extra_title")
    extra_modes = post_data.getlist("extra_mode")

    sections = []
    id_to_index = {}
    for idx, section_id in enumerate(extra_section_ids):
        sid = (section_id or "").strip() or f"extra-{idx}"
        title = extra_titles[idx].strip() if idx < len(extra_titles) else ""
        mode = extra_modes[idx].strip() if idx < len(extra_modes) else "items"
        if mode not in {"items", "subtitles", "subtitle_items", "detailed"}:
            mode = "items"
        section = {
            "section_id": sid,
            "title": title,
            "mode": mode,
            "entries": [],
        }
        sections.append(section)
        id_to_index[sid] = idx

    entry_sections = post_data.getlist("extra_entry_section")
    entry_subtitles = post_data.getlist("extra_entry_subtitle")
    entry_titles = post_data.getlist("extra_entry_title")
    entry_wheres = post_data.getlist("extra_entry_where")
    entry_techs = post_data.getlist("extra_entry_tech")
    entry_starts = post_data.getlist("extra_entry_start")
    entry_ends = post_data.getlist("extra_entry_end")
    entry_cities = post_data.getlist("extra_entry_city")
    entry_countries = post_data.getlist("extra_entry_country")
    entry_items_si = post_data.getlist("extra_entry_items_si")
    entry_items_detailed = post_data.getlist("extra_entry_items_detailed")
    legacy_entry_items = post_data.getlist("extra_entry_items")
    entry_count = len(entry_sections)
    has_mode_specific_items = bool(entry_items_si or entry_items_detailed)
    paired_legacy_entry_items = entry_count > 0 and len(legacy_entry_items) == (entry_count * 2)
    field_cursors = {
        "subtitle": 0,
        "title": 0,
        "where": 0,
        "tech": 0,
        "start": 0,
        "end": 0,
        "city": 0,
        "country": 0,
        "items_si": 0,
        "items_detailed": 0,
    }

    def _entry_field_value(
        values: List[str],
        idx: int,
        *,
        entry_mode: str,
        field_mode: str,
        cursor_key: str,
    ) -> str:
        # Caso alineado por entrada (una posición por cada entry del formulario).
        if entry_count > 0 and len(values) == entry_count:
            return values[idx] if idx < len(values) else ""

        # Caso sparse por modo (inputs ocultos deshabilitados en UI):
        # consumir solo para entries del modo correspondiente.
        if entry_mode != field_mode:
            return ""

        cursor = field_cursors[cursor_key]
        value = values[cursor] if cursor < len(values) else ""
        field_cursors[cursor_key] = cursor + 1
        return value

    def parse_items(raw_text: str) -> List[str]:
        """Parsea items ingresados por el editor (un item por línea)."""
        if raw_text is None:
            return []
        raw = str(raw_text).replace("\r\n", "\n").replace("\r", "\n")
        items: List[str] = []
        for line in raw.split("\n"):
            sline = (line or "").strip()
            if not sline:
                continue
            sline = re.sub(r"^[\\s•\\-–—*·]+\\s*", "", sline).strip()
            if sline:
                items.append(_clean_bullet(sline))
        return items

    single_section_sid = ""
    if len(sections) == 1:
        single_section_sid = (sections[0].get("section_id") or "").strip()
    last_valid_sid = single_section_sid

    for idx, section_id in enumerate(entry_sections):
        sid = (section_id or "").strip()
        if not sid and last_valid_sid:
            sid = last_valid_sid
        if not sid and single_section_sid:
            sid = single_section_sid
        if sid not in id_to_index:
            continue
        last_valid_sid = sid
        section_mode = (sections[id_to_index[sid]].get("mode") or "").strip()
        entry_mode = "detailed" if section_mode == "detailed" else "si"
        if has_mode_specific_items:
            if entry_mode == "detailed":
                raw_items = _entry_field_value(
                    entry_items_detailed,
                    idx,
                    entry_mode=entry_mode,
                    field_mode="detailed",
                    cursor_key="items_detailed",
                )
            else:
                raw_items = _entry_field_value(
                    entry_items_si,
                    idx,
                    entry_mode=entry_mode,
                    field_mode="si",
                    cursor_key="items_si",
                )
        elif paired_legacy_entry_items:
            raw_primary = legacy_entry_items[idx * 2] if (idx * 2) < len(legacy_entry_items) else ""
            raw_secondary = legacy_entry_items[(idx * 2) + 1] if ((idx * 2) + 1) < len(legacy_entry_items) else ""
            if section_mode == "detailed":
                raw_items = raw_primary or raw_secondary
            else:
                raw_items = raw_secondary or raw_primary
        else:
            raw_items = legacy_entry_items[idx] if idx < len(legacy_entry_items) else ""
        entry = {
            "subtitle": _entry_field_value(
                entry_subtitles,
                idx,
                entry_mode=entry_mode,
                field_mode="si",
                cursor_key="subtitle",
            ).strip(),
            "title": _entry_field_value(
                entry_titles,
                idx,
                entry_mode=entry_mode,
                field_mode="detailed",
                cursor_key="title",
            ).strip(),
            "where": _entry_field_value(
                entry_wheres,
                idx,
                entry_mode=entry_mode,
                field_mode="detailed",
                cursor_key="where",
            ).strip(),
            "tech": _entry_field_value(
                entry_techs,
                idx,
                entry_mode=entry_mode,
                field_mode="detailed",
                cursor_key="tech",
            ).strip(),
            "start": _normalize_date_token(
                _entry_field_value(
                    entry_starts,
                    idx,
                    entry_mode=entry_mode,
                    field_mode="detailed",
                    cursor_key="start",
                )
            ),
            "end": _normalize_date_token(
                _entry_field_value(
                    entry_ends,
                    idx,
                    entry_mode=entry_mode,
                    field_mode="detailed",
                    cursor_key="end",
                )
            ),
            "city": _entry_field_value(
                entry_cities,
                idx,
                entry_mode=entry_mode,
                field_mode="detailed",
                cursor_key="city",
            ).strip(),
            "country": _entry_field_value(
                entry_countries,
                idx,
                entry_mode=entry_mode,
                field_mode="detailed",
                cursor_key="country",
            ).strip(),
            "items": parse_items(raw_items),
        }

        # Si la sección está en modo Sub+Item y viene sin subtítulo pero con items,
        # usamos el primer item como subtítulo (y dejamos el resto como items).
        # Esto evita que una entrada válida se pierda al exportar.
        if section_mode == "subtitle_items" and (not entry.get("subtitle")) and entry.get("items"):
            entry["subtitle"] = entry["items"][0]
            entry["items"] = entry["items"][1:]
        if _has_extra_entry_content(entry):
            sections[id_to_index[sid]]["entries"].append(entry)

    extra_sections = []
    for section in sections:
        entries = [entry for entry in section["entries"] if _has_extra_entry_content(entry)]
        if not entries and section["title"]:
            entries = [_empty_extra_entry()]
        section["entries"] = entries
        if section["title"] or entries:
            extra_sections.append(section)

    data["extra_sections"] = extra_sections

    # Orden final de módulos para exportación:
    # 1) module_order_map (posición interna por módulo, generado por JS)
    # 2) core_order (fallback)
    # 3) módulos faltantes al final
    available_ids: List[str] = ["experience", "education", "skills"]
    for section in extra_sections:
        sid = (section.get("section_id") or "").strip()
        if sid and sid not in available_ids:
            available_ids.append(sid)

    core_order_ids: List[str] = []
    if core_order_raw:
        for token in [item.strip() for item in core_order_raw.split(",") if item.strip()]:
            if token == "extras":
                for section in extra_sections:
                    sid = (section.get("section_id") or "").strip()
                    if sid and sid not in core_order_ids:
                        core_order_ids.append(sid)
                continue
            if token in available_ids and token not in core_order_ids:
                core_order_ids.append(token)

    map_order_ids: List[str] = []
    if module_order_map_raw:
        ranked: List[tuple[int, int, str]] = []
        raw_pairs = [part.strip() for part in module_order_map_raw.split(",") if part.strip()]
        for raw_idx, pair in enumerate(raw_pairs):
            if ":" not in pair:
                continue
            key, order_raw = pair.split(":", 1)
            key = key.strip()
            if key not in available_ids:
                continue
            try:
                order = int(order_raw.strip())
            except ValueError:
                continue
            if order < 1:
                continue
            ranked.append((order, raw_idx, key))
        ranked.sort(key=lambda item: (item[0], item[1]))
        for _, _, key in ranked:
            if key not in map_order_ids:
                map_order_ids.append(key)

    final_order: List[str] = []
    for key in map_order_ids + core_order_ids + available_ids:
        if key in available_ids and key not in final_order:
            final_order.append(key)
    if final_order:
        data.setdefault("meta", {})["core_order"] = ",".join(final_order)

    _ensure_minimums(data)
    return data


# --------------------
# Extraccion de datos basicos
# --------------------

def _extract_contact(text: str) -> Dict[str, str]:
    email = _first_match(EMAIL_RE, text)
    phone = _first_match(PHONE_RE, text)
    urls = URL_RE.findall(text)
    linkedin = ""
    github = ""
    for url in urls:
        low = url.lower()
        if "linkedin.com" in low and not linkedin:
            linkedin = url
        if "github.com" in low and not github:
            github = url
    return {
        "email": email,
        "phone": phone,
        "linkedin": linkedin,
        "github": github,
    }


def _extract_name_and_description(
    lines: List[str], contact: Dict[str, str]
) -> Tuple[str, str, List[str]]:
    cleaned = [line for line in lines if line is not None]
    contact_values = {v for v in contact.values() if v}
    name = ""
    description_lines: List[str] = []
    remaining: List[str] = []
    last_index = -1
    for idx, line in enumerate(cleaned):
        last_index = idx
        if not line:
            if name:
                description_lines.append("")
            continue
        if any(value in line for value in contact_values):
            continue
        if not name:
            name = line
            continue
        if _is_heading(line):
            remaining = cleaned[idx:]
            break
        description_lines.append(line)
    if not remaining and last_index >= 0:
        remaining = cleaned[last_index + 1 :]

    description = _join_paragraph(description_lines)
    return name, description, remaining


# Detecta ubicacion (ciudad, pais) desde texto y lineas
def _extract_location(text: str, lines: List[str], contact: Dict[str, str]) -> Tuple[str, str]:
    contact_values = {v for v in contact.values() if v}
    for line in lines:
        if not line:
            continue
        if _is_heading(line):
            break
        for chunk in re.split(r"[·\u2022|]", line):
            cleaned = chunk.strip()
            if not cleaned:
                continue
            if _is_location_candidate(cleaned, contact_values):
                city, country = _parse_location(cleaned)
                if city and country:
                    return city, country
    return "", ""


# --------------------
# Separacion de secciones
# --------------------

def _split_sections(lines: List[str]) -> Tuple[Dict[str, List[str]], List[ExtraSectionRaw], List[str]]:
    sections: Dict[str, List[str]] = {"experience": [], "education": [], "skills": []}
    extras: List[ExtraSectionRaw] = []
    current_section = "other"
    current_extra: Optional[ExtraSectionRaw] = None
    detected_order: List[str] = []
    seen_core: set[str] = set()

    def register_core(module_id: str) -> None:
        if module_id in {"experience", "education", "skills"} and module_id not in seen_core:
            detected_order.append(module_id)
            seen_core.add(module_id)

    def register_extra(section_index: int) -> None:
        # El section_id real se asigna luego (_parse_extras), pero conservamos
        # posición relativa para mapearlo como extra-{idx}.
        detected_order.append(f"extra-{section_index}")

    for line in lines:
        if not line:
            if current_section in sections:
                sections[current_section].append("")
            elif current_section == "extra" and current_extra is not None:
                current_extra["lines"].append("")
            continue

        if current_section == "skills" and _is_extra_heading_after_skills(line):
            current_section = "extra"
            current_extra = {"title": _normalize_heading_line(line).strip().rstrip(":"), "lines": []}
            extras.append(current_extra)
            register_extra(len(extras) - 1)
            continue

        key, title = _match_heading(line)
        if key:
            if key == "extra" and current_section == "skills":
                if not _is_extra_keyword_heading(line):
                    sections[current_section].append(line)
                    continue
            if key == "extra":
                current_section = "extra"
                current_extra = {"title": title, "lines": []}
                extras.append(current_extra)
                register_extra(len(extras) - 1)
            else:
                current_section = key
                current_extra = None
                register_core(key)
            continue

        if current_section in sections:
            sections[current_section].append(line)
        elif current_section == "extra" and current_extra is not None:
            current_extra["lines"].append(line)

    return sections, extras, detected_order


# --------------------
# Parsers por seccion
# --------------------

def _parse_experience(lines: List[str]) -> List[Dict]:
    blocks = _group_entries(lines, section="experience")
    experience: List[Dict] = []
    for block in blocks:
        item = {
            "role": "",
            "company": "",
            "start": "",
            "end": "",
            "city": "",
            "country": "",
            "technologies": "",
            "highlights": [],
        }
        highlights: List[str] = []
        for raw_line in block:
            line = raw_line.strip()
            if not line:
                continue
            if not item["start"]:
                start, end_date, remainder = _extract_date_range_from_line(line)
                if start or end_date:
                    item["start"] = start
                    item["end"] = end_date
                    line = remainder.strip()
                    if not line:
                        continue
            tech = _extract_tech_from_line(line)
            if tech and not item["technologies"]:
                item["technologies"] = tech
                continue
            if (
                not item["technologies"]
                and (item["role"] or item["company"] or item["start"] or item["end"])
                and not DATE_RANGE_RE.search(line)
                and not _is_heading(line)
                and _looks_like_tech(line)
            ):
                item["technologies"] = line.strip()
                continue
            if _is_bullet(line) or _contains_bullet_symbol(line):
                _append_highlight(highlights, line)
                continue
            if not item["city"]:
                city, country = _extract_location_from_line(line)
                if city:
                    item["city"] = city
                    item["country"] = country
                    continue

            if not item["role"] and not item["company"]:
                role, company = _split_role_company(line)
                if company:
                    item["role"] = role
                    item["company"] = company
                else:
                    item["company"] = line.strip()
                continue

            if item["company"] and not item["role"]:
                item["role"] = line.strip()
                continue

            if not item["company"] and item["role"]:
                item["company"] = line.strip()
                continue

            _append_highlight(highlights, line)

        item["highlights"] = [h for h in highlights if h]
        experience.append(item)

    return experience or default_structure()["experience"]


def _parse_education(lines: List[str]) -> List[Dict]:
    blocks = _group_entries(lines, section="education")
    education: List[Dict] = []
    for block in blocks:
        item = {
            "degree": "",
            "institution": "",
            "start": "",
            "end": "",
            "city": "",
            "country": "",
            "honors": "",
        }
        for raw_line in block:
            line = raw_line.strip()
            if not line:
                continue
            normalized = _normalize_ascii(line)
            if not item["start"]:
                start, end_date, remainder = _extract_date_range_from_line(line)
                if start or end_date:
                    item["start"] = start
                    item["end"] = end_date
                    line = remainder.strip()
                    if not line:
                        continue
                    normalized = _normalize_ascii(line)
            if _is_bullet(line):
                cleaned = _clean_bullet(line)
                if not item["honors"]:
                    item["honors"] = cleaned
                continue
            if "honor" in normalized or "mencion" in normalized:
                parts = line.split(":", 1)
                item["honors"] = parts[1].strip() if len(parts) > 1 else line
                continue
            if not item["city"]:
                city, country = _extract_location_from_line(line)
                if city:
                    item["city"] = city
                    item["country"] = country
                    continue
            if not item["institution"] and _looks_like_org(line):
                item["institution"] = line.strip()
                continue
            if not item["degree"]:
                item["degree"] = line.strip()
                continue
            if not item["institution"]:
                item["institution"] = line.strip()
                continue
        education.append(item)
    return education or default_structure()["education"]


def _parse_skills(lines: List[str]) -> List[Dict]:
    items: List[Dict] = []
    current_category: str = ""
    current_items: List[str] = []

    def is_category_line(line: str, next_line: Optional[str]) -> bool:
        if _is_bullet(line) or _is_heading(line):
            return True
        if current_category and not current_items:
            return False
        if ":" in line and not current_category:
            return True
        if "," in line or len(line) > 48:
            return False
        if EMAIL_RE.search(line) or URL_RE.search(line):
            return False
        if line.strip().isupper():
            return True
        if "/" in line:
            return True
        normalized = _normalize_ascii(line)
        if f" {normalized} ".find(" de ") >= 0 or f" {normalized} ".find(" y ") >= 0:
            return True
        words = [w for w in line.split() if w]
        if not words:
            return False
        title_like = sum(1 for w in words if w[:1].isupper())
        if title_like == len(words):
            return True
        if next_line:
            next_words = [w for w in next_line.split() if w]
            if (
                len(words) <= 3
                and next_words
                and len(next_words) <= 2
                and "," not in next_line
                and not _is_bullet(next_line)
            ):
                return True
        if next_line and "," in next_line:
            return True
        return False

    non_empty = [line for line in lines if line.strip()]
    for idx, line in enumerate(non_empty):
        next_line = non_empty[idx + 1] if idx + 1 < len(non_empty) else None
        if is_category_line(line, next_line):
            if current_category or current_items:
                items.append(
                    {
                        "category": current_category.strip(),
                        "items": ", ".join([item for item in current_items if item]),
                    }
                )
            current_category = _clean_bullet(line)
            current_items = []
            continue
        if ":" in line and not current_category:
            category, value = line.split(":", 1)
            items.append({"category": category.strip(), "items": value.strip()})
            continue
        current_items.append(_clean_bullet(line))

    if current_category or current_items:
        items.append(
            {
                "category": current_category.strip(),
                "items": ", ".join([item for item in current_items if item]),
            }
        )

    return items or default_structure()["skills"]


def _ensure_minimums(data: Dict) -> None:
    if not data.get("experience"):
        data["experience"] = default_structure()["experience"]
    if not data.get("education"):
        data["education"] = default_structure()["education"]
    if not data.get("skills"):
        data["skills"] = default_structure()["skills"]
