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



def test_design_approval_flow():

    chat = ChatArchitect(
        FakeBrain()
    )


    # 1 - Create design

    result = chat.handle(
        "یک ویلای دو طبقه مدرن طراحی کن"
    )


    assert result["type"] == "design"


    state = chat.state.get()


    assert state["last_design"] is not None


    assert state["design_status"] == "draft"



    # 2 - Approve design

    chat.handle(
        "تایید شد"
    )


    state = chat.state.get()


    assert state["design_status"] == "approved"