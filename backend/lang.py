# -*- coding: utf-8 -*-
# AllPrime - Primer Tasarim Araci
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
# verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
"""
AllPrime - Dil Katmani
=======================
Kullaniciya donen mesajlar (hatalar ve notlar) istegin dilinde uretilir.

Neden ayri bir katalog dosyasi yok: mesajlarin cogu icinde hesaplanmis deger
tasiyor (koordinat, sayi, gen adi). Anahtar tabanli bir katalog bu degerleri
mesajdan koparip okunmaz hale getirirdi. Bunun yerine iki dil YAN YANA yazilir:

    raise PrimerError(t(f"Dizi cok kisa ({n} bp)", f"Sequence too short ({n} bp)"))

Dil, her istekte server.py tarafindan set_lang() ile ayarlanir. Flask threaded
calistigi icin ContextVar kullanilir - istekler birbirinin dilini bozmaz.
"""

import contextvars

_LANG = contextvars.ContextVar("allprime_lang", default="tr")


def set_lang(value):
    """'en' / 'en-US' -> en, digerleri -> tr"""
    v = str(value or "").strip().lower()
    _LANG.set("en" if v.startswith("en") else "tr")


def get_lang():
    return _LANG.get()


def t(tr, en):
    """Turkce ve Ingilizce karsiligi yan yana verilen mesaji sec."""
    return en if _LANG.get() == "en" else tr


def tr_sayi(n):
    """Turkce metinde binlik ayirici nokta: 1671 -> "1.671" (Ingilizce yarida f"{n:,}" -> "1,671").
    Arayuzdeki kartlar da sayilari boyle yaziyor (v0.8.66)."""
    return f"{n:,}".replace(",", ".")


def warn_prefix():
    """Arayuz notu 'UYARI'/'WARNING' ile baslayanlari vurgulu gosterir."""
    return t("UYARI", "WARNING")
