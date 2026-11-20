# ==========================================================
# ArchitectOS Memory Extractor v70.1
# User Message -> Structured Facts
# Persian + English Name Extraction
# ==========================================================


import re



class MemoryExtractor:


    def __init__(self):

        print(
            "🧠 Memory Extractor v70.1 ACTIVE"
        )



    def extract(
        self,
        text
    ):


        facts = {}


        if not text:

            return facts



        # Normalize text

        text = text.strip()

        text = re.sub(
            r"\s+",
            " ",
            text
        )



        # ==================================================
        # PERSIAN NAME PATTERNS
        # ==================================================

        patterns = [

            # من مهدی هستم
            r"من\s+([آ-ی]+)\s+هستم",


            # اسمم مهدی است
            r"اسمم\s+([آ-ی]+)\s+است",


            # اسم من مهدی است
            r"اسم\s+من\s+([آ-ی]+)\s+است",


            # نام من مهدی است
            r"نام\s+من\s+([آ-ی]+)\s+است",


            # نام: مهدی
            r"نام\s*[:：]\s*([آ-ی]+)",


            # اسم: مهدی
            r"اسم\s*[:：]\s*([آ-ی]+)"

        ]



        for pattern in patterns:


            match = re.search(
                pattern,
                text
            )


            if match:


                facts["user_name"] = (
                    match.group(1)
                )


                break




        # ==================================================
        # ENGLISH NAME PATTERN
        # ==================================================

        english = re.search(
            r"my\s+name\s+is\s+([A-Za-z]+)",
            text,
            re.IGNORECASE
        )



        if english:


            facts["user_name"] = (
                english.group(1)
            )



        return facts





memory_extractor = MemoryExtractor()