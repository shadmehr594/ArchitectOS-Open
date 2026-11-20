import os
import ast

class ImportFixer:

    def scan_file(self, path):

        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        errors = []

        for node in ast.walk(tree):

            if isinstance(node, ast.ImportFrom):

                if node.module is None:
                    errors.append("missing module import")

        return errors


    def fix_common_imports(self, content):

        replacements = {

            "from core.validator import": "from core.bim_validator import",
            "import Planner": "# FIXED: Planner moved to planner_agent",
            "Planner(": "PlannerAgent(",
        }

        for old, new in replacements.items():
            content = content.replace(old, new)

        return content