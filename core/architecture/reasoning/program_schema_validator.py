class ProgramSchemaValidator:

    VERSION = "1.0"

    def __init__(self):

        print(
            "🏛 PROGRAM SCHEMA VALIDATOR v1.0 ONLINE"
        )


    def validate(self, program):

        errors = []

        if not isinstance(program, dict):
            errors.append(
                "program must be dict"
            )
            return self._result(errors)


        required_keys = [
            "required_spaces",
            "optional_spaces",
            "relationships"
        ]


        for key in required_keys:

            if key not in program:

                errors.append(
                    f"missing key: {key}"
                )


        spaces = (
            program.get(
                "required_spaces",
                []
            )
            +
            program.get(
                "optional_spaces",
                []
            )
        )


        for index, space in enumerate(spaces):

            errors.extend(
                self._validate_space(
                    space,
                    index
                )
            )


        errors.extend(
            self._validate_relationships(
                program.get(
                    "relationships",
                    []
                )
            )
        )


        return self._result(errors)



    def _validate_space(
        self,
        space,
        index
    ):

        errors = []


        if "name" not in space:

            errors.append(
                f"space[{index}] missing name"
            )


        if "zone" not in space:

            errors.append(
                f"{space.get('name')} missing zone"
            )


        if "floor" not in space:

            errors.append(
                f"{space.get('name')} missing floor"
            )


        return errors



    def _validate_relationships(
        self,
        relationships
    ):

        errors = []


        for index, relation in enumerate(
            relationships
        ):

            required = [
                "from",
                "to",
                "type"
            ]


            for key in required:

                if key not in relation:

                    errors.append(
                        f"relationship[{index}] missing {key}"
                    )


        return errors



    def _result(
        self,
        errors
    ):

        return {

            "valid":
                len(errors) == 0,

            "errors":
                errors

        }