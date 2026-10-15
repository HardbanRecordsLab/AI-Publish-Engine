"""Fixed text printed in a book (headings like "Chapter", "Contents") in the
book's own language, so a Polish book doesn't ship with English chrome.

`language` is whatever the job carries: the form sends English names
("Polish"), the translator uses ISO codes ("pl"); both are accepted, as are
native names ("polski"). Anything unknown falls back to English.
"""

LABELS: dict[str, dict[str, str]] = {
    "en": {
        "created_with": "Created with",
        "key_features": "Key Features", "cta_heading": "Ready to get started?", "cta_button": "Get started",
        "chapter": "Chapter", "contents": "Contents", "introduction": "Introduction",
        "conclusion": "Conclusion", "glossary": "Glossary", "about_author": "About the Author",
        "references": "References", "key_takeaway": "Key Takeaway", "summary": "Summary",
        "chapter_summary": "Chapter Summary", "checklist": "Action Checklist",
        "faq": "Frequently Asked Questions", "back_cover": "Back Cover", "cover": "Cover",
        "published_by": "Published by", "rights": (
            "All rights reserved. No part of this publication may be reproduced, distributed, "
            "or transmitted in any form or by any means without prior written permission."),
        "ai_notice": "This book was created with the assistance of artificial intelligence.",
    },
    "pl": {
        "created_with": "Stworzono w",
        "key_features": "Najważniejsze cechy", "cta_heading": "Gotowy, by zacząć?", "cta_button": "Zacznij teraz",
        "chapter": "Rozdział", "contents": "Spis treści", "introduction": "Wstęp",
        "conclusion": "Zakończenie", "glossary": "Słowniczek", "about_author": "O autorze",
        "references": "Bibliografia", "key_takeaway": "Najważniejsze", "summary": "Podsumowanie",
        "chapter_summary": "Podsumowanie rozdziału", "checklist": "Lista działań",
        "faq": "Najczęściej zadawane pytania", "back_cover": "Tylna okładka", "cover": "Okładka",
        "published_by": "Wydawca", "rights": (
            "Wszelkie prawa zastrzeżone. Żadna część tej publikacji nie może być powielana, "
            "rozpowszechniana ani przekazywana w jakiejkolwiek formie i jakimikolwiek środkami "
            "bez uprzedniej pisemnej zgody."),
        "ai_notice": "Ta książka powstała przy wsparciu sztucznej inteligencji.",
    },
    "de": {
        "created_with": "Erstellt mit",
        "key_features": "Hauptmerkmale", "cta_heading": "Bereit loszulegen?", "cta_button": "Jetzt starten",
        "chapter": "Kapitel", "contents": "Inhalt", "introduction": "Einleitung",
        "conclusion": "Fazit", "glossary": "Glossar", "about_author": "Über den Autor",
        "references": "Literatur", "key_takeaway": "Das Wichtigste", "summary": "Zusammenfassung",
        "chapter_summary": "Kapitelzusammenfassung", "checklist": "Checkliste",
        "faq": "Häufig gestellte Fragen", "back_cover": "Rückseite", "cover": "Umschlag",
        "published_by": "Herausgegeben von", "rights": (
            "Alle Rechte vorbehalten. Kein Teil dieser Veröffentlichung darf ohne vorherige "
            "schriftliche Genehmigung in irgendeiner Form vervielfältigt, verbreitet oder "
            "übertragen werden."),
        "ai_notice": "Dieses Buch wurde mit Unterstützung künstlicher Intelligenz erstellt.",
    },
    "es": {
        "created_with": "Creado con",
        "key_features": "Características clave", "cta_heading": "¿Listo para empezar?", "cta_button": "Empezar",
        "chapter": "Capítulo", "contents": "Índice", "introduction": "Introducción",
        "conclusion": "Conclusión", "glossary": "Glosario", "about_author": "Sobre el autor",
        "references": "Referencias", "key_takeaway": "Idea clave", "summary": "Resumen",
        "chapter_summary": "Resumen del capítulo", "checklist": "Lista de acciones",
        "faq": "Preguntas frecuentes", "back_cover": "Contraportada", "cover": "Portada",
        "published_by": "Publicado por", "rights": (
            "Todos los derechos reservados. Ninguna parte de esta publicación puede ser "
            "reproducida, distribuida ni transmitida de ninguna forma ni por ningún medio sin "
            "autorización previa por escrito."),
        "ai_notice": "Este libro se creó con la ayuda de inteligencia artificial.",
    },
    "fr": {
        "created_with": "Créé avec",
        "key_features": "Points clés", "cta_heading": "Prêt à commencer ?", "cta_button": "Commencer",
        "chapter": "Chapitre", "contents": "Table des matières", "introduction": "Introduction",
        "conclusion": "Conclusion", "glossary": "Glossaire", "about_author": "À propos de l'auteur",
        "references": "Références", "key_takeaway": "À retenir", "summary": "Résumé",
        "chapter_summary": "Résumé du chapitre", "checklist": "Liste d'actions",
        "faq": "Questions fréquentes", "back_cover": "Quatrième de couverture", "cover": "Couverture",
        "published_by": "Publié par", "rights": (
            "Tous droits réservés. Aucune partie de cette publication ne peut être reproduite, "
            "distribuée ou transmise sous quelque forme ou par quelque moyen que ce soit sans "
            "autorisation écrite préalable."),
        "ai_notice": "Ce livre a été créé avec l'aide de l'intelligence artificielle.",
    },
}

_ALIASES = {
    "english": "en", "polish": "pl", "polski": "pl", "german": "de", "deutsch": "de",
    "spanish": "es", "español": "es", "espanol": "es", "french": "fr", "français": "fr",
    "francais": "fr",
}


def language_code(language: str | None) -> str:
    """BCP-47-ish primary code for the html/EPUB lang attribute ("en" if unknown).
    Unknown names keep English labels but a recognised 2-letter code is kept as-is."""
    key = (language or "").strip().lower()
    if key in LABELS:
        return key
    if key in _ALIASES:
        return _ALIASES[key]
    if len(key) == 2 and key.isalpha():
        return key
    return "en"


def book_labels(language: str | None) -> dict[str, str]:
    return LABELS.get(language_code(language), LABELS["en"])
