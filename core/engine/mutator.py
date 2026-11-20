import copy


class Mutator:


    VERSION = "v3.0"



    def __init__(self):

        print(
            "📐 Spatial Optimization Mutator v3 ACTIVE"
        )



    # ==========================================================
    # MAIN MUTATION
    # ==========================================================

    def mutate(
        self,
        design,
        request=None,
        history=None
    ):


        new_design = copy.deepcopy(
            design
        )


        # ------------------------------------------------------
        # NORMALIZE
        # ------------------------------------------------------

        if isinstance(
            new_design,
            list
        ):


            new_design = {

                f"node_{i}": item

                for i, item in enumerate(new_design)

            }



        elif (
            isinstance(
                new_design,
                dict
            )
            and "nodes" in new_design
        ):


            new_design = {

                key:value

                for key,value in new_design.items()

            }



        # ------------------------------------------------------
        # REQUEST
        # ------------------------------------------------------

        if not request:

            request = self.extract_request(
                history
            )


        request = str(
            request
        ).lower()



        print(
            "MUTATOR REQUEST:",
            request
        )



        # ------------------------------------------------------
        # MULTI TARGET SUPPORT
        # ------------------------------------------------------

        targets = self.detect_targets(
            request
        )


        operations = self.detect_operation(
            request
        )


        relation = self.detect_relation(
            request
        )



        if targets:


            for target in targets:


                for operation in operations:


                    self.apply_update(
                        new_design,
                        target,
                        operation,
                        relation
                    )



        else:


            self.add_generic_space(
                new_design
            )



        return new_design





    # ==========================================================
    # TARGET DETECTION
    # ==========================================================

    def detect_targets(
        self,
        request
    ):

        result = []

        mapping = {


            "استخر":
                "POOL",

            "pool":
                "POOL",



            "نما":
                "FACADE",

            "facade":
                "FACADE",

            "سنگ":
                "FACADE",



            "آشپزخانه":
                "KITCHEN",

            "kitchen":
                "KITCHEN",



            "اتاق خواب":
                "BEDROOM",

            "خواب":
                "BEDROOM",

            "اتاق کار":
                "WORKSPACE",

            "کار":
                "WORKSPACE",

            "مطالعه":
                "WORKSPACE",

            "دفتر":
                "WORKSPACE",

            "اتاق کودک":
                "CHILD_ROOM",

            "کودک":
                "CHILD_ROOM",



            "بام":
                "ROOF",

            "roof":
                "ROOF",

            "باغ": 
                "GARDEN",

            "garden":
                "GARDEN"

        }



        for key,value in mapping.items():


            if key in request:


                if value not in result:

                    result.append(
                        value
                    )


        return result





    # ==========================================================
    # OPERATION
    # ==========================================================

    def detect_operation(
        self,
        request
    ):
        
        operations = []



        if any(
            x in request
            for x in [
                "بزرگ",
                "larger",
                "large",
                "expand"
            ]
        ):

            operations.append(
                "increase"
            )



        if any(
            x in request
            for x in [
                "کوچک",
                "smaller",
                "small",
                "reduce"
            ]
        ):

            operations.append(
                "decrease"
            )



        if any(
            x in request
            for x in [
                "سنگ",
                "stone"
            ]
        ):

            operations.append(
                "stone"
            )


        if any(
            x in request
            for x in [
                "اضافه",
                "add",
                "ایجاد"
            ]
        ):

            operations.append(
                "add"
            )


        if not operations:

            operations.append(
                "update"
            )


        return operations




    # ==========================================================
    # SPATIAL RELATION
    # ==========================================================

    def detect_relation(
        self,
        request
    ):


        if (
            "کنار باغ" in request
            or
            "near garden" in request
        ):


            return {

                "relation":
                    "near",

                "target":
                    "garden"

            }



        if (
            "کنار استخر" in request
        ):


            return {

                "relation":
                    "near",

                "target":
                    "pool"

            }



        return None





    # ==========================================================
    # APPLY UPDATE
    # ==========================================================

    def apply_update(
        self,
        design,
        target,
        operation,
        relation=None
    ):



        if target == "POOL":


            pool = design.get(
                "POOL",
                {}
            )


            pool.setdefault(
                "type",
                "swimming_pool"
            )


            if operation == "increase":

                pool["size"] = "large"



            elif operation == "decrease":

                pool["size"] = "small"



            if relation:


                pool["spatial_relation"] = relation



            pool["status"] = "updated"


            design["POOL"] = pool





        elif target == "FACADE":


            facade = design.get(
                "FACADE",
                {}
            )


            if operation == "stone":

                facade["material"] = "stone"



            facade["status"] = "updated"


            design["FACADE"] = facade





        elif target == "KITCHEN":


            kitchen = design.get(
                "KITCHEN",
                {}
            )


            kitchen.setdefault(
                "type",
                "kitchen"
            )


            if operation == "increase":

                kitchen["size"] = "large"



            elif operation == "decrease":

                kitchen["size"] = "small"



            kitchen["status"] = "updated"


            design["KITCHEN"] = kitchen





        elif target == "ROOF":


            roof = design.get(
                "ROOF",
                {}
            )


            roof["status"] = "updated"


            design["ROOF"] = roof


        elif target == "WORKSPACE":

            design["WORK_ROOM"] = {

                "type":
                    "office",

                "category":
                    "workspace",

                "status":
                    "added"

            }





        elif target == "BEDROOM":


            design["CHILD_ROOM"] = {


                "type":
                    "bedroom",


                "category":
                    "child",


                "status":
                    "added"


            }





    # ==========================================================
    # MEMORY REQUEST EXTRACTION
    # ==========================================================

    def extract_request(
        self,
        history
    ):


        if isinstance(
            history,
            str
        ):

            return history



        if isinstance(
            history,
            dict
        ):


            candidates = [

                history.get(
                    "query",
                    ""
                ),

                history.get(
                    "input",
                    ""
                ),

                history.get(
                    "last_request",
                    ""
                )

            ]


            conversation = history.get(
                "conversation",
                {}
            )


            if isinstance(
                conversation,
                dict
            ):


                messages = conversation.get(
                    "user_messages",
                    []
                )


                if messages:

                    candidates.append(
                        messages[-1]
                    )



            for item in candidates:


                if item:

                    return str(
                        item
                    )



        return ""





    # ==========================================================
    # GENERIC FALLBACK MUTATION
    # ==========================================================

    def add_generic_space(
        self,
        design
    ):


        # اگر طراحی دیکشنری ساده است

        if not isinstance(
            design,
            dict
        ):

            return



        # جلوگیری از overwrite

        index = 1


        key = f"adaptive_space_{index}"



        while key in design:


            index += 1


            key = f"adaptive_space_{index}"



        design[key] = {


            "type":
                "flexible_space",


            "status":
                "added",


            "source":
                "mutator_v3_fallback"


        }