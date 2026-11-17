from dataclasses import dataclass


@dataclass(frozen=True)
class DocTheme:
    name: str
    primary_hex: str
    accent_hex: str
    dark_bg_hex: str
    soft_tint_hex: str
    zebra_hex: str
    border_hex: str
    body_text_hex: str
    muted_text_hex: str
    font_family: str = "Calibri"


THEMES: dict[str, DocTheme] = {
    "executive_navy": DocTheme(
        name="executive_navy",
        primary_hex="0F2942",
        accent_hex="0D9488",
        dark_bg_hex="0B192C",
        soft_tint_hex="F0F7FA",
        zebra_hex="F8FAFC",
        border_hex="CBD5E1",
        body_text_hex="1E293B",
        muted_text_hex="64748B",
    ),
    "emerald_slate": DocTheme(
        name="emerald_slate",
        primary_hex="064E3B",
        accent_hex="10B981",
        dark_bg_hex="052E26",
        soft_tint_hex="ECFDF5",
        zebra_hex="F8FAFC",
        border_hex="CBD5E1",
        body_text_hex="1E293B",
        muted_text_hex="64748B",
    ),
    "obsidian_gold": DocTheme(
        name="obsidian_gold",
        primary_hex="18181B",
        accent_hex="D97706",
        dark_bg_hex="111114",
        soft_tint_hex="FFFBEB",
        zebra_hex="F9FAFB",
        border_hex="D4D4D8",
        body_text_hex="27272A",
        muted_text_hex="71717A",
    ),
    "warm_editorial": DocTheme(
        name="warm_editorial",
        primary_hex="4C1D95",
        accent_hex="E11D48",
        dark_bg_hex="1E1B4B",
        soft_tint_hex="FDF2F8",
        zebra_hex="FAFAFC",
        border_hex="E2E8F0",
        body_text_hex="1E293B",
        muted_text_hex="64748B",
    ),
}


def get_theme(palette_name: str | None) -> DocTheme:
    return THEMES.get(palette_name or "executive_navy", THEMES["executive_navy"])


def hex_to_rgb_tuple(hex_str: str) -> tuple[int, int, int]:
    clean = hex_str.lstrip("#")
    return int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)
