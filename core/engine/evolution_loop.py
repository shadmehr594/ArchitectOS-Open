class EvolutionLoop:

    def __init__(self, brain, healer):
        self.brain = brain
        self.healer = healer

    def tick(self, context):

        errors = self._detect_errors(context)

        if errors:
            fixes = self.healer.tick(errors)

            for fix in fixes:
                self._apply_fix(fix)

        print("🧠 SELF EVOLUTION STEP COMPLETED")

    def _detect_errors(self, context):

        errors = []

        design = context.get("design")

        if design is None:
            errors.append("NULL DESIGN ERROR")

        return errors

    def _apply_fix(self, fix):
        print("🛠️ APPLYING FIX:", fix)