from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Map of emojis and nicknames to clean vector icon names
ICON_ALIASES = {
    "🩺": "stethoscope",
    "💉": "syringe",
    "🐾": "paw",
    "🐱": "cat",
    "🐶": "dog",
    "🦜": "bird",
    "🐰": "rabbit",
    "🐎": "horse",
    "📌": "pin",
    "🛠️": "sparkles",
    "🛠": "sparkles",
    "🔔": "bell",
    "📎": "paperclip",
    "✏️": "edit",
    "✏": "edit",
    "🔍": "search",
    "🔪": "scalpel",
    "🚨": "ambulance",
    "⚠️": "alert-triangle",
    "⚡": "zap",
    "📅": "calendar",
    "⏰": "clock",
    "📋": "clipboard-list",
    "💊": "pill",
    "📄": "file-text",
    "🗑️": "trash",
    "🗑": "trash",
    "🔒": "lock",
    "👤": "user",
    "📞": "phone",
    "🏢": "building",
    "⚙️": "settings",
    "⚙": "settings",
    "📊": "bar-chart",
    "📈": "trending-up",
    "🧪": "flask",
    "🛡️": "shield-check",
    "🛡": "shield-check",
    "✅": "check-circle",
    "❌": "x-circle",
    "📷": "camera",
    "📸": "camera",
    "🖼️": "image",
    "🖼": "image",
}

# SVG Paths library (Lucide / Heroicons 24x24 outline format)
SVG_PATHS = {
    "stethoscope": (
        '<path d="M4.5 12.5a3.5 3.5 0 0 0 7 0V4a1 1 0 0 0-1-1H9.5a1 1 0 0 0-1 1v8.5a1.5 1.5 0 0 1-3 0V4a1 1 0 0 0-1-1H3.5a1 1 0 0 0-1 1v8.5a5.5 5.5 0 0 0 11 0V11a1 1 0 0 1 1-1h1a3 3 0 0 1 3 3v2a4 4 0 1 1-8 0"/>'
        '<circle cx="19.5" cy="15.5" r="2.5"/>'
    ),
    "syringe": (
        '<path d="m18 2 4 4"/><path d="m17 7 3-3"/><path d="M19 9 8.7 19.3c-1 1-2.5 1-3.4 0l-.6-.6c-1-1-1-2.5 0-3.4L15 5"/><path d="m9 11 4 4"/><path d="m5 19-3 3"/><path d="m14 4 6 6"/>'
    ),
    "shield-check": (
        '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>'
    ),
    "shield-alert": (
        '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="M12 8v4"/><path d="M12 16h.01"/>'
    ),
    "bell": (
        '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>'
    ),
    "bell-ring": (
        '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/><path d="M4 2C2.8 3.7 2 5.7 2 8"/><path d="M22 8c0-2.3-.8-4.3-2-6"/>'
    ),
    "calendar": (
        '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>'
    ),
    "calendar-clock": (
        '<path d="M21 7.5V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3.5"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/><circle cx="16" cy="16" r="6"/><path d="M16 14v2.2l1.4 1.4"/>'
    ),
    "clock": (
        '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>'
    ),
    "sparkles": (
        '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/><path d="m19 19-1 3-1-3-3-1 3-1 1-3 1 3 3 1Z"/>'
    ),
    "layers": (
        '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>'
    ),
    "paperclip": (
        '<path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l7.88-7.88"/>'
    ),
    "file-text": (
        '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>'
    ),
    "clipboard-list": (
        '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/>'
    ),
    "alert-triangle": (
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>'
    ),
    "check-circle": (
        '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>'
    ),
    "x-circle": (
        '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>'
    ),
    "trash": (
        '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>'
    ),
    "edit": (
        '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>'
    ),
    "plus": (
        '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>'
    ),
    "search": (
        '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>'
    ),
    "filter": (
        '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>'
    ),
    "pin": (
        '<line x1="12" y1="17" x2="12" y2="22"/><path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a1 1 0 0 0 0-2H8a1 1 0 0 0 0 2h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z"/>'
    ),
    "scalpel": (
        '<path d="m18 2 4 4-13 13H5v-4L18 2z"/><path d="m14 6 4 4"/><path d="m4 20 2-2"/>'
    ),
    "ambulance": (
        '<path d="M10 17h4V5H2v12h3"/><path d="M20 17h2v-3.34a4 4 0 0 0-1.17-2.83L19 9h-5v8h1"/><path d="M14 9h4l2 3"/><circle cx="7.5" cy="17.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/><path d="M8 8v4"/><path d="M6 10h4"/>'
    ),
    "zap": (
        '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>'
    ),
    "paw": (
        '<circle cx="11" cy="4" r="2"/><circle cx="18" cy="8" r="2"/><circle cx="20" cy="16" r="2"/><path d="M9 10a5 5 0 0 1 5 5v3.5a3.5 3.5 0 0 1-6.84 1.05A4 4 0 0 1 4 16v-1a5 5 0 0 1 5-5Z"/><circle cx="4" cy="8" r="2"/>'
    ),
    "cat": (
        '<path d="M12 5c.67 0 1.35.09 2 .26 1.78-2 5.03-2.84 6.42-2.26 1.4.58-.42 7-.42 7A10 10 0 0 1 21 15a9 9 0 0 1-9 9 9 9 0 0 1-9-9c0-1.8.48-3.48 1-5 0 0-1.82-6.42-.42-7 1.39-.58 4.64.26 6.42 2.26.65-.17 1.33-.26 2-.26Z"/><path d="M8 14v.5"/><path d="M16 14v.5"/><path d="M11.25 16.25h1.5L12 17l-.75-.75Z"/>'
    ),
    "dog": (
        '<path d="M10 5.172C10 3.782 8.423 2.679 6.5 3c-2.823.47-4.113 6.006-4 7 .08.703 1.8 1.5 3.5 1.5 1.74 0 3-1.04 4-2.172v-4.156z"/><path d="M14 5.172C14 3.782 15.577 2.679 17.5 3c2.823.47 4.113 6.006 4 7-.08.703-1.8 1.5-3.5 1.5-1.74 0-3-1.04-4-2.172v-4.156z"/><path d="M8 14v.5"/><path d="M16 14v.5"/><path d="M11.25 16.25h1.5L12 17l-.75-.75Z"/><path d="M4 14c0 4.418 3.582 8 8 8s8-3.582 8-8c0-2.316-1.023-4.394-2.652-5.828C16.14 7.42 14.545 7 12 7c-2.545 0-4.14.42-5.348 1.172C5.023 9.606 4 11.684 4 14z"/>'
    ),
    "bird": (
        '<path d="M16 7h.01"/><path d="M3.4 18H12a8 8 0 0 0 8-8V7a4 4 0 0 0-7.28-2.3L2 18"/><path d="m20 7 2 .5-2 .5"/><path d="M10 18v3"/><path d="M14 17.75V21"/><path d="M7 18a6 6 0 0 0 3.84-10.61"/>'
    ),
    "rabbit": (
        '<path d="M13 16a3 3 0 0 1 2.24 5"/><path d="M18 12h.01"/><path d="M18 21a2 2 0 0 0 2-2c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/><path d="M12 4.5C10 2 6 2 4 4.5s0 7.5 2 9.5"/><path d="M12 4.5C14 2 18 2 20 4.5s0 7.5-2 9.5"/>'
    ),
    "pill": (
        '<path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z"/><path d="m8.5 8.5 7 7"/>'
    ),
    "activity": (
        '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>'
    ),
    "weight": (
        '<circle cx="12" cy="5" r="3"/><path d="M6.5 8a2 2 0 0 0-1.9 1.4l-2.4 8A2 2 0 0 0 4.1 20h15.8a2 2 0 0 0 1.9-2.6l-2.4-8A2 2 0 0 0 17.5 8z"/><path d="M12 12v3"/>'
    ),
    "user": (
        '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>'
    ),
    "phone": (
        '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>'
    ),
    "lock": (
        '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>'
    ),
    "settings": (
        '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>'
    ),
    "bar-chart": (
        '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>'
    ),
    "trending-up": (
        '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>'
    ),
    "download": (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>'
    ),
    "upload": (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>'
    ),
    "refresh": (
        '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>'
    ),
    "printer": (
        '<polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect width="12" height="8" x="6" y="14"/>'
    ),
    "camera": (
        '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/>'
    ),
    "image": (
        '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>'
    ),
}


@register.simple_tag
def icon(name, css_class="w-4 h-4", extra_attrs=""):
    """
    Renders an offline SVG vector icon by name or mapped emoji.
    Usage: {% icon 'stethoscope' class='w-5 h-5 text-teal-600' %}
           {% icon '💉' class='w-4 h-4 text-emerald-600' %}
           {% icon species.icon class='w-5 h-5' %}
    """
    if not name:
        name = "sparkles"

    name_str = str(name).strip()
    # Check if name is an emoji or alias
    icon_key = ICON_ALIASES.get(name_str, name_str.lower())
    
    # Clean up standard variations
    icon_key = icon_key.replace("icon-", "").replace("ri-", "").replace("-line", "").replace("_", "-")

    svg_content = SVG_PATHS.get(icon_key)
    if not svg_content:
        # Fallback to stethoscope or sparkles if unknown
        svg_content = SVG_PATHS.get("sparkles")

    svg_html = (
        f'<svg class="{css_class}" fill="none" stroke="currentColor" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24" '
        f'xmlns="http://www.w3.org/2000/svg" {extra_attrs}>{svg_content}</svg>'
    )
    return mark_safe(svg_html)


@register.filter
def render_icon(name, css_class="w-4 h-4"):
    """Filter version for easy chaining: {{ visit.icon|render_icon:'w-4 h-4 text-primary-600' }}"""
    return icon(name, css_class=css_class)
