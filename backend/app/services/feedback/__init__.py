"""Student feedback generation (template-based; editable by the teacher)."""


def build_feedback(items: list[dict], percent: float) -> tuple[str, list[str], list[str]]:
    """items: [{label, percent, error_category}] per question/objective → (text, strengths, weaknesses)."""
    strengths = [i["label"] for i in items if i["percent"] >= 80]
    weaknesses = [i["label"] for i in items if i["percent"] < 50]
    cats = {i.get("error_category") for i in items if i.get("error_category")}
    parts = []
    if percent >= 85:
        parts.append("Жарайсың! Бөлім материалын өте жақсы меңгергенсің.")
    elif percent >= 65:
        parts.append("Жақсы нәтиже. Материалдың негізгі бөлігін меңгергенсің.")
    elif percent >= 40:
        parts.append("Негізгі ұғымдарды түсінесің, бірақ бірнеше тақырыпты қайталау қажет.")
    else:
        parts.append("Бұл бөлімді мұғаліммен бірге қайта қарап шығу ұсынылады.")
    if strengths:
        parts.append("Сен мына тақырыптарды жақсы меңгергенсің: " + "; ".join(strengths[:4]) + ".")
    if weaknesses:
        parts.append("Қайта қара:\n" + "\n".join(f"- {w}" for w in weaknesses[:5]))
    hints = {
        "calculation": "Есептеу кезінде мұқият бол, жауапты тексеріп шық.",
        "formula": "Формулаларды қайталап, оларды қолдану ретін жаттық.",
        "concept": "Негізгі ұғымдардың анықтамаларын қайталап шық.",
        "incomplete": "Жауабыңды толық жаз: әр қадамды көрсет.",
        "spelling": "Терминдердің дұрыс жазылуына назар аудар.",
        "terminology": "Пәндік терминдерді дұрыс қолдануға тырыс.",
        "logic": "Шешімнің логикалық ретін тексер.",
        "task_misunderstanding": "Тапсырма шартын мұқият оқы.",
    }
    tips = [hints[c] for c in sorted(cats) if c in hints][:3]
    if tips:
        parts.append(" ".join(tips))
    return "\n\n".join(parts), strengths, weaknesses
