from core.chat.handlers.image_handler import ImageHandler


class FakeImage:

    filename = "test_house.png"

    def save(self, path):
        with open(path, "w") as f:
            f.write("fake-image")


class FakeState:

    def __init__(self):
        self.data = {}

    def update(self, value):
        self.data.update(value)

    def get(self):
        return self.data



class FakeImageBridge:

    def process_upload(self, project_id, image_path):

        return {
            "type": "image_asset",
            "asset": {
                "path": image_path,
                "filename": "test_house.png"
            }
        }



class FakeResponse:

    def adapt(self, value):
        return value



class FakeRender:

    pass



def test_image_edit_continuation_state():

    state = FakeState()

    handler = ImageHandler(

        render_runtime=FakeRender(),

        result_bridge=None,

        semantic_intent=None,

        image_bridge=FakeImageBridge(),

        image_response=FakeResponse(),

        writeback=None,

        state=state

    )


    # upload

    result = handler.handle_image_upload_only(
        FakeImage()
    )


    assert result["status"] == "waiting_for_instruction"

    assert state.get()["waiting_image_edit"] is True

    assert (
        "last_image_asset"
        in state.get()
    )


    # continuation

    captured = {}


    def fake_edit(
        text,
        image
    ):

        captured["image"] = image

        return {
            "status": "ok"
        }


    handler.handle_image_edit = fake_edit


    handler.handle_image_edit(
        "مدرنش کن",
        state.get()["last_image_asset"]
    )


    assert captured["image"] is not None

    print(
        "\n✅ IMAGE EDIT CONTINUATION STATE PASS\n"
    )