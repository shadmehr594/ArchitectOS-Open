class OutputGuard:

    def clean(self, text: str):

        if not text:
            return "I don't know"

        text = text.strip()

        # حذف پاسخ‌های خیلی کوتاه بی‌معنی
        if len(text) < 2:
            return "I don't know"

        # جلوگیری از greeting loop
        bad_words = [
            "مرحبا", "السلام", "Hello!", "Hi!",
            "unknown", "I don't know"
        ]

        if any(w.lower() in text.lower() for w in bad_words):
            return "I don't know"

        # جلوگیری از mixed language شدید
        words = text.split()
        if len(words) > 30:
            text = " ".join(words[:30])

        return text