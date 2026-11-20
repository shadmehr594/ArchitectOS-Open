from core.chat.chat_architect import ChatArchitect


class FakeBrain:

    def process(self, text, context=None):
        return {
            "result": {
                "architectural_intent": {
                    "building_type": "villa",
                    "style": "modern",
                    "floors": 2
                }
            },
            "architectural_intent": {
                "building_type": "villa",
                "style": "modern",
                "floors": 2
            }
        }



def test_design_only_no_render():

    chat = ChatArchitect(
        FakeBrain()
    )


    result = chat.handle(
        "یک ویلای دو طبقه مدرن طراحی کن"
    )


    print(result)


    assert result["type"] == "design"


    assert "render" not in result


    assert result.get(
        "has_render",
        False
    ) is False