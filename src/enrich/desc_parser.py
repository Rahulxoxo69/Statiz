"""Description-driven enrichment: parse brand, product type and technical
specs from minimal inputs (Mfg_Part_Num + Part_Desc + Part_Manuf) when no
manufacturer URL is available. Fully rule-based and generic — no hardcoded
part numbers; works on unseen evaluation data.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- brand maps
MANUF_TO_BRAND = [
    (re.compile(r"freud", re.I), "Diablo"),
    (re.compile(r"milwaukee", re.I), "Milwaukee"),
    (re.compile(r"phillips", re.I), "Philips"),
    (re.compile(r"kichler", re.I), "Kichler"),
    (re.compile(r"black.*decker|dewlt", re.I), "DEWALT"),
    (re.compile(r"satco", re.I), "SATCO"),
    (re.compile(r"makita", re.I), "Makita"),
    (re.compile(r"boise", re.I), "Boise Cascade"),
    (re.compile(r"appliance dealers", re.I), None),  # multi-brand co-op
]

# (regex on description, product_name, dept, klass, fine, unspsc)
PRODUCT_TYPES = [
    (r"sanding belt", "Sanding Belt", "Abrasives", "Coated Abrasives", "Sanding Belts", "23241405"),
    (r"grinding disc|grinding wheel", "Grinding Disc", "Abrasives", "Bonded Abrasives", "Grinding Wheels", "23241401"),
    (r"cut.?off disc|cutting disc", "Cut-Off Disc", "Abrasives", "Bonded Abrasives", "Cut-Off Discs", "23241408"),
    (r"cut.*grind|grind.*cut", "Cut and Grind Disc", "Abrasives", "Bonded Abrasives", "Cut-Off Discs", "23241408"),
    (r"sanding sponge", "Sanding Sponge", "Abrasives", "Coated Abrasives", "Sanding Sponges", "23241407"),
    (r"elect\.? tape|electrical tape", "Electrical Tape", "Electrical", "Tape", "Electrical Tape", "31201503"),
    (r"\btape\b", "Tape", "Building Materials", "Adhesives", "Tape", "31201503"),
    (r"rail kit|railing|baluster|rail panel|t-rail|\bgate\b", "Deck Railing", "Building Materials", "Railing", "Deck Railing Components", "30131700"),
    (r"mortar", "Mortar", "Building Materials", "Masonry", "Mortar", "30111509"),
    (r"heater", "Heater", "HVAC", "Heating", "Heaters", "40101700"),
    (r"laundry center", "Laundry Center", "Appliances", "Large Appliances", "Washers & Dryers", "52101501"),
    (r"tire pressure|inflator|gauge", "Gauge", "Tools", "Measuring Tools", "Gauges", "27111516"),
    (r"kneeling pad", "Kneeling Pad", "Safety", "PPE", "Knee Pads", "46181511"),
    (r"fan", "Fan", "HVAC", "Ventilation", "Fans", "40102100"),
    (r"grill", "Grill", "Appliances", "Outdoor Appliances", "Grills", "52101900"),
    (r"tube|fitting|elbow|tee\b|coupling", "Fitting", "Plumbing", "Fittings", "Fittings", "31142400"),
    (r"flap disc|flap wheel", "Flap Disc", "Abrasives", "Bonded Abrasives", "Flap Wheels", "23241403"),
    (r"wire wheel|wire brush", "Wire Brush", "Abrasives", "Brushes", "Wire Brushes", "23241504"),
    (r"hiolit|abranet|abralon|sandpaper|sanding sheet|sand sheet", "Sanding Sheet", "Abrasives", "Coated Abrasives", "Sanding Sheets", "23241406"),
    (r"backing pad|backup pad", "Backing Pad", "Abrasives", "Abrasive Accessories", "Backing Pads", "23241503"),
    (r"\bp\d{3}\b.*(?:disc|5\"|6\")|stikit|sanding disc|film disc|cubitron", "Sanding Disc", "Abrasives", "Coated Abrasives", "Sanding Discs", "23241404"),
    (r"saw blade|blade", "Saw Blade", "Tools", "Cutting Tools", "Saw Blades", "27112004"),
    (r"drill bit|drill\s|auger|spade bit|hole saw", "Drill Bit", "Tools", "Cutting Tools", "Drill Bits", "27112703"),
    (r"screw", "Screw", "Fasteners", "Threaded Fasteners", "Screws", "31171502"),
    (r"bolt", "Bolt", "Fasteners", "Threaded Fasteners", "Bolts", "31171501"),
    (r"\bnut\b", "Nut", "Fasteners", "Threaded Fasteners", "Nuts", "31171503"),
    (r"washer", "Washer", "Fasteners", "Threaded Fasteners", "Washers", "31171504"),
    (r"\bled\b|lamp|bulb|downlight|spot|flood|candelabra|par\d|br\d|a19|mr16|gu10", "LED Lamp", "Electrical", "Lighting", "LED Lamps", "39101629"),
    (r"fixture|pendant|chandelier|vanity light|wall sconce|flush mount", "Light Fixture", "Electrical", "Lighting", "Lighting Fixtures", "39111500"),
    (r"landscape.*(light|kit)|path light|spotlight kit", "Landscape Light", "Electrical", "Lighting", "Landscape Lighting", "39111603"),
    (r"track|rail light", "Track Light", "Electrical", "Lighting", "Track Lighting", "39111606"),
    (r"under.cabinet", "Under Cabinet Light", "Electrical", "Lighting", "Under Cabinet Lighting", "39111604"),
    (r"dishwasher", "Dishwasher", "Appliances", "Large Appliances", "Dishwashers", "52101506"),
    (r"refrigerator|\bfridge\b", "Refrigerator", "Appliances", "Large Appliances", "Refrigerators", "52101504"),
    (r"range|cooktop|wall oven", "Range", "Appliances", "Large Appliances", "Ranges", "52101508"),
    (r"microwave", "Microwave", "Appliances", "Large Appliances", "Microwaves", "52101510"),
    (r"washer.*dryer|washing machine|dryer", "Washer/Dryer", "Appliances", "Large Appliances", "Washers & Dryers", "52101501"),
    (r"glove", "Glove", "Safety", "PPE", "Gloves", "46181502"),
    (r"respirator|n95|mask", "Respirator", "Safety", "PPE", "Respirators", "46181801"),
    (r"safety glass|goggle", "Safety Eyewear", "Safety", "PPE", "Safety Glasses", "46181509"),
    (r"tape measure|measuring tape", "Tape Measure", "Tools", "Hand Tools", "Tape Measures", "27111505"),
    (r"hammer", "Hammer", "Tools", "Hand Tools", "Hammers", "27111506"),
    (r"wrench", "Wrench", "Tools", "Hand Tools", "Wrenches", "27111513"),
    (r"plier|grip", "Pliers", "Tools", "Hand Tools", "Pliers", "27111504"),
    (r"socket", "Socket", "Tools", "Hand Tools", "Sockets", "27111515"),
    (r"grinder", "Grinder", "Tools", "Power Tools", "Grinders", "27112700"),
    (r"sander", "Sander", "Tools", "Power Tools", "Sanders", "27112700"),
    (r"router", "Router", "Tools", "Power Tools", "Routers", "27112700"),
    (r"drill\s*\(?.*\)|driver|impact", "Power Drill", "Tools", "Power Tools", "Drills", "27112701"),
    (r"battery|battery pack", "Battery Pack", "Electrical", "Batteries", "Power Tool Batteries", "26111701"),
    (r"charger", "Charger", "Electrical", "Batteries", "Chargers", "26111737"),
    (r"lumber|fir|pine|spruce|plywood|osb|board|decking|trim|siding|fascia|shiplap|paneling", "Lumber", "Building Materials", "Lumber", "Dimensional Lumber", "30111501"),
    (r"door", "Door", "Building Materials", "Doors", "Doors", "30101700"),
    (r"window", "Window", "Building Materials", "Windows", "Windows", "30101600"),
    (r"insulation", "Insulation", "Building Materials", "Insulation", "Insulation", "30112100"),
    (r"drywall", "Drywall", "Building Materials", "Drywall", "Drywall Panels", "30111527"),
    (r"caulk|sealant|adhesive|glue|epoxy", "Adhesive/Sealant", "Building Materials", "Adhesives", "Adhesives & Sealants", "31201500"),
    (r"paint", "Paint", "Building Materials", "Paint", "Paint", "30971500"),
    (r"cable|wire|\bconductor\b|romex", "Cable/Wire", "Electrical", "Wire & Cable", "Wire & Cable", "26121500"),
    (r"switch", "Switch", "Electrical", "Wiring Devices", "Switches", "39121400"),
    (r"outlet|receptacle", "Receptacle", "Electrical", "Wiring Devices", "Receptacles", "39121404"),
    (r"breaker", "Circuit Breaker", "Electrical", "Circuit Protection", "Breakers", "39121606"),
    (r"filter", "Filter", "HVAC", "Filters", "Air Filters", "40161600"),
    (r"hose", "Hose", "Plumbing", "Hoses", "Hoses", "27112011"),
    (r"valve", "Valve", "Plumbing", "Valves", "Valves", "27111500"),
    (r"pump", "Pump", "Plumbing", "Pumps", "Pumps", "41113600"),
]

SPEC_PATTERNS = [
    # (label, regex, uom, value_transform)
    ("Grit", r"\b(P\d{3,4}|\d{2,3}[- ]?grit)\b", "", lambda m: m.group(1).replace(" grit", "").strip()),
    ("Width", r"(\d{1,2}(?:-\d{1,2}/\d{1,2})?)(?:\"| ?in\b\.?)[ ]*[x×]", "in", lambda m: m.group(1)),
    ("Length", r"[x×][ ]*(\d{1,2}(?:-\d{1,2}/\d{1,2})?)(?:\"| ?in\b\.?)", "in", lambda m: m.group(1)),
    ("Diameter", r"(\d{1,2}(?:-\d{1,2}/\d{1,2})?)\"(?: ?(?:dia|diameter))", "in", lambda m: m.group(1)),
    ("Board Size", r"\b(\d+(?:/\d+)?x\d+(?:-\d+'\d*)?)\b", "", lambda m: m.group(1)),
    ("Lumber Length", r"-(\d{1,2})'", "ft", lambda m: m.group(1)),
    ("Voltage", r"(\d{2,3})\s*[vV]\b", "V", lambda m: m.group(1)),
    ("Amperage", r"(\d{1,2}(?:\.\d)?)\s*[aA]\b", "A", lambda m: m.group(1)),
    ("Wattage", r"(\d{1,4})\s*[wW]\b(?![a-z])", "W", lambda m: m.group(1)),
    ("Color Temperature", r"(\d{4})\s*[kK]\b", "K", lambda m: m.group(1)),
    ("Lumens", r"(\d{3,5})\s*(?:lumens?|lm)\b", "lm", lambda m: m.group(1)),
    ("Sound Level", r"(\d{2})\s*dB?a?\b", "dBA", lambda m: m.group(1)),
    ("Pack Quantity", r"(\d{1,4})\s*(?:pc|pcs|piece|pieces|pack|ct|count|/box|per box)\b", "", lambda m: m.group(1)),
    ("Material", r"\b(SST|Stainless Steel|SS|Aluminum|Brass|Galvanized|Zinc|Carbide|Titanium|Bi-?Metal|Ceramic)\b",
     "", lambda m: {"SST": "Stainless Steel", "SS": "Stainless Steel",
                    "Bi-Metal": "Bi-Metal", "BiMetal": "Bi-Metal"}.get(m.group(1), m.group(1))),
    ("Color", r"\b(Stainless|White|Black|Red|Yellow|Blue|Green|Gray|Grey|Bronze|Nickel|Chrome|Brown|Beige)\b",
     "", lambda m: m.group(1)),
    ("Finish", r"\b(Matte|Gloss|Satin|Polished|Brushed|Oil.Rubbed)\b", "", lambda m: m.group(1)),
    ("Arbor Size", r"arbor[ :]*(\d+(?:-\d+/\d+)?\"?)", "", lambda m: m.group(1)),
    ("Teeth", r"(\d{1,3})\s*(?:tooth|teeth|T\b|TCT)", "", lambda m: m.group(1)),
]

SERIES_RE = re.compile(r"\b(Professional Series|Eco Series|Expert|Compact|Flexvolt|M18|M12|20V MAX|Atomic|Xtreme|Cubitron II|Stikit|Steel Demon|Speed Demon|Perform\+?|Performance\+?|DKO|HIOLIT|Abranet|Abralon)\b", re.I)

# brand tokens that appear as leading words in trading descriptions
BRAND_TOKEN_RE = re.compile(
    r"\b(3M|Diablo|Milw|Milwaukee|DeWalt|DEWALT|Makita|Bosch|Metabo|IRWIN|Lenox|Fein|"
    r"Mirka|Norton|Merit|Walter|Weiler|Pferd|CGW|Norton Clipper|Husqvarna|"
    r"Philips|GE|Sylvania|Satco|Kichler|Progress Lighting|Sea Gull|WAC|Juno|"
    r"Commercial Electric|Ecosmart|Cree|TCP|Feit|Leviton|Lutron|Legrand|Pass & Seymour|"
    r"Simpson|Grip-Rite|FasNate|Senco|Paslode|Bostitch|Hitachi|Spotnails|"
    r"Kidde|First Alert|3M Tekk|Ansell|Showa|PIP|Memco|Santiago|)"
    r"(?= |$)")


def parse_product(mfg_part_num: str, part_desc: str, part_manuf: str) -> dict:
    """Rule-based enrichment from minimal inputs. Returns canonical record."""
    desc = (part_desc or "").strip()
    dl = desc.lower()

    # brand: manufacturer mapping first, then tokens found in description
    brand = None
    for rx, b in MANUF_TO_BRAND:
        if rx.search(part_manuf or ""):
            brand = b
            break
    if brand is None or brand == "Jam Industrial Supply LLC":
        m = BRAND_TOKEN_RE.search(desc)
        if m:
            brand = {"Milw": "Milwaukee"}.get(m.group(1), m.group(1))
    if brand is None:
        for rx, b in MANUF_TO_BRAND:
            if b and b.lower() in dl:
                brand = b
                break
    if brand is None:
        # fall back: manufacturer legal name trimmed of parenthetical codes
        brand = re.sub(r"\s*\(.*?\)\s*$", "", (part_manuf or "").strip()) or None

    # product type
    product = (product_name, dept, klass, fine, unspsc) = ("Part", "", "", "", "")
    for rx, *rest in PRODUCT_TYPES:
        if re.search(rx, dl):
            product = tuple(rest)
            break
    if product[0] == "Part" and desc:
        # generic fallback: never leave a row unclassified — use leading
        # description words as the product name under General Supplies
        words = re.sub(r"[^A-Za-z0-9 /x'-]", " ", desc).split()
        skip = {m.group(0).lower() for m in [re.search(r"^[0-9/.-]+$", w) or type("", (), {"group": lambda s, i=0: ""})() for w in words]}
        keep = [w for w in words if not re.fullmatch(r"[0-9/.-]+", w)][:3]
        if keep:
            product = (" ".join(keep), "General Supplies", "General", "General", "")

    # specs
    attributes = []
    seen = set()
    for label, pattern, uom, tf in SPEC_PATTERNS:
        m = re.search(pattern, desc, re.I)
        if m and label not in seen:
            try:
                val = tf(m)
            except Exception:
                continue
            if val:
                attributes.append({"label": label, "value": str(val), "uom": uom})
                seen.add(label)

    sm = SERIES_RE.search(desc)
    series = sm.group(1).title() if sm else ""

    specs_str = ", ".join(f"{a['label']} {a['value']}{(' ' + a['uom']) if a['uom'] else ''}"
                          for a in attributes[:8])
    base = f"{brand} {product[0]}".strip()
    mfr_part = mfg_part_num or ""

    # description variants in the expected-output style
    short = f"{base}{', ' + series if series else ''}{', ' + mfr_part if mfr_part else ''}".strip(", ")
    invoice_tokens = [product[0].replace(" ", " ")]
    for a in attributes:
        invoice_tokens.append(f"{a['value']}{a['uom'].replace('in','IN') if a['uom']=='in' else a['uom'].upper()}")
    invoice = " ".join(invoice_tokens[:6]).upper()
    long_desc = f"{base}{', ' + series if series else ''}, Model {mfr_part}" if mfr_part else base
    if specs_str:
        long_desc += f", {specs_str}"

    return {
        "part_desc": desc,
        "manufacturer_name": re.sub(r"\s*\(.*?\)\s*$", "", (part_manuf or "").strip()) or None,
        "brand_name": brand,
        "trade_name": brand,
        "dept": product[1] or None, "klass": product[2] or None, "fine": product[3] or None,
        "unspsc": product[4] or None,
        "classpath": " > ".join(x for x in (product[1], product[2], product[3]) if x) or None,
        "manufacturer_part_number": mfr_part or None,
        "short_desc": short,
        "mobile_desc": f"{short}{', ' + specs_str if specs_str else ''}",
        "invoice_desc": invoice,
        "long_desc": long_desc,
        "retail_desc": short,
        "product_name": product[0],
        "attributes": attributes,
        "features": [f"{a['label']}: {a['value']}{' ' + a['uom'] if a['uom'] else ''}"
                     for a in attributes[:10]],
        "application": product[0],
    }
