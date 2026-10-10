"""Local project identity settings, read once at launch."""
from pathlib import Path
import json,re

DEFAULTS={'application_name':'MSD WINDOWS S1XLV','display_version':'26.10.1','menu_image':'menu_screen.png'}

def load(root):
 path=Path(root)/'branding.json';data=dict(DEFAULTS)
 if path.is_file():data.update(json.loads(path.read_text(encoding='utf-8')))
 if not isinstance(data['application_name'],str) or not 1<=len(data['application_name'])<=80 or any(c in data['application_name'] for c in '\r\n\0'):raise ValueError('Invalid application name')
 if not isinstance(data['display_version'],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+_-]{0,31}(?: beta)?',data['display_version']):raise ValueError('Invalid display version')
 image=data['menu_image']
 if not isinstance(image,str) or Path(image).name!=image or not image.lower().endswith('.png'):raise ValueError('Invalid menu image filename')
 return data
