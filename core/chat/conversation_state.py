# ==========================================================
# ArchitectOS Conversation State v1.5
# Intent Memory Layer
# Protected Design Memory
# Render Context Memory
# Image Asset Compatibility Layer
#
# Changes:
# - Unified last_render_asset / last_image_asset
# - Added image edit asset getter
# - Preserved legacy router compatibility
# ==========================================================


class ConversationState:


    def __init__(self):

        self.state = {


            "last_intent": None,


            "last_topic": None,


            "active_project": None,


            "last_request": None,


            "last_response_type": None,


            "last_design": None,


            "design_status": "none",

            "project_state": "IDLE",

            "approval_status": False,


            # BIM Design Output
            "bim_result": None,

            "ifc_asset": None,

            "cad_asset": None,

            "design_preview": None,



            # Last architectural prompt
            "last_prompt": None,



            # Extracted architectural meaning
            "last_architectural_intent": None,



            # Generated render output
            "last_render_asset": None,



            # Image edit compatibility asset
            # Used by legacy image router
            "last_image_asset": None,



            # Image edit session flag
            "waiting_image_edit": False,


            # T2I_I2I_CHAT_TO_IMAGE_EXECUTION_V1 — pending image-generation
            # request.  Set when a text-to-image request has been recognised
            # but the turn is not yet complete (e.g. the user was asked for a
            # missing specification), and consumed by the NEXT turn when that
            # turn is a specification answer ("5*5*5 سانتیمتر").
            #
            # It holds {"prompt": <accumulated request>, "source": <reason>,
            # "created_turn": <int>} or None.  It is deliberately separate
            # from `waiting_image_edit`, which belongs to the img2img path.
            "pending_image_generate": None,

            # Monotonic per-session turn counter. Used to expire a stale
            # pending request instead of letting it capture an unrelated
            # later turn.
            "turn_index": 0,


            "messages": [],

            # Durable, non-confirming material-correction review carriers.
            # ConversationStore validates and hydrates these through the
            # existing project chat.json owner.
            "material_correction_reviews": [],
            "material_correction_review_restore_errors": []


        }



        print(
            "🧠 CONVERSATION STATE v1.5 ONLINE"
        )



    # ======================================================
    # UPDATE STATE
    # ======================================================

    def update(
        self,
        data
    ):


        if not isinstance(
            data,
            dict
        ):

            return self.state



        for key, value in data.items():


            if key not in self.state:

                self.state[key] = value

                continue



            # ==================================================
            # DESIGN MEMORY PROTECTION
            # ==================================================

            if key == "last_design":


                if value is None:

                    continue



                if isinstance(
                    value,
                    dict
                ):


                    if (

                        value.get("type") == "image"

                        and

                        "output" in value

                    ):

                        continue




            self.state[key] = value



        return self.state



    # ======================================================
    # SAVE PROMPT
    # ======================================================

    def save_prompt(
        self,
        text
    ):


        if text:


            self.state["last_prompt"] = text



        return self.state



    # ======================================================
    # IMAGE EDIT SESSION
    # ======================================================

    def begin_image_edit(
        self
    ):


        self.state[
            "waiting_image_edit"
        ] = True


        return self.state




    def finish_image_edit(
        self
    ):


        self.state[
            "waiting_image_edit"
        ] = False


        return self.state




    # ======================================================
    # T2I_I2I_CHAT_TO_IMAGE_EXECUTION_V1
    # PENDING IMAGE GENERATION SESSION
    #
    # The text-to-image counterpart of begin_image_edit().  A recognised
    # generation request is remembered here so the NEXT turn can complete
    # it when the user answers a specification question instead of
    # repeating the whole request.
    # ======================================================

    def begin_image_generate(
        self,
        prompt=None,
        source=None
    ):


        self.state[
            "pending_image_generate"
        ] = {

            "prompt": prompt,

            "source": source,

            "created_turn": self.state.get(
                "turn_index",
                0
            )

        }


        return self.state




    def finish_image_generate(
        self
    ):


        self.state[
            "pending_image_generate"
        ] = None


        return self.state




    def next_turn(
        self
    ):


        self.state[
            "turn_index"
        ] = int(
            self.state.get(
                "turn_index",
                0
            )
            or 0
        ) + 1


        return self.state[
            "turn_index"
        ]




    # ======================================================
    # UPDATE FROM RESPONSE RESULT
    # ======================================================

    def update_from_result(
        self,
        request,
        result
    ):


        data = {


            "last_request": request


        }



        if isinstance(
            result,
            dict
        ):



            response_type = result.get(
                "type"
            )



            data[
                "last_response_type"
            ] = response_type




            # ==================================================
            # DESIGN MEMORY
            # ==================================================

            if response_type in [

                "design",

                "design_update"

            ]:



                data[
                    "last_intent"
                ] = "design"



                data[
                    "design_status"
                    ] = "waiting_approval"


                data[
                    "project_state"
                ] = "WAITING_APPROVAL"


                data[
                    "approval_status"
                ] = False



                data[
                    "last_topic"
                ] = "architecture"




                design_result = result.get(
                    "result"
                )



                if isinstance(
                    design_result,
                    dict
                ):

                    bim_result = result.get(
                        "bim_result"
                    )


                    if bim_result:


                        data[
                            "bim_result"
                        ] = bim_result



                        data[
                            "design_preview"
                        ] = bim_result.get(
                            "preview",
                            {}
                        ) if isinstance(
                            bim_result,
                            dict
                        ) else None



                    data[
                        "last_design"
                    ] = design_result


            
            # ======================================================
            # DESIGN APPROVAL MEMORY
            # ======================================================


            if result.get(
                "approval_status"
            ) is True:


                data[
                    "approval_status"
                ] = True


                data[
                    "design_status"
                ] = "approved"


                data[
                    "project_state"
                ] = "APPROVED"





            # ==================================================
            # IMAGE / RENDER MEMORY
            # ==================================================

            if response_type in [

                "image_render",

                "image_edit"

            ]:



                self.finish_image_edit()



                if request:


                    data[
                        "last_prompt"
                    ] = request




                image_asset = result.get(
                    "image"
                )



                if isinstance(
                    image_asset,
                    dict
                ):



                    # Main render memory

                    data[
                        "last_render_asset"
                    ] = image_asset



                    # Legacy image router compatibility

                    data[
                        "last_image_asset"
                    ] = image_asset






                architectural_intent = result.get(
                    "architectural_intent"
                )



                if isinstance(
                    architectural_intent,
                    dict
                ):


                    data[
                        "last_architectural_intent"
                    ] = architectural_intent





        self.update(
            data
        )



        return self.state





    # ======================================================
    # GET FULL STATE
    # ======================================================

    def get(
        self
    ):


        return self.state.copy()


    def add_message(
        self,
        role,
        text="",
        attachments=None
    ):

        attachments = attachments if isinstance(attachments, list) else []

        public_attachments = []

        for item in attachments:

            if not isinstance(item, dict):

                continue

            public_attachments.append({
                key: value
                for key, value in item.items()
                if key not in ("path", "storage_root", "relative_path", "file_object")
            })

        message = {
            "role": role,
            "text": str(text or ""),
            "attachments": public_attachments
        }

        messages = self.state.setdefault("messages", [])
        messages.append(message)

        if len(messages) > 100:

            del messages[:-100]

        return message





    # ======================================================
    # GET LAST PROMPT
    # ======================================================

    def get_last_prompt(
        self
    ):


        return self.state.get(
            "last_prompt"
        )





    # ======================================================
    # GET LAST RENDER ASSET
    # ======================================================

    def get_last_render_asset(
        self
    ):


        return self.state.get(
            "last_render_asset"
        )





    # ======================================================
    # GET LAST IMAGE ASSET
    # ======================================================

    def get_last_image_asset(
        self
    ):


        return self.state.get(
            "last_image_asset"
        )


    def get_project_state(
        self
    ):

        return self.state.get(
            "project_state"
        )



    def get_bim_result(
        self
    ):

        return self.state.get(
            "bim_result"
        )



    def is_design_approved(
        self
    ):

        return (
            self.state.get(
                "approval_status",
                False
            )
            is True
        )





    # ======================================================
    # FOLLOW UP DETECTOR
    # ======================================================

    def is_followup(
        self,
        text
    ):



        if not text:

            return False




        words = [


            "هم اضافه کن",

            "اضافه کن",

            "تغییر بده",

            "ویرایش کن",

            "اصلاح کن",

            "همچنین",

            "ادامه بده",

            "modify",

            "add",

            "change"


        ]



        text = text.lower()



        return any(


            word in text


            for word in words


        )





# ==========================================================
# GLOBAL INSTANCE
# ==========================================================

conversation_state = ConversationState()
