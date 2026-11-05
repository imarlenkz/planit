"""Demo content (used only when SEED_DEMO=true or `python -m app.seed`)."""

SCHOOL = {"name": "№7 жалпы білім беретін мектеп (Demo)", "city": "Астана", "region": "Астана қ."}

CLASSES = [("5А", 5, "А", 26), ("5Б", 5, "Б", 8), ("6А", 6, "А", 8), ("7А", 7, "А", 8), ("8Б", 8, "Б", 6)]

BOYS = ["Айдос", "Арман", "Данияр", "Ерлан", "Нұрсұлтан", "Әлихан", "Бекзат", "Темірлан", "Алихан", "Санжар",
        "Ернар", "Мирас", "Абылай", "Дінмұхаммед", "Ислам", "Расул", "Жансұлтан", "Әділет", "Нұрәли", "Бауыржан"]
GIRLS = ["Айдана", "Аружан", "Томирис", "Әйгерім", "Жансая", "Дана", "Мадина", "Аяулым", "Інжу", "Балнұр",
         "Камила", "Асель", "Жанель", "Сымбат", "Айша", "Ақбота", "Нұрай", "Гүлназ", "Медина", "Амина"]
SURNAMES_M = ["Ермек", "Сапаров", "Жұмабаев", "Нұрланов", "Қасымов", "Әбдірахманов", "Серікұлы", "Төлеуов",
              "Оспанов", "Байжанов", "Ахметов", "Құрманов", "Есенов", "Мұқанов"]
SURNAMES_F = ["Ермекқызы", "Сапарова", "Жұмабаева", "Нұрланова", "Қасымова", "Әбдірахманова", "Серікқызы",
              "Төлеуова", "Оспанова", "Байжанова", "Ахметова", "Құрманова", "Есенова", "Мұқанова"]

SUBJECTS = [("Математика", "MATH"), ("Қазақ тілі", "KAZ"), ("Жаратылыстану", "SCI"), ("Ағылшын тілі", "ENG")]

OBJECTIVES = [
    ("5.1.2.3", "Жай бөлшектерді салыстыру", "MATH", 5),
    ("5.1.2.6", "Жай бөлшектерді қосу және азайту", "MATH", 5),
    ("5.1.2.9", "Жай бөлшектерді ондық бөлшекке айналдыру", "MATH", 5),
    ("5.2.1.4", "Бөлшектері бар теңдеулерді шешу", "MATH", 5),
    ("5.1.2.1", "Дұрыс және бұрыс бөлшек ұғымы", "MATH", 5),
    ("5.1.2.12", "Бөлшекті натурал санға көбейту", "MATH", 5),
    ("5.2.1.1", "Зат есімнің септелуі", "KAZ", 5),
    ("5.3.1.2", "Мәтіннің негізгі ойын анықтау", "KAZ", 5),
    ("6.2.3.1", "Фотосинтез процесін түсіндіру", "SCI", 6),
    ("6.2.3.4", "Заттың агрегаттық күйлері", "SCI", 6),
    ("7.4.1.1", "Present Perfect tense", "ENG", 7),
    ("7.2.3.1", "Reading for main idea", "ENG", 7),
]

# Main demo: 5А Математика БЖБ №2 "Жай бөлшектер" (max 20) — used for the scan & check demo
MATH_BJB = {
    "type": "BZhB", "title": "Математика БЖБ №2 — Жай бөлшектер", "subject": "MATH", "class": "5А", "quarter": 2,
    "section": "Жай бөлшектер", "topic": "Жай бөлшектерге амалдар", "max_score": 20,
    "questions": [
        {"number": 1, "text": "Қай бөлшек 1/2 бөлшегіне тең?", "answer_type": "single_choice",
         "options": {"A": "2/4", "B": "1/3", "C": "3/4", "D": "2/3"}, "correct_answer": "A", "max_score": 1,
         "objective": "5.1.2.3", "wrong": ["C", "D"]},
        {"number": 2, "text": "3/5 + 2/5 қосындысын табыңыз.", "answer_type": "single_choice",
         "options": {"A": "5/10", "B": "1", "C": "6/5", "D": "1/5"}, "correct_answer": "B", "max_score": 1,
         "objective": "5.1.2.6", "wrong": ["A"]},
        {"number": 3, "text": "Дұрыс бөлшектерді таңдаңыз (бірнеше жауап).", "answer_type": "multiple_choice",
         "options": {"A": "3/7", "B": "9/4", "C": "5/6", "D": "8/8"}, "correct_answer": ["A", "C"], "max_score": 2,
         "objective": "5.1.2.1", "wrong": [["A"], ["A", "C", "D"], ["B", "D"]]},
        {"number": 4, "text": "Есептеңіз: 3/4 · 8 = ?", "answer_type": "numeric", "correct_answer": {"value": 6},
         "max_score": 2, "objective": "5.1.2.12", "right": ["6"], "wrong": ["24", "32/4", "3"]},
        {"number": 5, "text": "1/4 бөлшегін ондық бөлшек түрінде жазыңыз.", "answer_type": "numeric",
         "correct_answer": {"value": 0.25}, "tolerance": 0.001, "max_score": 2, "objective": "5.1.2.9",
         "right": ["0,25", "0.25"], "wrong": ["0,4", "1,4", "0,14"]},
        {"number": 6, "text": "Теңдеуді шешіңіз және тексеріңіз: x + 2/5 = 4/5", "answer_type": "math",
         "correct_answer": "x = 2/5", "max_score": 4, "objective": "5.2.1.4",
         "criteria": "Белгісіз қосылғышты табу ережесі, азайту, тексеру",
         "descriptors": [
             {"number": 1, "text": "Белгісіз қосылғышты табу үшін қосындыдан белгілі қосылғышты азайтады", "points": 1,
              "keywords": ["4/5 - 2/5"]},
             {"number": 2, "text": "Бөлшектерді дұрыс азайтып, түбірді табады", "points": 2, "keywords": ["2/5"]},
             {"number": 3, "text": "Табылған түбірді теңдеуге қойып тексереді", "points": 1, "keywords": ["2/5 + 2/5 = 4/5"]},
         ],
         "right": ["x = 4/5 - 2/5\nx = 2/5\nТексеру: 2/5 + 2/5 = 4/5"],
         "partial": ["x = 4/5 - 2/5\nx = 2/5", "x = 4/5 - 2/5\nx = 3/5"],
         "wrong": ["x = 4/5 + 2/5\nx = 6/5"]},
        {"number": 7, "text": "Бөлімдері бірдей бөлшектерді салыстыру ережесін түсіндіріңіз.", "answer_type": "open",
         "correct_answer": "Бөлімдері бірдей екі бөлшектің алымы үлкені үлкен болады.", "max_score": 2,
         "objective": "5.1.2.3",
         "descriptors": [
             {"number": 1, "text": "Бөлімдердің бірдей екенін атап өтеді", "points": 1, "keywords": ["бөлімдері бірдей"]},
             {"number": 2, "text": "Алымы үлкен бөлшек үлкен екенін көрсетеді", "points": 1, "keywords": ["алымы үлкен"]},
         ],
         "right": ["Бөлімдері бірдей болса, алымы үлкен бөлшек үлкен болады"],
         "partial": ["Алымы үлкен бөлшек үлкен"], "wrong": ["Бөлімі үлкен бөлшек үлкен"]},
        {"number": 8, "text": "Алымы бөлімінен кіші бөлшек қалай аталады?", "answer_type": "short_text",
         "correct_answer": {"accept": ["дұрыс бөлшек", "дұрыс"]}, "max_score": 1, "objective": "5.1.2.1",
         "right": ["дұрыс бөлшек"], "wrong": ["бұрыс бөлшек", "аралас сан"]},
        {"number": 9, "text": "2 1/3 аралас санын бұрыс бөлшекке айналдырыңыз.", "answer_type": "numeric",
         "correct_answer": {"value": 2.3333333}, "tolerance": 0.01, "max_score": 2, "objective": "5.1.2.1",
         "right": ["7/3"], "wrong": ["5/3", "6/3"]},
        {"number": 10, "text": "Сәйкестендіріңіз: 1) 1/2  2) 1/4  3) 3/4   —   A) 0,75  B) 0,5  C) 0,25",
         "answer_type": "matching", "correct_answer": {"1": "B", "2": "C", "3": "A"}, "max_score": 3,
         "objective": "5.1.2.9", "right": ["1-B, 2-C, 3-A"], "partial": ["1-B, 2-A, 3-C"], "wrong": ["1-A, 2-B, 3-C"]},
    ],
}

# Other demo assessments (results are synthesised, no scans)
OTHER = [
    {"type": "BZhB", "title": "Математика БЖБ №1 — Натурал сандар", "subject": "MATH", "class": "5А", "quarter": 1,
     "section": "Натурал сандар", "max_score": 15, "date_offset": -45, "synthetic": True, "questions": [
         {"number": i, "text": f"{i}-тапсырма", "answer_type": "numeric", "correct_answer": {"value": i * 3},
          "max_score": m, "objective": obj} for i, m, obj in
         [(1, 2, "5.1.2.6"), (2, 3, "5.1.2.6"), (3, 3, "5.1.2.12"), (4, 3, "5.2.1.4"), (5, 4, "5.2.1.4")]]},
    {"type": "BZhB", "title": "Қазақ тілі БЖБ №2 — Зат есім", "subject": "KAZ", "class": "5Б", "quarter": 2,
     "section": "Зат есім", "max_score": 15, "date_offset": -10, "synthetic": True, "questions": [
         {"number": 1, "text": "«Мектеп» сөзін барыс септігінде жазыңыз", "answer_type": "short_text",
          "correct_answer": "мектепке", "max_score": 2, "objective": "5.2.1.1"},
         {"number": 2, "text": "Дұрыс жалғауды таңдаңыз: кітап__ (ілік)", "answer_type": "single_choice",
          "options": {"A": "-тың", "B": "-тің", "C": "-дың", "D": "-ның"}, "correct_answer": "B", "max_score": 1,
          "objective": "5.2.1.1"},
         {"number": 3, "text": "Мәтіннің негізгі ойын жазыңыз", "answer_type": "open",
          "correct_answer": "Отанды сүю — әр азаматтың борышы.", "max_score": 4, "objective": "5.3.1.2",
          "descriptors": [{"number": 1, "text": "Негізгі ойды анықтайды", "points": 2},
                          {"number": 2, "text": "Өз сөзімен дәлелдейді", "points": 2}]},
         {"number": 4, "text": "Эссе: «Менің мектебім»", "answer_type": "essay", "correct_answer": "", "max_score": 8,
          "objective": "5.3.1.2", "descriptors": [
              {"number": 1, "text": "Тақырыпқа сай", "points": 2}, {"number": 2, "text": "Құрылымы сақталған", "points": 2},
              {"number": 3, "text": "Сауатты жазылған", "points": 2}, {"number": 4, "text": "Мысалдар келтірілген", "points": 2}]},
     ]},
    {"type": "TZhB", "title": "Жаратылыстану ТЖБ — 2-тоқсан", "subject": "SCI", "class": "6А", "quarter": 2,
     "section": "Өсімдіктер әлемі", "max_score": 20, "date_offset": -5, "synthetic": True, "questions": [
         {"number": 1, "text": "Фотосинтез кезінде не болады?", "answer_type": "open",
          "correct_answer": "Фотосинтез кезінде өсімдік көмірқышқыл газын сіңіріп, оттек бөледі.", "max_score": 2,
          "objective": "6.2.3.1", "descriptors": [
              {"number": 1, "text": "Көмірқышқыл газын сіңіретінін көрсетеді", "points": 1, "keywords": ["CO2 сіңіреді"]},
              {"number": 2, "text": "Оттек бөлетінін көрсетеді", "points": 1, "keywords": ["оттек бөледі"]}]},
         {"number": 2, "text": "Судың қай күйі қатты күй?", "answer_type": "single_choice",
          "options": {"A": "бу", "B": "мұз", "C": "су", "D": "тұман"}, "correct_answer": "B", "max_score": 2,
          "objective": "6.2.3.4"},
         {"number": 3, "text": "Судың қайнау температурасы (°C)", "answer_type": "numeric", "correct_answer": {"value": 100},
          "max_score": 2, "objective": "6.2.3.4"},
         {"number": 4, "text": "Фотосинтезге не қажет?", "answer_type": "multiple_choice",
          "options": {"A": "күн жарығы", "B": "су", "C": "CO2", "D": "азот"}, "correct_answer": ["A", "B", "C"],
          "max_score": 6, "objective": "6.2.3.1"},
         {"number": 5, "text": "Тәжірибені сипаттаңыз", "answer_type": "open", "correct_answer": "...", "max_score": 8,
          "objective": "6.2.3.1", "descriptors": [
              {"number": i, "text": t, "points": 2} for i, t in
              [(1, "Мақсатын жазады"), (2, "Құралдарды атайды"), (3, "Барысын сипаттайды"), (4, "Қорытынды жасайды")]]},
     ]},
    {"type": "AB", "title": "Ағылшын тілі АБ — 1-жартыжылдық", "subject": "ENG", "class": "7А", "quarter": 2,
     "section": "Units 1-4", "max_score": 25, "date_offset": -2, "synthetic": True, "questions": [
         {"number": 1, "text": "Choose: She ___ already finished.", "answer_type": "single_choice",
          "options": {"A": "have", "B": "has", "C": "is", "D": "was"}, "correct_answer": "B", "max_score": 5,
          "objective": "7.4.1.1"},
         {"number": 2, "text": "Write the past participle of 'go'", "answer_type": "short_text", "correct_answer": "gone",
          "max_score": 5, "objective": "7.4.1.1"},
         {"number": 3, "text": "What is the main idea of the text?", "answer_type": "open", "correct_answer": "...",
          "max_score": 7, "objective": "7.2.3.1", "descriptors": [
              {"number": 1, "text": "Identifies main idea", "points": 4}, {"number": 2, "text": "Supports with detail", "points": 3}]},
         {"number": 4, "text": "Essay: My summer", "answer_type": "essay", "correct_answer": "", "max_score": 8,
          "objective": "7.2.3.1", "descriptors": [
              {"number": 1, "text": "Task achievement", "points": 4}, {"number": 2, "text": "Grammar & vocabulary", "points": 4}]},
     ]},
]
