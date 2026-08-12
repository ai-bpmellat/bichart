import urllib.request
import json
import ssl
import os

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = 'https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_IRN_1.json'
print('Downloading GADM 4.1 Iran provinces...')
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
    raw_data = resp.read().decode('utf-8')

gadm = json.loads(raw_data)
features = gadm.get('features', [])
print(f'Downloaded {len(features)} province features.')

def normalize_name(s):
    return ''.join(c for c in (s or '').lower() if c.isalnum())

EN_TO_FA_PROVINCE = {
    "alborz": "البرز",
    "ardebil": "اردبیل",
    "ardabil": "اردبیل",
    "azarbayjanegharbi": "آذربایجان غربی",
    "azarbayjanesharqi": "آذربایجان شرقی",
    "eastazarbaijan": "آذربایجان شرقی",
    "westazarbaijan": "آذربایجان غربی",
    "bushehr": "بوشهر",
    "chaharmahallandbakhtiari": "چهارمحال و بختیاری",
    "chaharmahalandbakhtiari": "چهارمحال و بختیاری",
    "esfahan": "اصفهان",
    "isfahan": "اصفهان",
    "fars": "فارس",
    "gilan": "گیلان",
    "golestan": "گلستان",
    "hamadan": "همدان",
    "hormozgan": "هرمزگان",
    "ilam": "ایلام",
    "kerman": "کرمان",
    "kermanshah": "کرمانشاه",
    "khorasanejonubi": "خراسان جنوبی",
    "khorasanerazavi": "خراسان رضوی",
    "khorasaneshomali": "خراسان شمالی",
    "northkhorasan": "خراسان شمالی",
    "razavikhorasan": "خراسان رضوی",
    "southkhorasan": "خراسان جنوبی",
    "khuzestan": "خوزستان",
    "kohgiluyehandbuyerahmad": "کهگیلویه و بویراحمد",
    "kordestan": "کردستان",
    "kurdistan": "کردستان",
    "lorestan": "لرستان",
    "markazi": "مرکزی",
    "mazandaran": "مازندران",
    "qazvin": "قزوین",
    "qom": "قم",
    "semnan": "سمنان",
    "sistanandbaluchestan": "سیستان و بلوچستان",
    "tehran": "تهران",
    "yazd": "یزد",
    "zanjan": "زنجان",
}

standard_features = []
for f in features:
    p = f.get('properties', {})
    raw_name_en = p.get('NAME_1', '').strip()
    norm_en = normalize_name(raw_name_en)
    name_fa = EN_TO_FA_PROVINCE.get(norm_en, p.get('NL_NAME_1', raw_name_en))
    
    new_props = {
        "name": name_fa,
        "name_en": raw_name_en,
        "name_fa": name_fa,
        "id": p.get('GID_1', ''),
        "province_id": p.get('HASC_1', '')
    }
    
    standard_features.append({
        "type": "Feature",
        "id": p.get('GID_1', raw_name_en),
        "properties": new_props,
        "geometry": f.get('geometry')
    })

clean_geojson = {
    "type": "FeatureCollection",
    "name": "iran",
    "crs": {
        "type": "name",
        "properties": {
            "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
        }
    },
    "features": standard_features
}

output_path = os.path.join('static', 'vendor', 'iran.json')
with open(output_path, 'w', encoding='utf-8') as out:
    json.dump(clean_geojson, out, ensure_ascii=False, indent=None)

print(f'Successfully wrote clean WGS84 Iran GeoJSON to {output_path} (size: {os.path.getsize(output_path)} bytes).')
