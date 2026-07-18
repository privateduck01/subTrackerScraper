import os
import json
import re

icons_dir = "icons"
if not os.path.exists(icons_dir):
    print("No icons dir")
    exit(1)

icons = os.listdir(icons_dir)
json_files = [f for f in os.listdir(".") if f.endswith(".json") and f != "template.json"]

def normalize(name):
    name = os.path.splitext(name)[0]
    name = name.lower()
    name = re.sub(r'-(seeklogo|logo|cmyk|\d+)', '', name)
    name = re.sub(r'_(seeklogo|logo|cmyk|\d+)', '', name)
    name = re.sub(r'[^a-z0-9]', '', name)
    return name

icon_map = {}
for icon in icons:
    if icon == ".DS_Store":
        continue
    norm = normalize(icon)
    icon_map[norm] = icon
    
manual_map = {
    'btk': 'BTK_Logo_CMYK_1.svg',
    'beltelecom': 'BTK_Logo_CMYK_1.svg',
    'atnt': 'atnt.svg',
    'att': 'atnt.svg',
    'gazprommobile': 'gazprom-mobile.jpg',
    'gpbmobile': 'gazprom-mobile.jpg',
    'letai': 'letai-tattelecom.jpg',
    'mtsbelarus': 'mts-belarus.jpg',
    'mtsby': 'mts-belarus.jpg',
    't2': 't2.jpg',
    'tele2': 't2.jpg',
    'territoriyafitnessa': 'territoriya-fitnessa.jpg',
    'terfit': 'territoriya-fitnessa.jpg',
    'ttk': 'ttk-transtelecom.jpg',
    'x': 'x.svg',
    'xtwitter': 'x.svg',
    'grok': 'grok-seeklogo.svg',
    'xbox': 'xbox-icon-logo.svg',
    'xboxgamepass': 'xbox-icon-logo.svg',
    'max': 'hbo.png',
    'hbo': 'hbo.png',
    'tmobile': 't-mobile-ru.jpg',
    'tmobile_ru': 't-mobile-ru.jpg',
    'tmoliberu': 't-mobile-ru.jpg',
    'jio': 'jio-seeklogo.png',
    'reliancejio': 'jio-seeklogo.png',
    'mtn': 'mtn-group.svg',
    'mtngroup': 'mtn-group.svg',
    'domru': 'dom-ru.jpg',
    'sssrfitness': 'sssr.jpg',
    'worldclass': 'world-class.jpg',
    'drivefitness': 'drive-fitness.jpg',
    'zebrafitness': 'zebra-fitness.jpg'
}

updated = 0
for jf in json_files:
    with open(jf, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            continue
            
    norm_jf = normalize(jf)
    norm_id = normalize(data.get("id", ""))
    
    matched_icon = None
    if norm_jf in manual_map:
        matched_icon = manual_map[norm_jf]
    elif norm_id in manual_map:
        matched_icon = manual_map[norm_id]
    elif norm_jf in icon_map:
        matched_icon = icon_map[norm_jf]
    elif norm_id in icon_map:
        matched_icon = icon_map[norm_id]
    elif norm_jf.replace('ru', '') in icon_map:
        matched_icon = icon_map[norm_jf.replace('ru', '')]
    elif norm_jf.replace('by', '') in icon_map:
        matched_icon = icon_map[norm_jf.replace('by', '')]
        
    if matched_icon:
        data["icon_file"] = f"icons/{matched_icon}"
        with open(jf, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Mapped {jf} -> {matched_icon}")
        updated += 1
    else:
        print(f"No match for {jf}")

print(f"Total updated: {updated}")
