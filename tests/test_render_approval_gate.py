from core.chat.chat_architect import ChatArchitect


class FakeBrain:

    def run(self, text, context=None):

        return {
            "architectural_intent": {
                "building_type": "villa",
                "style": "modern",
                "floors": 2
            },
            "result": {
                "architectural_intent": {
                    "building_type": "villa",
                    "style": "modern",
                    "floors": 2
                }
            }
        }



def test_render_block_without_approval():

    chat = ChatArchitect(
        FakeBrain()
    )


    chat.handle(
        "یک ویلای دو طبقه مدرن طراحی کن"
    )


    state = chat.state.get()


    assert state["design_status"] == "draft"



    result = chat.handle(
        "رندر بگیر"
    )


    # Render must be blocked until design approval
    assert result["status"] == "waiting_approval"




def test_render_allowed_after_approval():

    chat = ChatArchitect(
        FakeBrain()
    )


    chat.handle(
        "یک ویلای دو طبقه مدرن طراحی کن"
    )


    chat.handle(
        "تایید شد"
    )


    state = chat.state.get()


    assert state["design_status"] == "approved"



    result = chat.handle(
        "رندر بگیر"
    )


    assert result["status"] == "success"
